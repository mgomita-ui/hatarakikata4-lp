#!/usr/bin/env bash
# 冒頭の問題提起パート（4カット・全画面16:9）の素材を生成する。
#
#   bash tools/gen-opening.sh          # 足りないものだけ生成（再開可能）
#   bash tools/gen-opening.sh o3       # 指定カットだけ作り直す
#
# 考え方:
#   旧冒頭は雨の車窓（intro.mp4）だった。象徴的すぎて「人が来ない」「求人費用が高い」を
#   何も語らない。ここは比喩をやめ、そのままの画で見せる。
#
#   o1/o2 は経営者の側、o3/o4 は求職者の側。o5 は使っていない予備（客が他社を選ぶ画）。o2 の終わりで社長の視線を上げ、
#   そこを橋にして o3 で人物を入れ替える。o3=求職者に飛ばされる、o5=客に他社を選ばれる、
#   o4=その求職者が何を見ているか。
#
#   生成AIは画面内の日本語を読める形で描けない。だから「応募ゼロ」「請求額」を
#   文字で出そうとせず、空欄・空席・スワイプ・止まる指という動作だけで成立させる。
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/media/cine/opening"; mkdir -p "$OUT"
JOBS=${JOBS:-4}
BASE="Cinematic photorealistic shot, Japanese office setting, shallow depth of field, natural light, no text, no subtitles, no watermark, no on-screen lettering. "

gen(){  # gen <name> <prompt>
  local f="$OUT/$1.mp4"
  [ -s "$f" ] && { echo "  skip $1"; return; }
  local u
  u=$(higgsfield generate create kling2_6 --duration 5 --aspect-ratio 16:9 \
        --prompt "$BASE$2" --wait --wait-timeout 15m 2>&1 \
        | grep -oE 'https://[^ ]+\.mp4' | tail -1)
  [ -z "$u" ] && { echo "  !! FAIL $1"; return; }
  curl -sSL -o "$f.dl" "$u" && ffmpeg -v error -i "$f.dl" -f null - 2>/dev/null \
    && mv "$f.dl" "$f" && echo "  ok $1 $(du -h "$f" | cut -f1)" \
    || echo "  !! 壊れたダウンロード $1"
}

run(){ case $1 in
 o1) gen o1 "a Japanese company president in his fifties in a white dress shirt leaning back in his desk chair and looking up at the ceiling with a tired resigned expression, a stack of job posting sheets and an open laptop on his desk, two completely empty office desks with empty chairs in the foreground, quiet small office, weekday morning";;
 o2) gen o2 "close shot of the hands of a Japanese company president in his fifties, holding a printed invoice in one hand and pressing the keys of a desk calculator with the other, brow furrowed, then slowly lifting his eyes up from the paper, small office desk, papers around";;
 o3) gen o3 "a Japanese man about 28 years old in a plain button-down shirt sitting at a cafe table, holding his smartphone UPRIGHT in one hand in portrait orientation, repeatedly flicking the screen upward with his thumb to scroll past a long list of company recruiting pages, dismissing one after another without stopping, bored uninterested face, bright window light";;
 o5) gen o5 "a Japanese client manager in a meeting room comparing two printed proposal documents side by side on the table, closing the one on the near side and sliding it away, then placing his pen decisively on the other one, natural office window light";;
 o4) gen o4 "the same Japanese man about 28 years old in the same plain button-down shirt, his smartphone still UPRIGHT in portrait orientation, his scrolling thumb suddenly stopping still, then leaning in closer to read one company page carefully, clearly interested focused expression, bright cafe window light";;
esac }

ALL="o1 o2 o3 o4"
n=0
for k in ${*:-$ALL}; do
  run "$k" &
  n=$((n+1)); [ $((n % JOBS)) -eq 0 ] && wait
done
wait
echo "--- 生成結果"; ls -la "$OUT"/*.mp4 2>/dev/null

