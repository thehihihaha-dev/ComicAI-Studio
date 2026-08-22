# ComicAI Agent Workflow

This directory is the vendor-neutral handoff surface for one checkpoint at a
time. Role contracts are in `roles/`; active artifacts remain at this level.

## State flow

`IDLE -> PLANNED -> IMPLEMENTED -> REVIEW_PASSED -> AWAITING_HUMAN_APPROVAL -> APPROVED`

A failed review follows
`IMPLEMENTED/FIXED -> REVIEW_FAILED -> FIXED -> REVIEW_PASSED`. Only a human
may authorize `APPROVED`. Approval never causes an automatic commit or push.

## Helper

From repository root:

- `python3 scripts/agent_workflow.py status`
- `python3 scripts/agent_workflow.py validate`
- `python3 scripts/agent_workflow.py advance <STATE>`
- `python3 scripts/agent_workflow.py archive <checkpoint>`

`advance` enforces legal transitions. `archive` is allowed only in `APPROVED`,
copies (never moves) `CURRENT_TASK.md`, `REPORT.md`, and `REVIEW.md` into a new
`history/<checkpoint>/` directory, and refuses to overwrite existing history.
The helper invokes no agent, model, network service, git commit, or git push.
