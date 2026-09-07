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
# f1: 主役(買い物)を大ゴマに。f2-f6: 主役+追加キャストを中小ゴマへ。f7/f8: 個性の立つ若手2人を新規追加
FACES = ['f1', 'f2', 'f3', 'f6', 'f4', 'f5', 'f7', 'f8']

# カットインのコマ配置 (x, y, w, h, 出現秒). 均等グリッドを避け、大ゴマ1枚+中ゴマ1枚+小ゴマを混在させて
# 漫画のコマ割りらしい強弱を出す
PANELS = [
    (0.00, 0.00, 0.50, 0.66, 0.00),   # 大ゴマ（主役）
    (0.52, 0.00, 0.23, 0.32, 0.15),   # 小
    (0.77, 0.00, 0.23, 0.32, 0.28),   # 小
    (0.52, 0.34, 0.48, 0.30, 0.42),   # 中（横長）
    (0.00, 0.68, 0.24, 0.32, 0.55),   # 小
    (0.26, 0.68, 0.24, 0.32, 0.66),   # 小
    (0.52, 0.68, 0.23, 0.32, 0.78),   # 小
    (0.77, 0.68, 0.23, 0.32, 0.90),   # 小
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


# AI/ロボットの進化を並べる背景グリッド。全コマ同時に動かし、正面のまま並べる
GRID_COLS, GRID_ROWS = 4, 4
GRID1 = ['g01', 'g02', 'g03', 'g04', 'g05', 'g06', 'g07', 'g08',
         'g09', 'g10', 'g11', 'g12', 'g13', 'g14', 'g15', 'g16']
GRID2 = ['g17', 'g02', 'g19', 'g04', 'g21', 'g06', 'g23', 'g08',
         'g18', 'g10', 'g20', 'g12', 'g22', 'g14', 'g24', 'g16']


# コマの色系統。cool=素材のまま(シアン系) / warm=アンバー / magenta,green=色相を回す(顔なしのコマのみ)
GRADE = {
    'g01': 'warm', 'g02': 'cool', 'g03': 'warm', 'g04': 'cool',
    'g05': 'warm', 'g06': 'magenta', 'g07': 'warm', 'g08': 'cool',
    'g09': 'magenta', 'g10': 'green', 'g11': 'warm', 'g12': 'cool',
    'g13': 'warm', 'g14': 'green', 'g15': 'magenta', 'g16': 'green',
    'g17': 'cool', 'g18': 'warm', 'g19': 'cool', 'g20': 'cool',
    'g21': 'green', 'g22': 'warm', 'g23': 'magenta', 'g24': 'cool',
}
GRADE_FILTER = {
    'cool': '',
    'warm': 'colortemperature=temperature=3300:mix=0.85,eq=saturation=1.15,',
    'magenta': 'hue=h=-45:s=1.0,',
    'green': 'hue=h=45:s=1.05,',
}


def build_grid(names, out, scene_clip, tail=1.30):
    total = scene_len(scene_clip) + tail
    src = [os.path.join(CINE, 'grid', f'{n}.mp4') for n in names]
    missing = [p for p in src if not os.path.exists(p)]
    if missing:
        sys.exit('素材が足りません: ' + ', '.join(os.path.basename(m) for m in missing))
    lum = [mean_luma(p) for p in src]
    target = sorted(lum)[len(lum) // 2]
    cw, ch = W // GRID_COLS, H // GRID_ROWS
    w, h = cw - GAP, ch - GAP
    w -= w % 2; h -= h % 2
    ins = ['-f', 'lavfi', '-t', f'{total}', '-i', f'color=c=black:s={W}x{H}:r={FPS}']
    filt, cur = [], '[0:v]'
    for i, p in enumerate(src):
        # 素材は5秒しかないのでループさせ、シーン尺ぶん等速で動かし続ける（スロー化を避ける）
        ins += ['-stream_loop', '-1', '-ss', '0.4', '-t', f'{total}', '-i', p]
        # 生成素材がシアン一色に寄るので、コマごとに色系統を振ってテレビ壁らしく散らす。
        # 顔が写るコマは色相を回すと肌が崩れるので warm/cool のみ
        tone = GRADE_FILTER[GRADE.get(names[i], 'cool')]
        filt.append(
            f"[{i+1}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"fps={FPS},setsar=1,{tone}eq=brightness={(target-lum[i])/255*0.9:.3f}:eval=init,"
            f"format=yuv420p[p{i}]")
        x = (i % GRID_COLS) * cw + GAP // 2
        y = (i // GRID_COLS) * ch + GAP // 2
        nxt = f'[s{i}]'
        filt.append(f"{cur}[p{i}]overlay=x={x}:y={y}{'' if i < len(src) - 1 else ':shortest=1'}{nxt}")
        cur = nxt
    filt[-1] = filt[-1].replace(cur, '[v]')
    run(['ffmpeg', '-y', '-v', 'error'] + ins +
        ['-filter_complex', ';'.join(filt), '-map', '[v]',
         '-c:v', 'libx264', '-crf', '20', '-preset', 'medium',
         '-profile:v', 'high', '-level', '4.1', '-x264-params', 'ref=4:bframes=2',
         '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out])
    print(f'grid: {out}  {len(src)}コマ / {total}s')


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if what in ('mont', 'all'):
        build_montage(os.path.join(CINE, 'montage.mp4'))
    if what in ('cutin', 'all'):
        build_cutin(os.path.join(CINE, 'cutin.mp4'))
    if what in ('grid1', 'all'):
        build_grid(GRID1, os.path.join(CINE, 'grid1.mp4'), 'grid1')
    if what in ('grid2', 'all'):
        build_grid(GRID2, os.path.join(CINE, 'grid2.mp4'), 'grid2')
