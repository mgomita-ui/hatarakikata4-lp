# -*- coding: utf-8 -*-
"""「時間がもったいない」篇を1本のmp4に焼く。

  python tools/build-koby.py

台本の正本は tools/koby.json の一箇所だけ。ここを直せば映像も字幕も追従する。

設計:
  - 字幕は焼き込む。配布して見てもらう前提なので、HTMLオーバーレイにしない
  - silence 区間は音楽を落とす（若手が言い切ったあとの沈黙）
  - 素材が必要尺に足りない場合はスローで伸ばす。伸ばしすぎ（1.5倍超）は警告する
"""
import io, json, os, subprocess, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, 'media', 'cine', 'koby', 'seed')
WORK = os.path.join(ROOT, 'media', 'cine', 'koby', '_work')
OUT = os.path.join(ROOT, 'media', 'cine', 'koby-flat.mp4')
FONT = 'C\\:/Windows/Fonts/YuGothB.ttc'   # libass 用にエスケープ
W, H, FPS = 1920, 1080, 30


def dur(p):
    return float(subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'csv=p=0', p]).decode().strip())


def ass(d):
    """字幕を ASS で組む。大きさは cls で切り替える。"""
    def t(s):
        h, s = divmod(s, 3600); m, s = divmod(s, 60)
        return '%d:%02d:%05.2f' % (h, m, s)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: base,Yu Gothic,58,&H00FFFFFF,&HC0000000,&H00000000,1,0,0,0,100,100,1,0,1,3,2,2,120,120,88,1
Style: big,Yu Gothic,86,&H00FFFFFF,&HC0000000,&H00000000,1,0,0,0,100,100,2,0,1,4,3,2,120,120,110,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    ls = sorted(d['lines'], key=lambda x: x['cue'])
    rows = []
    for i, l in enumerate(ls):
        end = ls[i + 1]['cue'] - 0.12 if i + 1 < len(ls) else d['total'] - 0.3
        end = min(end, l['cue'] + 6.0)
        style = l.get('cls', 'base')
        style = 'big' if style == 'big' else 'base'
        rows.append('Dialogue: 0,%s,%s,%s,,0,0,0,,%s' % (t(l['cue']), t(end), style, l['text']))
    return head + '\n'.join(rows) + '\n'


def main():
    d = json.load(io.open(os.path.join(ROOT, 'tools', 'koby.json'), encoding='utf-8'))
    os.makedirs(WORK, exist_ok=True)

    # 1. 各カットを必要尺に切り出す
    parts = []
    for s in d['scenes']:
        need = round(s['t1'] - s['t0'], 3)
        src = os.path.join(SEED, s['clip'] + '.mp4')
        have = dur(src) - s['in']
        out = os.path.join(WORK, s['clip'] + '_cut.mp4')
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}"
        if have < need - 0.02:
            rate = need / have
            if rate > 1.5:
                print('  !! %s 素材 %.2fs < 必要 %.2fs (%.2fx) 伸ばしすぎ' % (s['clip'], have, need, rate))
            else:
                print('  %s 素材 %.2fs < 必要 %.2fs → %.2fx スロー' % (s['clip'], have, need, rate))
            vf = f"setpts={rate:.4f}*PTS," + vf
            t_arg = ['-t', str(need)]
        else:
            t_arg = ['-t', str(need)]
        subprocess.check_call(['ffmpeg', '-y', '-v', 'error', '-ss', str(s['in']), '-i', src,
                               *t_arg, '-vf', vf, '-an', '-c:v', 'libx264', '-crf', '16',
                               '-preset', 'fast', out])
        parts.append(out)

    # 2. つなぐ
    lst = os.path.join(WORK, 'list.txt')
    io.open(lst, 'w', encoding='utf-8').write(
        '\n'.join("file '%s'" % p.replace('\\', '/') for p in parts))
    joined = os.path.join(WORK, 'joined.mp4')
    subprocess.check_call(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0',
                           '-i', lst, '-c', 'copy', joined])

    # 3. 音楽。沈黙区間だけ音量を落とす
    total = d['total']
    mus = os.path.join(ROOT, d['music'].replace('/', os.sep))
    vol = []
    for a, b in d.get('silence', []):
        vol.append(f"volume=enable='between(t,{a},{b})':volume=0")
    af = (f"atrim={d['music_from']}:{d['music_from'] + total},asetpts=N/SR/TB,"
          f"afade=t=in:st=0:d=1.5,afade=t=out:st={total - 2.5:.2f}:d=2.2,volume=0.62")
    if vol:
        af += ',' + ','.join(vol)
    audio = os.path.join(WORK, 'audio.m4a')
    subprocess.check_call(['ffmpeg', '-y', '-v', 'error', '-i', mus, '-af', af,
                           '-c:a', 'aac', '-b:a', '192k', audio])

    # 4. 字幕を焼いて合成
    sub = os.path.join(WORK, 'sub.ass')
    io.open(sub, 'w', encoding='utf-8').write(ass(d))
    subprocess.check_call([
        'ffmpeg', '-y', '-v', 'error', '-i', joined, '-i', audio,
        '-vf', "subtitles='%s':fontsdir='C\\:/Windows/Fonts'" % sub.replace('\\', '/').replace(':', '\\:'),
        '-map', '0:v', '-map', '1:a', '-shortest',
        '-c:v', 'libx264', '-crf', '20', '-preset', 'slow', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', OUT])

    print('%d カット / %.2f秒' % (len(d['scenes']), total))
    print('→ %s  %.1f MB  %.2fs' % (OUT, os.path.getsize(OUT) / 1048576, dur(OUT)))


if __name__ == '__main__':
    main()
