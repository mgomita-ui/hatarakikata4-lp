#!/usr/bin/env bash
# 締めの後ろに足す「ライバル講師陣」6秒。開始画像は rival_start.png（廊下を歩いてくる5人・静止画ゲートでユーザー選択）。
#   bash tools/gen-koby2-rival.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMG="$ROOT/media/cine/koby/v2"; OUT="$ROOT/media/cine/koby/v2clip"
mkdir -p "$OUT"
higgsfield account status | head -1
f="$OUT/rival.mp4"; log="$OUT/rival.log"
P="Live-action cinematic shot, one continuous take, realistic motion, consistent faces and wardrobe, no text, no subtitles, no logos. The start image fixes the corridor, the lighting, the camera and all five people. The five rival instructors walk slowly and confidently toward the low camera down the dim concrete corridor, coats swinging. The big curly-haired bearded LEADER in the centre throws his head back and laughs out loud with a huge open-mouthed grin, then looks straight into the camera, still grinning, jaw moving as if shouting a line. The others keep walking beside him with calm, cocky expressions. Locked-off low-angle camera, no cut, no zoom."
higgsfield generate create seedance_2_5 --mode omni_reference --duration 6 --aspect-ratio 16:9 \
  --resolution 1080p --generate-audio false --start-image "$IMG/rival_start.png" --prompt "$P" \
  --wait --wait-timeout 25m > "$log" 2>&1
u=$(grep -oE 'https://[^ ]+\.mp4' "$log" | tail -1)
if [ -z "$u" ]; then echo "  !! FAIL rival: $(grep -m1 -iE 'error|not_enough|fail|timeout|invalid' "$log" | cut -c1-220)"; exit 1; fi
curl -sSL -o "$f.dl" "$u" && ffmpeg -v error -i "$f.dl" -f null - 2>/dev/null && mv "$f.dl" "$f" && echo "  ok rival $(du -h "$f"|cut -f1)"
higgsfield account status | head -1
