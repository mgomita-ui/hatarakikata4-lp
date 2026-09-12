#!/usr/bin/env bash
# 検査で見つかった矛盾を直す動画生成。承認済みの開始画像だけを動かす。
#
#   bash tools/gen-koby2-fix.sh v18b v19b v24b v11c y1c v13c x1c
#   MAX=2 bash tools/gen-koby2-fix.sh ...     # 同時に走らせる本数（既定4）
#
# 尺は「必要尺＋in の余裕」で最小にする（5秒=45、6秒=54クレジット）。
#   v18b 必要4.2s → 5s   v19b 必要4.2s → 5s   v24b 必要3.6s → 5s
#   v11c 必要4.4s → 5s   y1c  必要5.4s → 6s   v13c 必要3.2s → 5s   x1c 必要4.6s → 6s
#
# 因果の台帳（ai-video-continuity 検査5）：
#   52.8 w2b で grip(赤髪, 営業.腕)=true → 72.4 w3b で false。
#   v18b / v19b はその間なので、赤髪の男は営業の腕を掴んだまま。
#
# 失敗したら理由を <カット>.log に残す。
#   2026-09-13、残高不足（not_enough_credits）を grep で捨てて「FAIL」としか出ず、原因の特定に手間取った。
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMG="$ROOT/media/cine/koby/v2"; OUT="$ROOT/media/cine/koby/v2clip"
mkdir -p "$OUT"
MAX=${MAX:-4}

LOOK="Live-action Japanese office drama, one continuous shot, restrained naturalistic performance, realistic body weight and object contact, consistent faces and wardrobe, DEEP FOCUS - sharp foreground to background. No text, no subtitles, no watermark, no logos. "
RED="The red-haired man keeps his SHORT swept-back red hair, black shirt and long CHARCOAL OVERCOAT throughout - never a suit jacket, never long hair. "

gen(){ # gen <name> <duration> <start.png> <prompt>
  local f="$OUT/$1.mp4" log="$OUT/$1.log" u
  [ -s "$f" ] && { echo "  skip $1"; return; }
  higgsfield generate create seedance_2_5 \
        --mode omni_reference --duration "$2" --aspect-ratio 16:9 \
        --resolution 1080p --generate-audio false \
        --start-image "$IMG/$3" --prompt "$LOOK$4" \
        --wait --wait-timeout 25m > "$log" 2>&1
  u=$(grep -oE 'https://[^ ]+\.mp4' "$log" | tail -1)
  if [ -z "$u" ]; then
    echo "  !! FAIL $1: $(grep -m1 -iE 'error|not_enough|fail|timeout' "$log" | cut -c1-220)"
    return
  fi
  curl -sSL -o "$f.dl" "$u" && ffmpeg -v error -i "$f.dl" -f null - 2>/dev/null \
    && mv "$f.dl" "$f" && echo "  ok $1 $(du -h "$f"|cut -f1)" || echo "  !! broken DL $1"
}

job(){ case "$1" in
 v18b) gen v18b 5 v18b_turn.png "${RED}The red-haired man keeps his grip on the navy-suited consultant's forearm the whole time and never lets go. Without hurry he turns his head away from the consultant and looks toward the seated president in the right foreground. The corner of his mouth lifts very slightly - calm, almost amused, not mocking. The consultant's held arm stays still. The seated woman and the navy-suited man behind them keep watching. The president does not move. Locked-off camera, no zoom, nobody walks between the camera and the grip.";;
 v19b) gen v19b 5 v19b_speak.png "${RED}Facing the seated president, the red-haired man speaks in a low, level voice, his jaw moving throughout, and gives one slow nod at the end of the sentence. His extended right hand stays closed around the navy sleeve at the right edge of frame the entire time - he does not let go and does not pull. His left hand stays at his side. The president in the left foreground stays still, listening. Locked-off camera over the president's shoulder, no zoom.";;
 v24b) gen v24b 5 v24b_laptop.png "The president steadies the base of the closed silver laptop with his left palm, hooks his right fingertips under the front edge of the lid and lifts it smoothly around the rear hinge to a normal working angle. The base stays flat on the dark wood table. The screen lights up and casts a soft glow on his light grey sleeves and white cuffs. His hands settle on either side of the keyboard. Locked-off camera, no zoom.";;
 v11c) gen v11c 5 v11c_before_stand.png "Starting fully seated, the young man in the grey shirt plants both feet, presses his palms on the table edge, lifts his hips clear of the seat and rises to full standing in one movement. His chair rolls back a few centimetres. The seated woman in the white blouse and the navy-suited man turn their heads up to him. The president in the right foreground turns his head toward him. The standing salesman stays where he is. Everyone else stays seated. Locked-off wide camera, no zoom.";;
 y1c) gen y1c 6 y1c_speak.png "The young man in the grey shirt draws a breath that lifts his chest, leans forward from the waist, brings his open hand up in front of him and speaks, his jaw moving throughout the shot. The seated woman in the white blouse and the navy-suited man keep their eyes on him. He ends leaning in, hand still raised, mid-sentence. Locked-off camera at his eye level - the framing stays at waist-up and never pushes into his face.";;
 v13c) gen v13c 5 v13c_president.png "The seated president in the light grey suit unfolds his hands, sits back against his chair so it rocks slightly, turns his head away from the young man and lowers his gaze to the signed document on the table. One hand comes up and rubs slowly across his mouth, then drops back to the table. The window wall and white wall behind him stay unchanged. Locked-off camera, no zoom.";;
 x1c) gen x1c 6 x1c_hat.png "${RED}The red-haired man closes his hand around the brim of the black fedora on the table, lifts it, raises it to his head and SETS IT ON, settling it with a small tug at the brim. He then turns his shoulders away from the table and takes one step toward the open floor on the left. The young man in the grey shirt behind him watches. The seated woman in the white blouse, the navy-suited man and the president in the light grey suit stay seated and follow him with their eyes. The standing salesman does not move. Locked-off wide camera, he moves within frame.";;
 # 俯瞰の書類カット。赤髪の男は右手で営業の腕を掴んだまま（52.8〜72.4）なので、書類に触れるのは左手。
 v20c) gen v20c 5 v20c_point.png "Overhead locked-off camera looking straight down at the dark wood table. The red-haired man's LEFT hand, in a CHARCOAL OVERCOAT sleeve with a BLACK shirt cuff, lowers from above; the extended index finger comes down onto the yellow highlighted line of the printed page and presses slightly, the paper shifting a millimetre under it. The hand then stays there, still. The dark wood table never changes colour. There are no other hands and no white shirt cuffs anywhere.";;
 v21c) gen v21c 5 v21c_two_sheets.png "Overhead locked-off camera looking straight down at the dark wood table. The red-haired man's LEFT hand, in a CHARCOAL OVERCOAT sleeve with a BLACK shirt cuff, grips the right edge of the upper page and slides it to the right until the two pages lie fully side by side with no overlap, then lets go and withdraws out of the right edge of frame. The lower page does not move. The dark wood table never changes colour. There are no other hands and no white shirt cuffs anywhere.";;
 *) echo "  ?? unknown $1";;
esac; }

[ $# -eq 0 ] && { echo "usage: $0 <cut> [cut...]"; exit 1; }
for c in "$@"; do
  while [ "$(jobs -rp | wc -l)" -ge "$MAX" ]; do sleep 5; done
  job "$c" &
done
wait
echo "--- done"
