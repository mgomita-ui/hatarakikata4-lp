# -*- coding: utf-8 -*-
"""
表示している秒数を TOTAL から自動で埋める。

  python tools/fix-labels.py --write

尺を変えるたびに文言を手で直すと、必ずどこかが取り残される。実際
「55秒の映像で見る」が \\uXXXX のエスケープ表記で生き残り、77秒に
作り替えたあとも古い秒数を出し続けていた（grep で見つからなかった）。
以後は再生時に JS が TOTAL から差し込むので、ずれようがない。
"""
import re, sys, io, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'index.html')

ESC = re.compile(r'\\u([0-9a-fA-F]{4})')


def main(write=False):
    src = open(P, encoding='utf-8').read()
    total = float(re.search(r'var TOTAL=([\d.]+)', src).group(1))
    secs = int(round(total))
    out = src
    done = []

    # 1) リプレイボタンの初期ラベル（エスケープ表記で残っていた箇所）
    old = "if(!seen) rep.innerHTML='\\u25b6 55\\u79d2\\u306e\\u6620\\u50cf\\u3067\\u898b\\u308b';"
    if old in out:
        new = ("if(!seen) rep.innerHTML='\\u25b6 '+Math.round(TOTAL)+"
               "'\\u79d2\\u306e\\u6620\\u50cf\\u3067\\u898b\\u308b';")
        out = out.replace(old, new, 1)
        done.append('リプレイボタンのラベルを TOTAL 連動に')


    # 3) 静的な文言も TOTAL に合わせる
    for pat, rep in (
        (r'(OPENING MOVIE ｜ )\d+( SEC)', r'\g<1>%d\g<2>' % secs),
        (r'\d+(秒の映像で、ご覧いただけます。)', r'%d\g<1>' % secs),
    ):
        new = re.sub(pat, rep, out)
        if new != out:
            out = new
            done.append('静的な秒数表記を %d 秒に' % secs)

    print('TOTAL=%s → 表示 %d 秒' % (total, secs))
    for d in done:
        print('  -', d)
    if not done:
        print('  変更なし')
    if write and done:
        open(P, 'w', encoding='utf-8').write(out)
        print('index.html を書き換えました。')
    elif not write:
        print('(--write で反映)')


if __name__ == '__main__':
    main('--write' in sys.argv)
