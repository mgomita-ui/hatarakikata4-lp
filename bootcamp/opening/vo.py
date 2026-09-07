# -*- coding: utf-8 -*-
"""script.json の各行を TTS で生成し、整音して vo/ に置き、実測尺を書き戻す。

  python bootcamp/opening/vo.py           # 未生成の行だけ作る
  python bootcamp/opening/vo.py --check   # 生成済みを speech2text にかけて読み間違いを探す
  python bootcamp/opening/vo.py --force   # 作り直す

声は tools/README.md の実測比較の結論に従い ElevenLabs / Arthur。
Inworld は演技指示のパラメータが無く抑揚が平坦（F0変動 0.294）で口上に向かない。
ElevenLabs は前後の無音を付けないので、silenceremove は保険として軽くかけるだけ。
"""
import json, os, subprocess, sys, io, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
VO = os.path.join(HERE, 'vo')
CLI = r'C:\Users\mgomi\AppData\Roaming\npm\higgsfield.cmd'

TRIM = ('silenceremove=start_periods=1:start_silence=0.04:start_threshold=-45dB:detection=peak,'
        'areverse,'
        'silenceremove=start_periods=1:start_silence=0.10:start_threshold=-45dB:detection=peak,'
        'areverse,'
        'loudnorm=I=-16:TP=-1.5:LRA=9,aresample=48000')


def hf(*args):
    p = subprocess.run([CLI, *args], capture_output=True)
    out = p.stdout.decode('utf-8', 'replace').strip()
    if p.returncode != 0:
        raise RuntimeError(f'{args[:3]}: {p.stderr.decode("utf-8", "replace")[:400]}')
    return json.loads(out)


def wait(jid):
    """CLI の wait は長尺で自前タイムアウトして非ゼロ終了する。待ち直すだけにする。"""
    for _ in range(90):
        try:
            r = hf('generate', 'wait', jid, '--json')
        except RuntimeError:
            time.sleep(4)
            continue
        if r.get('status') == 'completed' and r.get('result_url'):
            return r['result_url']
        if r.get('status') in ('failed', 'canceled'):
            raise RuntimeError(f'{jid} {r.get("status")}')
        time.sleep(3)
    raise RuntimeError(f'{jid} timeout')


def dur(path):
    p = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'csv=p=0', path], capture_output=True, text=True)
    return round(float(p.stdout.strip()), 3)


def make(line, v):
    dst = os.path.join(VO, line['id'] + '.wav')
    if os.path.exists(dst):
        return line['id'], dur(dst), 'cached'
    jid = hf('generate', 'create', v['model'], '--prompt', line['say'],
             '--variant', v['variant'], '--voice-id', v['voice_id'],
             '--voice-type', 'preset', '--json')[0]
    url = wait(jid)
    raw = os.path.join(VO, '_' + line['id'] + os.path.splitext(url.split('?')[0])[1])
    urllib.request.urlretrieve(url, raw)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', raw, '-af', TRIM, '-ac', '1', dst],
                   check=True)
    os.remove(raw)
    return line['id'], dur(dst), 'new'


def check(lines):
    """生成した音声を書き起こして、読み間違いを目で確認できるようにする。"""
    for l in lines:
        f = os.path.join(VO, l['id'] + '.wav')
        if not os.path.exists(f):
            continue
        up = hf('upload', 'create', f, '--json')
        aid = up[0] if isinstance(up, list) else (up.get('id') or up.get('media_id'))
        jid = hf('generate', 'create', 'speech2text', '--audio-references', str(aid), '--json')[0]
        url = wait(jid)
        got = urllib.request.urlopen(url).read().decode('utf-8', 'replace').strip()
        print(f'--- {l["id"]}')
        print(f'  台本: {l["say"]}')
        print(f'  実音: {got[:200]}')


def main():
    os.makedirs(VO, exist_ok=True)
    p = os.path.join(HERE, 'script.json')
    d = json.load(open(p, encoding='utf-8'))

    if '--force' in sys.argv:
        for f in os.listdir(VO):
            os.remove(os.path.join(VO, f))
    if '--check' in sys.argv:
        check(d['lines'])
        return

    with ThreadPoolExecutor(max_workers=5) as ex:
        res = list(ex.map(lambda l: make(l, d['voice']), d['lines']))

    by = {r[0]: r[1] for r in res}
    total = 0.0
    for lid, sec, how in res:
        total += sec
        print(f'{lid}  {sec:6.2f}s  {how}')
    print(f'---- narration total {total:.2f}s')
    for l in d['lines']:
        l['dur'] = by[l['id']]
    json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
