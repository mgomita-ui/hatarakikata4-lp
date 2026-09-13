#!/usr/bin/env bash
# 赤髪の男の左腕の欠けを直す動画生成。実際の映像フレームを起点にし、見た目は参照画像で保つ。
#
#   bash tools/gen-koby2-arm.sh w3c v18c v19c
#
# 前提：
#   v2/w2e_end.png      … w2e.mp4（歩いて入って掴む）の最終フレーム。検査合格後に書き出す
#   v2/v18c_turn.png    … gen_arm_fix_stills.py で作り、静止画ゲートに合格したもの
#   v2/v19c_speak.png   … 同上
#   v2/hold2.png        … 赤髪の男の見た目（短い赤髪・黒シャツ・ロングコート・両腕）の参照。画角は無視させる
#
# 台帳：grip(赤髪.右手, 営業.左前腕) = true 52.8→72.4。左腕は常に体の横で見える。
#       画面の左右：若手 → 営業 → 赤髪の男 → 社長（右手前）
#
# 尺：w3c 必要5.0s→6s（54）、v18c 必要4.2s→5s（45）、v19c 必要4.2s→5s（45）
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMG="$ROOT/media/cine/koby/v2"; OUT="$ROOT/media/cine/koby/v2clip"
mkdir -p "$OUT"
MAX=${MAX:-3}
REF="$IMG/hold2.png"

LOOK="Live-action Japanese office drama, one continuous shot, restrained naturalistic performance, realistic body weight and object contact, consistent faces and wardrobe, DEEP FOCUS - sharp foreground to background. No text, no subtitles, no watermark, no logos. "
ROLE="The start image fixes the room, the camera and everyone's position. The reference image shows ONLY what the red-haired man looks like - his face, SHORT swept-back red hair, black shirt, long CHARCOAL OVERCOAT and TWO arms; ignore its framing. "
ARM="The red-haired man's LEFT arm hangs naturally at his left side and stays visible the whole time - it never disappears into the coat. "

gen(){ # gen <name> <duration> <start.png> <prompt>
  local f="$OUT/$1.mp4" log="$OUT/$1.log" u
  [ -s "$f" ] && { echo "  skip $1"; return; }
  [ -f "$IMG/$3" ] || { echo "  !! FAIL $1: start image $3 がない"; return; }
  higgsfield generate create seedance_2_5 \
        --mode omni_reference --duration "$2" --aspect-ratio 16:9 \
        --resolution 1080p --generate-audio false \
        --start-image "$IMG/$3" --image-references "$REF" --prompt "$LOOK$ROLE$4" \
        --wait --wait-timeout 25m > "$log" 2>&1
  u=$(grep -oE 'https://[^ ]+\.mp4' "$log" | tail -1)
  if [ -z "$u" ]; then
    echo "  !! FAIL $1: $(grep -m1 -iE 'error|not_enough|fail|timeout|invalid' "$log" | cut -c1-220)"
    return
  fi
  curl -sSL -o "$f.dl" "$u" && ffmpeg -v error -i "$f.dl" -f null - 2>/dev/null \
    && mv "$f.dl" "$f" && echo "  ok $1 $(du -h "$f"|cut -f1)" || echo "  !! broken DL $1"
}

job(){ case "$1" in
 w3c) gen w3c 6 w2e_end.png "${ARM}TWO movements happen AT THE SAME TIME, calmly. The red-haired man OPENS his RIGHT hand and releases the navy-suited consultant's left forearm. The consultant lowers his reaching right hand, draws both arms back to his sides and takes ONE clear step BACKWARD away from the young man, his weight settling onto the back foot, his eyes dropping. Simultaneously the seated grey-suited president in the foreground leans BACK into his chair and lowers both hands to his lap. The young man was never touched and stays where he is. The red-haired man does not move his feet. Everyone ends completely still. Locked-off camera, no zoom, no cut.";;
 v18c) gen v18c 5 v18c_turn.png "${ARM}The red-haired man keeps his RIGHT hand gripping the navy-suited consultant's left forearm the whole time and never lets go. Without hurry he turns his head away from the consultant and looks toward the seated president in the right foreground. The corner of his mouth lifts very slightly - calm, almost amused, not mocking. The consultant's held arm stays still. The seated woman and the navy-suited man keep watching. The president does not move. Locked-off camera, no zoom, nobody walks between the camera and the grip.";;
 v19c) gen v19c 5 v19c_speak.png "${ARM}Facing the seated president, the red-haired man speaks in a low, level voice, his jaw moving throughout, and gives one slow nod at the end of the sentence. His RIGHT hand stays closed around the navy sleeve at the LEFT edge of frame the entire time - he does not let go and does not pull. The president in the right foreground stays still, listening. Locked-off camera over the president's shoulder, no zoom.";;
 *) echo "  ?? unknown $1";;
esac; }

[ $# -eq 0 ] && { echo "usage: $0 <cut> [cut...]"; exit 1; }
for c in "$@"; do
  while [ "$(jobs -rp | wc -l)" -ge "$MAX" ]; do sleep 5; done
  job "$c" &
done
wait
echo "--- done"
