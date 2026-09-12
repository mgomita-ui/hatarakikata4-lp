# -*- coding: utf-8 -*-
"""「時間がもったいない」v2 を1本のmp4に焼く。

  python tools/build-koby2.py

台本の正本は tools/koby2.json の一箇所だけ。ここを直せば映像も字幕も追従する。

build-koby.py との違い:
  - 素材は media/cine/koby/v2clip（24カット、1080p）
  - scene に "still" を書くと静止画をゆっくり寄せて1カットにする
    （カレンダーのように、動画にすると焼き込んだ日本語が描き直されてしまうもの用）
  - 音楽は尺に合わせて生成した koby2.m4a。足りなければ無音で埋める
"""
import io, json, os, subprocess, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, 'media', 'cine', 'koby', '_work2')
OUT = os.path.join(ROOT, 'media', 'cine', 'koby2-flat.mp4')
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
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: %d
PlayResY: %d
WrapStyle: 2

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: base,Yu Gothic,58,&H00FFFFFF,&HC0000000,&H00000000,1,0,0,0,100,100,1,0,1,3,2,2,120,120,88,1
Style: big,Yu Gothic,86,&H00FFFFFF,&HC0000000,&H00000000,1,0,0,0,100,100,2,0,1,4,3,2,120,120,110,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
""" % (W, H)
    ls = sorted(d['lines'], key=lambda x: x['cue'])
    rows = []
    for i, l in enumerate(ls):
        end = ls[i + 1]['cue'] - 0.12 if i + 1 < len(ls) else d['total'] - 0.2
        end = min(end, l['cue'] + 6.0)
        style = 'big' if l.get('cls') == 'big' else 'base'
        rows.append('Dialogue: 0,%s,%s,%s,,0,0,0,,%s'
                    % (t(l['cue']), t(end), style, l['text']))
    # 読み速度の確認。速すぎる字幕は読めないので警告だけ出す
    for i, l in enumerate(ls):
        end = ls[i + 1]['cue'] - 0.12 if i + 1 < len(ls) else d['total'] - 0.2
        end = min(end, l['cue'] + 6.0)
        cps = len(l['text']) / max(end - l['cue'], .01)
        if cps > 6.5:
            print('  !! 字幕が速い %.1f字/秒  %.1fs %s' % (cps, l['cue'], l['text']))
    return head + '\n'.join(rows) + '\n'


def cut_clip(s, need, srcdir, out):
    src = os.path.join(srcdir, s['clip'] + '.mp4')
    have = dur(src) - s['in']
    vf = 'scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,fps=%d' % (W, H, W, H, FPS)
    if have < need - 0.02:
        rate = need / have
        if rate > 1.5:
            print('  !! %s 素材 %.2fs < 必要 %.2fs (%.2fx) 伸ばしすぎ' % (s['clip'], have, need, rate))
        else:
            print('  %s 素材 %.2fs → %.2fx スロー' % (s['clip'], have, rate))
        vf = 'setpts=%.4f*PTS,' % rate + vf
    # 秒数で切ると fps 変換の丸めで1フレーム足りなくなる。フレーム数で切り、足りない分は最終フレームを複製
    frames = int(round(need * FPS))
    vf += ',tpad=stop_mode=clone:stop_duration=0.5'
    subprocess.check_call(['ffmpeg', '-y', '-v', 'error', '-ss', str(s['in']), '-i', src,
                           '-vf', vf, '-frames:v', str(frames), '-an',
                           '-c:v', 'libx264', '-crf', '16', '-preset', 'fast', out])


def cut_still(s, need, stilldir, out):
    """静止画をゆっくり寄せて1カットにする。焼き込んだ文字が消えない。"""
    src = os.path.join(stilldir, s['still'])
    z = s.get('zoom', 1.12)
    frames = int(round(need * FPS))
    step = (z - 1.0) / frames
    vf = ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
          "zoompan=z='min(zoom+%.6f,%.4f)':d=%d:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          ":s=%dx%d:fps=%d" % (W * 2, H * 2, W * 2, H * 2, step, z, frames, W, H, FPS))
    subprocess.check_call(['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-i', src,
                           '-t', str(need), '-vf', vf, '-an',
                           '-c:v', 'libx264', '-crf', '16', '-preset', 'fast', out])


def main():
    d = json.load(io.open(os.path.join(ROOT, 'tools', 'koby2.json'), encoding='utf-8'))
    os.makedirs(WORK, exist_ok=True)
    clipdir = os.path.join(ROOT, d['clipdir'].replace('/', os.sep))
    stilldir = os.path.join(ROOT, d['stilldir'].replace('/', os.sep))

    total = d['total']

    # 1. 各カットを必要尺に切り出す
    parts = []
    for i, s in enumerate(d['scenes']):
        need = round(s['t1'] - s['t0'], 3)
        out = os.path.join(WORK, '%02d.mp4' % i)
        if 'still' in s:
            cut_still(s, need, stilldir, out)
        else:
            cut_clip(s, need, clipdir, out)
        parts.append(out)

    # 2. つなぐ
    lst = os.path.join(WORK, 'list.txt')
    io.open(lst, 'w', encoding='utf-8').write(
        '\n'.join("file '%s'" % p.replace('\\', '/') for p in parts))
    joined = os.path.join(WORK, 'joined.mp4')
    subprocess.check_call(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0',
                           '-i', lst, '-c', 'copy', joined])

    # 3. 音楽。場面ごとに別の曲を敷き、境目でクロスフェードする。
    #    1本通しだと「シーンごとに使い分けられていない」と見える。
    XF = 1.0
    segs, ins = [], []
    for i, m in enumerate(d['musics']):
        t0, t1 = m['t0'], m['t1']
        need = t1 - t0 + (XF if i + 1 < len(d['musics']) else 0)
        src = os.path.join(ROOT, m['file'].replace('/', os.sep))
        have = dur(src)
        if have < need - 0.05:
            print('  !! 音楽 %s %.1fs < 必要 %.1fs' % (os.path.basename(src), have, need))
        fin = XF if i else 1.2
        fout = XF if i + 1 < len(d['musics']) else 2.4
        af = ('atrim=0:%.3f,asetpts=N/SR/TB,apad,atrim=0:%.3f,'
              'afade=t=in:st=0:d=%.2f,afade=t=out:st=%.3f:d=%.2f,'
              'volume=%.3f,adelay=%d|%d'
              % (need, need, fin, max(need - fout, 0), fout, m['gain'],
                 int(t0 * 1000), int(t0 * 1000)))
        ins += ['-i', src]
        segs.append(af)
    fc = ''.join('[%d:a]%s[a%d];' % (i, af, i) for i, af in enumerate(segs))
    fc += ''.join('[a%d]' % i for i in range(len(segs)))
    fc += 'amix=inputs=%d:normalize=0:duration=longest,atrim=0:%.3f[out]' % (len(segs), total)
    audio = os.path.join(WORK, 'audio.m4a')
    subprocess.check_call(['ffmpeg', '-y', '-v', 'error', *ins,
                           '-filter_complex', fc, '-map', '[out]',
                           '-c:a', 'aac', '-b:a', '192k', audio])

    # 4. 字幕を焼いて合成
    sub = os.path.join(WORK, 'sub.ass')
    io.open(sub, 'w', encoding='utf-8').write(ass(d))
    subprocess.check_call([
        'ffmpeg', '-y', '-v', 'error', '-i', joined, '-i', audio,
        '-vf', "subtitles='%s':fontsdir='C\\:/Windows/Fonts'"
               % sub.replace('\\', '/').replace(':', '\\:'),
        '-map', '0:v', '-map', '1:a', '-shortest',
        '-c:v', 'libx264', '-crf', '20', '-preset', 'slow', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', OUT])

    print('%d カット / %.2f秒' % (len(d['scenes']), total))
    print('→ %s  %.1f MB  %.2fs' % (OUT, os.path.getsize(OUT) / 1048576, dur(OUT)))


if __name__ == '__main__':
    main()
