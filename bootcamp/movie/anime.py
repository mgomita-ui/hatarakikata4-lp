# -*- coding: utf-8 -*-
"""漫画のコマを Seedance 2.0 Mini で本格的にアニメ化する（anim2/*.mp4）。

  python bootcamp/movie/anime.py          # 未生成のカットだけ
  python bootcamp/movie/anime.py a_face   # 指定したカットだけ

Kling との違いは end_image を受けられること。始点と終点の2枚を渡すと、
モデルが「その間の芝居」を作る。Kling(始点のみ)では静止画が漂うだけだった。

終点が無いカットは始点のみ＋動きの指示。動きを禁止しないのが要点で、
以前の「subtle motion only」という縛りが、そのまま間延びの原因だった。
"""
import json, os, subprocess, sys, io, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ANIM, OUT = os.path.join(HERE, 'anim'), os.path.join(HERE, 'anim2')
PAGES = os.path.join(HERE, '..', '..', 'manga2', 'pages')
CLI = r'C:\Users\mgomi\AppData\Roaming\npm\higgsfield.cmd'

STYLE = (' Japanese anime, hand-drawn cel animation. Keep the original line art, colour palette and '
         'character design exactly. No style change, no text or captions added, no watermark.')

# 終点フレーム。(ページ, x0,y0,x1,y1) を 16:9 に切って使う。
ENDS = {
    'c08': ('p13', 20, 1180, 587, 1499),    # 見積を見る → 出てきた紙を見る
    'a_trio': ('p05', 60, 400, 689, 754),   # 社員2人：パネル1 → パネル2（同じ2人の後の瞬間）
    # 'c06' は始点=終点を渡すと API が受け付けなかった。プロンプトで指を固定する。
}

MOVE = {
    'a_desk': 'The middle-aged factory owner slowly turns his gaze from the desk toward the window; '
              'warm sunset light drifts across the room. Slow push in.',
    'a_trio': 'Two young employees talk quietly in the office; they shift their weight and glance at '
              'each other. Natural in-between motion between the two frames.',
    'c03': 'The man sits at his desk, lowers his eyes, and his shoulders drop as he lets out a breath. '
           'His hand rests on the closed laptop. Slow push in.',
    'c04': 'The man pushes the door open and walks two steps into the meeting room; the seated people '
           'turn their heads to look at him. The camera follows him slightly.',
    'c05': 'The woman beside the whiteboard turns to face the room and lowers the marker. '
           'The writing on the whiteboard stays exactly as it is.',
    'c06': 'The woman holds up three fingers and breathes; a single small nod. The number of fingers '
           'never changes. Almost no other movement.',
    'c08': 'The man watches the laptop, then leans back, takes a printed sheet and looks down at it '
           'with a faint smile of realisation. Natural in-between motion between the two frames.',
    'a_face': 'A tear wells up and rolls slowly down his cheek; he blinks, and his smile deepens. '
              'The camera pushes in very slowly.',
    'c10': 'Three people look at a laptop at night; the older man in the work jacket nods once and '
           'says nothing. The younger man glances at him.',
}

DUR = {'a_desk': 10, 'a_trio': 5, 'c03': 10, 'c04': 10, 'c05': 5,
       'c06': 5, 'c08': 10, 'a_face': 10, 'c10': 5}


def hf(*args):
    p = subprocess.run([CLI, *args], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f'{args[:3]}: {p.stderr.decode("utf-8", "replace")[:300]}')
    return json.loads(p.stdout.decode('utf-8', 'replace').strip())


def wait(jid):
    for _ in range(180):
        try:
            r = hf('generate', 'wait', jid, '--json')
        except RuntimeError:
            time.sleep(5)
            continue
        if r.get('status') == 'completed' and r.get('result_url'):
            return r['result_url']
        if r.get('status') in ('failed', 'canceled'):
            raise RuntimeError(f'{jid} {r.get("status")}')
        time.sleep(4)
    raise RuntimeError(f'{jid} timeout')


def end_frame(name):
    """終点画像のパスを返す。ENDS に無ければ None、値が None なら始点と同じ絵。"""
    if name not in ENDS:
        return None
    spec = ENDS[name]
    if spec is None:
        return os.path.join(ANIM, name + '.png')
    dst = os.path.join(OUT, name + '_end.png')
    if not os.path.exists(dst):
        page, x0, y0, x1, y1 = spec
        Image.open(os.path.join(PAGES, page + '.jpg')).crop((x0, y0, x1, y1)) \
             .resize((1280, 720), Image.LANCZOS).save(dst)
    return dst


def one(name):
    dst = os.path.join(OUT, name + '.mp4')
    if os.path.exists(dst):
        return name, 'cached'
    args = ['generate', 'create', 'seedance_2_0_mini',
            '--start-image', os.path.join(ANIM, name + '.png'),
            '--duration', str(DUR[name]), '--resolution', '720p',
            '--aspect-ratio', '16:9', '--genre', 'drama',
            '--prompt', MOVE[name] + STYLE, '--json']
    e = end_frame(name)
    if e:
        args[5:5] = ['--end-image', e]
    jid = hf(*args)[0]
    urllib.request.urlretrieve(wait(jid), dst)
    return name, ('new +end' if e else 'new')


def main():
    os.makedirs(OUT, exist_ok=True)
    names = [a for a in sys.argv[1:] if not a.startswith('-')] or list(MOVE)
    def safe(n):
        try:
            return one(n)
        except Exception as e:                 # 1カットの失敗で他を巻き添えにしない
            return n, 'FAILED ' + str(e)[:120]

    with ThreadPoolExecutor(max_workers=4) as ex:
        for name, how in ex.map(safe, names):
            print(f'{name:9s} {how}')


if __name__ == '__main__':
    main()
