"""Run up to ten cases from a pinned Hugging Face dataset through a judge.

This script makes real dataset and model requests when invoked. It never retries
an uncertain provider outcome. Install datasets and the selected provider SDK.
Keep its output outside this public repository.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def save_new(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


def private_output(path: Path) -> Path:
    target = path.expanduser().resolve()
    if target == REPO or REPO in target.parents:
        raise ValueError("output must be outside the public repository")
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    if target.stat().st_mode & 0o077:
        raise ValueError("output directory must have 0700 permissions")
    if any(target.iterdir()):
        raise ValueError("output directory must be empty; no implicit retry or overwrite")
    return target


def packet_json(row: dict[str, Any]) -> str:
    if "packet" not in row:
        raise ValueError("dataset row lacks packet")
    value = row["packet"]
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, (dict, list)):
        raise ValueError("packet must be a JSON object or array")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compare_expected(actual: Any, expected: Any) -> Any:
    """Compare only reference fields; an uncertain value remains visible."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return {"reference": expected, "judge": actual, "agreement": False}
        return {key: compare_expected(actual[key], item) if key in actual else
                {"reference": item, "judge": None, "agreement": False, "missing": True}
                for key, item in expected.items()}
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return {"reference": expected, "judge": actual, "agreement": False}
        return [compare_expected(a, e) for a, e in zip(actual, expected)]
    result = {"reference": expected, "judge": actual, "agreement": actual == expected}
    if actual == "uncertain" or expected == "uncertain":
        result["uncertain"] = True
    return result


def call_model(provider: str, model: str, system: str, user: str, key: str,
               base_url: str | None) -> tuple[str, dict[str, Any]]:
    if provider in ("openai", "openai-compatible"):
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=base_url, max_retries=0)
        if provider == "openai":
            response = client.responses.create(model=model, input=[{"role": "system", "content": system},
                                                                    {"role": "user", "content": user}])
            return response.output_text, response.usage.model_dump() if response.usage else {}
        response = client.chat.completions.create(model=model, messages=[{"role": "system", "content": system},
                                                                          {"role": "user", "content": user}])
        return response.choices[0].message.content or "", response.usage.model_dump() if response.usage else {}
    if provider == "anthropic":
        from anthropic import Anthropic
        client = Anthropic(api_key=key, max_retries=0)
        response = client.messages.create(model=model, system=system, messages=[{"role": "user", "content": user}],
                                          max_tokens=4096)
        text = "".join(block.text for block in response.content if block.type == "text")
        return text, response.usage.model_dump() if response.usage else {}
    raise ValueError("unsupported provider")


def run(args: argparse.Namespace) -> None:
    if not 1 <= args.limit <= 10:
        raise ValueError("limit must be 1 through 10")
    if args.start < 0:
        raise ValueError("start must be nonnegative")
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", args.revision):
        raise ValueError("revision must be a pinned 40–64 character commit hash")
    if args.provider == "openai-compatible" and not args.base_url:
        raise ValueError("openai-compatible requires --base-url")
    if args.provider == "anthropic" and args.base_url:
        raise ValueError("anthropic does not use --base-url")
    key = os.environ.get(args.key_env)
    if not key:
        raise ValueError("provider API key environment variable is missing")
    system = args.system.read_text(encoding="utf-8")
    if not system.strip():
        raise ValueError("empty system prompt")
    output = private_output(args.output)
    save_new(output / "manifest.json", {"dataset": args.dataset, "revision": args.revision, "split": args.split,
                                        "provider": args.provider, "model": args.model, "start": args.start,
                                        "limit": args.limit,
                                        "system_sha256": sha256(system)})

    from datasets import load_dataset  # SDK imported only after arguments and output checks
    rows = load_dataset(args.dataset, revision=args.revision, split=args.split,
                        streaming=True, trust_remote_code=False)
    processed = 0
    seen: set[str] = set()
    for index, row in enumerate(itertools.islice(rows, args.start, args.start + args.limit), args.start + 1):
        if not isinstance(row, dict):
            raise ValueError("dataset row must be an object")
        case_id = row.get("id")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in seen:
            raise ValueError("each row needs a unique nonempty id")
        seen.add(case_id)
        user = packet_json(row)  # Only packet: expected, notes and provenance remain local.
        prefix = f"case-{index:02d}"
        save_new(output / f"{prefix}-request.json", {"id": case_id, "system": system, "user": user,
                                                      "packet_sha256": sha256(user), "status": "intent-recorded"})
        try:
            raw, usage = call_model(args.provider, args.model, system, user, key, args.base_url)
        except Exception as exc:
            save_new(output / f"{prefix}-error.json", {"id": case_id, "error_type": type(exc).__name__,
                                                     "status": "provider outcome unknown; no automatic retry"})
            raise RuntimeError("provider outcome unknown; inspect private intent and stop") from None
        save_new(output / f"{prefix}-raw.json", {"id": case_id, "text": raw, "usage": usage})
        try:
            parsed = json.loads(raw)
            expected = row.get("expected")
            if isinstance(expected, str):
                expected = json.loads(expected)
            comparison = compare_expected(parsed, expected) if expected is not None else None
        except (ValueError, TypeError) as exc:
            save_new(output / f"{prefix}-invalid.json", {"id": case_id, "error_type": type(exc).__name__,
                                                       "status": "invalid JSON; no automatic retry"})
            raise RuntimeError("invalid judge JSON; inspect private raw and stop") from None
        save_new(output / f"{prefix}-result.json", {"id": case_id, "parsed_response": parsed,
                                                     "expected_comparison": comparison, "usage": usage})
        processed += 1
    if processed == 0:
        raise ValueError("selected split contains no cases")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--system", type=Path, required=True, help="system message file")
    p.add_argument("--dataset", required=True, help="Hugging Face dataset repo ID")
    p.add_argument("--revision", required=True, help="pinned dataset commit hash")
    p.add_argument("--split", required=True, help="dataset split")
    p.add_argument("--provider", choices=("openai", "openai-compatible", "anthropic"), required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--key-env", required=True, help="provider API key environment-variable name")
    p.add_argument("--base-url", help="openai-compatible endpoint only")
    p.add_argument("--output", type=Path, required=True, help="empty private directory outside this repository")
    p.add_argument("--limit", type=int, default=1, help="1–10 cases; default 1")
    p.add_argument("--start", type=int, default=0, help="zero-based dataset row offset; default 0")
    return p


if __name__ == "__main__":
    try:
        run(parser().parse_args())
    except Exception as exc:
        # Provider exception messages can contain request details. Never print them.
        print(f"Stopped ({type(exc).__name__}); inspect private output when available", file=sys.stderr)
        raise SystemExit(1) from None
