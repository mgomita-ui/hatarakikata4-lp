# -*- coding: utf-8 -*-
"""
配信する opening.m4a を再デコードして技術QAを行う。

  python tools/audio-qc.py

エンコード前の WAV で合格しても、AAC の先頭パディングや末尾処理で
実再生の同期はずれる。必ず「配信するファイル」を測ること。

検査項目:
  1. 尺        narration.json の total を満たしているか
  2. 内容      Whisper で文字起こしし、台本(say)と照合。脱落・誤読を検出
  3. 音量      統合ラウドネス(LUFS) と true peak
  4. 無音      冒頭・末尾の欠けと、途中の異常に長い無音

注意: これは「技術QA」であって演出品質の保証ではない。
      口上としての格好よさは人が聴いて判断すること。
"""
import json, os, re, subprocess, sys, io, difflib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIX = os.path.join(ROOT, 'media', 'cine', 'opening.m4a')
NAR = os.path.join(ROOT, 'tools', 'narration.json')


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, errors='replace', **kw)


def norm(s):
    """比較用に正規化: 記号・空白を落とし、カナと英字の揺れを吸収する"""
    s = s.lower()
    for a, b in (('アマゾン', 'amazon'), ('ユーチューブ', 'youtube'), ('エーアイ', 'ai'),
                 ('よんてんゼロ', '4.0'), ('いま', '今'), ('ひとつ', '一つ')):
        s = s.replace(a, b)
    return re.sub(r'[、。「」！？　\s・\-–—ー…]', '', s)


def main():
    if not os.path.exists(MIX):
        sys.exit('ミックスが見つかりません: ' + MIX)
    d = json.load(open(NAR, encoding='utf-8'))
    ng = []

    # --- 1. 尺 ---
    dur = float(sh(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                    '-of', 'csv=p=0', MIX]).stdout.strip())
    need = d['total']
    ok = dur >= need - 0.05
    print(f"尺        {dur:.2f}s / 必要 {need}s  {'OK' if ok else '★不足'}")
    if not ok: ng.append('尺不足')

    # --- 3. 音量 ---
    r = sh(['ffmpeg', '-v', 'info', '-i', MIX, '-af',
            'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-']).stderr
    m = re.search(r'\{[^{}]*"input_i"[^{}]*\}', r, re.S)
    if m:
        j = json.loads(m.group(0))
        I, TP = float(j['input_i']), float(j['input_tp'])
        okI, okTP = -17.5 <= I <= -13.0, TP <= -0.8
        print(f"ラウドネス {I:.1f} LUFS  {'OK' if okI else '★範囲外(-17.5〜-13)'}")
        print(f"true peak {TP:.1f} dBTP  {'OK' if okTP else '★過大(-0.8以下)'}")
        if not okI: ng.append('ラウドネス')
        if not okTP: ng.append('true peak')

    # --- 4. 無音 ---
    r = sh(['ffmpeg', '-v', 'info', '-i', MIX, '-af',
            'silencedetect=n=-45dB:d=1.2', '-f', 'null', '-']).stderr
    sil = [(float(a), float(b)) for a, b in
           zip(re.findall(r'silence_start: ([\d.]+)', r),
               re.findall(r'silence_duration: ([\d.]+)', r))]
    long = [(a, b) for a, b in sil if b >= 1.8]
    print(f"長い無音   {len(long)} 箇所" + (''.join(f"  {a:.1f}s({b:.1f}s)" for a, b in long[:4])))
    if long: ng.append('長い無音')

    # --- 2. 内容（Whisper） ---
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        print("文字起こし  スキップ（OPENAI_API_KEY なし）")
    else:
        out = os.path.join(ROOT, 'tools', '.qc-transcript.txt')
        r = sh(['curl', '-s', 'https://api.openai.com/v1/audio/transcriptions',
                '-H', f'Authorization: Bearer {key}',
                '-F', f'file=@{MIX}', '-F', 'model=whisper-1',
                '-F', 'language=ja', '-F', 'response_format=text', '-o', out])
        got = norm(open(out, encoding='utf-8').read()) if os.path.exists(out) else ''
        want = norm(''.join(l['say'] for l in d['lines']))
        ratio = difflib.SequenceMatcher(None, want, got).ratio()
        # 表記ゆれ(いまは/今は, アマゾン/amazon)で落とさないよう、行ごとの最良一致で判定する
        miss = []
        for l in d['lines']:
            w = norm(l['say'])
            best = max((difflib.SequenceMatcher(None, w, got[i:i+len(w)+6]).ratio()
                        for i in range(0, max(1, len(got) - len(w) + 7))), default=0)
            if best < 0.55:
                miss.append((l['say'], best))
        okT = ratio >= 0.75 and not miss
        print(f"文字起こし 一致率 {ratio*100:.1f}%  欠落 {len(miss)} 行  {'OK' if okT else '★要確認'}")
        for t, b in miss[:5]:
            print(f"           欠落候補(一致{b*100:.0f}%): {t}")
        if not okT: ng.append('内容照合')

    print('-' * 46)
    print('技術QA 合格' if not ng else '技術QA 不合格: ' + ', '.join(ng))
    print('※ 演出としての良し悪しは測れない。最終判断は聴取で。')
    return 1 if ng else 0


if __name__ == '__main__':
    sys.exit(main())
