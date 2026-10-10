# Ruflo mod runtime experiment

This lab verifies the difference between installing Ruflo configuration and
executing its Claude Code function hooks.

## Versions tested

- Claude Code `2.1.296`
- Ruflo `3.56.3`
- Node.js `24.19.0`

## Isolated setup

```bash
mkdir ruflo-mod-lab
cd ruflo-mod-lab

npx -y ruflo@3.56.3 init \
  --minimal \
  --no-global \
  --no-plugin-install \
  --no-signup \
  --no-skills-sh \
  --no-codex-detect

claude plugin marketplace add ruvnet/ruflo --scope project
claude plugin install ruflo-mods@ruflo --scope project
claude plugin install ruflo-swarm@ruflo --scope project
claude plugin install ruflo-console@ruflo --scope project

export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1
npx -y ruflo@3.56.3 mods doctor
```

Accept Claude Code's trust prompt only after reviewing the generated project
settings and plugin permissions.

## Restricted execution

The test disabled nonessential traffic and excluded project MCP servers:

```bash
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export DISABLE_TELEMETRY=1
export DISABLE_ERROR_REPORTING=1
export DISABLE_BUG_COMMAND=1

printf '{"mcpServers":{}}\n' > empty-mcp.json

claude -p \
  "Create exactly one disposable file named mod-hook-test.txt containing exactly this one line: Ruflo mod hook experiment succeeded. Do not modify any other files and do not run any other commands. Then stop." \
  --max-turns 2 \
  --output-format text \
  --mcp-config empty-mcp.json \
  --strict-mcp-config
```

## Verified evidence

Ruflo's event stream recorded:

```text
router picked coder (60%)
claude: Write
```

The post-edit learning record contained:

```json
{"type":"edit","file":"mod-hook-test.txt","success":true}
```

This verifies the complete sequence:

`prompt → route → coder → Write → post-edit → persisted evidence`

The `/ruflo-mods` counters are session-local. A fresh status session begins at
zero; persistent evidence should be checked in the project's Ruflo event and
pending-insight records.
