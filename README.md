# otel-hooks

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/HikaruEgashira/otel-hooks/badge)](https://scorecard.dev/viewer/?uri=github.com/HikaruEgashira/otel-hooks)
[![PyPI](https://img.shields.io/pypi/v/otel-hooks)](https://pypi.org/project/otel-hooks/)

Send Claude Code session traces to [Langfuse](https://langfuse.com).

## Install

```bash
mise use -g pipx:otel-hooks
```

```bash
pip install otel-hooks
```

## Usage

```bash
otel-hooks enable          # configure Langfuse credentials and register the hook
otel-hooks enable --global # write to ~/.claude/settings.json
otel-hooks enable --local  # write to .claude/settings.local.json

otel-hooks status          # show configuration for both scopes
otel-hooks doctor          # detect and fix issues
otel-hooks disable         # remove the hook
```

## How it works

`enable` registers a [Stop hook](https://docs.anthropic.com/en/docs/claude-code/hooks) that runs `otel-hooks hook` after each Claude Code response. The hook reads the session transcript incrementally and emits traces to Langfuse.

`--global` writes to `~/.claude/settings.json` (applies to all projects).
`--local` writes to `.claude/settings.local.json` (current project only).
When neither flag is given, you are prompted to choose.

## Environment variables

| Variable | Description |
|---|---|
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key |
| `LANGFUSE_BASE_URL` | Langfuse host (default: `https://cloud.langfuse.com`) |
| `CC_LANGFUSE_DEBUG` | Set `true` to enable debug logging |
| `CC_LANGFUSE_MAX_CHARS` | Truncation limit per message (default: `20000`) |

## References

- [Claude Code Integration with Langfuse](https://langfuse.com/integrations/other/claude-code) – Langfuse official guide for Claude Code tracing
- [Entire CLI](https://github.com/entireio/cli) – AI agent session capture for git workflows

## License

MIT
