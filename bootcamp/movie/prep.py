# -*- coding: utf-8 -*-
"""TTS の生 wav から前後の無音を落として整音し、実測尺を lines.json に書き戻す。

Inworld の出力は行ごとに前後 0.25〜0.86 秒の無音が付く（tools/README.md 参照）。
11 行ぶんで 5〜9 秒の死に間になるので、ここで削ってからタイムラインを組む。

  python bootcamp/movie/prep.py
"""
import json, os, subprocess, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
RAW, OUT = os.path.join(HERE, 'voice'), os.path.join(HERE, 'voice_t')

TRIM = ('silenceremove=start_periods=1:start_silence=0.04:start_threshold=-45dB:detection=peak,'
        'areverse,'
        'silenceremove=start_periods=1:start_silence=0.12:start_threshold=-45dB:detection=peak,'
        'areverse,'
        'loudnorm=I=-16:TP=-1.5:LRA=9')


def duration(path):
    p = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'csv=p=0', path], capture_output=True, text=True)
    return round(float(p.stdout.strip()), 3)


def main():
    os.makedirs(OUT, exist_ok=True)
    d = json.load(open(os.path.join(HERE, 'lines.json'), encoding='utf-8'))
    before = after = 0.0
    for l in d['lines']:
        src, dst = os.path.join(RAW, l['id'] + '.wav'), os.path.join(OUT, l['id'] + '.wav')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', src, '-af', TRIM, dst], check=True)
        b, a = duration(src), duration(dst)
        before += b
        after += a
        l['dur'] = a
        print(f'{l["id"]}  {b:5.2f}s -> {a:5.2f}s  (-{b-a:.2f})')
    print(f'---- {before:.2f}s -> {after:.2f}s  (無音 {before-after:.2f}s を除去)')
    json.dump(d, open(os.path.join(HERE, 'lines.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
