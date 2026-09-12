# -*- coding: utf-8 -*-
"""アニメ用のキーフレームを新規に描き起こす（key/*.png）。

  python bootcamp/movie/keyframes.py         # 未生成のカットだけ
  python bootcamp/movie/keyframes.py k01     # 指定したカットだけ

漫画のコマを切り出すのをやめた理由:
  コマにはフキダシ・枠線・印刷用の構図が入っており、動かしても「漫画のダイジェスト」
  にしかならない。キャラクターシートが揃ったので、映像用の画をゼロから起こす。

  - 16:9 全画面。コマ枠もフキダシも文字も入れない（セリフは build2.py が字幕で焼く）
  - キャラは参照シートでデザインを固定し、芝居と画角はカットごとに変える
  - 画角を意図的にばらす（引き／寄り／手元／背中越し）
"""
import base64, io, json, os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'key')
REFS = r'C:\Users\mgomi\Documents\claude-vault\05_働き方4.0\sales_manga\sequel\generator\output\characters'

STYLE = (
    "Modern Japanese anime film still, hand-drawn cel animation look, warm soft colour palette, "
    "gentle cel-shading, clean confident line art, cinematic lighting and depth of field. "
    "Full-bleed 16:9 frame. "
    "ABSOLUTELY NO comic panel borders, NO speech bubbles, NO thought bubbles, NO captions, "
    "NO subtitles, NO text of any kind anywhere in the image, no watermark, no logo. "
    "This is a single cinematic frame, not a manga page."
)

# 参照シートの使い方（デザインだけ写し、芝居は本文に従わせる）
REF_NOTE = (
    "Use the attached reference sheets for the characters' DESIGN only — face structure, hairstyle, "
    "glasses, colour and clothing type. Do NOT copy their poses or expressions from the sheets: "
    "the pose, camera angle and facial expression must be exactly as described for this shot."
)

SHOTS = {
    # name: (参照キャラ, 画角と芝居)
    'k01': (['yamada', 'tamura'],
            "Interior, a small Japanese factory company's meeting room, afternoon. MEDIUM SHOT from behind and "
            "beside the desk. In the foreground, the young worker in a navy work uniform has just lowered a "
            "desk telephone receiver from his ear; his shoulders have dropped and he cannot look up. Behind "
            "him, slightly out of focus, the middle-aged president in a navy work jacket sits very still at "
            "the desk, staring at nothing. Cold flat daylight from a window. Heavy, quiet atmosphere."),

    'k02': (['tamura'],
            "Interior, the president's office at night. TIGHT CLOSE-UP on the middle-aged president's face, "
            "three-quarter angle, lit from one side by a desk lamp. His hand is at his chin. His eyes are "
            "lowered in thought and then hardening as something becomes clear to him. Out-of-focus in the "
            "foreground, the corner of a stack of competitor proposal documents. Shallow depth of field."),

    'k03': (['kiriyama', 'tamura'],
            "Interior, a reception room, late afternoon. TWO SHOT, slightly low angle. The younger rival "
            "president in a dark navy blazer and thin glasses stands and has just finished speaking, already "
            "looking away toward the door, disappointed. On the right, the older president in the navy work "
            "jacket has no answer and his eyes are lowered. A wide gap of empty room between them."),

    'k04': (['tamura', 'aitsu'],
            "Interior, the same office one year earlier — warm sepia-tinted memory lighting, softer and "
            "hazier than the present-day shots. OVER-THE-SHOULDER SHOT from behind the president, who sits "
            "at his desk at night. On the open laptop screen in front of him glows the cyan geometric AI "
            "avatar, calm and gently smiling, turned slightly toward him. Warm lamp light on the man's "
            "shoulder. The screen is the brightest thing in the frame."),

    'k05': (['tamura', 'yamada'],
            "Interior, the office doorway, daytime. MEDIUM-WIDE SHOT. The president is pulling his jacket on "
            "over one shoulder and turning decisively toward the door, his face set. Behind him, deeper in "
            "the room and out of focus, the young worker and a woman in a beige cardigan look up at him, "
            "surprised. Strong daylight from the corridor beyond the door, so he is half in silhouette."),

    'k06': (['tamura', 'nishiyama'],
            "Interior, a bright training room, daytime. CLOSE TWO SHOT. The president sits at a laptop, eyes "
            "wide, leaning back very slightly — the look of a man who has just seen something work for the "
            "first time. The glow of the screen is on his face. Beside him, the woman consultant in a navy "
            "suit watches with a small, satisfied nod. The laptop screen itself is turned away from the "
            "camera so no text is visible."),

    'k07': (['tamura'],
            "Interior, the training room, late afternoon, everyone else gone. EXTREME CLOSE-UP on the "
            "president's face, filling most of the frame, three-quarter angle. A single tear has spilled and "
            "is running down his cheek; his eyes are wet and he is smiling. Warm low sunlight from a window "
            "behind him rims his hair. Very shallow depth of field, the background dissolved into soft light."),

    'k08': (['tamura', 'nishiyama'],
            "Interior, the training room by a whiteboard, end of the day. MEDIUM SHOT. The president has "
            "lifted his head, calm and resolved, looking slightly off-camera. Beside him the woman consultant "
            "listens and gives a small warm nod. Late afternoon light. The whiteboard behind them is turned "
            "at an angle and out of focus, with no readable writing on it."),

    'k09': (['tamura', 'yamada'],
            "Interior, the office, daytime. MEDIUM SHOT. In the foreground the young worker has just turned "
            "from the phone, his face lit up, one fist half raised. Behind him the president stands in the "
            "doorway with a quiet smile, and a woman in a beige cardigan has risen from her desk with both "
            "hands to her mouth. Bright natural light, a sense of the room coming alive."),

    'k10': (['tamura'],
            "Interior of the factory floor, morning. WIDE SHOT. The president stands in the middle distance "
            "in his navy work jacket, seen from behind and slightly to the side, looking toward the open "
            "factory gate where strong morning daylight floods in. Workers move at their benches on either "
            "side, softly out of focus. Dust motes in the light. Hopeful, expansive."),
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
    dst = os.path.join(OUT, name + '.png')
    if os.path.exists(dst):
        return name, 'cached'
    chars, shot = SHOTS[name]
    prompt = f"{shot}\n\n{REF_NOTE}\n\n{STYLE}"

    files = [os.path.join(REFS, c + '.png') for c in chars]
    boundary = '----kf'
    body = b''
    for f in files:
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="image[]"; '
                 f'filename="{os.path.basename(f)}"\r\nContent-Type: image/png\r\n\r\n').encode()
        body += io.open(f, 'rb').read() + b'\r\n'
    for k, v in (('model', 'gpt-image-2'), ('prompt', prompt), ('size', '1536x1024'), ('quality', 'high'), ('n', '1')):
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    body += f'--{boundary}--\r\n'.encode()

    req = urllib.request.Request('https://api.openai.com/v1/images/edits', data=body,
                                 headers={'Authorization': 'Bearer ' + KEY,
                                          'Content-Type': f'multipart/form-data; boundary={boundary}'})
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.load(r)
    item = d['data'][0]
    raw = base64.b64decode(item['b64_json']) if item.get('b64_json') else urllib.request.urlopen(item['url']).read()

    im = Image.open(io.BytesIO(raw)).convert('RGB')
    h = int(im.width * 9 / 16)                       # 3:2 で返るので中央を 16:9 に
    top = (im.height - h) // 2
    im.crop((0, top, im.width, top + h)).resize((1280, 720), Image.LANCZOS).save(dst)
    return name, 'new'


def main():
    os.makedirs(OUT, exist_ok=True)
    names = [a for a in sys.argv[1:] if not a.startswith('-')] or list(SHOTS)

    def safe(n):
        try:
            return make(n)
        except Exception as e:
            return n, 'FAILED ' + str(e)[:160]

    with ThreadPoolExecutor(max_workers=4) as ex:
        for name, how in ex.map(safe, names):
            print(f'{name:5s} {how}')


if __name__ == '__main__':
    main()
