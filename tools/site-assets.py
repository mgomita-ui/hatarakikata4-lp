# -*- coding: utf-8 -*-
"""
index.html の埋め込み(base64)画像を外部ファイルに出し、遅延読み込みにする。
あわせて共有用の OG 画像を生成し、canonical / og / twitter のメタを <head> に入れる。
  python tools/site-assets.py
"""
import re, os, io, base64, hashlib, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'index.html'); IMG = os.path.join(ROOT, 'media', 'img')
BASE = 'https://mgomita-ui.github.io/hatarakikata4-lp/'
s = open(P, encoding='utf-8').read(); before = len(s.encode('utf-8'))

# ---- 1. 埋め込み画像を外に出す ----
seen = {}; hero = None
def name_for(ctx, ext, digest):
    m = re.search(r'href="(manga\d|bootcamp)/"', ctx)
    sel = re.findall(r'([.#][\w-]+(?: [.#][\w-]+)*)\{[^{}]*$', ctx)   # 直前の CSS セレクタ
    css = {'.hero .bg': 'hero-bg', '.bcta .im': 'bcta-bg'}.get(sel[-1] if sel else '', None)
    base = css or ((m.group(1) + '-cover') if m else 'img-' + digest[:6])
    return base + '.' + ('jpg' if ext == 'jpeg' else ext)
def repl(m):
    global hero
    ctx = s[max(0, m.start()-400):m.start()+5]
    ext, data = m.group(1), m.group(2)
    digest = hashlib.sha1(data.encode()).hexdigest()
    if digest not in seen:
        fn = name_for(ctx, ext, digest)
        open(os.path.join(IMG, fn), 'wb').write(base64.b64decode(data)); seen[digest] = fn
    fn = seen[digest]
    if fn.startswith('hero-bg'): hero = fn
    return 'media/img/' + fn
s = re.sub(r'data:image/(\w+);base64,([A-Za-z0-9+/=]+)', repl, s)
# <img> に遅延読み込みを付ける（既に指定があるものは触らない）
s = re.sub(r'<img(?![^>]*loading=)([^>]*src="media/img/)', r'<img loading="lazy" decoding="async"\1', s)
print('外部化した画像:', sorted(set(seen.values())))

# ---- 2. OG 画像 ----
src = Image.open(os.path.join(IMG, hero or sorted(set(seen.values()))[0])).convert('RGB')
W, H = 1200, 630
r = max(W/src.width, H/src.height); im = src.resize((round(src.width*r), round(src.height*r)), Image.LANCZOS)
im = im.crop(((im.width-W)//2, (im.height-H)//2, (im.width-W)//2+W, (im.height-H)//2+H)).filter(ImageFilter.GaussianBlur(1.2))
ov = Image.new('RGBA', (W, H), (7, 34, 30, 0)); od = ImageDraw.Draw(ov)
for y in range(H): od.line([(0, y), (W, y)], fill=(7, 34, 30, int(120 + 110*y/H)))
im = Image.alpha_composite(im.convert('RGBA'), ov)
d = ImageDraw.Draw(im); F = r'C:\Windows\Fonts\BIZ-UDGothicB.ttc'
d.text((72, 118), '働き方4.0 ｜ 働き方と福利厚生の再設計', font=ImageFont.truetype(F, 30), fill=(228, 199, 107))
d.text((70, 186), '採用と定着を、', font=ImageFont.truetype(F, 92), fill=(255, 255, 255))
d.text((70, 300), '働く条件から。', font=ImageFont.truetype(F, 92), fill=(255, 255, 255))
d.text((72, 452), 'なぜ人は、同じ場所に、同じ時間に集まるのだろう。', font=ImageFont.truetype(F, 34), fill=(243, 245, 239))
d.text((72, 540), 'レリック社会保険労務士法人', font=ImageFont.truetype(F, 28), fill=(228, 199, 107))
im.convert('RGB').save(os.path.join(ROOT, 'media', 'og.jpg'), quality=86, optimize=True)
print('OG 画像: media/og.jpg', im.size, f'{os.path.getsize(os.path.join(ROOT,"media","og.jpg"))//1024}KB')

# ---- 3. メタタグ ----
title = re.search(r'<title>(.*?)</title>', s, re.S).group(1).strip()
desc = re.search(r'<meta name="description" content="([^"]*)"', s).group(1)
meta = f'''
  <link rel="canonical" href="{BASE}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="レリック社会保険労務士法人">
  <meta property="og:locale" content="ja_JP">
  <meta property="og:url" content="{BASE}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:image" content="{BASE}media/og.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{desc}">
  <meta name="twitter:image" content="{BASE}media/og.jpg">'''
if 'property="og:' not in s:
    s = s.replace('</title>', '</title>' + meta, 1)
open(P, 'w', encoding='utf-8').write(s)
print(f'index.html {before//1024}KB -> {len(s.encode("utf-8"))//1024}KB')
