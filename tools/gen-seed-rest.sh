#!/usr/bin/env bash
# コビー篇 残り7カット。Seedance 2.5 / omni_reference / start のみ。
# プロンプトは 開始状態 → 主動作 → 物理的な結果 → 着地点 → カメラ の順で書く。
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMG="$ROOT/media/cine/koby/seed"; OUT="$IMG"
LOOK="Live-action Japanese office drama, restrained naturalistic performance, realistic body weight and object contact, consistent faces and wardrobe, one continuous shot. No text, no subtitles, no watermark, no logos. "

gen(){ local f="$OUT/$1.mp4"
  [ -s "$f" ] && { echo "  skip $1"; return; }
  local u
  u=$(higgsfield generate create seedance_2_5 --mode omni_reference --duration "$2" \
        --aspect-ratio 16:9 --resolution 720p --generate-audio false \
        --start-image "$IMG/$3" --prompt "$LOOK$4" --wait --wait-timeout 20m 2>&1 \
      | grep -oE 'https://[^ ]+\.mp4' | tail -1)
  [ -z "$u" ] && { echo "  !! FAIL $1"; return; }
  curl -sSL -o "$f.dl" "$u" && ffmpeg -v error -i "$f.dl" -f null - 2>/dev/null \
    && mv "$f.dl" "$f" && echo "  ok $1 $(du -h "$f"|cut -f1)" || echo "  !! 壊れたDL $1"
}

run(){ case $1 in
 t1) gen t1 8 s1_start.png "The standing consultant slides the proposal folder across the table toward the seated president, then opens his hand to indicate one section of it. The president lowers his gaze to the page and leans slightly forward. The closed laptop stays untouched on the table. Both remain professional and composed. The camera makes a slow short lateral move, creating gentle parallax between the folder and their faces.";;
 t2) gen t2 5 s2_start.png "The hand lifts the lower corner of the calendar page, turns it up and over the binding, and releases it. The paper bends and settles onto the back of the calendar, revealing the next month. The closed laptop beside it does not move at all. Locked-off camera.";;
 t4) gen t4 5 s4_start.png "All four people react to something off-screen to the left. The consultant's hand stops above the open folder. The president turns his eyes first, then his head. The writing man lifts his pen and turns a fraction later. The woman stops reaching for her cup. They settle into a quiet listening posture with subtle breathing and occasional blinking. Locked-off camera.";;
 t6a) gen t6a 6 s6a_start.png "The man in the grey-blue cardigan begins speaking to the seated president, makes one small open-palm gesture, then lowers his hand back to his side. His expression stays firm and measured. A slow subtle camera push-in toward his face.";;
 t6b) gen t6b 8 s6b_start.png "The index finger moves steadily down the page, stops beside the highlighted band, and traces a short line beneath it. The paper shifts slightly under the pressure of the fingertip. The hand then lifts away. The camera makes a short slow slide along the tabletop.";;
 t6c) gen t6c 8 s6c_start.png "The hand slides the upper sheet to the right, revealing the sheet underneath, then aligns the two pages side by side on the table. Both sheets settle flat. The hand withdraws out of frame after the pages stop moving. Locked-off overhead camera.";;
 t7) gen t7 7 s7_start.png "The consultant lowers his gaze to the open folder, closes it with one hand, releases it onto the table, and then takes one small step backward away from the table. His weight shifts onto his back foot. His expression becomes thoughtful and considering, not defeated. Locked-off medium-wide shot with his hands and feet visible.";;
esac }

for k in ${*:-t1 t2 t4 t6a t6b t6c t7}; do run "$k" & done
wait
echo "--- 結果"; ls "$OUT"/*.mp4 2>/dev/null | wc -l
