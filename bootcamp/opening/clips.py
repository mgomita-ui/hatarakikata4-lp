# -*- coding: utf-8 -*-
"""anim/*.png を Higgsfield(Kling) で動かして anim/*.mp4 にする。

  python bootcamp/opening/clips.py          # 未生成のカットだけ
  python bootcamp/opening/clips.py window   # 指定したカットだけ

尺は script.json の実測ナレーション尺から決める（足りないとスローで伸ばすことになるため）。
動かしすぎると絵が崩れるので、動きは「1つだけ」書く。文字は生成させない。
"""
import json, os, subprocess, sys, io, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ANIM = os.path.join(HERE, 'anim')
CLI = r'C:\Users\mgomi\AppData\Roaming\npm\higgsfield.cmd'

STYLE = (' Live-action cinematic footage, photorealistic, keep the original framing and color grade, '
         'no style change, no morphing, no added text or captions or numbers, no camera shake, '
         'one single subtle motion only.')

MOVE = {
    'goldfish': 'The goldfish turns slowly in the bowl and the water ripples faintly. Everything else '
                'is still. Very slow push in.',
    'robot2025': 'The humanoid robot runs past with an unsteady, laboured stride; the background '
                 'spectators blur slightly. Static camera.',
    'robot2026': 'The humanoid robot runs past fast and smoothly with a powerful stride; strong motion '
                 'blur streaks the background. Static camera, slight slow motion.',
    'robotaxi': 'The self-driving taxi rolls forward through the frame; street light reflections slide '
                'across its wet body. The driver seat stays empty. Static camera.',
    'office': 'The employees type quietly at their desks with small natural movements. Nobody stands '
              'up, nobody turns around. Very slow push in.',
    'meeting': 'One person turns a page of the printed document. The others stay still, looking down. '
               'Nobody speaks, all mouths stay closed. Very slow push in.',
    'window': 'The man breathes slowly at the window; distant city lights shimmer. He does not turn '
              'around. Very slow push in.',
}


def hf(*args):
    p = subprocess.run([CLI, *args], capture_output=True)
    out = p.stdout.decode('utf-8', 'replace').strip()
    if p.returncode != 0:
        raise RuntimeError(f'{args[:3]}: {p.stderr.decode("utf-8", "replace")[:400]}')
    return json.loads(out)


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


def need(script):
    """カットごとに必要な素材尺（10秒 or 5秒）を、実測ナレーション尺から決める。"""
    out = {}
    for l in script['lines']:
        if l['clip'] in MOVE:
            out[l['clip']] = 10 if l['dur'] > 4.2 else 5
    return out


def one(name, seconds):
    dst = os.path.join(ANIM, name + '.mp4')
    if os.path.exists(dst):
        return name, 'cached'
    jid = hf('generate', 'create', 'kling3_0_turbo',
             '--start-image', os.path.join(ANIM, name + '.png'),
             '--duration', str(seconds), '--resolution', '1080p', '--aspect-ratio', '16:9',
             '--prompt', MOVE[name] + STYLE, '--json')[0]
    url = wait(jid)
    urllib.request.urlretrieve(url, dst)
    return name, f'new {seconds}s'


def main():
    d = json.load(open(os.path.join(HERE, 'script.json'), encoding='utf-8'))
    secs = need(d)
    names = [a for a in sys.argv[1:] if not a.startswith('-')] or list(secs)
    with ThreadPoolExecutor(max_workers=4) as ex:
        for name, how in ex.map(lambda n: one(n, secs[n]), names):
            print(f'{name:11s} {how}')


if __name__ == '__main__':
    main()
