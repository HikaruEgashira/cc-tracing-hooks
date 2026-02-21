# ADR-0001: ツール連携は trace と metrics の2種別で定義する

## ステータス
採用

## コンテキスト
`otel-hooks` は AI ツールの hook payload を provider に送信する。
しかしツールごとに公開される情報量が異なるため、すべてを transcript ベースの trace として扱うと意味論が崩れる。

ツール連携には以下の2種類がある。

- `trace`: セッションを再構成できる transcript もしくは同等のイベント系列を取得できる
- `metrics`: prompt/tool/session 単位の集計イベントのみ取得できる

## 決定
サポートは `trace` と `metrics` を明示して管理する。

- OpenCode は plugin event stream を使って `trace + metrics` をサポートする。
- GitHub Copilot は hook payload の公開情報に合わせて `metrics` をサポートする。
- Kiro は hook payload の公開情報に合わせて `metrics` をサポートする。

## 根拠
- GitHub Copilot は `UserPromptSubmit/PreToolUse/PostToolUse/SessionEnd` で prompt/tool/session 情報を取得できるが transcript は公開されない。
- Kiro は `userPromptSubmit/preToolUse/postToolUse/stop` で prompt/tool/session 情報を取得できるが transcript は公開されない。
- OpenCode plugin は `message.updated` と `message.part.updated` を取得でき、セッションとメッセージ系列を再構成できる。

## 影響
- サポート一覧と実装の意味論を一致させる。
- `trace` 不可ツールでも `metrics` で観測可能性を維持する。
- 将来、公開仕様が拡張された場合は `metrics` から `trace` へ昇格を再評価する。
