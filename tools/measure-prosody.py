# -*- coding: utf-8 -*-
"""
ナレーション候補の「抑揚」を客観指標で比べる。

  python tools/measure-prosody.py <wavが入ったディレクトリ>

指標（いずれも大きいほど抑揚が大きい）:
  LRA   ラウドネスレンジ。静かな所と大きい所の差。EBU R128 の loudnorm から取得
  Mレンジ 瞬時ラウドネス(M)の最大-最小。「低く入って最後に張る」がここに出る
  M標準偏差 声の大きさの揺れ幅
  F0変動  基本周波数の変動係数。声の高さがどれだけ動いているか（＝狭義の抑揚）
  F0レンジ 有声区間の F0 の 10-90 パーセンタイル幅（半音）

注意: これらは「起伏の大きさ」を測るだけで、日本語として自然かどうかは測れない。
      数値で候補を絞ったうえで、最終判断は必ず人が聴いて行うこと。
"""
import subprocess, sys, os, re, io, json, wave
import numpy as np
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def loudness(path):
    """loudnorm から LRA、ebur128 から瞬時ラウドネスの推移を取る"""
    out = subprocess.run(['ffmpeg', '-v', 'info', '-i', path, '-af',
                          'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json',
                          '-f', 'null', '-'],
                         capture_output=True, text=True, errors='replace').stderr
    m = re.search(r'\{[^{}]*"input_lra"[^{}]*\}', out, re.S)
    lra = float(json.loads(m.group(0))['input_lra']) if m else float('nan')

    out2 = subprocess.run(['ffmpeg', '-v', 'info', '-i', path, '-af', 'ebur128=metadata=1',
                           '-f', 'null', '-'],
                          capture_output=True, text=True, errors='replace').stderr
    ms = [float(x) for x in re.findall(r'M:\s*(-?\d+\.\d+)', out2)]
    ms = [v for v in ms if v > -70]          # 無音区間は除く
    if not ms:
        return lra, float('nan'), float('nan')
    a = np.array(ms)
    return lra, float(a.max() - a.min()), float(a.std())


def f0_stats(path):
    """自己相関で基本周波数を推定し、その動きの大きさを返す"""
    with wave.open(path, 'rb') as w:
        sr, n = w.getframerate(), w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float64)
        if w.getnchannels() == 2:
            x = x.reshape(-1, 2).mean(axis=1)
    if x.size == 0:
        return float('nan'), float('nan')
    x /= (np.abs(x).max() or 1)

    win, hop = int(sr * 0.04), int(sr * 0.01)
    lo, hi = int(sr / 400), int(sr / 70)      # 70-400Hz を探索
    f0 = []
    for s in range(0, len(x) - win, hop):
        seg = x[s:s + win]
        if np.sqrt((seg ** 2).mean()) < 0.02:  # 無声・無音は飛ばす
            continue
        seg = seg - seg.mean()
        ac = np.correlate(seg, seg, 'full')[win - 1:]
        if ac[0] <= 0:
            continue
        ac /= ac[0]
        band = ac[lo:hi]
        if band.size == 0:
            continue
        k = int(band.argmax()) + lo
        if ac[k] > 0.3:                        # 周期性が弱い所は有声とみなさない
            f0.append(sr / k)
    if len(f0) < 20:
        return float('nan'), float('nan')
    a = np.array(f0)
    cv = float(a.std() / a.mean())             # 変動係数
    semi = float(12 * np.log2(np.percentile(a, 90) / np.percentile(a, 10)))
    return cv, semi


def main(d):
    rows = []
    for f in sorted(os.listdir(d)):
        if not f.endswith('.wav'):
            continue
        p = os.path.join(d, f)
        dur = float(subprocess.check_output(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', p]).decode().strip())
        lra, mrange, mstd = loudness(p)
        cv, semi = f0_stats(p)
        # 総合点: ラウドネスの起伏と声の高さの動きを同じ重みで
        score = (np.nan_to_num(lra) / 12 + np.nan_to_num(mrange) / 30
                 + np.nan_to_num(cv) * 4 + np.nan_to_num(semi) / 12)
        rows.append((score, f[:-4], dur, lra, mrange, mstd, cv, semi))

    rows.sort(reverse=True)
    print(f"{'候補':<18}{'秒':>6}{'LRA':>7}{'Mレンジ':>9}{'M標準偏差':>10}{'F0変動':>8}{'F0レンジ':>9}{'総合':>7}")
    print('-' * 76)
    for sc, n, dur, lra, mr, ms, cv, semi in rows:
        print(f"{n:<18}{dur:6.2f}{lra:7.1f}{mr:9.1f}{ms:10.1f}{cv:8.3f}{semi:9.1f}{sc:7.2f}")
    print('-' * 76)
    print('※ 数値は起伏の大きさのみ。日本語としての自然さは測れないので、上位を必ず聴いて決めること。')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
