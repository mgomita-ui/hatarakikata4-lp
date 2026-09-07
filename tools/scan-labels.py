# -*- coding: utf-8 -*-
"""
index.html の中で「秒数」を名乗っている表示文言を洗い出す。

  python tools/scan-labels.py

なぜ要るか: 文言が '\\u30aa\\u30fc...' のようなエスケープで書かれている箇所があり、
そのままの grep では見つからない。実際「55秒の映像で見る」がこれで生き残り、
オープニングを 77 秒に作り替えたあとも古い秒数を表示し続けていた。
"""
import re, sys, io, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ESC = re.compile(r'\\u([0-9a-fA-F]{4})')
SEC = re.compile(r'.{0,26}\d+\s*(?:秒|SEC|sec).{0,26}')


def unescape(s):
    return ESC.sub(lambda m: chr(int(m.group(1), 16)), s)


def main():
    total = None
    src = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    m = re.search(r'var TOTAL=([\d.]+)', src)
    if m:
        total = float(m.group(1))

    print('実際の尺: TOTAL=%s 秒' % (total if total else '?'))
    print('-' * 60)
    hits = 0
    for i, line in enumerate(src.split('\n'), 1):
        if 'base64' in line:
            continue
        plain = unescape(line)
        if not re.search(r'\d+\s*(?:秒|SEC|sec)', plain):
            continue
        for f in SEC.finditer(plain):
            frag = f.group(0).strip()
            n = re.search(r'(\d+)\s*(?:秒|SEC|sec)', frag)
            stale = total and n and abs(int(n.group(1)) - round(total)) > 1
            esc = '（エスケープ表記）' if ESC.search(line) else ''
            print('%s %5d: %s %s' % ('★' if stale else ' ', i, frag[:70], esc))
            hits += 1
    print('-' * 60)
    print('%d 箇所。★ は TOTAL と食い違うもの。' % hits)


if __name__ == '__main__':
    main()
