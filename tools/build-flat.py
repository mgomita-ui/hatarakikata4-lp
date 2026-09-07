# -*- coding: utf-8 -*-
"""
オープニング全体を 1 本の MP4（映像＋音声）に焼き込む。

  python tools/build-flat.py            # media/cine/opening-flat.mp4 を作る

いつ使うか:
  2 つの <video> を切り替える方式は、端末側の都合（デコーダ互換・読み込み遅延・
  要素の使い回し）で映像だけ止まる余地が残る。1 本の動画なら再生は端末の標準機能に
  任せられ、時計も video.currentTime ひとつで済む。切り替え方式で解決しきれない
  ときの退避先として用意しておく。

やること:
  - narration.json のシーン順に、各クリップを inp からシーン尺だけ切り出す
  - 1920x1080 に object-fit:cover 相当で収め、HTML と同じ focus 位置で切り取る
  - 彩度指定(sat)があるクリップは同じだけ落とす
  - ハードカットで連結し、末尾は最終フレームを保持して音声の余韻ぶん伸ばす
  - opening.m4a を音声として合流、level 4.1 / 参照4枚（携帯互換）で書き出す
"""
import json, subprocess, sys, os, importlib.util
# stdout はここでは包み直さない。下で読み込む apply-timeline.py が同じ buffer を
# 包み直すため、二重にすると先の wrapper が回収されて buffer が閉じ、print で落ちる。

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CINE = os.path.join(ROOT, 'media', 'cine')
W, H, FPS = 1920, 1080, 24
OUT = os.path.join(CINE, 'opening-flat.mp4')
# クリップ名 -> 次のカットへ何秒かけて溶けるか。前カットをその分長く切り出して重ねるので全体尺は変わらない。
XFADE = {'cutin': 0.8}   # 顔のカットイン -> 夜明けの街

# apply-timeline.py の INP / FOCUS を流用（ファイル名にハイフンがあるので spec で読む）
spec = importlib.util.spec_from_file_location('at', os.path.join(ROOT, 'tools', 'apply-timeline.py'))
at = importlib.util.module_from_spec(spec); spec.loader.exec_module(at)


def dur(p):
    return float(subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p]).decode())


def main():
    d = json.load(open(os.path.join(ROOT, 'tools', 'narration.json'), encoding='utf-8'))
    audio = os.path.join(CINE, 'opening.m4a')
    scenes = [s for s in d['scenes'] if s['clip']]
    ins, filt, labels = [], [], []
    vtotal = 0.0; segs = []
    for i, s in enumerate(scenes):
        c = s['clip']; seg = round(s['t1'] - s['t0'], 3); inp = at.INP[c]
        fade = XFADE.get(c, 0.0) if i + 1 < len(scenes) else 0.0
        take = seg + fade
        p = os.path.join(CINE, f'{c}.mp4')
        avail = max(0.0, dur(p) - inp)
        # 素材がシーン尺に足りないときは、最大 1.5 倍までスローにして伸ばし、残りは最終フレームを保持する。
        # 台詞を長くしたときに素材を作り直さずに済む（空撮や引きの画はスローが自然）。
        stretch = 1.0
        if avail < take - 0.02:
            stretch = min(1.5, take / avail) if avail > 0 else 1.0
            print(f'  {c}: 素材 {avail:.2f}s < 必要 {take:.2f}s → {stretch:.2f}x スロー'
                  + ('' if avail * stretch >= take - 0.02 else f' + 末尾 {take - avail*stretch:.2f}s 保持'))
        segs.append((take, fade, stretch, avail))
        focus, sat = at.FOCUS[c]
        fx, fy = [float(v.strip('%')) / 100 for v in focus.split()]
        src_t = take if stretch == 1.0 else min(avail, take / stretch)
        ins += ['-ss', f'{inp}', '-t', f'{src_t:.3f}', '-i', p]
        chain = (f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                 f"crop={W}:{H}:(iw-{W})*{fx:.3f}:(ih-{H})*{fy:.3f},")
        if sat:
            chain += f"eq=saturation={sat},"
        if stretch != 1.0:
            chain += f"setpts={stretch:.4f}*PTS,"
        chain += f"fps={FPS},setsar=1,format=yuv420p,"
        # 伸ばしても届かない端数は最終フレームを保持して尺を揃える
        chain += f"tpad=stop_mode=clone:stop_duration={max(0.0, take - src_t*stretch):.3f},trim=duration={take:.3f}[v{i}]"
        filt.append(chain); labels.append(f'[v{i}]')
        vtotal += seg
    atotal = dur(audio)
    pad = max(0.0, atotal - vtotal)
    # 左から畳み込む: フェード指定の境界は xfade、それ以外は concat
    cur, curdur, k = labels[0], segs[0][0], 0
    for i in range(1, len(labels)):
        take = segs[i][0]; fade = segs[i - 1][1]
        if fade > 0:
            filt.append(f"{cur}settb=AVTB,fps={FPS}[a{k}];{labels[i]}settb=AVTB,fps={FPS}[b{k}];"
                        f"[a{k}][b{k}]xfade=transition=fade:duration={fade:.3f}:offset={curdur - fade:.3f},format=yuv420p[x{k}]")
            curdur = curdur - fade + take
        else:
            filt.append(f"{cur}{labels[i]}concat=n=2:v=1:a=0[x{k}]")
            curdur += take
        cur = f'[x{k}]'; k += 1
    filt.append(f"{cur}tpad=stop_mode=clone:stop_duration={pad:.3f}[v]")
    ins += ['-i', audio]
    cmd = (['ffmpeg', '-y', '-v', 'error'] + ins +
           ['-filter_complex', ';'.join(filt), '-map', '[v]', '-map', f'{len(scenes)}:a',
            '-c:v', 'libx264', '-crf', os.environ.get('CRF', '23'), '-preset', 'medium',
            '-profile:v', 'high', '-level', '4.1', '-x264-params', 'ref=4:bframes=2',
            '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', '-shortest', OUT])
    print(f'{len(scenes)} シーン / 映像 {vtotal:.2f}s + 末尾保持 {pad:.2f}s / 音声 {atotal:.2f}s')
    r = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
    if r.returncode:
        print(r.stderr[-2000:]); sys.exit('ffmpeg 失敗')
    lvl = subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                   '-show_entries', 'stream=level', '-of', 'csv=p=0', OUT]).decode().strip()
    print(f'→ {OUT}  {os.path.getsize(OUT)/1048576:.1f} MB  {dur(OUT):.2f}s  level {int(lvl)/10}')


if __name__ == '__main__':
    main()
