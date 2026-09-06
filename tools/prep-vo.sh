#!/usr/bin/env bash
# TTS の生データを整える:
#   1. 前後の無音を落とす（Inworld は 0.3〜0.6 秒の余白を付けてくる）
#   2. ラウドネスを揃える（-18 LUFS / ピーク -1.5dBTP）
#   3. 実測尺を tools/vo-durations.tsv に書き出す（layout.py が推定値の代わりに使う）
#   bash tools/prep-vo.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RAW="$ROOT/media/cine/vo"; OUT="$RAW/n"; mkdir -p "$OUT"
: > "$ROOT/tools/vo-durations.tsv"
n=0
for f in "$RAW"/*.wav; do
  [ -f "$f" ] || continue
  b=$(basename "$f" .wav)
  ffmpeg -y -v error -i "$f" \
    -af "silenceremove=start_periods=1:start_silence=0.05:start_threshold=-45dB:detection=peak,areverse,silenceremove=start_periods=1:start_silence=0.05:start_threshold=-45dB:detection=peak,areverse,loudnorm=I=-18:TP=-1.5:LRA=11" \
    -ar 48000 -ac 1 "$OUT/$b.wav"
  raw=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")
  new=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/$b.wav")
  printf "%s\t%s\n" "$b" "$new" >> "$ROOT/tools/vo-durations.tsv"
  awk -v b="$b" -v r="$raw" -v x="$new" 'BEGIN{printf "  %s  %5.2fs -> %5.2fs (無音 %.2fs 除去)\n", b, r, x, r-x}'
  n=$((n+1))
done
echo "$n 本を整音しました。実測尺: tools/vo-durations.tsv"
