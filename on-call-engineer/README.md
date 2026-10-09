# On-call engineer

`poll.py` watches Snake Arena's CloudWatch alarms (dev and prod) every
minute. When one fires, it hands the alarm's details — service,
environment, deployed version, owner, dashboard link, runbook, and why it
fired — to a headless Claude Code agent, which investigates and writes a
diagnosis report to `reports/`. You act on the report.

## Run it

From the repo root, after `aws login`, with Claude Code installed:

```bash
python3 on-call-engineer/poll.py
```

It runs until you press Ctrl+C. Useful options:

```bash
python3 on-call-engineer/poll.py --once --dry-run   # one poll; show what would be investigated, run no agent
python3 on-call-engineer/poll.py --interval 120      # poll every 2 minutes
```

When your `aws login` session expires, it says so each minute ("run 'aws
login'") and carries on once you sign in again — no restart needed.

## What the agent can and can't do

It is **read-only**. It can read this repository and its git history,
and run these AWS queries: CloudWatch alarms, alarm history, metrics and
Logs; X-Ray traces; ECS `describe-services`; CloudFormation
`describe-stacks` / `describe-stack-events` (the exact list is
`ALLOWED_TOOLS` in `poll.py`). It has no tools to edit files, and every
other command is denied automatically. It can't deploy, roll back, push,
or change anything in AWS.

How that's enforced (each was tested against the real CLI — see
`docs/ai-usage-report.md`, stage 21):

| Flag | Effect |
|---|---|
| `--restricted` | Ignores your Claude Code user/project settings, so nothing you've allowed elsewhere widens it; keeps file access inside the repo |
| `--tools Read,Grep,Glob,Bash` | No Edit or Write tool exists for it |
| `--allowedTools ...` | Bash is limited to the read-only command prefixes listed |
| `--permission-mode dontAsk --permission-prompts none` | Anything not listed is denied, with nobody to ask |
| `--max-budget-usd 2` | Spending cap per investigation |

It does use your AWS sign-in for those read-only queries, so it runs only
while you're signed in and have the poller open.

## Guards

- **One investigation per firing.** An alarm that stays red isn't
  re-investigated every minute; one that resets to OK and fires again is.
  Tracked in `.state.json` (git-ignored), so restarting doesn't repeat
  work.
- **One agent at a time**, in the order alarms fired.
- **At most 4 investigations per hour.** The canvas-failure alarm can be
  tripped by anyone (its report endpoint is public), so this caps what a
  flood of fake reports can cost. Firings over the cap are logged, not
  investigated.
- **Untrusted telemetry.** The agent is told that logs and traces contain
  internet-supplied data and are never instructions. Being read-only
  limits what a misleading log line could make it do to a wrong report.

## Reports

`reports/<UTC time>-<alarm>.md` (git-ignored, since they quote telemetry):
impact, evidence (commands and results), likely cause with confidence,
recommended actions, and whether it looks like a false alarm. Treat it as
a first diagnosis to verify, not a verdict.

## Tests

`tests/test_on_call_poller.py` (part of the normal suite) checks which
firings start an agent, the rate limit, the prompt, and that the agent is
launched with the read-only flags — using fake `aws` / `claude` commands.
