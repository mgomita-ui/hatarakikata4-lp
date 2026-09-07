# -*- coding: utf-8 -*-
"""作り直した manga2 v7 のコマを Seedance 2.0 Mini でアニメ化する（anim3/*.mp4）。

  python bootcamp/movie/anime2.py          # 未生成のカットだけ
  python bootcamp/movie/anime2.py c17      # 指定したカットだけ

anime.py（旧2話用）との違いは素材だけ。動きを禁止しないのが要点で、
「subtle motion only」と縛ると静止画が漂うだけになり、間延びの原因になる。
"""
import json, os, subprocess, sys, io, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'anim3')
CLI = r'C:\Users\mgomi\AppData\Roaming\npm\higgsfield.cmd'

STYLE = (' Japanese anime, hand-drawn cel animation. Keep the original line art, colour palette and '
         'character design exactly. No style change, no text or captions added, no watermark. '
         'Any Japanese text already in the frame stays exactly as it is and does not deform.')

MOVE = {
    'c02': 'The young worker lowers the telephone receiver from his ear and his shoulders drop; behind him '
           'the seated president slowly raises his eyes. Slow push in.',
    'c03': 'The middle-aged man in the work jacket lowers his gaze in thought, then his eyes harden as he '
           'understands something. His hand stays at his chin. Very slow push in.',
    'c04': 'The younger man in glasses finishes speaking and looks away; the older man cannot answer and '
           'lowers his eyes. A small, heavy pause between them.',
    'c05': 'The laptop screen glows; the cyan avatar on it breathes and blinks once. The three printed '
           'proposal sheets on the desk stay perfectly still. Slow push in on the screen.',
    'c09': 'The man pulls his jacket on over one shoulder and turns toward the door, decided; the two staff '
           'in the doorway look up at him, surprised. The camera follows him slightly.',
    'c11': 'The man stares at the laptop screen, his eyes widening as he realises it worked; the woman '
           'beside him gives a small satisfied nod. Slow push in.',
    'c17': 'A tear wells up and rolls slowly down his cheek; he blinks, and his smile deepens. The camera '
           'pushes in very slowly.',
    'c18': 'The man speaks quietly and lifts his head, resolved; the woman beside him listens, then gives a '
           'small warm nod. Almost no camera movement.',
    'c22': 'The man alone rests his hand on the laptop and lets out a breath, a quiet smile spreading. '
           'Very slow push in.',
    'c23': 'The president looks toward the open factory gate and the daylight; behind him workers move at '
           'their benches. Slow push in toward the light.',
}

DUR = {'c02': 5, 'c03': 5, 'c04': 5, 'c05': 5, 'c09': 5,
       'c11': 5, 'c17': 5, 'c18': 5, 'c22': 5, 'c23': 5}


def hf(*args):
    p = subprocess.run([CLI, *args], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f'{args[:3]}: {p.stderr.decode("utf-8", "replace")[:300]}')
    return json.loads(p.stdout.decode('utf-8', 'replace').strip())


def wait(jid):
    """CLI の wait は長尺で自前タイムアウトして非ゼロ終了する。待ち直すだけにする。"""
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


def one(name):
    dst = os.path.join(SRC, name + '.mp4')
    if os.path.exists(dst):
        return name, 'cached'
    jid = hf('generate', 'create', 'seedance_2_0_mini',
             '--start-image', os.path.join(SRC, name + '.png'),
             '--duration', str(DUR[name]), '--resolution', '720p',
             '--aspect-ratio', '16:9', '--genre', 'drama',
             '--prompt', MOVE[name] + STYLE, '--json')[0]
    urllib.request.urlretrieve(wait(jid), dst)
    return name, 'new'


def main():
    names = [a for a in sys.argv[1:] if not a.startswith('-')] or list(MOVE)

    def safe(n):
        try:
            return one(n)
        except Exception as e:                 # 1カットの失敗で他を巻き添えにしない
            return n, 'FAILED ' + str(e)[:120]

    with ThreadPoolExecutor(max_workers=4) as ex:
        for name, how in ex.map(safe, names):
            print(f'{name:6s} {how}')


if __name__ == '__main__':
    main()
