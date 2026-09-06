# -*- coding: utf-8 -*-
"""drills_12weeks.md → 配信用 HTML メール本文（1回ずつ）を生成する。

使い方:  python build_drills.py
出力:    week00_intro.html, week01.html … week12.html, index.html
方針:    プレーンな HTML。外部 CSS・JS・画像なし。インラインスタイルのみ。
"""
import html
import re
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "drills_12weeks.md"

# ---- 色・書体（LP の配色に寄せた控えめな設定） ----
INK = "#1a1a1a"
SUB = "#555555"
LINE = "#e3e3e3"
ACCENT = "#c8a24a"      # LP の山吹（.y）に近い金
BG = "#f6f5f2"
CODEBG = "#f1f1ee"
FONT = "-apple-system,BlinkMacSystemFont,'Hiragino Sans','Hiragino Kaku Gothic ProN','Yu Gothic',Meiryo,sans-serif"
MONO = "Consolas,'Courier New',monospace"

ORG = "レリック社会保険労務士法人"
SERIES = "帰ってからも伸びる：毎週届く15分のドリル"
CONTACT = "m.gomita@canvas-sr.jp"
UPDATED = "2026年9月6日"


def esc(t: str) -> str:
    return html.escape(t, quote=False)


def inline(t: str) -> str:
    """太字・インラインコード・URL を HTML に。"""
    t = esc(t)
    t = re.sub(r"`([^`]+)`", lambda m: f'<code style="font-family:{MONO};background:{CODEBG};padding:1px 4px;border-radius:3px;font-size:13px;">{m.group(1)}</code>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(https?://[^\s<）]+)", lambda m: f'<a href="{m.group(1)}" style="color:#1d4ed8;word-break:break-all;">{m.group(1)}</a>', t)
    return t


def render_table(rows):
    head, body = rows[0], rows[2:]
    out = [f'<table cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;margin:12px 0;font-size:14px;">']
    out.append("<tr>")
    for c in head:
        out.append(f'<th align="left" style="padding:8px 10px;border-bottom:2px solid {INK};font-weight:700;">{inline(c)}</th>')
    out.append("</tr>")
    for r in body:
        out.append("<tr>")
        for i, c in enumerate(r):
            style = f"padding:8px 10px;border-bottom:1px solid {LINE};vertical-align:top;"
            if i == 0:
                style += "white-space:nowrap;color:" + SUB + ";"
            out.append(f'<td style="{style}">{inline(c)}</td>')
        out.append("</tr>")
    out.append("</table>")
    return "".join(out)


def md_to_html(md: str) -> str:
    lines = md.splitlines()
    out = []
    i = 0
    para = []

    def flush_para():
        if para:
            out.append(f'<p style="margin:0 0 12px;line-height:1.9;">{inline(" ".join(para))}</p>')
            para.clear()

    while i < len(lines):
        ln = lines[i]
        # fenced code
        if ln.startswith("```"):
            flush_para()
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].startswith("```"):
                buf.append(lines[j])
                j += 1
            code = esc("\n".join(buf))
            out.append(
                f'<pre style="font-family:{MONO};font-size:13px;line-height:1.7;background:{CODEBG};'
                f'border:1px solid {LINE};border-radius:6px;padding:12px 14px;margin:10px 0 14px;'
                f'white-space:pre-wrap;word-break:break-all;overflow-x:auto;">{code}</pre>'
            )
            i = j + 1
            continue
        # table
        if ln.startswith("|"):
            flush_para()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            out.append(render_table(rows))
            continue
        # headings
        m = re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            flush_para()
            lvl, text = len(m.group(1)), m.group(2)
            if lvl <= 2:
                out.append(f'<h2 style="font-size:20px;margin:28px 0 10px;line-height:1.5;">{inline(text)}</h2>')
            elif lvl == 3:
                out.append(
                    f'<h3 style="font-size:16px;margin:26px 0 8px;padding-left:10px;border-left:4px solid {ACCENT};line-height:1.5;">{inline(text)}</h3>'
                )
            else:
                out.append(f'<h4 style="font-size:15px;margin:18px 0 6px;">{inline(text)}</h4>')
            i += 1
            continue
        # hr
        if ln.strip() == "---":
            flush_para()
            out.append(f'<hr style="border:0;border-top:1px solid {LINE};margin:24px 0;">')
            i += 1
            continue
        # lists (bullets, checkboxes, numbered)
        if re.match(r"^\s*(-|\d+\.)\s+", ln):
            flush_para()
            items = []
            while i < len(lines) and re.match(r"^\s*(-|\d+\.)\s+", lines[i]):
                items.append(lines[i])
                i += 1
            ordered = bool(re.match(r"^\s*\d+\.", items[0]))
            tag = "ol" if ordered else "ul"
            out.append(f'<{tag} style="margin:6px 0 14px;padding-left:22px;line-height:1.9;">')
            for it in items:
                indent = len(it) - len(it.lstrip())
                body = re.sub(r"^\s*(-|\d+\.)\s+", "", it)
                cb = re.match(r"^\[( |x)\]\s+(.*)$", body)
                if cb:
                    box = "☑" if cb.group(1) == "x" else "☐"
                    body = f"{box} {cb.group(2)}"
                style = "margin:2px 0;"
                if indent >= 2:
                    style += "list-style:none;margin-left:6px;color:" + SUB + ";"
                out.append(f'<li style="{style}">{inline(body)}</li>')
            out.append(f"</{tag}>")
            continue
        # blank
        if not ln.strip():
            flush_para()
            i += 1
            continue
        para.append(ln.strip())
        i += 1
    flush_para()
    return "\n".join(out)


def wrap(title: str, kicker: str, body_html: str, week_no: int | None) -> str:
    badge = f'<div style="font-size:13px;letter-spacing:.12em;color:{ACCENT};font-weight:700;">{esc(kicker)}</div>'
    weekline = ""
    if week_no is not None:
        weekline = f'<div style="font-size:40px;font-weight:800;line-height:1;margin:6px 0 4px;">第{week_no}週</div>'
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}｜{esc(SERIES)}</title>
</head>
<body style="margin:0;padding:0;background:{BG};color:{INK};font-family:{FONT};font-size:15px;">
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:{BG};">
<tr><td align="center" style="padding:24px 12px;">
<table cellpadding="0" cellspacing="0" border="0" width="640" style="max-width:640px;width:100%;background:#ffffff;border:1px solid {LINE};border-radius:8px;">
<tr><td style="padding:28px 28px 8px;border-top:6px solid {ACCENT};border-radius:8px 8px 0 0;">
  <div style="font-size:12px;color:{SUB};">{esc(ORG)}　AI経営 × クエスト型ブートキャンプ</div>
  {badge}
  {weekline}
  <h1 style="font-size:22px;margin:4px 0 6px;line-height:1.5;">{esc(title)}</h1>
  <div style="font-size:13px;color:{SUB};">1回15分。頼む → 動かす → 確かめる → 直す。決めるのは、あなた。</div>
</td></tr>
<tr><td style="padding:8px 28px 28px;">
{body_html}
</td></tr>
<tr><td style="padding:18px 28px 24px;border-top:1px solid {LINE};font-size:12px;color:{SUB};line-height:1.8;">
  このドリルは、AI の新機能や仕様変更に合わせて改定しています（最終更新：{esc(UPDATED)}）。<br>
  詰まった点は、月次1on1でお持ちください。ご質問は <a href="mailto:{CONTACT}" style="color:#1d4ed8;">{CONTACT}</a> まで。<br>
  記載の所要時間は当プログラムの設計値です。効果を保証するものではありません。Claude Code、Codex、Claude、MCP はそれぞれの権利者の商標または名称です。<br>
  © 2026 {esc(ORG)}
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
"""


def main():
    md = SRC.read_text(encoding="utf-8")
    # 本文の最初の H1 は捨てる
    md = re.sub(r"^# .*\n", "", md, count=1)
    # 週ごとに分割
    parts = re.split(r"(?m)^## (第(\d+)週　(.*))$", md)
    intro = parts[0]
    weeks = []
    for k in range(1, len(parts), 4):
        heading, num, title, body = parts[k], int(parts[k + 1]), parts[k + 2], parts[k + 3]
        weeks.append((num, title.strip(), body))
    # 付録（最終週の本文末尾にある「## 付録」以降）を切り出して最終週から外す
    last_num, last_title, last_body = weeks[-1]
    appendix = ""
    if "\n## 付録" in last_body:
        idx = last_body.index("\n## 付録")
        appendix = last_body[idx:]
        weeks[-1] = (last_num, last_title, last_body[:idx])

    # 第0週：はじめに（使い方・準備）
    intro_md = intro.replace("## このドリルの使い方", "### このドリルの使い方")
    intro_md = re.sub(r"(?m)^---\s*$", "", intro_md)
    intro_html = md_to_html(intro_md + "\n" + appendix.replace("## 付録", "### 付録"))
    (HERE / "week00_intro.html").write_text(
        wrap("はじめに：使い方と、最初の準備（10分）", "WEEKLY DRILL ｜ WEEK 0", intro_html, None), encoding="utf-8"
    )

    base = "https://mgomita-ui.github.io/hatarakikata4-lp/bootcamp/drills/"
    rows = []
    all_parts = [f'<h2 style="font-size:20px;margin:28px 0 10px;">第0週　はじめに：使い方と、最初の準備（10分）</h2>', intro_html]
    for num, title, body in weeks:
        body_html = md_to_html(body)
        fn = f"week{num:02d}.html"
        (HERE / fn).write_text(wrap(title, f"WEEKLY DRILL ｜ WEEK {num}", body_html, num), encoding="utf-8")
        aim = re.search(r"### ねらい\n\n(.+?)\n", body)
        aim_txt = aim.group(1).strip() if aim else ""
        rows.append(
            f'<tr><td style="padding:10px 8px;border-bottom:1px solid {LINE};white-space:nowrap;color:{SUB};vertical-align:top;">第{num}週</td>'
            f'<td style="padding:10px 8px;border-bottom:1px solid {LINE};vertical-align:top;"><a href="{fn}" style="color:#1d4ed8;font-weight:700;">{esc(title)}</a>'
            f'<div style="font-size:13px;color:{SUB};line-height:1.7;margin-top:2px;">{inline(aim_txt)}</div></td></tr>'
        )
        all_parts.append(f'<hr style="border:0;border-top:2px solid {ACCENT};margin:36px 0;"><h2 style="font-size:20px;margin:0 0 10px;"><a id="week{num:02d}"></a>第{num}週　{esc(title)}</h2>')
        all_parts.append(body_html)
        print("wrote", fn, title)

    index = (
        f'<p style="line-height:1.9;">ブートキャンプの受講者に、毎週月曜の朝に1回ずつ届く15分のドリルです。'
        f'型はいつも「頼む → 動かす → 確かめる → 直す」。合宿の3つの約束'
        f'（Claude Code と Codex が自分のPCで動く／MCP で自社の数字につながる／計算は Codex、文章は Claude）と揃えてあります。</p>'
        f'<p style="line-height:1.9;"><a href="week00_intro.html" style="color:#1d4ed8;font-weight:700;">第0週　はじめに：使い方と、最初の準備（10分）</a> から始めてください。</p>'
        f'<table cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;margin:12px 0;font-size:15px;">{"".join(rows)}</table>'
        f'<p style="line-height:1.9;font-size:13px;color:{SUB};">全12週を1ページで読む：<a href="all.html" style="color:#1d4ed8;">all.html</a>　／　原本（Markdown）：'
        f'<a href="drills_12weeks.md" style="color:#1d4ed8;">drills_12weeks.md</a><br>'
        f'「今週の変更点」は配信週に改定します（現在は {esc(UPDATED)} 時点）。</p>'
    )
    (HERE / "index.html").write_text(wrap("毎週届く、15分のドリル", "WEEKLY DRILL ｜ 全12週", index, None), encoding="utf-8")
    toc = "".join(f'<li><a href="#week{n:02d}" style="color:#1d4ed8;">第{n}週　{esc(t)}</a></li>' for n, t, _ in weeks)
    all_html = f'<p style="line-height:1.9;">全12週を1ページにまとめた版です。<a href="index.html" style="color:#1d4ed8;">週ごとのページ一覧はこちら</a>。</p><ol style="line-height:2;padding-left:22px;">{toc}</ol>' + "\n".join(all_parts)
    (HERE / "all.html").write_text(wrap("毎週届く、15分のドリル（全12週・通し）", "WEEKLY DRILL ｜ ALL", all_html, None), encoding="utf-8")
    print("wrote index.html, all.html, week00_intro.html")


if __name__ == "__main__":
    main()
