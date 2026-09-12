#!/usr/bin/env bash
# Seedance 2.5 の設計検証。3=人体 / 5=歩行 / 8=物体 の3種だけ回す。
#
# 設計（GPT-6と詰めた結論）:
#   - start_image は動作の「前」。到達点を渡さない
#   - end_image は原則使わない。PCだけ start のみ / 両端あり を比較する
#   - プロンプトは 開始状態 → 主動作 → 物理的な結果 → 着地点 → カメラ の順
#   - 合否は差分値ではなく「所定の動作が完了したか」
#   - generate_audio=false（音楽と声優音源は既存を使う）
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMG="$ROOT/media/cine/koby/seed"; OUT="$IMG"
JOBS=${JOBS:-3}

LOOK="Live-action Japanese office drama, restrained naturalistic performance, realistic body weight and object contact, consistent faces and wardrobe, one continuous shot. No text, no subtitles, no watermark, no logos. "

gen(){ # gen <name> <duration> <start> <end|-> <prompt>
  local f="$OUT/$1.mp4"
  [ -s "$f" ] && { echo "  skip $1"; return; }
  local args=(--mode omni_reference --duration "$2" --aspect-ratio 16:9
              --resolution 720p --generate-audio false --start-image "$IMG/$3")
  [ "$4" != "-" ] && args+=(--end-image "$IMG/$4")
  local u
  u=$(higgsfield generate create seedance_2_5 "${args[@]}" --prompt "$LOOK$5" \
        --wait --wait-timeout 20m 2>&1 | grep -oE 'https://[^ ]+\.mp4' | tail -1)
  [ -z "$u" ] && { echo "  !! FAIL $1"; return; }
  curl -sSL -o "$f.dl" "$u" && ffmpeg -v error -i "$f.dl" -f null - 2>/dev/null \
    && mv "$f.dl" "$f" && echo "  ok $1 $(du -h "$f"|cut -f1)" || echo "  !! 壊れたDL $1"
}

run(){ case $1 in
 t3) gen t3 7 s3_start.png - \
   "Starting fully seated, the young employee in the grey shirt plants both feet on the floor, leans forward, presses his palms against the edge of the table, lifts his hips clear of the seat and rises to a full standing position. The chair rolls back slightly as he stands. He finishes standing upright, facing down the table, shoulders tense but controlled. The camera tilts up gently to keep his face in frame.";;
 t5) gen t5 7 s5_start.png - \
   "The empty-handed man in the grey-blue cardigan steps across the threshold, walks two measured steps into the room and stops beside the end of the table. His arms swing naturally and settle at his sides. The seated people in the foreground turn their heads to follow him. The camera pans gently to the left to follow his walk. Locked framing otherwise.";;
 t8) gen t8 6 s8_start.png - \
   "The man steadies the base of the laptop with one palm, lifts the front edge of the closed lid with the other hand, and rotates the lid smoothly around its rear hinge up to a normal working angle. The base stays flat on the table throughout. The screen lights up and casts a faint glow on his hands. His hands relax once the lid is open. Locked-off camera.";;
esac }

for k in ${*:-t3 t5 t8}; do run "$k" & done
wait
echo "--- 結果"; ls -la "$OUT"/*.mp4 2>/dev/null
