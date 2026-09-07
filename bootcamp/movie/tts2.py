# -*- coding: utf-8 -*-
"""lines.json のナレーションを Higgsfield TTS で生成し、voice/ に wav を落として尺を記録する。

  python bootcamp/movie/tts.py            # 未生成の行だけ作る
  python bootcamp/movie/tts.py --force    # 全部作り直す

生成済みの行は voice/<id>.wav の有無で判定するので、途中で落ちても再実行すれば続きから。
"""
import json, os, subprocess, sys, io, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
VOICE = os.path.join(HERE, 'voice2')
CLI = r'C:\Users\mgomi\AppData\Roaming\npm\higgsfield.cmd'


def hf(*args):
    """higgsfield CLI を叩いて JSON を返す。CLI は UTF-8 で出力する。"""
    p = subprocess.run([CLI, *args], capture_output=True)
    out = p.stdout.decode('utf-8', 'replace').strip()
    if p.returncode != 0:
        raise RuntimeError(f'{args[:3]} failed: {p.stderr.decode("utf-8", "replace")[:400]}')
    return json.loads(out)


def duration(path):
    p = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'csv=p=0', path], capture_output=True, text=True)
    return round(float(p.stdout.strip()), 3)


def make(line, voices):
    dst = os.path.join(VOICE, line['id'] + '.wav')
    if os.path.exists(dst):
        return line['id'], duration(dst), 'cached'
    jid = hf('generate', 'create', 'inworld_text_to_speech',
             '--prompt', line['say'], '--voice', voices[line['voice']], '--json')[0]
    for _ in range(60):
        res = hf('generate', 'wait', jid, '--json')
        if res.get('status') == 'completed' and res.get('result_url'):
            urllib.request.urlretrieve(res['result_url'], dst)
            return line['id'], duration(dst), 'new'
        if res.get('status') in ('failed', 'canceled'):
            raise RuntimeError(f'{line["id"]} {res.get("status")}')
        time.sleep(2)
    raise RuntimeError(f'{line["id"]} timed out')


def main():
    os.makedirs(VOICE, exist_ok=True)
    d = json.load(open(os.path.join(HERE, 'lines2.json'), encoding='utf-8'))
    if '--force' in sys.argv:
        for f in os.listdir(VOICE):
            os.remove(os.path.join(VOICE, f))

    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(lambda l: make(l, d['voices']), d['lines']))

    total = 0.0
    for lid, dur, how in results:
        total += dur
        print(f'{lid}  {dur:6.2f}s  {how}')
    print(f'---- narration total {total:.2f}s')

    by_id = dict((r[0], r[1]) for r in results)
    for l in d['lines']:
        l['dur'] = by_id[l['id']]
    json.dump(d, open(os.path.join(HERE, 'lines2.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
