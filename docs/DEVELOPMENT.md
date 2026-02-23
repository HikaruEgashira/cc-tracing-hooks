# Development

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker (for local provider backends)

## Setup

```bash
uv sync
```

## Local Provider Backends

`docker-compose.yml` defines three provider backends. Jaeger starts by default; Datadog and Langfuse use [Docker Compose profiles](https://docs.docker.com/compose/how-tos/profiles/).

### Jaeger (OTLP) — recommended

API key不要。ローカル検証のデフォルト。

```bash
# 1. Start Jaeger
docker compose up -d jaeger

# 2. Enable hook
uv run otel-hooks enable --tool claude --provider otlp --project
# endpoint を聞かれたら: http://localhost:4318/v1/traces
```

- Jaeger UI: http://localhost:16686

### Datadog

DD_API_KEY が必要。ddtrace SDKはAPIキーなしでも動作するが、dd-agentはキーがないと起動しない。

```bash
# 1. Start Datadog Agent
echo 'DD_API_KEY=your_key' > .env
docker compose --profile datadog up -d

# 2. Enable hook
uv run otel-hooks enable --tool claude --provider datadog --project
```

### Langfuse (v2)

```bash
# 1. Start Langfuse
docker compose --profile langfuse up -d
# 初回: http://localhost:3000 でサインアップしてAPI keyを取得

# 2. Enable hook
uv run otel-hooks enable --tool claude --provider langfuse --project
# public_key, secret_key, base_url (http://localhost:3000) を入力
```

## Provider Debugging Limitations

| Provider | ローカル完結 | API key | 制約 |
|----------|:----------:|:-------:|------|
| **OTLP (Jaeger)** | Yes | 不要 | 制約なし。トレースの送信・検索・UIすべてローカルで完結 |
| **Datadog** | No | 必須 | dd-agentは`DD_API_KEY`なしでは起動しない。SDKレベルの動作確認（emit_turn成功・ログ出力）は可能だが、トレースの到達確認にはDatadogアカウントが必要 |
| **Langfuse** | Partial | 必要（セルフホスト） | v2をセルフホストすればローカル完結するが、初回にUIでサインアップしてAPI keyを発行する手順が必要。SDK単体テストはダミーキーで401を確認するのみ |

hookのデバッグログは `~/.config/otel-hooks/state/otel_hook.log` に出力される。`OTEL_HOOKS_DEBUG=true` で詳細ログを有効化できる。

## Tests

```bash
uv run pytest
```

## Cleanup

```bash
docker compose --profile datadog --profile langfuse down -v
```
