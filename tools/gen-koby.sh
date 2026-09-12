#!/usr/bin/env bash
# 「時間がもったいない」篇（コビー／シャンクス構造）の素材を生成する。
#
#   bash tools/gen-koby.sh        # 足りないものだけ
#   bash tools/gen-koby.sh k3     # 指定カットだけ作り直す
#
# 考え方:
#   敵は「無駄な作業」ではなく「助成金をめぐる商談と待ち時間」。
#   その検討をしている間に月が変わり、経営から置いていかれる。
#   誰でもない若手が止め、手ぶらの人間が前提を外して終わらせる。
#
#   人物の一貫性は開始フレーム（media/cine/koby/*.png）で担保する。
#   社長は既存オープニング動画 o2 のフレームを参照に作ってあるので、同じ顔が続く。
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMG="$ROOT/media/cine/koby"; OUT="$IMG"
JOBS=${JOBS:-3}
BASE="Cinematic photorealistic shot, Japanese office, natural light, shallow depth of field, no text, no subtitles, no watermark, no on-screen lettering, no company logos. "

gen(){ # gen <name> <start-image|-> <prompt>
  local f="$OUT/$1.mp4"
  [ -s "$f" ] && { echo "  skip $1"; return; }
  local args=(--duration 5 --aspect-ratio 16:9)
  [ "$2" != "-" ] && args+=(--start-image "$IMG/$2")
  local u
  u=$(higgsfield generate create kling2_6 "${args[@]}" --prompt "$BASE$3" --wait --wait-timeout 15m 2>&1 \
      | grep -oE 'https://[^ ]+\.mp4' | tail -1)
  [ -z "$u" ] && { echo "  !! FAIL $1"; return; }
  curl -sSL -o "$f.dl" "$u" && ffmpeg -v error -i "$f.dl" -f null - 2>/dev/null \
    && mv "$f.dl" "$f" && echo "  ok $1 $(du -h "$f" | cut -f1)" || echo "  !! 壊れたDL $1"
}

run(){ case $1 in
 k1) gen k1 s1_shodan.png "The consultant keeps talking and slides the thick stack of application forms across the table toward the president. The president listens politely without moving, his closed laptop untouched beside him.";;
 k2) gen k2 - "Close shot of a wall calendar in an office. A hand reaches in and tears off one month, then another, then another. Between the tears the light in the room shifts from morning to evening and back. On the desk below, a laptop stays closed the whole time.";;
 k3) gen k3 s3_tatsu.png "The young man in the grey shirt, already standing, takes one breath and begins to speak to the seated people. He is not shouting; his voice is level and he does not look away. His hands stay at his sides.";;
 k4) gen k4 s4_tomaru.png "The five seated people hold absolutely still, all facing the same way. Only small things move: one pen rolls a few centimetres, one person blinks. Nobody speaks. Nobody looks at anyone else.";;
 k5) gen k5 s5_toujou.png "The man in the cardigan walks two slow steps into the room and stops. He carries nothing. He looks around once, unhurried, and the seated people turn toward him. He does not raise his hands or gesture.";;
 k6) gen k6 - "Close shot of a closed laptop on a meeting room desk. A hand comes in and opens it. The screen wakes and lights the desk. Morning light from a window. Nothing else in frame moves.";;
esac }

ALL="k1 k2 k3 k4 k5 k6"
n=0
for k in ${*:-$ALL}; do run "$k" & n=$((n+1)); [ $((n % JOBS)) -eq 0 ] && wait; done
wait
echo "--- 生成結果"; ls -la "$OUT"/*.mp4 2>/dev/null
