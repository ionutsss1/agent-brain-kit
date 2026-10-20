# MCP policy server (optional example)

A pattern, not a product: give agents a few bounded tools through an MCP server, and put every rule in one
policy file, instead of handing them a raw shell for risky work. Copy it and replace the four example tools
with your own (start a test environment, read a log, run a named check...).

| File | What it does |
|---|---|
| `server.py` | stdio MCP server (newline-delimited JSON-RPC: initialize, ping, tools/list, tools/call). Standard library only. |
| `policy.py` | Every argument passes through here. Refusals name their rule (`SECRET_PATH`, `OUTSIDE_ROOTS`, `FORBIDDEN_WORD`, `UNKNOWN_CHECK`, `RANGE`, `TRAVERSAL`...). |
| `tests/test_policy.py` | `python3 -B -m unittest discover -s optional/mcp-policy-server/tests` |

## Example tools
- `kit_status`: brain lease and account usage (read-only).
- `activity_tail`: last n activity-log lines with a literal filter.
- `read_note`: one text file under `mcp.allowed_read_roots`; secret paths and names from `guard` refused.
- `run_check`: one named command from `mcp.checks` (an argv list, never a shell string).
Every tool takes `dry_run`: it validates and reports, and changes nothing. Every call is audited to
`<paths.logs>/mcp_audit.jsonl`.

## Rules worth copying
- Refuse by name: forbidden accounts, folders and actions live in the policy, not in prompts.
- No free-form commands: named checks map to fixed argv lists.
- Destructive actions (stopping a service, deleting data) are simply not exposed.
- Owner-only resources (the owner's own accounts, their working copy) are refused even when asked.

## Register
Project `.mcp.json`:
```json
{"mcpServers": {"kit-policy": {"command": "python3", "args": ["<kit repo>/optional/mcp-policy-server/server.py"]}}}
```
Worker sessions started with `-p` may need `--mcp-config <path to .mcp.json>` if it does not load by itself.
