# -*- coding: utf-8 -*-
"""
ナレーション(media/cine/vo/n/*.wav)と音楽を1本の opening.m4a に焼き込む。

  python tools/build-audio.py            # 既定の music/C.m4a を使う
  python tools/build-audio.py --music A  # 別案で作る

なぜ1本に焼き込むか:
  再生側は <audio> ひとつのままでよく、index.html の同期ロジックを触らずに済む。
  ナレーションと音楽を別トラックにすると 2 要素の時刻合わせが必要になり、
  モバイルのバッファリング差でズレる。

処理:
  1. 各行を cue 秒の位置に置く。スロットに収まらない行だけ atempo で詰める
     (ピッチは変わらない。上限 MAX_TEMPO)
  2. ナレーションのバスを作り、それをサイドチェインにして音楽を自動で下げる
  3. 音楽にフェードイン/アウトを掛けて合成
"""
import json, subprocess, sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VO   = os.path.join(ROOT, 'media', 'cine', 'vo', 'n')
MUS  = os.path.join(ROOT, 'media', 'cine', 'music')
OUT  = os.path.join(ROOT, 'media', 'cine', 'opening.m4a')
MAX_TEMPO = 1.30      # これ以上は早口に聞こえるので詰めない（尺を食い込ませる）
DUCK_DB   = 7         # ナレーション中に音楽を下げる量
NO_VO     = '--no-vo' in sys.argv   # 仮ナレを鳴らさない（音楽＋効果音のみ）

def dur(p):
    return float(subprocess.check_output(
        ['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',p]).decode().strip())

def main(track='C'):
    d = json.load(open(os.path.join(ROOT,'tools','narration.json'), encoding='utf-8'))
    L, TOTAL = d['lines'], d['total']
    music = os.path.join(MUS, f'{track}.m4a')
    if not os.path.exists(music): sys.exit(f'音楽が見つかりません: {music}')

    # カットインのコマ出現時刻（build-montage.py の PANELS と一致させること）
    PANEL_AT = [0.00, 0.22, 0.44, 0.66, 0.88, 1.10]
    cut = next((sc for sc in d['scenes'] if sc.get('clip') == 'cutin'), None)
    sfx = []
    if cut:
        hit = os.path.join(MUS, '..', 'sfx', 'hit.m4a')
        imp = os.path.join(MUS, '..', 'sfx', 'impact.m4a')
        if os.path.exists(imp):
            # 直前の台詞(「世は、まさに――」)に被せないこと。台詞が終わってから、
            # タイトルコールの語頭を埋めない位置に置く＝ごく短い溜めになる。
            prev_end = max((l['cue'] + 0.0 for l in L if l['cue'] < cut['t0']), default=0)
            at = max(prev_end, cut['t0'] - 0.22)
            sfx.append((imp, min(at, cut['t0'] - 0.12), 0.85))    # 溜めの一撃
        if os.path.exists(hit):
            for a in PANEL_AT:
                sfx.append((hit, cut['t0'] + a, 0.42))            # コマ出現の軽い打音

    inputs, filters, labels = ['-i', music], [], []
    end = 0.0
    for i, l in enumerate(L):
        f = os.path.join(VO, f'{i:02d}.wav')
        if not os.path.exists(f): sys.exit(f'音声が足りません: {f}')
        slot = (L[i+1]['cue'] if i+1 < len(L) else TOTAL) - l['cue']
        sp   = dur(f)
        tempo = min(max(sp/slot, 1.0), MAX_TEMPO)
        inputs += ['-i', f]
        ch = f"[{i+1}:a]aresample=48000"
        if tempo > 1.001: ch += f",atempo={tempo:.4f}"
        ch += f",adelay={int(l['cue']*1000)}:all=1[v{i}]"
        filters.append(ch); labels.append(f'[v{i}]')
        end = max(end, l['cue'] + sp/tempo)

    total = round(max(TOTAL, end) + 0.6, 2)
    # --no-vo: 仮ナレ(TTS)を鳴らさず、音楽と効果音だけで書き出す(声優の音声が来るまでの公開用)。
    # 行の配置と尺はそのまま使うので、字幕の同期は変わらない。
    novo = ',volume=0' if NO_VO else ''
    filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:dropout_transition=0{novo}[vo]")

    slabels = []
    for j, (path, at, gain) in enumerate(sfx):
        idx = len(L) + 1 + j
        inputs += ['-i', path]
        # 打音は先頭の立ち上がりが命なので、頭を削らずそのまま置く
        filters.append(f"[{idx}:a]aresample=48000,volume={gain},"
                       f"adelay={int(at*1000)}:all=1[x{j}]")
        slabels.append(f'[x{j}]')
    if slabels:
        filters.append(f"{''.join(slabels)}amix=inputs={len(slabels)}:normalize=0:"
                       f"dropout_transition=0,apad=whole_dur={total}[sfx]")
    filters.append(f"[vo]apad=whole_dur={total},asplit=2[vo1][vosc]")
    # 音楽: 尺合わせ + 前後フェード + ナレーションでダッキング
    filters.append(f"[0:a]aresample=48000,atrim=0:{total},apad=whole_dur={total},"
                   f"afade=t=in:st=0:d=1.2,afade=t=out:st={total-2.2:.2f}:d=2.0,volume=0.85[mus]")
    filters.append(f"[mus][vosc]sidechaincompress=threshold=0.05:ratio={DUCK_DB}:attack=25:release=350:makeup=1[duck]")
    mixin = "[duck][vo1]" + ("[sfx]" if slabels else "")
    n_mix = 3 if slabels else 2
    filters.append(f"{mixin}amix=inputs={n_mix}:normalize=0:dropout_transition=0,"
                   f"alimiter=limit=0.95,loudnorm=I=-16:TP=-1.5:LRA=11[out]")

    cmd = ['ffmpeg','-y','-v','error'] + inputs + \
          ['-filter_complex', ';'.join(filters), '-map','[out]',
           '-c:a','aac','-b:a','128k','-ar','48000','-ac','2',
           '-movflags','+faststart', OUT]
    print(f"音楽 {track} / ナレーション {len(L)} 行 / 全長 {total} 秒")
    subprocess.check_call(cmd)
    print(f"→ {OUT}  {os.path.getsize(OUT)/1048576:.2f} MB  {dur(OUT):.2f}s")

if __name__ == '__main__':
    t = 'C'
    if '--music' in sys.argv: t = sys.argv[sys.argv.index('--music')+1]
    main(t)
