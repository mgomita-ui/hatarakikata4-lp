#!/usr/bin/env bash
# 配信中のクリップを、携帯のハードウェアデコーダで確実に再生できる H.264 に作り直す。
#   bash tools/recompat.sh          # 検証して media/cine/_compat に出力
#   bash tools/recompat.sh apply    # 差し替え
#
# 経緯(2026-09-07): veryslow が参照フレーム16枚を使い 1080p で level 5.1 になっていた。
# 携帯は 1080p を level 4.1〜4.2(参照4枚)までしか保証せず、遠い参照を要求する最初の
# フレームで映像だけが止まった(音声は続く。倍速にしても同じ位置で止まる)。
# 既に最適化済みのファイルからの再エンコード(2世代目)なので CRF は少し甘く 22 にする。
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/media/cine"; OUT="$SRC/_compat"; mkdir -p "$OUT"
CLIPS=$(python - "$ROOT/tools/narration.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
print(' '.join(s['clip'] for s in d['scenes'] if s['clip']))
PY
)
if [ "${1:-}" = "apply" ]; then
  n=0; for f in "$OUT"/*.mp4; do cp "$f" "$SRC/$(basename "$f")"; n=$((n+1)); done
  echo "$n 本を差し替えました。"; exit 0
fi
printf "%-9s %7s %7s %6s %6s  %s\n" CLIP 元MB 後MB level VMAF 判定
echo "------------------------------------------------------"
NG=""
for c in $CLIPS; do
  in="$SRC/$c.mp4"; out="$OUT/$c.mp4"
  ffmpeg -y -v error -i "$in" -c:v libx264 -crf 22 -preset slow \
    -profile:v high -level 4.1 -x264-params ref=4:bframes=2 \
    -pix_fmt yuv420p -movflags +faststart -an "$out" || { echo "$c: エンコード失敗"; NG="$NG $c"; continue; }
  lvl=$(ffprobe -v error -select_streams v:0 -show_entries stream=level -of csv=p=0 "$out")
  v=$(ffmpeg -v info -i "$out" -i "$in" -lavfi libvmaf -f null - 2>&1 | grep -oE 'VMAF score: [0-9.]+' | grep -oE '[0-9.]+$')
  dec=$(ffmpeg -v error -i "$out" -f null - 2>&1 | head -1)
  ok="OK"; [ "$lvl" -gt 41 ] && ok="★level"; [ -n "$dec" ] && ok="★decode"
  awk -v v="${v:-0}" 'BEGIN{exit !(v>=93)}' || ok="★VMAF"
  [ "$ok" != "OK" ] && NG="$NG $c"
  printf "%-9s %7.2f %7.2f %6s %6.1f  %s\n" "$c" "$(stat -c%s "$in" | awk '{print $1/1048576}')" \
    "$(stat -c%s "$out" | awk '{print $1/1048576}')" "$(echo "$lvl" | awk '{print $1/10}')" "${v:-0}" "$ok"
done
echo "------------------------------------------------------"
if [ -n "$NG" ]; then echo "★ 要確認:$NG"; exit 1; fi
echo "全クリップ level 4.1 / VMAF 93 以上。問題なければ: bash tools/recompat.sh apply"
