#!/usr/bin/env python3
"""Validate and archive ComicAI's vendor-neutral agent workflow."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "ai-workflow"
STATE_PATH = WORKFLOW / "STATE.json"
ARTIFACTS = ("CURRENT_TASK.md", "REPORT.md", "REVIEW.md")
REQUIRED = (*ARTIFACTS, "FIX_TASK.md", "STATE.json")
TRANSITIONS = {
    "IDLE": {"PLANNED"},
    "PLANNED": {"IMPLEMENTED"},
    "IMPLEMENTED": {"REVIEW_FAILED", "REVIEW_PASSED"},
    "REVIEW_FAILED": {"FIXED"},
    "FIXED": {"REVIEW_FAILED", "REVIEW_PASSED"},
    "REVIEW_PASSED": {"AWAITING_HUMAN_APPROVAL"},
    "AWAITING_HUMAN_APPROVAL": {"APPROVED"},
    "APPROVED": {"IDLE"},
}
NEXT_ROLE = {
    "IDLE": "ARCHITECT",
    "PLANNED": "CODER",
    "IMPLEMENTED": "REVIEWER",
    "REVIEW_FAILED": "CODER",
    "FIXED": "REVIEWER",
    "REVIEW_PASSED": "REVIEWER",
    "AWAITING_HUMAN_APPROVAL": "HUMAN",
    "APPROVED": "HUMAN",
}


def load_state() -> dict:
    with STATE_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_state(data: dict) -> None:
    STATE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def validate() -> dict:
    missing = [name for name in REQUIRED if not (WORKFLOW / name).is_file()]
    if missing:
        raise ValueError(f"Missing workflow files: {', '.join(missing)}")
    data = load_state()
    state = data.get("state")
    if state not in TRANSITIONS:
        raise ValueError(f"Invalid state: {state!r}")
    if data.get("next_role") != NEXT_ROLE[state]:
        raise ValueError(f"next_role does not match state {state}")
    if set(data.get("allowed_states", [])) != set(TRANSITIONS):
        raise ValueError("allowed_states does not match the workflow")
    return data


def advance(target: str) -> None:
    data = validate()
    current = data["state"]
    if target not in TRANSITIONS[current]:
        allowed = ", ".join(sorted(TRANSITIONS[current])) or "none"
        raise ValueError(f"Illegal transition {current} -> {target}; allowed: {allowed}")
    data["state"] = target
    data["next_role"] = NEXT_ROLE[target]
    data["note"] = f"Advanced from {current} to {target}; no git action performed."
    save_state(data)
    print(f"{current} -> {target}; next role: {NEXT_ROLE[target]}")


def archive(checkpoint: str) -> None:
    data = validate()
    if data["state"] != "APPROVED":
        raise ValueError("Archive requires explicit human-approved state APPROVED")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", checkpoint):
        raise ValueError("Checkpoint must contain only letters, digits, dot, dash, underscore")
    destination = WORKFLOW / "history" / checkpoint
    if destination.exists():
        raise FileExistsError(f"History already exists: {destination.relative_to(ROOT)}")
    destination.mkdir(parents=True)
    for name in ARTIFACTS:
        shutil.copy2(WORKFLOW / name, destination / name)
    print(f"Archived copies to {destination.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("validate")
    advance_parser = commands.add_parser("advance")
    advance_parser.add_argument("state", choices=tuple(TRANSITIONS))
    archive_parser = commands.add_parser("archive")
    archive_parser.add_argument("checkpoint")
    args = parser.parse_args()

    if args.command == "status":
        data = validate()
        print(f"state: {data['state']}")
        print(f"next role: {data['next_role']}")
    elif args.command == "validate":
        data = validate()
        print(f"Workflow valid; state: {data['state']}; next role: {data['next_role']}")
    elif args.command == "advance":
        advance(args.state)
    else:
        archive(args.checkpoint)


if __name__ == "__main__":
    main()
