# otel-hooks

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/HikaruEgashira/otel-hooks/badge)](https://scorecard.dev/viewer/?uri=github.com/HikaruEgashira/otel-hooks)
[![PyPI](https://img.shields.io/pypi/v/otel-hooks)](https://pypi.org/project/otel-hooks/)

AI coding tools tracing hooks for observability.

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
| [Claude Code](https://code.claude.com/docs/en/hooks) | Stop hook → transcript parsing | `otel-hooks enable --tool claude` |
| [Cursor](https://cursor.com/ja/docs/agent/hooks) | Stop hook (v1.7+ beta) | `otel-hooks enable --tool cursor` |
| [Codex CLI](https://developers.openai.com/codex/config-reference) | Native OTLP (`~/.codex/config.toml`) | `otel-hooks enable --tool codex` |
| [OpenCode](https://opencode.ai/docs/plugins/) | `session_completed` hook | `otel-hooks enable --tool opencode` |
| [GitHub Copilot](https://docs.github.com/en/copilot/reference/hooks-configuration) | `sessionEnd` hook (CLI & VS Code) | `otel-hooks enable --tool copilot` |
| [Gemini CLI](https://geminicli.com/docs/hooks/) | `SessionEnd` hook | `otel-hooks enable --tool gemini` |
| [Kiro](https://kiro.dev/docs/cli/hooks/) | `stop` hook (agent config) | `otel-hooks enable --tool kiro` |
| [Cline](https://docs.cline.bot/customization/hooks) | `TaskComplete` script | `otel-hooks enable --tool cline` |

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

| Provider | Install |
|----------|---------|
| Langfuse | `pip install otel-hooks[langfuse]` |
| OTLP | `pip install otel-hooks[otlp]` |
| Datadog | `pip install otel-hooks[datadog]` |

<details>
<summary>Langfuse</summary>

```bash
pip install otel-hooks[langfuse]
otel-hooks enable --tool claude --provider langfuse
```

| Variable | Description |
|---|---|
| `LANGFUSE_PUBLIC_KEY` | Public key |
| `LANGFUSE_SECRET_KEY` | Secret key |
| `LANGFUSE_BASE_URL` | Host (default: `https://cloud.langfuse.com`) |

</details>

<details>
<summary>OTLP</summary>

```bash
pip install otel-hooks[otlp]
otel-hooks enable --tool claude --provider otlp
```

| Variable | Description |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Endpoint URL |
| `OTEL_EXPORTER_OTLP_HEADERS` | Headers (`key=value,key=value`) |

</details>

<details>
<summary>Datadog</summary>

```bash
pip install otel-hooks[datadog]
otel-hooks enable --tool claude --provider datadog
```

Requires a running [Datadog Agent](https://docs.datadoghq.com/agent/).

| Variable | Description |
|---|---|
| `DD_SERVICE` | Service name (default: `otel-hooks`) |
| `DD_ENV` | Environment tag |
| `DD_AGENT_HOST` | Agent host (default: `localhost`) |
| `DD_TRACE_AGENT_PORT` | Agent port (default: `8126`) |

</details>

<details>
<summary>Common environment variables</summary>

| Variable | Description |
|---|---|
| `OTEL_HOOKS_PROVIDER` | `langfuse`, `otlp`, or `datadog` |
| `OTEL_HOOKS_ENABLED` | Set `true` to enable |
| `OTEL_HOOKS_DEBUG` | Set `true` to enable debug logging |
| `OTEL_HOOKS_MAX_CHARS` | Truncation limit per message (default: `20000`) |

</details>

## References

- [Claude Code Integration with Langfuse](https://langfuse.com/integrations/other/claude-code) – Langfuse official guide for Claude Code tracing
- [Entire CLI](https://github.com/entireio/cli) – AI agent session capture for git workflows

## License

MIT
