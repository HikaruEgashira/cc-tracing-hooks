# otel-hooks

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/HikaruEgashira/otel-hooks/badge)](https://scorecard.dev/viewer/?uri=github.com/HikaruEgashira/otel-hooks)
[![PyPI](https://img.shields.io/pypi/v/otel-hooks)](https://pypi.org/project/otel-hooks/)

AI coding tools tracing hooks for observability. Supports **Claude Code**, **Cursor**, **Codex CLI**, **OpenCode**, **GitHub Copilot**, **Gemini CLI**, **Kiro**, and **Cline**.

<img src="langfuse-demo.png" alt="demo" width="600" />

## Install

```bash
mise use -g pipx:otel-hooks
```

```bash
pip install otel-hooks
```

## Supported tools

| Tool | Mechanism | Setup |
|------|-----------|-------|
| [**Claude Code**](https://code.claude.com/docs/en/hooks) | Stop hook → transcript parsing | `otel-hooks enable --tool claude` |
| [**Cursor**](https://cursor.com/ja/docs/agent/hooks) | Stop hook (v1.7+ beta) | `otel-hooks enable --tool cursor` |
| [**Codex CLI**](https://github.com/openai/codex) | Native OTLP (`~/.codex/config.toml`) | `otel-hooks enable --tool codex` |
| [**OpenCode**](https://opencode.ai/docs/plugins/) | `session_completed` hook | `otel-hooks enable --tool opencode` |
| [**GitHub Copilot**](https://docs.github.com/en/copilot/reference/hooks-configuration) | `sessionEnd` hook (CLI & VS Code) | `otel-hooks enable --tool copilot` |
| [**Gemini CLI**](https://geminicli.com/docs/hooks/) | `SessionEnd` hook | `otel-hooks enable --tool gemini` |
| [**Kiro**](https://kiro.dev/docs/cli/hooks/) | `stop` hook (agent config) | `otel-hooks enable --tool kiro` |
| [**Cline**](https://docs.cline.bot/customization/hooks) | `TaskComplete` script | `otel-hooks enable --tool cline` |

## Usage

```bash
otel-hooks enable          # interactive tool/provider selection
otel-hooks enable --tool <name> --provider <provider>
otel-hooks status          # show status for all tools
otel-hooks doctor          # detect and fix issues
otel-hooks disable --tool <name>
```

## How it works

`enable` registers a hook in each tool's configuration that runs `otel-hooks hook` at session end. The hook reads the session transcript incrementally and emits traces to the configured provider. Codex CLI uses native OTLP support instead of hooks.

## Providers

| Provider | Install | Description |
|----------|---------|-------------|
| Langfuse | `pip install otel-hooks[langfuse]` | Traces to Langfuse |
| OTLP | `pip install otel-hooks[otlp]` | Traces via OpenTelemetry OTLP |

## Environment variables

| Variable | Description |
|---|---|
| `OTEL_HOOKS_PROVIDER` | Provider name (`langfuse` or `otlp`) |
| `OTEL_HOOKS_ENABLED` | Set `true` to enable |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key |
| `LANGFUSE_BASE_URL` | Langfuse host (default: `https://cloud.langfuse.com`) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP endpoint URL |
| `OTEL_EXPORTER_OTLP_HEADERS` | OTLP headers (`key=value,key=value`) |
| `OTEL_HOOKS_DEBUG` | Set `true` to enable debug logging |
| `OTEL_HOOKS_MAX_CHARS` | Truncation limit per message (default: `20000`) |

## References

- [Claude Code Integration with Langfuse](https://langfuse.com/integrations/other/claude-code) – Langfuse official guide for Claude Code tracing
- [Entire CLI](https://github.com/entireio/cli) – AI agent session capture for git workflows

## License

MIT
