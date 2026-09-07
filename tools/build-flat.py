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
    vtotal = 0.0
    for i, s in enumerate(scenes):
        c = s['clip']; seg = round(s['t1'] - s['t0'], 3); inp = at.INP[c]
        p = os.path.join(CINE, f'{c}.mp4')
        if dur(p) < inp + seg - 0.02:
            sys.exit(f'{c}: 素材が足りません ({dur(p):.2f}s < {inp + seg:.2f}s)')
        focus, sat = at.FOCUS[c]
        fx, fy = [float(v.strip('%')) / 100 for v in focus.split()]
        ins += ['-ss', f'{inp}', '-t', f'{seg}', '-i', p]
        chain = (f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                 f"crop={W}:{H}:(iw-{W})*{fx:.3f}:(ih-{H})*{fy:.3f},")
        if sat:
            chain += f"eq=saturation={sat},"
        chain += f"fps={FPS},setsar=1,format=yuv420p[v{i}]"
        filt.append(chain); labels.append(f'[v{i}]')
        vtotal += seg
    atotal = dur(audio)
    pad = max(0.0, atotal - vtotal)
    filt.append(''.join(labels) + f"concat=n={len(labels)}:v=1:a=0,"
                f"tpad=stop_mode=clone:stop_duration={pad:.3f}[v]")
    ins += ['-i', audio]
    cmd = (['ffmpeg', '-y', '-v', 'error'] + ins +
           ['-filter_complex', ';'.join(filt), '-map', '[v]', '-map', f'{len(scenes)}:a',
            '-c:v', 'libx264', '-crf', '23', '-preset', 'medium',
            '-profile:v', 'high', '-level', '4.1', '-x264-params', 'ref=4:bframes=2',
            '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', '-shortest', OUT])
    print(f'{len(scenes)} シーン / 映像 {vtotal:.2f}s + 末尾保持 {pad:.2f}s / 音声 {atotal:.2f}s')
    subprocess.check_call(cmd)
    lvl = subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                   '-show_entries', 'stream=level', '-of', 'csv=p=0', OUT]).decode().strip()
    print(f'→ {OUT}  {os.path.getsize(OUT)/1048576:.1f} MB  {dur(OUT):.2f}s  level {int(lvl)/10}')


if __name__ == '__main__':
    main()
