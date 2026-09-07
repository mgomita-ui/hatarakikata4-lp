#!/usr/bin/env bash
# ------------------------------------------------------------------
# optimize-cine.sh — オープニング動画(media/cine)の軽量化パイプライン
#
#   使い方:
#     bash tools/optimize-cine.sh            # 検証のみ(_opt に出力してレポート)
#     bash tools/optimize-cine.sh apply      # 検証済みの _opt を本番へ差し替え
#
#   考え方:
#     1. 各クリップは index.html の CLIP.inp とシーン尺ぶんしか再生されない。
#        使わない後半を捨てる(= 完全に無劣化な削減)。KEEP はその範囲 +0.4s の余裕。
#     2. そのうえで x264 で再エンコードし、libvmaf で原本との客観画質を測る。
#     3. 攻めた CRF から順に試し、VMAF 下限を満たした時点で採用する。
#        暗部グラデーションの多いカットは自然と低い CRF に落ちるので、
#        クリップごとに「下限を守れる範囲で最も攻めた設定」が選ばれる。
#        下限割れ・「切っただけ(-c copy)」より大きい案は捨てる。
#        → どのクリップも「原本より確実に小さく、画質下限は保証」される。
#
#   計測メモ(2026-09-07, commute.mp4 8.3s で比較):
#     x264 CRF26 1.68MB/VMAF93.9   CRF28 1.35MB/VMAF90.4
#     SVT-AV1  crf38 1.44MB/VMAF93.6   crf44 0.99MB/VMAF90.1  ← 利得14〜27%止まり
#     VP9      crf33 2.28MB/VMAF77.1                          ← 論外
#     → 全ブラウザ対応の H.264 単一配信が最適。AV1 二重配信は割に合わない。
#
#   互換性(2026-09-07): veryslow は参照フレーム16枚を使い、1080p では level 5.1 になる。
#     携帯のハードウェアデコーダは 1080p を level 4.1〜4.2(参照4枚)までしか保証せず、
#     遠い参照を要求する最初のフレームで映像だけが止まった(音声は続く)。
#     -level 4.1 -x264-params ref=4 で必ず縛る。画質への影響は VMAF で 1 未満。
# ------------------------------------------------------------------
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/media/cine"
OUT="$SRC/_opt"
VMAF_FLOOR=${VMAF_FLOOR:-89.5}   # これを割る案は採用しない
CRFS=${CRFS:-"30 28 26"}         # 攻めた順に試し、下限を満たした時点で採用

# name:KEEP秒 (再生に必要な範囲 = inp + シーン尺、に +0.4s の余裕)。tools/narration.json と対応。
CLIPS=${CLIPS:-"intro:4.73 old1:3.9 new1:5.9 old2:3.9 new2:5.9 old3:3.9 new3:5.9 old4:3.9 new4:5.9 grid1:4.76 grid2:7.9 commute:8.57 legacy:11.95 founder:11.41 rooftop:9.72 montage:5.6 strideA:3.95 cutin:4.5 finale:8.68"}

mb(){ awk -v b="$1" 'BEGIN{printf "%.2f", b/1048576}'; }
vmaf(){ # distorted ref keep
  ffmpeg -v info -i "$1" -t "$3" -i "$2" -lavfi libvmaf -f null - 2>&1 \
    | grep -oE 'VMAF score: [0-9.]+' | grep -oE '[0-9.]+' | tail -1
}

if [ "${1:-report}" = "apply" ]; then
  [ -d "$OUT" ] || { echo "先に検証を実行してください (bash tools/optimize-cine.sh)"; exit 1; }
  n=0
  for f in "$OUT"/*.mp4 "$OUT"/*.jpg; do [ -f "$f" ] || continue; cp "$f" "$SRC/$(basename "$f")"; n=$((n+1)); done
  echo "$n 件を差し替えました。"; exit 0
fi

mkdir -p "$OUT"
printf "%-9s %8s %8s %8s  %-22s\n" CLIP 元 採用 削減 採用した設定
printf -- "------------------------------------------------------------------\n"
TOT_O=0; TOT_N=0; BROKEN=""
for e in $CLIPS; do
  name=${e%%:*}; keep=${e##*:}
  in="$SRC/$name.mp4"
  # 生成物のダウンロードは途中で切れることがある。壊れた素材のまま
  # 再エンコードすると無劣化コピーに落ちて気付けないので、先に弾く。
  if [ ! -f "$in" ]; then echo "!! $name.mp4 が無い"; BROKEN="$BROKEN $name"; continue; fi
  if ffmpeg -v error -i "$in" -f null - 2>&1 | grep -q .; then
    echo "!! $name.mp4 がデコードできない（ダウンロード破損の可能性）"; BROKEN="$BROKEN $name"; continue
  fi
  dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$in")
  keep=$(awk -v k="$keep" -v d="$dur" 'BEGIN{print (k<d)?k:d}')
  osz=$(stat -c%s "$in"); TOT_O=$((TOT_O+osz))

  # 案0: 切っただけ(無劣化)。これが常に安全側の上限になる
  cut="$OUT/.cut_$name.mp4"
  ffmpeg -y -v error -i "$in" -t "$keep" -c copy -movflags +faststart "$cut"
  best="$cut"; bsz=$(stat -c%s "$cut"); blabel="切りのみ(無劣化)"

  for crf in $CRFS; do
    cand="$OUT/.crf${crf}_$name.mp4"
    ffmpeg -y -v error -i "$in" -t "$keep" -c:v libx264 -crf "$crf" -preset slow \
      -pix_fmt yuv420p -profile:v high -level 4.1 -x264-params ref=4:bframes=2 \
      -movflags +faststart -an "$cand"
    csz=$(stat -c%s "$cand")
    [ "$csz" -lt "$bsz" ] || { rm -f "$cand"; continue; }
    v=$(vmaf "$cand" "$in" "$keep"); v=${v:-0}
    if awk -v v="$v" -v f="$VMAF_FLOOR" 'BEGIN{exit !(v>=f)}'; then
      best="$cand"; bsz=$csz; blabel="CRF$crf (VMAF $(printf %.1f "$v"))"
      break
    fi
    rm -f "$cand"
  done

  cp "$best" "$OUT/$name.mp4"; rm -f "$OUT"/.cut_$name.mp4 "$OUT"/.crf*_$name.mp4
  TOT_N=$((TOT_N+bsz))
  printf "%-9s %7sM %7sM %6s%%  %-22s\n" "$name" "$(mb $osz)" "$(mb $bsz)" \
    "$(awk -v a=$osz -v b=$bsz 'BEGIN{printf "%.0f", -100*(1-b/a)}')" "$blabel"
done

# 静止画(トリプティク用ポスター)。JPEG のまま再圧縮するので index.html は変更不要。
# WebP なら更に -5% 程度縮むが、HTML の書き換えが要るので割に合わない。
for p in "$SRC"/*_p.jpg; do
  [ -f "$p" ] || continue
  name=$(basename "$p" .jpg); osz=$(stat -c%s "$p"); TOT_O=$((TOT_O+osz))
  ffmpeg -y -v error -i "$p" -q:v 6 "$OUT/$name.jpg"
  nsz=$(stat -c%s "$OUT/$name.jpg"); TOT_N=$((TOT_N+nsz))
  s=$(ffmpeg -v info -i "$OUT/$name.jpg" -i "$p" -lavfi ssim -f null - 2>&1 \
      | grep -oE 'All:[0-9.]+' | grep -oE '[0-9.]+' | head -1)
  printf "%-9s %7sM %7sM %6s%%  %-22s\n" "$name" "$(mb $osz)" "$(mb $nsz)" \
    "$(awk -v a=$osz -v b=$nsz 'BEGIN{printf "%.0f", -100*(1-b/a)}')" "JPEG q6 (SSIM ${s:-?})"
done

printf -- "------------------------------------------------------------------\n"
printf "%-9s %7sM %7sM %6s%%\n" 合計 "$(mb $TOT_O)" "$(mb $TOT_N)" \
  "$(awk -v a=$TOT_O -v b=$TOT_N 'BEGIN{printf "%.0f", -100*(1-b/a)}')"
echo
if [ -n "$BROKEN" ]; then
  echo "★ 使えない素材:$BROKEN  — 作り直してから apply すること"
  exit 1
fi
echo "問題なければ: bash tools/optimize-cine.sh apply"
