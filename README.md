# otel-hooks

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/HikaruEgashira/otel-hooks/badge)](https://scorecard.dev/viewer/?uri=github.com/HikaruEgashira/otel-hooks)
[![PyPI](https://img.shields.io/pypi/v/otel-hooks)](https://pypi.org/project/otel-hooks/)

AI Agent hooks for llm observability.

<img src="langfuse-demo.png" alt="demo" width="600" />

## Install

```bash
mise use -g pipx:otel-hooks
# or
pip install otel-hooks
# or
pipx otel-hooks
```

## Supported tools

| Tool | Support | Scope | Setup |
|------|---------|--------|-------|
| [Claude Code](https://code.claude.com/docs/en/hooks) | Trace | Global / Project | `otel-hooks enable --tool claude` |
| [Cursor](https://cursor.com/ja/docs/agent/hooks) | Trace | Global / Project | `otel-hooks enable --tool cursor` |
| [Codex CLI](https://developers.openai.com/codex/config-reference) | Trace | Global | `otel-hooks enable --tool codex` |
| [OpenCode](https://opencode.ai/docs/plugins/) | Trace | Project | `otel-hooks enable --tool opencode` |
| [Gemini CLI](https://geminicli.com/docs/hooks/) | Trace | Global / Project | `otel-hooks enable --tool gemini` |
| [Cline](https://docs.cline.bot/customization/hooks) | Trace | Project | `otel-hooks enable --tool cline` |
| [GitHub Copilot](https://docs.github.com/en/copilot/reference/hooks-configuration) | Metrics Only | Project | `otel-hooks enable --tool copilot` |
| [Kiro](https://kiro.dev/docs/cli/hooks/) | Metrics Only | Global / Project | `otel-hooks enable --tool kiro` |

## Usage

```bash
otel-hooks enable          # interactive tool/provider selection
otel-hooks enable --tool <name> --provider <provider>
otel-hooks status          # show status for all tools
otel-hooks doctor          # detect and fix issues
otel-hooks disable --tool <name>
```

## How it works

`enable` registers tool-specific integration that runs `otel-hooks hook`. **Trace** tools provide transcript data for full turn reconstruction (including per-event metrics). **Metrics** tools lack transcript access, so only coarse hook events (prompt/tool/session level) are recorded. Provider settings are stored in a unified otel-hooks config file, shared across all tools.

For metrics-only tools, `otel-hooks` registers all observable hook events (not only end events) to avoid data gaps.

`preToolUse` / `postToolUse` event names can overlap across tools. `otel-hooks` injects `source_tool` via the `--tool` CLI flag at hook execution time to keep payload adapter selection deterministic.

## Configuration

Provider settings are stored in otel-hooks config files (not in each tool's settings):

- **Global**: `~/.config/otel-hooks/config.json`
- **Project**: `.otel-hooks.json` (repository root)

Project config overrides global. Environment variables override both.

```json
{
  "provider": "langfuse",
  "debug": false,
  "max_chars": 20000,
  "langfuse": {
    "public_key": "pk-...",
    "secret_key": "sk-...",
    "base_url": "https://cloud.langfuse.com"
  }
}
```

`otel-hooks enable` writes this config interactively. Each tool's own settings file only contains the hook registration.

## Providers

Langfuse, OTLP, Datadog are all included — no extras needed.

| Provider | Docs |
|----------|------|
| Langfuse | `langfuse.public_key`, `langfuse.secret_key`, `langfuse.base_url` |
| OTLP | `otlp.endpoint`, `otlp.headers` |
| Datadog | `datadog.service`, `datadog.env` — requires [Datadog Agent](https://docs.datadoghq.com/agent/) |

Environment variables (`LANGFUSE_PUBLIC_KEY`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `DD_SERVICE`, etc.) override config file values. See also `OTEL_HOOKS_PROVIDER`, `OTEL_HOOKS_DEBUG`, `OTEL_HOOKS_MAX_CHARS`.

## License

MIT
