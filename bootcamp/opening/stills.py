# -*- coding: utf-8 -*-
"""各カットの開始画像を gpt-image-2 で作り、16:9 に整えて anim/ に置く。

  python bootcamp/opening/stills.py            # 未生成のカットだけ
  python bootcamp/opening/stills.py goldfish   # 指定したカットだけ作り直す

文字は一切描かせない（テロップは build.py が PIL で焼く）。
生成画像に文字が入ると、Kling がそれを崩して読めない模様にする。
"""
import base64, io, json, os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ANIM = os.path.join(HERE, 'anim')

NO_TEXT = (' Photographic, cinematic still, shot on a full-frame camera, shallow depth of field, '
           'natural light, muted desaturated color grade, documentary tone, no people looking at '
           'the camera. Absolutely no text, no letters, no numbers, no captions, no watermarks, '
           'no logos, no signage anywhere in the frame.')

SHOTS = {
    'goldfish': 'A single goldfish in a plain round glass bowl on a dark wooden desk in a quiet, '
                'dim Japanese office at night. A closed laptop sits beside the bowl. The water '
                'catches a little light. Calm, still, slightly melancholy.',
    'robot2025': 'A humanoid robot running awkwardly on a wide city road at a public race in China, '
                 'early morning overcast light, safety barriers and blurred spectators far in the '
                 'background, motion blur on the legs, slightly unstable posture.',
    'robot2026': 'A humanoid robot running fast and smoothly on a wide city road, low angle from the '
                 'side, strong motion blur in the background, confident stride, morning light, '
                 'the same race setting but faster and more composed.',
    'robotaxi': 'A white self-driving taxi with a roof sensor unit driving through a city street at '
                'dusk, seen from the side, the driver seat clearly empty, wet asphalt reflecting '
                'street lights, other cars blurred.',
    'office': 'A modern Japanese office in the afternoon, several employees working at laptops, seen '
              'from behind at a slight distance, quiet and orderly, soft window light, nobody talking.',
    'meeting': 'A Japanese meeting room where four people sit around a table with printed documents '
               'and closed laptops, viewed from the corner of the room, everyone looking down at '
               'paper, static and heavy atmosphere, afternoon light through blinds.',
    'window': 'A middle-aged Japanese business owner in a dark suit standing alone at a large office '
              'window at dusk, seen from behind, looking out over a city skyline, hands at his sides, '
              'warm low sun on the buildings.',
}


def api_key():
    k = os.environ.get('OPENAI_API_KEY')
    if k:
        return k
    env = r'C:\Users\mgomi\dev\lovebu-manga-builder\lovebu-manga-builder\.env'
    for ln in io.open(env, encoding='utf-8'):
        if ln.startswith('OPENAI_API_KEY='):
            return ln.split('=', 1)[1].strip().strip('"').strip("'")
    raise RuntimeError('OPENAI_API_KEY not found')


KEY = api_key()


def make(name):
    dst = os.path.join(ANIM, name + '.png')
    if os.path.exists(dst):
        return name, 'cached'
    body = json.dumps({
        'model': 'gpt-image-2',
        'prompt': SHOTS[name] + NO_TEXT,
        'size': '1536x1024',
        'n': 1,
    }).encode()
    req = urllib.request.Request(
        'https://api.openai.com/v1/images/generations', data=body,
        headers={'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.load(r)
    item = d['data'][0]
    raw = base64.b64decode(item['b64_json']) if item.get('b64_json') else \
        urllib.request.urlopen(item['url']).read()

    im = Image.open(io.BytesIO(raw)).convert('RGB')
    # 3:2 で返るので、中央を 16:9 に切って 1280x720 に落とす
    h = int(im.width * 9 / 16)
    top = (im.height - h) // 2
    im.crop((0, top, im.width, top + h)).resize((1280, 720), Image.LANCZOS).save(dst)
    return name, 'new'


def main():
    os.makedirs(ANIM, exist_ok=True)
    names = [a for a in sys.argv[1:] if not a.startswith('-')] or list(SHOTS)
    with ThreadPoolExecutor(max_workers=4) as ex:
        for name, how in ex.map(make, names):
            print(f'{name:11s} {how}')


if __name__ == '__main__':
    main()
