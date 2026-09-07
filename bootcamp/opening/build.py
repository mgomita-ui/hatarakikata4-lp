# -*- coding: utf-8 -*-
"""オープニングを1本の MP4 に焼く。映像・テロップ・ナレーション・BGM を全部内包する。

  python bootcamp/opening/build.py            # 通し
  python bootcamp/opening/build.py --probe    # テロップの見え方だけ静止画で確認

tools/README.md の結論に従う:
  - 2本の <video> を切り替える方式は使わない。単一動画にして端末の標準再生に任せる。
  - 携帯のハードウェアデコーダ対策で -profile:v high -level 4.1 -x264-params ref=4:bframes=2 を必須。
    veryslow は参照16枚で level 5.1 になり、特定フレームで映像だけ止まる。
  - xfade は両入力の timebase/fps を揃えないと EINVAL で落ちる。settb=AVTB,fps=FPS を必ず通す。
  - ffmpeg の stderr は必ず拾う。-v error だけだと原因が全く出ない。
文字は ffmpeg の drawtext ではなく PIL で焼く（このビルドは fontconfig が無く日本語で落ちる）。
"""
import json, os, subprocess, sys, io
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ANIM, VO, WORK = (os.path.join(HERE, d) for d in ('anim', 'vo', 'work'))

W, H, FPS = 1920, 1080, 24
LEAD, TAIL, XF = 0.40, 0.65, 0.50
FADE_IN, END_HOLD, MAX_SLOW = 1.0, 1.0, 1.4

F_BOLD = r'C:\Windows\Fonts\BIZ-UDGothicB.ttc'
F_MED = r'C:\Windows\Fonts\YuGothM.ttc'
F_NUM = r'C:\Windows\Fonts\BIZ-UDGothicB.ttc'
GOLD, PAPER, DIM, GREEN = (255, 215, 0), (243, 245, 239), (168, 186, 180), (15, 95, 82)

X264 = ['-profile:v', 'high', '-level', '4.1', '-x264-params', 'ref=4:bframes=2']


def run(cmd):
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(' '.join(map(str, cmd[:8])) + '\n' +
                           p.stderr.decode('utf-8', 'replace')[-1500:])


def probe(path):
    p = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'csv=p=0', path], capture_output=True, text=True)
    return float(p.stdout.strip())


def font(path, size):
    return ImageFont.truetype(path, size)


def outlined(d, xy, text, f, fill, anchor, ow=4):
    x, y = xy
    for dx in range(-ow, ow + 1):
        for dy in range(-ow, ow + 1):
            if dx * dx + dy * dy <= ow * ow:
                d.text((x + dx, y + dy), text, font=f, fill=(0, 0, 0, 225), anchor=anchor)
    d.text(xy, text, font=f, fill=fill, anchor=anchor)


def scrim(strength=210, start=.45):
    a = np.zeros((H, W, 4), np.uint8)
    y = np.arange(H, dtype=np.float32)
    a[..., 3] = (np.clip((y - H * start) / (H * (1 - start)), 0, 1) ** 1.4 *
                 strength)[:, None].astype(np.uint8)
    return Image.fromarray(a, 'RGBA')


SCRIM = scrim()


def bgdark():
    """タイポグラフィのカット用。LPと同じ深緑。"""
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.clip(np.sqrt(((x - W * .5) / (W * .8)) ** 2 + ((y - H * 1.0) / (H * .95)) ** 2), 0, 1)
    top, bot = np.array([13, 74, 66]), np.array([6, 17, 26])
    return Image.fromarray((top * (1 - d[..., None]) + bot * d[..., None]).astype(np.uint8))


def stat_png(line):
    """数字カット。大きな数字＋注記＋出典。報道の見出しのように置く。"""
    img = SCRIM.copy()
    d = ImageDraw.Draw(img)
    t, sub, src = line['text'], line['sub'], line['src']
    if t:
        big = len(t) <= 10
        f = font(F_NUM, 210 if big else 76)
        outlined(d, (W // 2, 700 if big else 760), t, f, (255, 255, 255, 255), 'mm', ow=5)
        if big:
            d.line([W // 2 - 190, 830, W // 2 + 190, 830], fill=GOLD + (230,), width=3)
    if sub:
        outlined(d, (W // 2, 890), sub, font(F_MED, 40), PAPER + (245,), 'mm', ow=3)
    if src:
        outlined(d, (56, H - 44), 'SOURCE ｜ ' + src, font(F_MED, 24), DIM + (215,), 'lm', ow=2)
    return img


def quote_png(line):
    img = SCRIM.copy()
    d = ImageDraw.Draw(img)
    outlined(d, (W // 2, 760), line['text'], font(F_BOLD, 86), (255, 255, 255, 255), 'mm', ow=5)
    outlined(d, (W // 2, 862), line['sub'], font(F_MED, 34), GOLD + (235,), 'mm', ow=3)
    return img


def ask_png(line):
    img = SCRIM.copy()
    d = ImageDraw.Draw(img)
    outlined(d, (W // 2, 780), line['text'], font(F_BOLD, 82), (255, 255, 255, 255), 'mm', ow=5)
    return img


def choice_png(ch, upto):
    """A/B/C を順に立ち上げる。upto までを表示し、Cだけ金で起こす。"""
    img = bgdark()
    d = ImageDraw.Draw(img)
    d.text((W // 2, 150), '経営者の選択肢は、三つ。', font=font(F_MED, 44), fill=PAPER, anchor='mm')
    y = 320
    for i, c in enumerate(ch):
        on = i < upto
        last = i == 2
        col = (GOLD if last else PAPER) if on else (40, 60, 58)
        d.text((330, y), c['k'], font=font(F_NUM, 92), fill=col, anchor='lm')
        d.text((470, y - 22), c['h'], font=font(F_BOLD, 62), fill=col, anchor='lm')
        if on:
            d.text((474, y + 40), '結果：' + c['r'], font=font(F_MED, 32),
                   fill=(GOLD if last else DIM), anchor='lm')
        d.line([330, y + 96, W - 330, y + 96], fill=(30, 52, 50), width=2)
        y += 230
    return img


def title_png(line):
    img = bgdark()
    d = ImageDraw.Draw(img)
    d.text((W // 2, H * .40), 'AIは、来る。', font=font(F_BOLD, 88), fill=PAPER, anchor='mm')
    d.text((W // 2, H * .50), '来ない、という選択肢は、無い。', font=font(F_BOLD, 88),
           fill=PAPER, anchor='mm')
    d.line([W * .38, H * .60, W * .62, H * .60], fill=GOLD, width=2)
    d.text((W // 2, H * .68), line['text'], font=font(F_BOLD, 54), fill=GOLD, anchor='mm')
    d.text((W // 2, H * .755), line['sub'], font=font(F_MED, 34), fill=DIM, anchor='mm')
    return img


def overlays(line, slot):
    """[PNGパス, 開始, 終了] のリスト。カットごとに何をいつ出すか。"""
    out, k = [], line['id']
    end = slot - 0.15

    def save(img, name):
        p = os.path.join(WORK, f'{k}_{name}.png')
        img.save(p)
        return p

    if k == 'S01':
        out.append([save(quote_png(line), 'q'), 0.9, end])
    elif k == 'S07':
        out.append([save(ask_png(line), 'a'), 0.3, end])
    elif k == 'S08':
        ch = SCRIPT['choices']
        # ナレーション「何もしない／ツールを入れる／経営に、AIを組み込む」に合わせて起こす
        for i, at in enumerate([LEAD + 1.9, LEAD + 3.5, LEAD + 5.1]):
            nxt = [LEAD + 3.5, LEAD + 5.1, end][i]
            out.append([save(choice_png(ch, i + 1), f'c{i}'), at, nxt])
    elif k == 'S09':
        out.append([save(choice_png(SCRIPT['choices'], 3), 'c3'), 0.0, end])
    elif k == 'S10':
        out.append([save(title_png(line), 't'), 0.3, slot])
    else:
        out.append([save(stat_png(line), 's'), 0.6, end])
    return out


def build_cut(i, line, slot):
    dst = os.path.join(WORK, f'cut{i:02d}.mp4')
    ins, filt = [], []
    clip = os.path.join(ANIM, line['clip'] + '.mp4')

    if os.path.exists(clip):
        L = probe(clip)
        ins += ['-i', clip]
        if L >= slot:
            pre = f'[0:v]trim=0:{slot:.3f},setpts=PTS-STARTPTS'
        else:
            r = min(slot / L, MAX_SLOW)
            pre = f'[0:v]setpts={r:.4f}*PTS'
            if L * r < slot - 0.05:
                pre += f',tpad=stop_mode=clone:stop_duration={slot - L * r + .2:.3f}'
        filt.append(f'{pre},scale={W}:{H}:force_original_aspect_ratio=increase,'
                    f'crop={W}:{H},fps={FPS},settb=AVTB,setsar=1[v0]')
    else:
        p = os.path.join(WORK, f'bg{i:02d}.png')
        bgdark().save(p)
        ins += ['-loop', '1', '-t', f'{slot:.3f}', '-i', p]
        filt.append(f'[0:v]fps={FPS},settb=AVTB,setsar=1[v0]')

    last = 'v0'
    for n, (png, a, b) in enumerate(overlays(line, slot), start=1):
        ins += ['-loop', '1', '-i', png]
        filt.append(f'[{n}:v]format=rgba,fade=t=in:st=0:d=0.28:alpha=1,'
                    f'fade=t=out:st={max(0.0, b - a - 0.2):.3f}:d=0.2:alpha=1,'
                    f'setpts=PTS-STARTPTS+{a:.3f}/TB[o{n}]')
        filt.append(f"[{last}][o{n}]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[v{n}]")
        last = f'v{n}'

    run(['ffmpeg', '-y', '-v', 'error', *ins, '-filter_complex', ';'.join(filt),
         '-map', f'[{last}]', '-t', f'{slot:.3f}', '-an',
         '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p',
         *X264, dst])
    return dst


def main():
    global SCRIPT
    os.makedirs(WORK, exist_ok=True)
    SCRIPT = json.load(open(os.path.join(HERE, 'script.json'), encoding='utf-8'))
    lines = SCRIPT['lines']
    slots = [round(LEAD + l['dur'] + TAIL + (END_HOLD if i == len(lines) - 1 else 0), 3)
             for i, l in enumerate(lines)]

    if '--probe' in sys.argv:
        stat_png(lines[2]).save(os.path.join(HERE, '_p_stat.png'))
        choice_png(SCRIPT['choices'], 3).save(os.path.join(HERE, '_p_choice.png'))
        title_png(lines[9]).save(os.path.join(HERE, '_p_title.png'))
        print('probe written')
        return

    paths = []
    for i, (l, s) in enumerate(zip(lines, slots)):
        paths.append(build_cut(i, l, s))
        print(f'  cut{i:02d} {l["id"]} {s:5.2f}s  {l["clip"]}')

    ins = []
    for p in paths:
        ins += ['-i', p]
    filt, last, off = [], '0:v', 0.0
    for i in range(1, len(paths)):
        off += slots[i - 1] - XF
        filt.append(f'[{last}][{i}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[x{i}]')
        last = f'x{i}'
    total = sum(slots) - XF * (len(paths) - 1)
    filt.append(f'[{last}]fade=t=in:st=0:d={FADE_IN}[vout]')

    at, starts = 0.0, []
    for s in slots:
        starts.append(at + LEAD)
        at += s - XF
    ai = len(paths)
    for l in lines:
        ins += ['-i', os.path.join(VO, l['id'] + '.wav')]
    bgm = os.path.join(HERE, 'bgm.wav')
    ins += ['-i', bgm]

    af = []
    for k, st in enumerate(starts):
        af.append(f'[{ai+k}:a]adelay={int(st*1000)}|{int(st*1000)},apad[n{k}]')
    af.append(''.join(f'[n{k}]' for k in range(len(starts))) +
              f'amix=inputs={len(starts)}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,asplit=2[na][nsc]')
    bi = ai + len(starts)
    af.append(f'[{bi}:a]afade=t=in:st=0:d=3,afade=t=out:st={total-3.5:.3f}:d=3.5,volume=0.30[bg]')
    af.append('[bg][nsc]sidechaincompress=threshold=0.03:ratio=9:attack=25:release=650[bgd]')
    af.append('[na][bgd]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[aout]')

    out = os.path.join(HERE, 'opening.mp4')
    run(['ffmpeg', '-y', '-v', 'error', *ins, '-filter_complex', ';'.join(filt + af),
         '-map', '[vout]', '-map', '[aout]', '-t', f'{total:.3f}',
         '-c:v', 'libx264', '-preset', 'slow', '-crf', '24', '-pix_fmt', 'yuv420p', *X264,
         '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', out])
    lv = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                         '-show_entries', 'stream=level', '-of', 'csv=p=0', out],
                        capture_output=True, text=True).stdout.strip()
    print(f'done {total:.2f}s level={lv} -> {out} {os.path.getsize(out)//1024} KB')


if __name__ == '__main__':
    main()
