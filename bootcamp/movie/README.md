# 59秒の物語（bootcamp LP の説明動画）

漫画『ある経営者の選択 II』のコマを動かした 58.8 秒の動画。
配信しているのは `../media/boot-movie.mp4`（1280x720・約6MB）と
`../media/boot-movie-poster.webp` の2つだけ。ここにあるのは作り直すための材料。

## 作り直す手順

```bash
python bootcamp/movie/crops.py      # 漫画ページから開始画像を切る（フキダシを外した窓）
python bootcamp/movie/tts.py        # ナレーションを Higgsfield TTS で生成
python bootcamp/movie/prep.py       # 前後の無音を落として実測尺を lines.json に書き戻す
python bootcamp/movie/animate.py    # Kling で各コマを動かす（約60クレジット）
python bootcamp/movie/build.py      # テロップを焼き、連結し、BGMとミックス
```

BGM だけは手で作る:

```bash
higgsfield generate create sonilo_music --duration 70 --prompt "..." --json
# 落としたものを bootcamp/movie/bgm_raw.wav に置く
```

最後に 720p へ落として配信ファイルにする（1080p のままだと 9.4MB になる）:

```bash
ffmpeg -i boot-movie.mp4 -vf scale=1280:720 -c:v libx264 -preset veryslow -crf 26 \
       -pix_fmt yuv420p -c:a copy -movflags +faststart ../media/boot-movie.mp4
```

## 直すときにどこを触るか

| 直したいもの | ファイル |
|---|---|
| ナレーションの文言・話者 | `lines.json`（直したら tts.py → prep.py → build.py） |
| 画面のテロップ、カットの順番 | `build.py` の `CUTS` |
| どのコマを使うか | `crops.py` の `ANIM` / `STRIP` |
| コマの動かし方 | `shots.json` |

## 効いた知見

**フキダシごと動かすと中の日本語が崩れる。** だから `crops.py` の窓はすべて
フキダシを外した領域にしてあり、セリフは `build.py` が映画字幕として焼き直している。

**Kling は指の本数を描き替える。** 講師の「三つできています」のカットは、
何度プロンプトで縛っても 2 本指になったので、原画を静止で使っている（`still='c06'`）。
画面内の文字・数字は `prompt` に "stays perfectly still and unchanged" と書けば保たれる
（ホワイトボードの 10:00-15:00、ノートPCの見積表はこれで無事だった）。

**`higgsfield generate wait` は長尺ジョブで自前タイムアウトして非ゼロ終了する。**
そこで諦めるとワーカー全体が落ちるので、`animate.py` は待ち直すだけにしてある。

**Inworld TTS は前後に 0.25〜0.86 秒の無音を付ける。** 11 行で約 4 秒。
`prep.py` で落としてからタイムラインを組まないと、間延びする。

**ffmpeg の drawtext はこのビルドだと日本語で落ちる**（fontconfig が無い）。
文字は全部 PIL で 1920x1080 の RGBA に焼いて overlay している。
