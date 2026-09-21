# -*- coding: utf-8 -*-
"""毎週の「今週の変更点」の候補を作る。

4つの出典を取得し、前回見た項目の指紋（updates/state.json）と比べて、
新規・更新の項目だけを updates/YYYY-MM-DD.md に候補として書き出す。
各項目に「経営者向けの言い換え案」を付ける（環境変数 OPENAI_API_KEY があれば
gpt-6-astra に頼む。無ければ空欄）。

使い方:
  python tools/weekly_update.py                      # 今日の日付で候補を作り、state を更新
  python tools/weekly_update.py --date 2026-09-14    # 日付を指定
  python tools/weekly_update.py --dry-run            # state を更新せず、候補を画面に表示するだけ
  python tools/weekly_update.py --no-llm             # 言い換え案を空欄のまま（API を呼ばない）
  python tools/weekly_update.py --max-per-source 12  # 初回など、候補が多いときの1出典あたりの上限

出典（取得できなければ「取得失敗」と記録して続行する）:
  Claude Code changelog   https://code.claude.com/docs/en/changelog
  Codex changelog         https://developers.openai.com/codex/changelog
  Claude release notes    https://support.claude.com/en/articles/12138966-release-notes
  MCP blog                https://blog.modelcontextprotocol.io/

取得は requests があればそれを、無ければ標準の urllib を使う。HTML→テキストは標準の html.parser。
このスクリプトは git を触らない。メールも送らない。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# Windows の cp932 端末でも UTF-8 で出す
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
DRILLS = HERE.parent
UPDATES = DRILLS / "updates"
STATE = UPDATES / "state.json"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) weekly_update/1.0 (relic drills)"
TIMEOUT = 30

SOURCES = [
    {"key": "claude_code", "name": "Claude Code", "url": "https://code.claude.com/docs/en/changelog"},
    {"key": "codex", "name": "Codex", "url": "https://developers.openai.com/codex/changelog"},
    {"key": "claude", "name": "Claude（アプリ・Desktop・Cowork）", "url": "https://support.claude.com/en/articles/12138966-release-notes"},
    {"key": "mcp", "name": "MCP", "url": "https://blog.modelcontextprotocol.io/"},
]

# 言い換え案に入ってはいけない語（drills_12weeks.md と同じ約束）
FORBIDDEN = ["使い倒", "疑", "打つ", "打って", "打ち", "座", "ChatGPT", "Gemini", "補助金", "部下", "社外に出ない"]

FAILED = "取得失敗"


# ---------------------------------------------------------------- 取得
def fetch(url: str, timeout: int = TIMEOUT) -> str:
    """URL の HTML を文字列で返す。失敗は例外。"""
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en,ja;q=0.8"}
    try:
        import requests  # type: ignore

        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        r.encoding = r.encoding or "utf-8"
        return r.text
    except ImportError:
        import urllib.request

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- HTML → イベント列
SKIP_TAGS = {"script", "style", "svg", "noscript", "template", "head", "iframe"}
BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div", "tr", "br", "section", "article", "header", "footer", "time", "pre", "blockquote"}
VOID_TAGS = {"br", "img", "hr", "meta", "link", "input", "source", "wbr", "area", "base", "col", "embed", "param", "track"}


class EventParser(HTMLParser):
    """HTML を (kind, tag, attrs, depth, text) の並びにする。深さで入れ子を追える。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events: list[tuple] = []
        self.stack: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            if tag == "br" and not self.skip:
                self.events.append(("start", tag, {}, len(self.stack)))
            return
        self.stack.append(tag)
        if tag in SKIP_TAGS:
            self.skip += 1
            return
        if self.skip:
            return
        self.events.append(("start", tag, dict(attrs), len(self.stack) - 1))

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        # 閉じ忘れに強くする：スタック内で一番近い同名タグまで閉じる
        if tag not in self.stack:
            return
        while self.stack:
            t = self.stack.pop()
            if t in SKIP_TAGS:
                self.skip = max(0, self.skip - 1)
            elif not self.skip:
                self.events.append(("end", t, {}, len(self.stack)))
            if t == tag:
                break

    def handle_data(self, data):
        if self.skip:
            return
        s = re.sub(r"[​‌‍﻿]", "", data)  # ゼロ幅文字（アンカーの飾り）は捨てる
        s = re.sub(r"\s+", " ", s)
        if s.strip():
            tag = self.stack[-1] if self.stack else ""
            self.events.append(("text", tag, {}, len(self.stack), s))


def to_events(html_text: str) -> list[tuple]:
    p = EventParser()
    p.feed(html_text)
    p.close()
    return p.events


def has_class(attrs: dict, name: str) -> bool:
    return name in (attrs.get("class") or "").split()


def collect_lines(events: list[tuple], start: int, end: int) -> list[tuple[str, str]]:
    """events[start:end] の文字列を、ブロック単位の行 (tag, text) にまとめる。"""
    lines: list[list] = []
    cur_tag = ""
    cur: list[str] = []

    def flush():
        nonlocal cur, cur_tag
        text = "".join(cur).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            lines.append([cur_tag, text])
        cur = []

    for ev in events[start:end]:
        kind, tag = ev[0], ev[1]
        if kind == "start" and tag in BLOCK_TAGS:
            flush()
            cur_tag = tag
        elif kind == "end" and tag in BLOCK_TAGS:
            flush()
        elif kind == "text":
            cur.append(ev[4])
    flush()
    return [(t, s) for t, s in lines]


# ---------------------------------------------------------------- 日付
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS["sept"] = 9

DATE_PATTERNS = [
    re.compile(r"\b(20\d\d)-(\d{1,2})-(\d{1,2})\b"),
    re.compile(r"\b([A-Za-z]{3,9})\.? (\d{1,2}),? (20\d\d)\b"),
    re.compile(r"\b(\d{1,2}) ([A-Za-z]{3,9}) (20\d\d)\b"),
    re.compile(r"(20\d\d)年(\d{1,2})月(\d{1,2})日"),
]


def find_date(text: str) -> str:
    """文字列から最初の日付を ISO 形式で返す。無ければ空。"""
    for i, pat in enumerate(DATE_PATTERNS):
        m = pat.search(text or "")
        if not m:
            continue
        try:
            if i == 0 or i == 3:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            elif i == 1:
                mo = MONTHS.get(m.group(1).lower())
                if not mo:
                    continue
                d, y = int(m.group(2)), int(m.group(3))
            else:
                mo = MONTHS.get(m.group(2).lower())
                if not mo:
                    continue
                d, y = int(m.group(1)), int(m.group(3))
            return dt.date(y, mo, d).isoformat()
        except ValueError:
            continue
    return ""


# ---------------------------------------------------------------- 出典ごとの切り出し
def make_item(key: str, ident: str, title: str, date: str, url: str, lines: list[tuple[str, str]], max_chars: int = 1200) -> dict:
    body_parts = []
    for tag, text in lines:
        if tag == "li":
            body_parts.append("- " + text)
        else:
            body_parts.append(text)
    body = "\n".join(body_parts).strip()
    if len(body) > max_chars:
        body = body[:max_chars].rstrip() + " …"
    return {"source": key, "id": ident, "title": title.strip(), "date": date, "url": url, "body": body}


def parse_claude_code(events, base_url, key):
    """code.claude.com：div.update-container（id=バージョン）ごとに1項目。"""
    items = []
    n = len(events)
    i = 0
    while i < n:
        ev = events[i]
        if ev[0] == "start" and ev[1] == "div" and has_class(ev[2], "update-container") and ev[2].get("id"):
            depth = ev[3]
            j = i + 1
            while j < n and not (events[j][0] == "end" and events[j][3] == depth):
                j += 1
            lines = collect_lines(events, i + 1, j)
            ident = ev[2]["id"]
            title = ""
            date = ""
            rest = []
            for tag, text in lines:
                if not title and re.match(r"^\d+\.\d+\.\d+", text):
                    title = text
                    continue
                if not date and find_date(text) and len(text) < 40:
                    date = find_date(text)
                    continue
                rest.append((tag, text))
            if not title:
                title = ident.replace("-", ".")
            items.append(make_item(key, ident, title, date, f"{base_url}#{ident}", rest))
            i = j
        i += 1
    return items


def parse_codex(events, base_url, key):
    """developers.openai.com：li[id^=codex-] ごとに1項目。time が日付、最初の h3 が題名、article が本文。"""
    items = []
    n = len(events)
    i = 0
    while i < n:
        ev = events[i]
        if ev[0] == "start" and ev[1] == "li" and str(ev[2].get("id", "")).startswith("codex-"):
            depth = ev[3]
            j = i + 1
            while j < n and not (events[j][0] == "end" and events[j][3] == depth):
                j += 1
            lines = collect_lines(events, i + 1, j)
            ident = ev[2]["id"]
            date, title, rest = "", "", []
            for tag, text in lines:
                if tag == "time" and not date:
                    date = find_date(text) or text
                    continue
                if tag == "h3" and not title:
                    title = re.sub(r"\s+\d+\.\d+(\.\d+)?$", "", text)  # 末尾のバージョン番号は落とす
                    continue
                rest.append((tag, text))
            if not date:
                date = find_date(ident)
            items.append(make_item(key, ident, title or ident, date, f"{base_url}#{ident}", rest))
            i = j
        i += 1
    return items


def parse_claude_notes(events, base_url, key):
    """support.claude.com：日付の h3 ごとに1項目。次の h2/h3 までが本文。太字の1行目を題名にする。"""
    items = []
    n = len(events)
    heads = []
    for idx, ev in enumerate(events):
        if ev[0] == "start" and ev[1] in ("h2", "h3"):
            heads.append(idx)
    for k, idx in enumerate(heads):
        ev = events[idx]
        if ev[1] != "h3":
            continue
        end = heads[k + 1] if k + 1 < len(heads) else n
        lines = collect_lines(events, idx, end)
        if not lines:
            continue
        head_text = lines[0][1]
        date = find_date(head_text)
        if not date:
            continue
        rest = lines[1:]
        # 太字の見出し行（短い行）を題名に
        bold = [t for _, t in rest if len(t) <= 90 and not t.endswith(".")]
        title = f"{head_text}：{bold[0]}" if bold else head_text
        ident = ev[2].get("id") or date
        items.append(make_item(key, ident, title, date, f"{base_url}#{ident}", rest))
    return items


def parse_mcp_blog(events, base_url, key):
    """blog.modelcontextprotocol.io：article.post-entry ごとに1項目。entry-link が記事URL、footer が日付。"""
    items = []
    n = len(events)
    i = 0
    while i < n:
        ev = events[i]
        if ev[0] == "start" and ev[1] == "article" and has_class(ev[2], "post-entry"):
            depth = ev[3]
            j = i + 1
            href = ""
            while j < n and not (events[j][0] == "end" and events[j][3] == depth):
                e = events[j]
                if e[0] == "start" and e[1] == "a" and e[2].get("href") and not href:
                    href = e[2]["href"]
                j += 1
            lines = collect_lines(events, i + 1, j)
            title, date, rest = "", "", []
            for tag, text in lines:
                if tag == "h2" and not title:
                    title = text
                    continue
                if tag == "footer" and not date:
                    date = find_date(text)
                    continue
                rest.append((tag, text))
            url = href if href.startswith("http") else (base_url.rstrip("/") + "/" + href.lstrip("/") if href else base_url)
            ident = url.rstrip("/").rsplit("/", 1)[-1] or title
            items.append(make_item(key, ident, title or ident, date, url, rest, max_chars=600))
            i = j
        i += 1
    return items


def parse_generic(events, base_url, key):
    """どの型にも当たらないときの保険：h2/h3 ごとに1項目。"""
    items = []
    n = len(events)
    heads = [idx for idx, ev in enumerate(events) if ev[0] == "start" and ev[1] in ("h2", "h3")]
    for k, idx in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else n
        lines = collect_lines(events, idx, end)
        if not lines:
            continue
        title = lines[0][1]
        if len(title) > 120 or len(lines) < 2:
            continue
        ident = events[idx][2].get("id") or hashlib.sha1(title.encode("utf-8")).hexdigest()[:10]
        date = find_date(title) or find_date(" ".join(t for _, t in lines[1:3]))
        items.append(make_item(key, ident, title, date, f"{base_url}#{ident}" if events[idx][2].get("id") else base_url, lines[1:]))
    return items


PARSERS = {
    "claude_code": parse_claude_code,
    "codex": parse_codex,
    "claude": parse_claude_notes,
    "mcp": parse_mcp_blog,
}


def extract_items(src: dict, html_text: str) -> list[dict]:
    events = to_events(html_text)
    items = PARSERS[src["key"]](events, src["url"], src["key"])
    if not items:
        items = parse_generic(events, src["url"], src["key"])
    # 同じ id が二つあれば後ろに枝番
    seen = {}
    for it in items:
        if it["id"] in seen:
            seen[it["id"]] += 1
            it["id"] = f'{it["id"]}~{seen[it["id"]]}'
        else:
            seen[it["id"]] = 0
    return items


# ---------------------------------------------------------------- 指紋と state
def fingerprint(item: dict) -> str:
    base = "|".join([item["source"], item["title"], item["date"], re.sub(r"\s+", " ", item["body"])[:400]])
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"[warn] {STATE} が読めないので、初回として扱います", file=sys.stderr)
    return {"version": 1, "sources": {}}


def save_state(state: dict) -> None:
    UPDATES.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- 言い換え案（gpt-6-astra）
REWRITE_RULES = """あなたは、経営者向けAI研修「AIブートキャンプ」の毎週ドリル（15分）の編集者です。
下の項目それぞれについて、経営者に届ける「今週の変更点」の文を日本語で作ってください。

書き方の約束（厳守）:
- 1項目 = 2〜3文、120字以内。1文目は「何が変わったか」を**太字**で言い切る。2文目は「受講者（経営者）の毎週15分のドリルで、どこがどう楽になるか／何をすればよいか」。最後に丸括弧で（製品名 バージョン、日付）。日付が無ければ省く。
- 例：**Claude Code に「差分パネル」が付きました。** 全画面モードで `/diff` と入力すると、AI が直した箇所が会話の横に並んで出ます。「直す」の3分で開くと、どこが変わったかが一目で分かります。（Claude Code 2.1.260、2026年9月3日）
- AIは「相棒」（部下ではない）。「使いこなす」と書く。「使い倒す」「疑う」「打つ」「座る」は使わない（→たたき台／聞き返す／動かす／頼む）。決めるのは人。
- 製品名は Claude Code／Codex／MCP／Claude をそのまま。ChatGPT／Gemini とは書かない（Codex のデスクトップアプリは「Codex のアプリ」と書く。モデル名 GPT-6 Astra は可）。
- 「補助金」と書かない。「自社PCで動くのでデータが社外に出ない」と書かない。
- 開発者向けの細部（SDK、API の引数、内部設定）は、経営者の仕事に関係が薄ければ「関係薄」とだけ書く。
- 事実を足さない。原文に無い効果や数字を書かない。

出力は JSON 配列だけ。各要素は {"n": 番号, "text": "言い換え文"}。コードフェンスや前置きは付けない。

項目:
"""


def rewrite_with_gpt6(items: list[dict], effort: str = "medium") -> tuple[dict[int, str], str]:
    """候補を gpt-6-astra に渡し、番号→言い換え案 を返す。失敗したら ({}, 理由)。"""
    if not os.environ.get("OPENAI_API_KEY"):
        return {}, "OPENAI_API_KEY が無いので空欄"
    if not items:
        return {}, ""
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        return {}, "openai パッケージが無いので空欄（pip install openai）"
    parts = []
    for n, it in enumerate(items, 1):
        parts.append(f"[{n}] 出典={it['source_name']} / 題名={it['title']} / 日付={it['date'] or '不明'}\n原文: {it['body'][:700]}\n")
    prompt = REWRITE_RULES + "\n".join(parts)
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    print(f"[llm] model=gpt-6-astra reasoning={effort} items={len(items)} prompt_chars={len(prompt)}", file=sys.stderr)
    text = ""
    last_err = ""
    for attempt in range(3):  # 混雑（RateLimit）は少し待って3回まで
        try:
            r = client.responses.create(model="gpt-6-astra", reasoning={"effort": effort}, input=[{"role": "user", "content": prompt}])
            text = r.output_text.strip()
            break
        except Exception as e:  # ネットワーク・認証・課金・混雑など
            msg = re.sub(r"\s+", " ", str(e))[:160]
            last_err = f"{type(e).__name__}: {msg}"
            print(f"[llm] 失敗 {attempt + 1}/3 {last_err}", file=sys.stderr)
            # 残高切れ・枠切れは待っても直らないので1回で止める。混雑（429）だけ待って再試行
            if type(e).__name__ != "RateLimitError" or attempt == 2 or re.search(r"no credits|insufficient_quota|billing", msg, re.I):
                break
            import time

            time.sleep(20 * (attempt + 1))
    if not text:
        return {}, f"gpt-6-astra の呼び出しに失敗したので空欄（{last_err}）"
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", text, flags=re.S)
        if not m:
            return {}, "gpt-6-astra の返答が JSON でなかったので空欄"
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {}, "gpt-6-astra の返答が JSON でなかったので空欄"
    out = {}
    for row in data if isinstance(data, list) else []:
        try:
            out[int(row["n"])] = str(row["text"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
    return out, ""


def lint(text: str) -> list[str]:
    return [w for w in FORBIDDEN if w in text]


# ---------------------------------------------------------------- 出力（Markdown）
def jp_date(iso: str) -> str:
    if not iso:
        return "日付不明"
    try:
        d = dt.date.fromisoformat(iso)
        return f"{d.year}年{d.month}月{d.day}日"
    except ValueError:
        return iso


def render_markdown(run_date: dt.date, results: list[dict], candidates: list[dict], rewrites: dict[int, str], llm_note: str, dry_run: bool) -> str:
    out = []
    out.append(f"# 今週の変更点の候補（{run_date.isoformat()}）\n")
    out.append("`tools/weekly_update.py` が4つの出典を取得し、前回（`updates/state.json`）以降に増えた・変わった項目だけを載せています。"
               "ここから **2件** を選び、`drills_12weeks.md` の該当週「今週の変更点」に貼り替えてください（型は末尾）。"
               "言い換え案はたたき台です。決めるのは人。\n")
    if dry_run:
        out.append("> --dry-run：state.json は更新していません。次回も同じ項目が候補に出ます。\n")
    out.append("## 取得結果\n")
    out.append("| 出典 | 状態 | 見つかった項目 | 候補（新規・更新） |")
    out.append("|---|---|---|---|")
    for r in results:
        out.append(f"| {r['name']} | {r['status']} | {r['total']} | {r['new']} |")
    out.append("")
    if llm_note:
        out.append(f"> 言い換え案：{llm_note}\n")
    if not candidates:
        # ネットワーク不通と「本当に0件」を分ける。据え置きと誤読させない
        failed = [r for r in results if r["status"].startswith(FAILED)]
        if results and len(failed) == len(results):
            out.append("## 取得できませんでした\n\n"
                       "4つの出典すべてが取得失敗です。ネットワークか出典URLを確かめて、"
                       "もう一度 `python tools/weekly_update.py --date …` を動かしてください。前回の変更点を据え置きます。\n")
        elif failed:
            names = "、".join(r["name"] for r in failed)
            out.append("## 候補はありません\n\n"
                       f"取得できた出典には新しい項目がありませんでした（取得失敗：{names}）。据え置きます。\n")
        else:
            out.append("## 候補はありません\n\n前回から新しい項目はありませんでした。該当週の「今週の変更点」は前回のまま配信し、日付だけ確かめてください。\n")
    n = 0
    for r in results:
        cs = [c for c in candidates if c["source"] == r["key"]]
        if not cs:
            continue
        out.append(f"## {r['name']}（{r['url']}）\n")
        for c in cs:
            n += 1
            flag = "更新" if c.get("changed") else "新規"
            out.append(f"### [{n}] {c['title']}　（{jp_date(c['date'])}・{flag}）\n")
            out.append(f"- 出典：{c['url']}")
            body = c["body"].replace("\n", "\n  ")
            out.append(f"- 原文（要約・原語のまま）：\n  {body}")
            rw = rewrites.get(n, "")
            bad = lint(rw) if rw else []
            if rw:
                out.append(f"- 経営者向けの言い換え案：{rw}")
                if bad:
                    out.append(f"  - ⚠ 禁止語が含まれています（{'、'.join(bad)}）。直してから貼ってください。")
            else:
                out.append("- 経営者向けの言い換え案：（空欄。人が書く）")
            out.append("")
    out.append("## 貼り替えの型（drills_12weeks.md と同じ）\n")
    out.append("```")
    out.append(f"### 今週の変更点（{jp_date(run_date.isoformat())}時点）")
    out.append("")
    out.append("- **（何が変わったか、一文で言い切る）。** （受講者の15分のどこで効くか、何をすればよいか）。（製品名 バージョン、日付）")
    out.append("  出典：https://…")
    out.append("- **（2件目）。** …")
    out.append("  出典：https://…")
    out.append("```")
    out.append("")
    out.append("貼り替えたら：冒頭の `最終更新` と `build_drills.py` の `UPDATED` を直し、`python build_drills.py` を通し、`CHANGELOG.md` に1行。手順は `運用.md`。")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="今週の変更点の候補を作る")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="候補ファイルの日付 YYYY-MM-DD（既定：今日）")
    ap.add_argument("--dry-run", action="store_true", help="state を更新せず、候補を表示するだけ")
    ap.add_argument("--no-llm", action="store_true", help="言い換え案を作らない（API を呼ばない）")
    ap.add_argument("--effort", default="medium", help="gpt-6-astra の reasoning effort（既定 medium）")
    ap.add_argument("--max-per-source", type=int, default=12, help="1出典あたりの候補の上限（既定 12。初回は新しい順にこの数まで）")
    ap.add_argument("--timeout", type=int, default=TIMEOUT, help="取得のタイムアウト秒")
    args = ap.parse_args(argv)

    try:
        run_date = dt.date.fromisoformat(args.date)
    except ValueError:
        print(f"--date は YYYY-MM-DD で指定してください: {args.date}", file=sys.stderr)
        return 2

    state = load_state()
    state.setdefault("sources", {})
    results = []
    candidates = []

    for src in SOURCES:
        key = src["key"]
        st = state["sources"].setdefault(key, {"seen": {}, "last_ok": "", "last_status": ""})
        seen: dict = st.get("seen", {})
        first_run = not seen
        rec = {"key": key, "name": src["name"], "url": src["url"], "status": "", "total": 0, "new": 0}
        try:
            html_text = fetch(src["url"], timeout=args.timeout)
            items = extract_items(src, html_text)
        except Exception as e:  # ネットワーク不可、HTTP エラーなど
            rec["status"] = f"{FAILED}（{type(e).__name__}）"
            st["last_status"] = rec["status"]
            results.append(rec)
            print(f"[{key}] {rec['status']}", file=sys.stderr)
            continue
        rec["total"] = len(items)
        if not items:
            rec["status"] = "取得できたが項目0件（ページ構造が変わった可能性）"
        else:
            rec["status"] = "取得"
        new_items = []
        for it in items:
            fp = fingerprint(it)
            prev = seen.get(it["id"])
            if prev == fp:
                continue
            it["changed"] = prev is not None
            it["fp"] = fp
            new_items.append(it)
        # 新しい順（日付があるものを優先）に並べ、上限で切る
        new_items.sort(key=lambda x: (x["date"] or "0000-00-00"), reverse=True)
        if len(new_items) > args.max_per_source:
            rec["status"] += f"（{len(new_items)}件のうち新しい{args.max_per_source}件を候補に）" if first_run else f"（{len(new_items)}件のうち{args.max_per_source}件）"
            shown = new_items[: args.max_per_source]
        else:
            shown = new_items
        for it in shown:
            it["source_name"] = src["name"]
        candidates.extend(shown)
        rec["new"] = len(shown)
        # 見た印は「候補に出したもの」だけでなく取得できた全項目に付ける（初回の山を次回に持ち越さない）
        if not args.dry_run:
            for it in items:
                seen[it["id"]] = fingerprint(it)
            if len(seen) > 800:  # 古いものから間引く（id は取得順＝おおむね新しい順）
                keep = list(seen.items())[:800]
                seen.clear()
                seen.update(keep)
            st["seen"] = seen
            st["last_ok"] = run_date.isoformat()
            st["last_status"] = rec["status"]
        results.append(rec)
        print(f"[{key}] {rec['status']} 項目{rec['total']} 候補{rec['new']}", file=sys.stderr)

    rewrites: dict[int, str] = {}
    llm_note = ""
    if args.no_llm:
        llm_note = "--no-llm のため空欄"
    elif candidates:
        rewrites, llm_note = rewrite_with_gpt6(candidates, effort=args.effort)
        if rewrites and not llm_note:
            llm_note = f"gpt-6-astra のたたき台（{len(rewrites)}/{len(candidates)}件）。事実を足していないか、出典と見比べてから使ってください。"

    md = render_markdown(run_date, results, candidates, rewrites, llm_note, args.dry_run)

    if args.dry_run:
        print(md)
        print(f"[dry-run] state.json は更新していません（{STATE}）", file=sys.stderr)
        return 0

    UPDATES.mkdir(parents=True, exist_ok=True)
    out_path = UPDATES / f"{run_date.isoformat()}.md"
    out_path.write_text(md, encoding="utf-8")
    state["last_run"] = run_date.isoformat()
    save_state(state)
    print(f"wrote {out_path}（候補 {len(candidates)} 件）")
    print(f"state {STATE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
