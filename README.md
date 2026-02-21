# cc-tracing-hooks

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/HikaruEgashira/cc-tracing-hooks/badge)](https://scorecard.dev/viewer/?uri=github.com/HikaruEgashira/cc-tracing-hooks)
[![PyPI](https://img.shields.io/pypi/v/cc-tracing-hooks)](https://pypi.org/project/cc-tracing-hooks/)

Claude Code の全セッションを [Langfuse](https://langfuse.com) にトレースする hooks プラグイン。

## Install

```bash
mise use -g pipx:cc-tracing-hooks
```

or

```bash
pip install cc-tracing-hooks
```

## Usage

```bash
# Langfuse の接続情報を対話的に設定し、hooks を有効化
cc-tracing-hooks enable

# 現在の設定を確認
cc-tracing-hooks status

# 設定の問題を検出・自動修復
cc-tracing-hooks doctor

# hooks を無効化
cc-tracing-hooks disable
```

## How it works

`enable` は以下を行います:

1. `~/.claude/hooks/langfuse_hook.py` にシンボリックリンクを作成
2. `~/.claude/settings.json` の `hooks.Stop` にフックを登録
3. Langfuse の環境変数 (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`) を設定

Claude Code のセッション終了時にフックが起動し、トランスクリプトを差分読み取りして Langfuse にトレースを送信します。

## Environment variables

| Variable | Description |
|---|---|
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key |
| `LANGFUSE_BASE_URL` | Langfuse host (default: `https://cloud.langfuse.com`) |
| `CC_LANGFUSE_DEBUG` | `true` でデバッグログを有効化 |
| `CC_LANGFUSE_MAX_CHARS` | トランスクリプトの最大文字数 (default: `20000`) |

## License

MIT
