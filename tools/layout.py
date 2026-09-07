# -*- coding: utf-8 -*-
"""
narration.json のシーン構成と台詞から、素材尺の上限を守りつつ
ナレーションが自然に収まるタイムラインを算出する。

  python tools/layout.py            # 算出してレポート
  python tools/layout.py --write    # narration.json の cue / scenes を更新

考え方:
  - 各行に必要な発話秒数を推定し、許容する時間圧縮(MAX_TEMPO)で割った値を「最低スロット」とする
  - シーンの必要尺 = 配下の行の最低スロット合計 + 余韻(TAIL)
  - クリップのあるシーンは素材尺(cap)で頭打ち。足りない分は圧縮を強めて吸収する
  - クリップの無いシーンは自由に伸ばせるので、ここで全体の帳尻を合わせる
"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

RATE = 5.6        # 拍/秒（Satoshi の実測値から校正）
PAUSE = 0.25      # 句点ごとの間
MAX_TEMPO = float(__import__("os").environ.get("MAX_TEMPO", "1.15"))  # 自然に聞こえる時間圧縮の上限
TAIL = 0.35       # シーン末尾の余韻
MIN_CLIP = 3.0    # クリップのあるシーンの最短尺（詰まりすぎて絵が飛ぶのを防ぐ）

def mora(t):
    n = 0
    for ch in t:
        o = ord(ch)
        if ch in 'ゃゅょャュョぁぃぅぇぉァィゥェォ':
            continue
        if 0x3040 <= o <= 0x30ff:   n += 1      # かな
        elif 0x4e00 <= o <= 0x9fff: n += 2      # 漢字 ≒ 2拍
        elif ch.isalnum():          n += 1
    return n

def estimate(say):
    return mora(say)/RATE + PAUSE*max(0, say.count('。') + say.count('？') - 1)

# tools/vo-durations.tsv があれば推定ではなく実測尺を使う（prep-vo.sh が書き出す）
MEASURED = {}
try:
    for row in open('tools/vo-durations.tsv', encoding='utf-8'):
        i, sec = row.split('\t')
        MEASURED[int(i)] = float(sec)
except FileNotFoundError:
    pass

def speech(l):
    m = MEASURED.get(l.get('_i'))
    return m if m else estimate(l['say'])

def main(write=False):
    d = json.load(open('tools/narration.json', encoding='utf-8'))
    SC, L = d['scenes'], d['lines']
    for i, l in enumerate(L): l['_i'] = i
    if MEASURED and len(MEASURED) != len(L):
        print(f"!! 実測 {len(MEASURED)} 本 / 台本 {len(L)} 行 — 数が合いません。prep-vo.sh を流し直してください。")
        return
    print('尺の根拠:', '実測 (vo-durations.tsv)' if MEASURED else '推定 (mora ベース)')

    # 行を、現在の cue が入っているシーンへ割り当てる
    for s in SC:
        s['lines'] = [l for l in L if s['t0'] <= l['cue'] < s['t1']]
    orphan = [l for l in L if not any(l in s['lines'] for s in SC)]
    if orphan:
        print('!! どのシーンにも属さない行:', [o['say'][:12] for o in orphan]); return

    # 各シーンの必要尺を求め、cap で頭打ちにする
    for s in SC:
        need = sum(speech(l)/MAX_TEMPO for l in s['lines']) + (TAIL if s['lines'] else 0)
        # min: 台詞が短くても映像として必要な尺（畳みかけ・カットインなど）
        s['need'] = max(need, s.get('min', 0), MIN_CLIP if s['cap'] else 1.0)
        s['dur']  = min(s['need'], s['cap']) if s['cap'] else s['need']

    # 先頭から詰め直す
    t = 0.0
    for s in SC:
        s['t0'] = round(t, 2); t += s['dur']; s['t1'] = round(t, 2)
        # シーン内で行を、必要秒数の比で配分する
        tot = sum(speech(l)/MAX_TEMPO for l in s['lines']) or 1
        avail = s['dur'] - TAIL
        c = s['t0']
        for l in s['lines']:
            l['cue'] = round(c, 2)
            c += avail * (speech(l)/MAX_TEMPO) / tot
    total = round(t, 1)

    print(f"{'シーン':<10}{'尺':>7}{'上限':>7}{'必要':>7}  判定")
    print('-'*46)
    for s in SC:
        cap = f"{s['cap']:.2f}" if s['cap'] else '  --'
        flag = '★圧縮強' if s['cap'] and s['need'] > s['cap'] + 0.01 else 'OK'
        print(f"{(s['clip'] or s.get('note','—')):<10}{s['dur']:7.2f}{cap:>7}{s['need']:7.2f}  {flag}")
    print('-'*46)
    print(f"合計 {total} 秒 (現行 55 秒)\n")

    print(f"{'cue':>6}{'slot':>7}{'発話':>7}{'倍率':>7}  text")
    print('-'*72)
    worst = 0
    for s in SC:
        for i, l in enumerate(s['lines']):
            nxt = s['lines'][i+1]['cue'] if i+1 < len(s['lines']) else s['t1']
            slot = nxt - l['cue']; sp = speech(l); tempo = sp/slot if slot else 9
            worst = max(worst, tempo)
            mark = '' if tempo <= MAX_TEMPO + 0.01 else '  ★'
            print(f"{l['cue']:6.2f}{slot:7.2f}{sp:7.2f}{tempo:7.2f}{mark}  {l['say'][:22]}")
    print('-'*72)
    print(f"最大圧縮 {worst:.2f}x (許容 {MAX_TEMPO}x)")

    if write:
        d['total'] = total
        for s in SC: s.pop('lines', None); s.pop('need', None); s.pop('dur', None)
        for l in L: l.pop('_i', None)
        json.dump(d, open('tools/narration.json','w',encoding='utf-8'),
                  ensure_ascii=False, indent=2)
        print('\ntools/narration.json を更新しました。')

if __name__ == '__main__':
    main('--write' in sys.argv)
