#!/usr/bin/env bash
# ナレーションの声・モデルを総当たりで作り、抑揚を客観指標で比べる。
#   bash tools/voice-bakeoff.sh
# 費用はどれも 0.01〜0.15 クレジット/回。全部回しても 2 クレジット未満。
set -u
W="${TEMP:-/tmp}/vo/bakeoff"; mkdir -p "$W"

# 口上の山場を通しで読ませる（静→動の振れ幅を見たいので、抑えた入りと叫びを両方含む）
LINE="欲しければ、くれてやる。探せ。すべて、この会社に置いてきた。世は、まさに――働き方、よんてんゼロ、時代！"
INST="講談師のように。低く重々しく溜めて語り出し、最後の一句は朗々と張り上げて叫ぶ。抑揚を大きく。"

grab(){ grep -oE 'https://[^ ]+\.(mp3|wav|m4a|aac)' | tail -1; }
save(){ n=$1; u=$2
  [ -z "$u" ] && { echo "  !! FAIL $n"; return 1; }
  curl -sSL -o "$W/$n.audio" "$u"
  ffmpeg -y -v error -i "$W/$n.audio" -ar 48000 -ac 1 "$W/$n.wav" && rm -f "$W/$n.audio"
  echo "  ok $n"
}

# 1) Inworld（演技指示なし・現行）
for v in "Satoshi (ja)" "Asuka (ja)"; do
  n="inworld_$(echo "$v" | cut -d' ' -f1)"
  [ -s "$W/$n.wav" ] && { echo "  skip $n"; continue; }
  save "$n" "$(higgsfield generate create inworld_text_to_speech --prompt "$LINE" --voice "$v" --wait --wait-timeout 5m 2>&1 | grab)"
done

# 2) Qwen（演技指示あり）。使えない声は弾かれるので総当たりで確かめる
while read -r id name; do
  n="qwen_$name"
  [ -s "$W/$n.wav" ] && { echo "  skip $n"; continue; }
  save "$n" "$(higgsfield generate create qwen_audio_tts --language ja --prompt "$LINE" \
      --instruction "$INST" --speech-rate 0.92 --format mp3 \
      --voice-id "$id" --voice-type preset --wait --wait-timeout 5m 2>&1 | grab)"
done <<'VOICES'
30fc8796-ceb6-4a66-b3a7-4a145ef7f346 Arthur
e2a2d2e6-9ed2-59cd-82af-feaa27f8a678 Grady
3c9d6053-6334-592c-8997-4e325286af3f Holden
bd072316-f77c-588b-b6e5-e46b9b03d008 Archie
6705e465-7b52-5915-a1d8-b1222885e01d Fraser
d8ba9f14-8a24-44db-932b-99e16c45bd32 Cillian
b847bc29-f184-583a-8ad9-d1f1e16d1a60 Dylan
66469f5a-10db-586a-bab1-72f6ee66ba69 Reid
3c7d32be-0182-5c5e-aa6a-663409bfbb26 Emmett
VOICES

# 3) text2speech_v2 の各エンジン（声は Arthur で固定して engine 差を見る）
for va in elevenlabs minimax seed_speech vibe_voice cozy_voice; do
  n="t2s_$va"
  [ -s "$W/$n.wav" ] && { echo "  skip $n"; continue; }
  save "$n" "$(higgsfield generate create text2speech_v2 --prompt "$LINE" --variant "$va" \
      --voice-id "30fc8796-ceb6-4a66-b3a7-4a145ef7f346" --voice-type preset --wait --wait-timeout 5m 2>&1 | grab)"
done

echo "出力: $W"
