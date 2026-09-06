# -*- coding: utf-8 -*-
"""アニメ版の本組み。anim/*.mp4（Higgsfieldで動かしたコマ）を並べ、
テロップを焼き、ナレーションとBGMを乗せて boot-movie.mp4 を作る。

  python bootcamp/movie/build.py            # 通し
  python bootcamp/movie/build.py --cuts     # カット単位の中間ファイルまで
  python bootcamp/movie/build.py --probe    # テロップの見え方だけ静止画で確認

方針（GPT-6 と詰めた結論）:
  - 文字は全部 PIL で焼く。ffmpeg の drawtext はこのビルドだと日本語で落ちる。
  - セリフは吹き出しではなく映画字幕型。顔と動きを隠さない。
  - 音を切っても通るよう、左上に常時「経営者のための、AIブートキャンプ」を出す。
  - クリップは尺が足りなければ 1.3 倍までスローで伸ばし、それ以上は最終フレームを持たせる。
"""
import json, os, subprocess, sys, io
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ANIM, SRC, VOICE = (os.path.join(HERE, d) for d in ('anim', 'src', 'voice_t'))
WORK = os.path.join(HERE, 'work')

W, H, FPS = 1920, 1080, 30
LEAD, TAIL, XF = 0.45, 0.75, 0.45
FADE_IN, END_HOLD, MAX_SLOW = 0.8, 0.9, 1.3

F_BOLD = r'C:\Windows\Fonts\BIZ-UDGothicB.ttc'
F_MED = r'C:\Windows\Fonts\YuGothM.ttc'
GOLD, PAPER, GREEN = (255, 215, 0), (243, 245, 239), (15, 95, 82)

# カット定義。src はクリップ名（anim/<name>.mp4）、still は静止画（src/<name>.png）。
# tel は [テキスト, 開始, 終了] の相対秒。終了 None はカット末尾まで。
CUTS = [
    dict(line='L01', src='a_desk',
         tel=[['借りた力が去ったあと、\n人は、何をもって立つのだろう。', .2, None]]),
    dict(line='L02', src='a_trio',
         tel=[['社長が使ってくれたら、\nうちも変われるのに。', .2, None]]),
    dict(line='L03', src='c03',
         tel=[['使えるもんなら、使うとる。', .2, 2.9],
              ['あいつがおらん画面に、\n何を頼めばええんや。', 3.1, None]]),
    dict(line='L04', src='c04', chip='経営者だけの、5時間',
         tel=[['半年後。', .2, None]]),
    dict(line='L05', src='c05',
         tel=[['ルールは一つ。\n五時間、他の仕事は捨ててください。', .2, None]]),
    # Kling が指を 2 本に描き替えてしまい「三つできています」と食い違うので、
    # このカットだけ原画（3 本指）を全画面で使い、寄りだけ付ける。
    dict(line='L06', still='c06', anim_still=True,
         tel=[['部屋を出るときには、\n三つできています。', .2, None]]),
    dict(line='L07', still='card3'),
    dict(line='L08', src='c08', chip='見積3案　半日 → 2分',
         tel=[['この見積、三通り出せ。', .2, 2.7],
              ['……二分か。去年は、半日や。', 2.9, None]]),
    dict(line='L09', src='a_face',
         tel=[['あいつの言うとったこと、\n全部、意味があったんや。', .2, None]]),
    dict(line='L10', src='c10',
         tel=[['決めるんは、ワシらや。', .2, None]]),
    dict(line='L11', still='s12'),
]


def run(cmd):
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(cmd[:6] + [p.stderr.decode('utf-8', 'replace')[-1200:]])


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
                d.text((x + dx, y + dy), text, font=f, fill=(0, 0, 0, 235), anchor=anchor)
    d.text(xy, text, font=f, fill=fill, anchor=anchor)


def scrim():
    """下からの黒グラデーション。明るい絵でも字幕が読めるようにする。"""
    a = np.zeros((H, W, 4), np.uint8)
    y = np.arange(H, dtype=np.float32)
    g = np.clip((y - H * .52) / (H * .48), 0, 1) ** 1.5 * 205
    a[..., 3] = g[:, None].astype(np.uint8)
    return Image.fromarray(a, 'RGBA')


SCRIM = scrim()


def telop_png(text, chip=None):
    """字幕1枚（1920x1080 RGBA）。スクリム込みで焼く。"""
    img = SCRIM.copy()
    d = ImageDraw.Draw(img)
    lines = text.split('\n')
    f = font(F_BOLD, 76 if max(len(l) for l in lines) <= 18 else 64)
    lh = int(f.size * 1.42)
    y0 = 962 - lh * (len(lines) - 1)
    for i, ln in enumerate(lines):
        outlined(d, (W // 2, y0 + i * lh), ln, f, (255, 255, 255, 255), 'mm')
    if chip:
        draw_chip(d, chip)
    return img


def draw_chip(d, chip):
    """見出しラベル。字幕とぶつからないよう右上に置く。"""
    fc = font(F_BOLD, 42)
    cx, cy = W - 78, 96
    bb = d.textbbox((cx, cy), chip, font=fc, anchor='rm')
    d.rounded_rectangle([bb[0] - 32, bb[1] - 17, bb[2] + 32, bb[3] + 17], radius=999,
                        fill=(7, 20, 31, 230), outline=GOLD + (255,), width=2)
    d.text((cx, cy), chip, font=fc, fill=GOLD + (255,), anchor='rm')


def chip_only_png(chip):
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw_chip(ImageDraw.Draw(img), chip)
    return img


def brand_png():
    """左上の常時表示。音を切っても誰向けの何か分かるようにする。"""
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    outlined(d, (64, 74), '経営者のための、AIブートキャンプ ｜ 5時間', font(F_BOLD, 36),
             (255, 255, 255, 225), 'lm', ow=3)
    return img


def card_three():
    c = Image.new('RGB', (W, H), (250, 250, 246))
    d = ImageDraw.Draw(c)
    d.rectangle([70, 60, W - 70, H - 60], outline=GREEN, width=5)
    fn, ft, fs = font(F_BOLD, 78), font(F_BOLD, 56), font(F_MED, 34)
    d.text((W // 2, 176), '部屋を出るときに、できていること', font=ft, fill=(26, 26, 26), anchor='mm')
    d.line([330, 246, W - 330, 246], fill=GREEN, width=3)
    rows = [('01', 'Claude Code と Codex が、自分のPCで動く', '日本語で頼んで、動くものを作る'),
            ('02', 'MCPで、自社の数字につながる', '会計・勤怠・メールから数字を引く'),
            ('03', '人・AI・専門家の線が引ける', '決めるのは、人')]
    y = 380
    for n, t, s in rows:
        d.text((250, y + 20), n, font=fn, fill=GREEN, anchor='lm')
        d.text((420, y), t, font=ft, fill=(26, 26, 26), anchor='lm')
        d.text((422, y + 58), s, font=fs, fill=(110, 118, 115), anchor='lm')
        y += 200
    return c


def still_png(name, full=False):
    """静止カットを 1920x1080 に収める。上下の余白は深緑で埋める。
    full=True のときは anim/ の 16:9 画像をそのまま全画面に使う。"""
    if name == 'card3':
        return card_three()
    if full:
        return Image.open(os.path.join(ANIM, name + '.png')).convert('RGB').resize((W, H), Image.LANCZOS)
    im = Image.open(os.path.join(SRC, name + '.png')).convert('RGB')
    bg = Image.new('RGB', (W, H), (7, 20, 31))
    r = min((W - 160) / im.width, (H - 120) / im.height)
    im = im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)
    pad = Image.new('RGB', (im.width + 16, im.height + 16), (255, 255, 255))
    pad.paste(im, (8, 8))
    bg.paste(pad, ((W - pad.width) // 2, (H - pad.height) // 2))
    return bg


def slot_durations():
    d = json.load(open(os.path.join(HERE, 'lines.json'), encoding='utf-8'))
    dur = {l['id']: l['dur'] for l in d['lines']}
    out = []
    for i, c in enumerate(CUTS):
        s = LEAD + dur[c['line']] + TAIL
        if i == len(CUTS) - 1:
            s += END_HOLD
        out.append(round(s, 3))
    return out, dur


def build_cut(i, cut, slot):
    """1カットぶんの動画（テロップ焼き込み済み）を work/cut_i.mp4 に作る。"""
    dst = os.path.join(WORK, f'cut{i:02d}.mp4')
    ins, filt = [], []

    if 'still' in cut:
        p = os.path.join(WORK, f'still{i:02d}.png')
        still_png(cut['still'], cut.get('anim_still', False)).save(p)
        ins += ['-loop', '1', '-t', f'{slot:.3f}', '-i', p]
        # 静止カットもゆっくり寄せて、動画の中で浮かないようにする
        filt.append(f"[0:v]scale={int(W*1.06)}:-1,zoompan=z='min(zoom+0.00025,1.06)':"
                    f"d={int(slot*FPS)}:s={W}x{H}:fps={FPS},setsar=1[v0]")
    else:
        clip = os.path.join(ANIM, cut['src'] + '.mp4')
        L = probe(clip)
        ins += ['-i', clip]
        if L >= slot:
            pre = f"[0:v]trim=0:{slot:.3f},setpts=PTS-STARTPTS"
        else:
            ratio = slot / L
            if ratio <= MAX_SLOW:
                pre = f"[0:v]setpts={ratio:.4f}*PTS"
            else:
                pre = (f"[0:v]setpts={MAX_SLOW:.4f}*PTS,"
                       f"tpad=stop_mode=clone:stop_duration={slot - L*MAX_SLOW + .2:.3f}")
        filt.append(f"{pre},scale={W}:{H}:force_original_aspect_ratio=increase,"
                    f"crop={W}:{H},fps={FPS},setsar=1[v0]")

    last, n = 'v0', 1
    for text, s, e in cut.get('tel', []):
        e = slot - 0.15 if e is None else e
        p = os.path.join(WORK, f'tel{i:02d}_{n}.png')
        telop_png(text, cut.get('chip')).save(p)
        ins += ['-loop', '1', '-i', p]
        filt.append(f"[{n}:v]format=rgba,fade=t=in:st=0:d=0.16:alpha=1,"
                    f"fade=t=out:st={max(0.0, e-s-0.12):.3f}:d=0.12:alpha=1,"
                    f"setpts=PTS-STARTPTS+{s:.3f}/TB[o{n}]")
        filt.append(f"[{last}][o{n}]overlay=0:0:enable='between(t,{s:.3f},{e:.3f})'[v{n}]")
        last = f'v{n}'
        n += 1

    if not cut.get('tel') and cut.get('chip'):
        p = os.path.join(WORK, f'chip{i:02d}.png')
        chip_only_png(cut['chip']).save(p)
        ins += ['-loop', '1', '-i', p]
        filt.append(f"[{n}:v]format=rgba[o{n}]")
        filt.append(f"[{last}][o{n}]overlay=0:0[v{n}]")
        last = f'v{n}'
        n += 1

    if 'still' not in cut or cut.get('anim_still'):
        p = os.path.join(WORK, 'brand.png')
        if not os.path.exists(p):
            brand_png().save(p)
        ins += ['-loop', '1', '-i', p]
        filt.append(f"[{n}:v]format=rgba[b{n}]")
        filt.append(f"[{last}][b{n}]overlay=0:0[v{n}]")
        last = f'v{n}'

    run(['ffmpeg', '-y', '-v', 'error', *ins, '-filter_complex', ';'.join(filt),
         '-map', f'[{last}]', '-t', f'{slot:.3f}', '-an',
         '-c:v', 'libx264', '-preset', 'faster', '-crf', '16', '-pix_fmt', 'yuv420p', dst])
    return dst


def main():
    os.makedirs(WORK, exist_ok=True)
    slots, dur = slot_durations()

    if '--probe' in sys.argv:
        telop_png(CUTS[2]['tel'][1][0]).save(os.path.join(HERE, '_tel_probe.png'))
        still_png('card3').save(os.path.join(HERE, '_card_probe.png'))
        print('probe written')
        return

    paths = []
    for i, (cut, slot) in enumerate(zip(CUTS, slots)):
        paths.append(build_cut(i, cut, slot))
        print(f'  cut{i:02d} {cut["line"]:4s} {slot:5.2f}s  {cut.get("src") or cut.get("still")}')

    if '--cuts' in sys.argv:
        return

    # xfade で連結
    ins = []
    for p in paths:
        ins += ['-i', p]
    filt, last, off = [], '0:v', 0.0
    for i in range(1, len(paths)):
        off += slots[i - 1] - XF
        filt.append(f"[{last}][{i}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[x{i}]")
        last = f'x{i}'
    total = sum(slots) - XF * (len(paths) - 1)

    bi = len(paths) - 1
    filt.append(f"[{last}]fade=t=in:st=0:d={FADE_IN}[vout]")

    # 音：ナレーションを所定の位置に置き、BGM をダッキングして下に敷く
    at, starts = 0.0, []
    for i, (cut, slot) in enumerate(zip(CUTS, slots)):
        starts.append(at + LEAD)
        at += slot - XF
    ai = bi + 1
    for c in CUTS:
        ins += ['-i', os.path.join(VOICE, c['line'] + '.wav')]
    ins += ['-i', os.path.join(HERE, 'bgm_raw.wav')]

    afl = []
    for k, st in enumerate(starts):
        afl.append(f"[{ai+k}:a]adelay={int(st*1000)}|{int(st*1000)},apad[n{k}]")
    afl.append(''.join(f'[n{k}]' for k in range(len(starts))) +
               f"amix=inputs={len(starts)}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,asplit=2[na][nsc]")
    bgi = ai + len(starts)
    afl.append(f"[{bgi}:a]afade=t=in:st=0:d=2.5,afade=t=out:st={total-3.4:.3f}:d=3.4,volume=0.34[bg]")
    afl.append("[bg][nsc]sidechaincompress=threshold=0.028:ratio=9:attack=25:release=600[bgd]")
    afl.append("[na][bgd]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[aout]")

    out = os.path.join(HERE, 'boot-movie.mp4')
    run(['ffmpeg', '-y', '-v', 'error', *ins,
         '-filter_complex', ';'.join(filt + afl),
         '-map', '[vout]', '-map', '[aout]', '-t', f'{total:.3f}',
         '-c:v', 'libx264', '-preset', 'veryslow', '-crf', '25', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', out])
    print(f'done {total:.2f}s -> {out} {os.path.getsize(out)//1024} KB')


if __name__ == '__main__':
    main()
