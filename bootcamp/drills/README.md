# 毎週届く15分のドリル（配信素材）

ブートキャンプ LP（`../index.html`）の「帰ってからも、伸びる。01 毎週届く、15分のドリル」の実物です。

## ファイル

| ファイル | 用途 |
|---|---|
| `drills_12weeks.md` | 12週分の原本（ねらい／15分の手順／使うプロンプト例／できたかの確認／今週のAI係数／今週の変更点）。編集はここだけ |
| `build_drills.py` | 原本から配信用 HTML を生成するスクリプト（`python build_drills.py`） |
| `week00_intro.html` | 第0週：使い方・最初の準備（10分）・付録。初回配信時に同梱 |
| `week01.html` 〜 `week12.html` | 各週の HTML メール本文。プレーンな HTML、インラインスタイルのみ、外部 CSS／JS／画像なし |
| `index.html` | 確認用の一覧 |

## 設計の要点

- LP の3カードと揃える：① Claude Code と Codex が自分のPCで動く（第1・2・3・7・11週）② MCP で自社の数字につながる（第5・6・9週）③ 計算は Codex、文章は Claude／人・AI・専門家の線（第4・8・10・12週）。
- 合宿当日の反復AIドリルの5動作（集める・要約・比べる・洗い出す・分析する）と、AI係数の5記録（前提・比較・リスク・聞き返し・改善）を各週に対応させてある。
- 型は毎週同じ「頼む → 動かす → 確かめる → 直す」。第5週まではダミーデータ、第6週から自社データ（顧客名は伏せて可）。
- 言い回し：AI は相棒（部下ではない）、「使いこなす」、「たたき台／聞き返す」、「動かす／頼む」。決めるのは人。製品名は Claude Code／Codex／MCP／Claude をそのまま（ロゴ不可）。ChatGPT／Gemini は書かない。

## 配信前にやること（毎週）

1. `drills_12weeks.md` の該当週の「今週の変更点」を、配信週の最新に差し替える（2〜3件、出典 URL 付き）。調べ先：
   - Claude Code：https://code.claude.com/docs/en/changelog
   - Codex：https://developers.openai.com/codex/changelog
   - Claude（アプリ・Desktop・Cowork）：https://support.claude.com/en/articles/12138966-release-notes
   - MCP：https://blog.modelcontextprotocol.io/
2. 冒頭の「最終更新」日付と、`build_drills.py` の `UPDATED` を更新する。
3. `python build_drills.py` を実行し、該当週の `weekNN.html` をメール本文に貼る。

現在の「今週の変更点」は 2026年9月6日時点の調査です。

## 公開について

GitHub Pages への公開（git push）は五味田さんの確認後に行う。このフォルダはまだコミットしていない。
