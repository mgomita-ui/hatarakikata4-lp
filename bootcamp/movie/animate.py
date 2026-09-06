# -*- coding: utf-8 -*-
"""anim/*.png（フキダシを外した16:9のコマ）を Higgsfield で動かして anim/*.mp4 に落とす。

  python bootcamp/movie/animate.py a_face a_desk        # 指定したカットだけ
  python bootcamp/movie/animate.py --all                # shots.json の全カット

生成済み（anim/<key>.mp4 がある）はスキップするので、途中で落ちても再実行でよい。
プロンプトは shots.json に置く。コマは静止画なので「大きく動かさない」ことが要点で、
派手に動かすと絵柄が崩れて別人になる。
"""
import json, os, subprocess, sys, io, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ANIM = os.path.join(HERE, 'anim')
CLI = r'C:\Users\mgomi\AppData\Roaming\npm\higgsfield.cmd'

STYLE = (' Japanese anime manga illustration, keep the original drawing style and character '
         'design exactly, no style change, no morphing, no added text or captions, '
         'no camera shake, subtle natural motion only.')


def hf(*args):
    p = subprocess.run([CLI, *args], capture_output=True)
    out = p.stdout.decode('utf-8', 'replace').strip()
    if p.returncode != 0:
        raise RuntimeError(f'{args[:3]}: {p.stderr.decode("utf-8", "replace")[:400]}')
    return json.loads(out)


def one(key, shot):
    dst = os.path.join(ANIM, key + '.mp4')
    if os.path.exists(dst):
        return key, 'cached'
    jid = hf('generate', 'create', 'kling3_0_turbo',
             '--start-image', os.path.join(ANIM, key + '.png'),
             '--duration', str(shot.get('duration', 5)),
             '--resolution', '1080p', '--aspect-ratio', '16:9',
             '--prompt', shot['prompt'] + STYLE, '--json')[0]
    for _ in range(150):
        # CLI 側の wait は長尺ジョブで自前タイムアウトして非ゼロ終了する。
        # ここで諦めるとプール全体が落ちるので、待ち直すだけにする。
        try:
            res = hf('generate', 'wait', jid, '--json')
        except RuntimeError:
            time.sleep(5)
            continue
        if res.get('status') == 'completed' and res.get('result_url'):
            urllib.request.urlretrieve(res['result_url'], dst)
            return key, 'new'
        if res.get('status') in ('failed', 'canceled'):
            return key, 'FAILED ' + str(res.get('status'))
        time.sleep(3)
    return key, 'TIMEOUT'


def main():
    shots = json.load(open(os.path.join(HERE, 'shots.json'), encoding='utf-8'))
    keys = [a for a in sys.argv[1:] if not a.startswith('--')] or list(shots)
    with ThreadPoolExecutor(max_workers=4) as ex:
        for key, how in ex.map(lambda k: one(k, shots[k]), keys):
            print(f'{key:10s} {how}')


if __name__ == '__main__':
    main()
