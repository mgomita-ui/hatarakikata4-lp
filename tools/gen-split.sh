#!/usr/bin/env bash
# 冒頭の「むかし / いま」比較カットを左右分割で作るための素材を生成する。
#
#   bash tools/gen-split.sh          # 足りないものだけ生成（再開可能）
#
# 考え方:
#   順番に見せる方式（旧3秒 → 新3秒）は、視聴者に記憶での比較を強いるうえ、
#   旧カットの方が絵として綺麗だと「昔の方が良かった」に読めてしまった。
#   左右に並べれば比較は一瞬で済み、同じ18秒で3組が6組になる。
#
#   左右half は 960x1080（縦長 8:9）なので、素材は 9:16 で作って中央を切る。
#   16:9 から切ると構図の大半を捨てることになる。
#   半分の幅でも読めるよう、寄りの構図・表情で「つらい / 楽」を出すこと。
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/media/cine/split"; mkdir -p "$OUT"
JOBS=${JOBS:-4}          # 同時に投げる数
BASE="Vertical cinematic photorealistic shot, Japanese setting, shallow depth of field, no text, no subtitles, no watermark. "

gen(){  # gen <name> <prompt>
  local f="$OUT/$1.mp4"
  [ -s "$f" ] && { echo "  skip $1"; return; }
  local u
  u=$(higgsfield generate create kling2_6 --duration 5 --aspect-ratio 9:16 \
        --prompt "$BASE$2" --wait --wait-timeout 15m 2>&1 \
        | grep -oE 'https://[^ ]+\.mp4' | tail -1)
  [ -z "$u" ] && { echo "  !! FAIL $1"; return; }
  curl -sSL -o "$f.dl" "$u" && ffmpeg -v error -i "$f.dl" -f null - 2>/dev/null \
    && mv "$f.dl" "$f" && echo "  ok $1 $(du -h "$f" | cut -f1)" \
    || echo "  !! 壊れたダウンロード $1"
}

# 1 場所 / 2 時間 / 3 選択肢 / 4 速さ / 5 手続き / 6 移動
# a = むかし(不便の痛み)  b = いま(便利の楽さ)
run(){ case $1 in
 1a) gen 1a "a woman in a coat standing alone in front of a closed shop shutter at night, her hand dropping to her side, shoulders sinking with disappointment, cold street lights, rain-damp pavement";;
 1b) gen 1b "a woman lying in bed in a dark bedroom at night, her face softly lit by her phone screen, a small relaxed smile as she taps to order something, warm screen glow, cozy duvet";;
 2a) gen 2a "a man sitting stiffly on a sofa in front of an old television, glancing impatiently at the wall clock, waiting for a program to start, dim living room, evening";;
 2b) gen 2b "a man seated by a train window wearing earphones, smiling while watching a video on his phone, daylight passing outside, relaxed posture";;
 3a) gen 3a "a woman facing an almost empty store shelf, holding the last remaining box, brow furrowed with disappointment, harsh fluorescent store lighting";;
 3b) gen 3b "a woman at a kitchen table comparing many product options side by side on a laptop screen, calm satisfied expression, soft morning light, coffee cup";;
 4a) gen 4a "a man at a desk holding a telephone handset to his ear, kept waiting on hold, sighing with a tired expression, stacks of paper, dull office lighting";;
 4b) gen 4b "a man looking at his phone and immediately breaking into a smile as a reply arrives, bright cafe window light, relaxed shoulders";;
 5a) gen 5a "a tired woman standing in a long queue at a public office counter, clutching paperwork, harsh institutional lighting, rows of waiting people";;
 5b) gen 5b "a woman relaxing on a sofa at home, finishing a task with a few taps on her phone, soft warm home lighting, calm satisfied expression";;
 6a) gen 6a "a commuter pressed against the door glass of a packed rush-hour train, exhausted resigned expression, harsh morning light";;
 6b) gen 6b "a woman at home smiling and talking with colleagues on a laptop video call, houseplants and warm daylight, relaxed and unhurried";;
esac }

ALL="1a 1b 2a 2b 3a 3b 4a 4b 5a 5b 6a 6b"
n=0
for k in ${*:-$ALL}; do
  run "$k" &
  n=$((n+1)); [ $((n % JOBS)) -eq 0 ] && wait
done
wait
echo "--- 生成結果"; ls -la "$OUT"/*.mp4 2>/dev/null | wc -l
