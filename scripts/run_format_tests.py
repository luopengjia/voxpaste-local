#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from voxpaste import add_pause_punctuation_from_segments, clean_speech_without_llm  # noqa: E402


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def run_speech_cases(path: Path, tag: str | None = None) -> list[str]:
    failures: list[str] = []
    cases = load_json(path)
    for case in cases:
        if tag and tag not in case.get("tags", []):
            continue
        actual = clean_speech_without_llm(case["input"], "zh")
        expected = case["expected"]
        if actual != expected:
            failures.append(
                "\n".join(
                    [
                        f"[speech] {case['name']}",
                        f"input:    {case['input']}",
                        f"expected: {expected}",
                        f"actual:   {actual}",
                    ]
                )
            )
    return failures


def run_pause_cases(path: Path) -> list[str]:
    failures: list[str] = []
    cases = load_json(path)
    for case in cases:
        actual = add_pause_punctuation_from_segments(
            {"segments": case["segments"]},
            case["fallback_text"],
            float(case.get("comma_sec", 0.45)),
            float(case.get("period_sec", 0.85)),
        )
        expected = case["expected"]
        if actual != expected:
            failures.append(
                "\n".join(
                    [
                        f"[pause] {case['name']}",
                        f"fallback: {case['fallback_text']}",
                        f"expected: {expected}",
                        f"actual:   {actual}",
                    ]
                )
            )
    return failures


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run VoxPaste formatting regression tests.")
    parser.add_argument(
        "--tag",
        help="Only run speech cleanup cases with this tag.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fixture_dir = ROOT / "tests" / "fixtures"
    failures = []
    failures.extend(run_speech_cases(fixture_dir / "zh_speech_cases.json", args.tag))
    if not args.tag:
        failures.extend(run_pause_cases(fixture_dir / "pause_cases.json"))

    if failures:
        print("\n\n".join(failures), file=sys.stderr)
        print(f"\n{len(failures)} formatting test(s) failed.", file=sys.stderr)
        return 1

    print("All formatting tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
