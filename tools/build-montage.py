# -*- coding: utf-8 -*-
"""
終盤の2カットを素材から合成する。

  python tools/build-montage.py mont     # 働き方モンタージュ -> media/cine/montage.mp4
  python tools/build-montage.py cutin    # 顔の分割カットイン -> media/cine/cutin.mp4
  python tools/build-montage.py all

montage: 時間と場所にとらわれない働き方を約1秒ずつ畳みかける
cutin  : 顔を分割コマで1枚ずつ増やしていく。漫画のコマ割りを模した構成のみで、
         絵は全て自前の生成素材（既存作品の画像は一切使わない）
"""
import subprocess, sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CINE = os.path.join(ROOT, 'media', 'cine')
W, H, FPS = 1920, 1080, 24

MONT = ['m_home', 'm_cafe', 'm_country', 'm_night', 'm_park', 'm_cowork']
FACES = ['f1', 'f2', 'f3', 'f4', 'f5', 'f6']

# カットインのコマ配置 (x, y, w, h, 出現秒). 斜めに散らして順に増やす
PANELS = [
    (0.00, 0.00, 0.52, 0.56, 0.00),
    (0.54, 0.10, 0.46, 0.52, 0.22),
    (0.06, 0.60, 0.44, 0.40, 0.44),
    (0.52, 0.64, 0.48, 0.36, 0.66),
    (0.28, 0.24, 0.40, 0.50, 0.88),
    (0.00, 0.30, 0.30, 0.44, 1.10),
]
GAP = 4  # コマの隙間(px)。黒い枠線として残る


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
    if r.returncode:
        print(r.stderr[-1500:]); sys.exit('ffmpeg 失敗')


def scene_len(clip):
    import json
    d = json.load(open(os.path.join(ROOT, 'tools', 'narration.json'), encoding='utf-8'))
    for s in d['scenes']:
        if s['clip'] == clip:
            return round(s['t1'] - s['t0'], 2)
    sys.exit('シーンが見つかりません: ' + clip)


def build_montage(out, total=None):
    """シーン尺ちょうどに収める。後ろのカットほど少し長くして加速感を出す"""
    total = total or scene_len('montage') + 0.30   # 末尾に余裕
    weights = [0.80, 0.85, 0.90, 1.00, 1.10, 1.25]  # 合計で total になるよう正規化
    durs = [total * w / sum(weights) for w in weights]
    src = [os.path.join(CINE, 'mont', f'{n}.mp4') for n in MONT]
    missing = [p for p in src if not os.path.exists(p)]
    if missing:
        sys.exit('素材が足りません: ' + ', '.join(os.path.basename(m) for m in missing))
    ins, filt, labs = [], [], []
    for i, p in enumerate(src):
        e = durs[i]
        ins += ['-ss', '1.6', '-t', f'{e:.3f}', '-i', p]
        # ディゾルブではなくハードカット。切り替わりだけ 1 フレーム分の明滅で繋ぐ
        filt.append(
            f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"fps={FPS},setsar=1,fade=t=in:st=0:d=0.05[m{i}]")
        labs.append(f'[m{i}]')
    filt.append(''.join(labs) + f'concat=n={len(src)}:v=1:a=0[v]')
    run(['ffmpeg', '-y', '-v', 'error'] + ins +
        ['-filter_complex', ';'.join(filt), '-map', '[v]',
         '-c:v', 'libx264', '-crf', '20', '-preset', 'medium',
         # 携帯のハードウェアデコーダ向け: 1080p は level 4.1 / 参照4枚を超えない
         '-profile:v', 'high', '-level', '4.1', '-x264-params', 'ref=4:bframes=2',
         '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out])
    print('montage: %s  %s' % (out, ' / '.join(f'{d:.2f}s' for d in durs)))


def mean_luma(path, at=1.2):
    """素材の平均輝度(0-255)。コマ間の露出差を機械的に揃えるために使う"""
    r = subprocess.run(['ffmpeg', '-v', 'info', '-ss', str(at), '-t', '0.5', '-i', path,
                        '-vf', 'signalstats,metadata=print:key=lavfi.signalstats.YAVG',
                        '-f', 'null', '-'], capture_output=True, text=True, errors='replace').stderr
    import re as _re
    v = [float(x) for x in _re.findall(r'YAVG=([\d.]+)', r)]
    return sum(v) / len(v) if v else 128.0


def build_cutin(out, total=None):
    total = total or scene_len('cutin') + 1.30   # 次カットへのクロスフェード(0.8s)ぶんも含める
    """黒地の上にコマを順に重ねる。各コマは出現時に一瞬だけ拡大して落ち着く"""
    src = [os.path.join(CINE, 'faces', f'{n}.mp4') for n in FACES]
    missing = [p for p in src if not os.path.exists(p)]
    if missing:
        sys.exit('素材が足りません: ' + ', '.join(os.path.basename(m) for m in missing))
    lum = [mean_luma(p) for p in src]
    target = sorted(lum)[len(lum) // 2]          # 中央値に合わせる
    print('  露出補正: ' + ' '.join(f'{l:.0f}->{target:.0f}' for l in lum))
    ins = ['-f', 'lavfi', '-t', f'{total}', '-i', f'color=c=black:s={W}x{H}:r={FPS}']
    filt, cur = [], '[0:v]'
    for i, (px, py, pw, ph, at) in enumerate(PANELS):
        ins += ['-ss', '1.2', '-t', f'{total}', '-i', src[i]]
        w, h = int(W * pw) - GAP, int(H * ph) - GAP
        w -= w % 2; h -= h % 2
        filt.append(
            f"[{i+1}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"fps={FPS},setsar=1,"
            # コマ間の露出を揃える。eq の時間可変式は使えないので静的補正のみ。
            # 出現の衝撃はハードカットと打撃音で作る。
            f"eq=brightness={(target-lum[i])/255*0.9:.3f}:eval=init,"
            f"format=rgba[p{i}]")
        nxt = f'[s{i}]'
        filt.append(
            f"{cur}[p{i}]overlay=x={int(W*px)+GAP//2}:y={int(H*py)+GAP//2}:"
            f"enable='gte(t,{at})'{nxt}")
        cur = nxt
    filt[-1] = filt[-1].replace(cur, '[v]')
    run(['ffmpeg', '-y', '-v', 'error'] + ins +
        ['-filter_complex', ';'.join(filt), '-map', '[v]',
         '-c:v', 'libx264', '-crf', '20', '-preset', 'medium',
         # 携帯のハードウェアデコーダ向け: 1080p は level 4.1 / 参照4枚を超えない
         '-profile:v', 'high', '-level', '4.1', '-x264-params', 'ref=4:bframes=2',
         '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out])
    print(f'cutin: {out}  {len(PANELS)}コマ / {total}s')


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if what in ('mont', 'all'):
        build_montage(os.path.join(CINE, 'montage.mp4'))
    if what in ('cutin', 'all'):
        build_cutin(os.path.join(CINE, 'cutin.mp4'))
