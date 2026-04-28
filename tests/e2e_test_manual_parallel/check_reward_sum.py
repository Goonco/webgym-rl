# python tests/e2e_test_manual_parallel/check_reward_sum.py \
#   tests/e2e_test_manual_parallel/__snapshots__/260429-005233_counter \
#   --expected 512 \
#   --expected-count 512

import argparse
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import NamedTuple

DEFAULT_EXPECTED_TOTAL = Decimal("64")
REWARD_RELATIVE_PATH = Path("7_reward") / "reward.txt"


class RewardSummary(NamedTuple):
    count: int
    total: Decimal
    missing: list[Path]
    invalid: list[tuple[Path, str]]


def collect_rewards(snapshot_root: Path) -> RewardSummary:
    session_dirs = sorted(path for path in snapshot_root.iterdir() if path.is_dir())
    total = Decimal("0")
    count = 0
    missing: list[Path] = []
    invalid: list[tuple[Path, str]] = []

    for session_dir in session_dirs:
        reward_path = session_dir / REWARD_RELATIVE_PATH
        if not reward_path.exists():
            missing.append(reward_path)
            continue

        text = reward_path.read_text(encoding="utf-8").strip()
        try:
            reward = Decimal(text)
        except InvalidOperation:
            invalid.append((reward_path, text))
            continue

        total += reward
        count += 1

    return RewardSummary(count=count, total=total, missing=missing, invalid=invalid)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sum */7_reward/reward.txt files under an e2e snapshot directory."
    )
    parser.add_argument(
        "snapshot_root",
        type=Path,
        help="Snapshot directory containing sid_* subdirectories.",
    )
    parser.add_argument(
        "--expected",
        type=Decimal,
        default=DEFAULT_EXPECTED_TOTAL,
        help=f"Expected reward total. Defaults to {DEFAULT_EXPECTED_TOTAL}.",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=None,
        help="Optional expected number of reward.txt files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot_root = args.snapshot_root.resolve()

    if not snapshot_root.is_dir():
        print(f"ERROR: snapshot directory not found: {snapshot_root}")
        return 2

    summary = collect_rewards(snapshot_root)
    print(f"snapshot_root: {snapshot_root}")
    print(f"reward_files: {summary.count}")
    print(f"total: {summary.total}")
    print(f"expected: {args.expected}")

    failed = False
    if summary.total != args.expected:
        print(f"ERROR: total mismatch: got {summary.total}, expected {args.expected}")
        failed = True

    if args.expected_count is not None and summary.count != args.expected_count:
        print(f"ERROR: count mismatch: got {summary.count}, expected {args.expected_count}")
        failed = True

    if summary.missing:
        print("ERROR: missing reward files:")
        for path in summary.missing:
            print(f"  {path}")
        failed = True

    if summary.invalid:
        print("ERROR: invalid reward values:")
        for path, value in summary.invalid:
            print(f"  {path}: {value!r}")
        failed = True

    if failed:
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
