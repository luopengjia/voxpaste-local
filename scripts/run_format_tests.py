#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from voxpaste import (  # noqa: E402
    add_pause_punctuation_from_segments,
    clean_speech_without_llm,
    detect_speech_intervals,
)


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


def run_audio_pause_detection_cases() -> list[str]:
    import math

    import numpy as np

    sample_rate = 16000

    def tone(duration_sec: float) -> np.ndarray:
        sample_count = int(sample_rate * duration_sec)
        values = [
            0.04 * math.sin(2 * math.pi * 220 * index / sample_rate)
            for index in range(sample_count)
        ]
        return np.asarray(values, dtype="float32")

    audio = np.concatenate(
        [
            tone(0.65),
            np.zeros(int(sample_rate * 0.55), dtype="float32"),
            tone(0.7),
            np.zeros(int(sample_rate * 0.95), dtype="float32"),
            tone(0.65),
        ]
    )

    intervals = detect_speech_intervals(audio, sample_rate, 0.45, 0.45)
    if len(intervals) != 3:
        return [f"[audio-pause] expected 3 speech intervals, got {len(intervals)}: {intervals}"]
    return []


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
        failures.extend(run_audio_pause_detection_cases())

    if failures:
        print("\n\n".join(failures), file=sys.stderr)
        print(f"\n{len(failures)} formatting test(s) failed.", file=sys.stderr)
        return 1

    print("All formatting tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
