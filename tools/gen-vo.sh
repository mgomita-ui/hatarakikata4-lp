#!/usr/bin/env bash
# narration.json の各行を TTS で生成し media/cine/vo/ に落とす（既存はスキップ＝再開可能）
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/media/cine/vo"; mkdir -p "$OUT"
eval "$(python - "$ROOT/tools/narration.json" <<'PY'
import json,sys
v=json.load(open(sys.argv[1],encoding='utf-8'))['voice']
for k in ('variant','voice_id'): print(f"{k.upper()}='{v[k]}'")
PY
)"
python - "$ROOT/tools/narration.json" <<'PY' > "$OUT/.lines.tsv"
import json,sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
d=json.load(open(sys.argv[1],encoding='utf-8'))
for i,l in enumerate(d['lines']): print(f"{i:02d}\t{l['say']}")
PY
made=0
while IFS=$'\t' read -r idx say; do
  f="$OUT/$idx.wav"; [ -s "$f" ] && continue
  u=$(higgsfield generate create text2speech_v2 --prompt "$say" --variant "$VARIANT" \
        --voice-id "$VOICE_ID" --voice-type preset --wait --wait-timeout 5m 2>&1 \
        | grep -oE 'https://[^ ]+\.(wav|mp3|m4a)' | tail -1)
  [ -z "$u" ] && { echo "  !! FAIL $idx  $say"; continue; }
  curl -sSL -o "$OUT/.dl_$idx" "$u"
  ffmpeg -y -v error -i "$OUT/.dl_$idx" -ar 48000 -ac 1 "$f" && rm -f "$OUT/.dl_$idx"
  made=$((made+1)); printf "  ok %s %5.2fs %s\n" "$idx" "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")" "$say"
done < "$OUT/.lines.tsv"
echo "生成 $made 行"
