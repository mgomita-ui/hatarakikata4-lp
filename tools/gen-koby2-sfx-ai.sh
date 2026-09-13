#!/usr/bin/env bash
# 「時間がもったいない」の効果音を Higgsfield の mirelo_text_to_audio で作る（合成音は間抜けに聞こえたため）。
#   bash tools/gen-koby2-sfx-ai.sh            全部（各2案）
#   bash tools/gen-koby2-sfx-ai.sh impact     指定のみ
# 出力: media/cine/koby/sfx/ai/<name>_<n>.<ext>  ／ ログ: 同じ場所の <name>_<n>.log
set -u
cd "$(dirname "$0")/.."
OUT=media/cine/koby/sfx/ai
mkdir -p "$OUT"
higgsfield account status | head -1

declare -A DUR PROMPT
DUR[impact]=4;    PROMPT[impact]="Anime battle sound effect: a sword suddenly blocks a mighty punch. One massive deep impact boom with an air-pressure shockwave blast and a rumbling tail. Dramatic and heavy, like a manga DON!! moment. No music, no voices."
DUR[explosion]=3; PROMPT[explosion]="A sudden powerful cinematic explosion boom with a short debris rumble. Punchy, dramatic, comedic anime timing. No music, no voices."
DUR[sting]=3;     PROMPT[sting]="Dramatic shock stinger for bad news: a single low heavy orchestral hit with a dark brass swell, anime comedy 'gaan' shock. No voices."
DUR[whoosh]=2;    PROMPT[whoosh]="A quick heavy whoosh of a long coat as a man strides in fast and stops. Short cloth swish. No music, no voices."
DUR[don]=3;       PROMPT[don]="A single heavy taiko drum hit with deep hall reverb, a dramatic anime 'DON' accent. No music bed, no voices."
DUR[reveal]=5;   PROMPT[reveal]="Epic cinematic hero reveal: a deep rising whoosh and sub riser that lands on a huge powerful boom as a team of heroes walks toward the camera. Trailer style, confident and cool. No music melody, no voices."
DUR[title]=3;    PROMPT[title]="Cinematic trailer title hit: one bold metallic impact with a deep boom and a shimmering tail, confident and cool, for a logo appearing. No voices."

names=("$@"); [ ${#names[@]} -eq 0 ] && names=(impact explosion sting whoosh don)

gen() {
  local name=$1 n=$2 log="$OUT/${1}_${2}.log"
  higgsfield generate create mirelo_text_to_audio --duration "${DUR[$name]}" --prompt "${PROMPT[$name]}" \
    --wait --wait-timeout 10m --json > "$log" 2>&1
  local url
  url=$(python -c "
import json,re,sys
t=open(sys.argv[1],encoding='utf-8',errors='replace').read()
m=re.findall(r'https://[^\"\s]+\.(?:wav|mp3|m4a|ogg|flac|aac)[^\"\s]*',t)
print(m[-1] if m else '')" "$log")
  if [ -z "$url" ]; then echo "  !! FAIL $name $n: $(grep -m1 -i 'error\|fail' "$log")"; return; fi
  local ext="${url%%\?*}"; ext="${ext##*.}"
  curl -sL "$url" -o "$OUT/${name}_${n}.${ext}" && echo "  ok ${name}_${n}.${ext}"
}

for name in "${names[@]}"; do
  for n in 1 2; do gen "$name" "$n" & done
done
wait
echo "--- done"
higgsfield account status | head -1
