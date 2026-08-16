<p align="center">
  <img src="harness_banner.png" alt="Harness Banner" width="600">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.1.0-brightgreen.svg" alt="Version">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/Claude_Code-Plugin-purple.svg" alt="Claude Code Plugin">
  <img src="https://img.shields.io/badge/Patterns-6_Architectures-orange.svg" alt="6 Architecture Patterns">
</p>

# myharness — Claude Code のエージェントチーム & スキルアーキテクト

[English](README.md) | [한국어](README_KO.md) | **日本語**

> **「ハーネスを構成して」** の一言で、ドメインの説明をエージェントチームと、それらが使うスキルセットに変換します。

> **フォークについて.** [revfactory/harness](https://github.com/revfactory/harness)（Apache-2.0）の個人フォークです。原著者のクレジットと変更内容の全文は [`NOTICE`](NOTICE) を参照してください。

## 概要

myharness は複雑なタスクを専門エージェントの協調チームに分解します。ドメインに合わせたエージェント定義（`.claude/agents/`）とスキル（`.claude/skills/`）を生成し、オーケストレータースキルで一つのワークフローにまとめます。

## インストール

```shell
/plugin marketplace add punkyade/myharness
/plugin install myharness@myharness-marketplace
```

プラグインを使わずスキルだけを直接インストールする場合:

```shell
cp -r skills/harness ~/.claude/skills/harness
```

## 要件

- [エージェントチームの有効化](https://code.claude.com/docs/en/agent-teams): `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`

このフラグがないと、チームベースの実行モードは単一エージェント実行にフォールバックします。[`docs/experimental-dependency.md`](docs/experimental-dependency.md) を参照。

**任意 — マルチランタイムモード専用:** `codex` および／または `agy` が `PATH` にあり、認証済みであること。外部ランタイムでのクロス検証を明示的に要求したときにのみ呼び出され、他のモードはこれらなしで動作します。未インストールでも基本機能は損なわれません。

## 使い方

Claude Code で次のようにトリガーします:

```
ハーネスを構成して
このドメイン向けのエージェントチームを設計して
Build a harness for this project
```

後続作業も同じスキルが処理します。「ハーネスの点検」「エージェントを追加して」「ハーネスを修正して」は、ゼロから作り直さずに監査・保守の経路に入ります。

## ワークフロー

```
Phase 0: 現状監査（新規構築 / 既存拡張 / 運用・保守）
    ↓
Phase 1: ドメイン分析
    ↓
Phase 2: チームアーキテクチャ設計（チーム / サブ / ハイブリッド / マルチランタイム）
    ↓
Phase 3: エージェント定義の生成（.claude/agents/）
    ↓
Phase 4: スキルの生成（.claude/skills/）
    ↓
Phase 5: 統合とオーケストレーション
    ↓
Phase 6: 検証とテスト
    ↓
Phase 7: ハーネスの進化（フィードバック → 反映 → 変更履歴）
```

### 実行モード

| モード | 方式 | 推奨される場面 |
|--------|------|---------------|
| **エージェントチーム**（既定） | `TeamCreate` + `SendMessage` + `TaskCreate` | 2名以上の協業・調整が必要なとき |
| **サブエージェント** | `Agent` ツールの直接呼び出し | 単発タスク、エージェント間通信が不要 |
| **ハイブリッド** | Phase ごとに異なるモード | 例: 並列収集（サブ）→ 合意統合（チーム） |
| **マルチランタイム**（任意） | ネイティブチーム + アダプターが外部 CLI（`codex`, `agy`）へ読み取り専用で委譲 | モデルの多様性が必要なクロス検証 — 明示的に要求したときのみ |

### アーキテクチャパターン

| パターン | 説明 |
|----------|------|
| パイプライン | 順次依存するタスク |
| ファンアウト/ファンイン | 並列で独立したタスク |
| エキスパートプール | 状況に応じた選択的呼び出し |
| 生成-レビュー | 生成後に品質レビュー |
| スーパーバイザー | 中央エージェントが状態管理と動的分配 |
| 階層的委譲 | 上位エージェントが下位へ再帰的に委譲 |

## プラグイン構成

```
myharness/
├── .claude-plugin/
│   ├── plugin.json                     # プラグインマニフェスト
│   └── marketplace.json                # マーケットプレイスマニフェスト
├── skills/
│   └── harness/
│       ├── SKILL.md                    # メインスキル定義（Phase 0〜7）
│       ├── references/
│       │   ├── agent-design-patterns.md   # 6つのアーキテクチャパターン
│       │   ├── orchestrator-template.md   # オーケストレーターテンプレート（A〜D）
│       │   ├── team-examples.md           # 実践的なチーム構成例 5種
│       │   ├── skill-writing-guide.md     # スキル作成ガイド
│       │   ├── skill-testing-guide.md     # テスト・評価の方法論
│       │   ├── qa-agent-guide.md          # QA エージェント統合ガイド
│       │   └── multi-runtime-guide.md     # 外部 CLI 統合（codex, agy）
│       └── scripts/
│           └── delegate.py             # 外部ランタイムへの委譲
└── docs/
    ├── quickstart.md
    └── experimental-dependency.md
```

## 生成物

対象プロジェクトに生成されるファイル:

```
your-project/
├── CLAUDE.md            # ハーネスのポインタ（トリガー規則 + 変更履歴）
└── .claude/
    ├── agents/          # エージェント定義ファイル
    │   ├── analyst.md
    │   ├── builder.md
    │   └── qa.md
    └── skills/          # スキルファイル
        ├── analyze/
        │   └── SKILL.md
        └── build/
            ├── SKILL.md
            └── references/
```

## プロンプト例

```
ディープリサーチ用のハーネスを構成して。ウェブ検索、学術資料、
コミュニティの反応など複数の角度からトピックを調査し、
クロス検証したうえで総合レポートを出すエージェントチームが欲しい。
```

```
フルスタックのウェブサイト開発ハーネスを構成して。デザイン、
フロントエンド（React/Next.js）、バックエンド（API）、QA テストを
ワイヤーフレームからデプロイまでパイプラインで処理するチームで。
```

```
コードレビュー用のハーネスを構成して。アーキテクチャ、セキュリティ脆弱性、
パフォーマンスのボトルネック、コードスタイルを並列エージェントが検査し、
一つのレポートに統合してほしい。
```

## ライセンス

Apache 2.0 — [`LICENSE`](LICENSE) および [`NOTICE`](NOTICE) を参照。
