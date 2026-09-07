# 動画・静止画の軽量化ノウハウ

`media/cine/`（4.0 LP オープニング）を **9.98MB → 5.69MB** にした際の手順と実測値。
再実行は `bash tools/optimize-cine.sh`（検証）→ `bash tools/optimize-cine.sh apply`（適用）。

---

## 1. 効いた順

| 施策 | 削減 | 備考 |
|---|---|---|
| **使っていない尺を捨てる** | 大 | 完全に無劣化。まずこれを疑う |
| **クリップ別に CRF を最適化** | 大 | VMAF 下限を守れる範囲で最も攻めた設定を自動選択 |
| JPEG 再圧縮 | 小 | 178KB → 101KB、HTML 変更不要 |
| コーデック変更（AV1/VP9） | ― | **見送り。下記の実測参照** |

結果：

```
CLIP        元      後    削減   採用設定
old1      0.63M   0.25M  -60%   CRF30 (VMAF 90.6)
new1      0.51M   0.27M  -48%   CRF28 (VMAF 91.0)
old2      0.33M   0.20M  -38%   CRF26 (VMAF 91.6)
new2      0.67M   0.36M  -45%   CRF28 (VMAF 90.4)
old3      0.90M   0.32M  -64%   CRF30 (VMAF 91.8)
new3      0.65M   0.34M  -47%   CRF28 (VMAF 91.4)
commute   2.77M   1.36M  -51%   CRF28 (VMAF 90.4)
rooftop   0.66M   0.31M  -52%   CRF30 (VMAF 90.4)
climax    1.84M   1.31M  -29%   CRF26 (VMAF 92.3)   ← 暗部が厳しく自動的に低CRF
合計      8.95M   4.73M  -47%
```

## 2. 「使っていない尺」を見つける

このオープニングは JS タイムラインで駆動していて、各クリップは
`CLIP[name].inp` から `シーン尺（t1-t0）` ぶんしか再生されない。
つまり **必要なのは `inp + (t1-t0)` 秒まで**で、その先は 1 バイトも使われていない。

```js
var expect = c.inp + (time - sceneStart);        // index.html の syncVideo()
if (expect > v.duration - 0.05) return;          // 尺が足りないと seek せず静止する
```

`rooftop.mp4` は 10 秒あるが実際は 9 秒しか使わない、という具合。
`optimize-cine.sh` の `CLIPS` がこの対応表で、余裕 +0.4 秒を足してある。

**シーン尺を変えたら `CLIPS` も更新すること。** 検証コマンド：

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 media/cine/rooftop.mp4
# 必要尺（inp + シーン尺）以上あることを確認する
```

## 3. コーデック実測（commute.mp4 8.3 秒・原本 2318kbps h264）

| 設定 | サイズ | VMAF |
|---|---|---|
| x264 CRF26 veryslow | 1.68MB | 93.9 |
| x264 CRF28 veryslow | 1.35MB | 90.4 |
| SVT-AV1 crf38 preset5 | 1.44MB | 93.6 |
| SVT-AV1 crf44 preset5 | 0.99MB | 90.1 |
| VP9 crf33 cpu-used2 | 2.28MB | 77.1 |

**結論：AV1 の利得は同画質で 14〜27% どまり。** `<source>` の出し分けと
Safari 向け H.264 フォールバックを抱える価値はないと判断し、H.264 単一配信のまま。
VP9 は同ビットレートで大きく劣り、この手の素材では選択肢に入らない。

*10 分程度の素材で 5MB 以上あるなら AV1 二重配信を再検討する価値はある。*

## 4. 画質の決め方

VMAF 下限 **89.5** を採用。理由は、この動画が

- 背景レイヤー（テキストが上に乗る）
- `scale(1.18)` + `object-fit:cover` + 暗転フィルタ
- 1 カット 3〜8 秒で切り替わる

という条件で、原本 / CRF26 / CRF28 / CRF30 を等倍で並べても判別できなかったため。
**前面に出る動画（顔のアップ、細かい文字）なら 93 以上を推奨。**

```bash
# 客観画質の測り方（distorted を先、reference を後に置く）
ffmpeg -v info -i out.mp4 -t 8.3 -i original.mp4 -lavfi libvmaf -f null -
```

## 5. ハマりどころ

| 症状 | 原因と対処 |
|---|---|
| VMAF スコアが出ない | `-v error` だとスコア行（info レベル）ごと消える。`-v info` にする |
| `bc: command not found` | Git Bash に bc は無い。`awk 'BEGIN{...}'` で計算する |
| `drawtext` が Segfault | fontconfig が無い。ラベルを諦めるか `pad` で色帯を挟んで区別する |
| push がタイムアウトしたように見える | ツール側のタイムアウト表示のことがある。リトライ前に `git ls-remote origin refs/heads/main` でリモートのハッシュを確認 |
| 再生が途中で止まる | 尺の切りすぎ。2. の検証コマンドで必要尺を満たしているか確認 |

`faststart`（moov アトムを先頭に置く／再生開始が速くなる）は
`-movflags +faststart` で必ず付ける。現行ファイルは全て対応済み。

## 6. ブラウザでの確認

```bash
python -m http.server 8790     # リポジトリ直下で
```

`window.cineSeek(t)` が公開されているので、任意の秒数へ飛んで確認できる。

```js
document.getElementById('cineReplay').click();  // オープニング開始
window.cineSeek(42.5);                          // 42.5 秒へ
```

---

# ナレーション版オープニング（77秒）

`media/cine/opening.m4a` は **ナレーション＋音楽を1本に焼き込んだもの**。
再生側は `<audio>` ひとつのままなので、同期対象が増えない。

## 作り直す手順

```bash
python tools/layout.py            # 台本から尺を計算（--write で確定）
bash   tools/gen-vo.sh            # Higgsfield TTS で行ごとに生成（約56クレジット）
bash   tools/prep-vo.sh           # 無音除去＋整音。実測尺を書き出す
python tools/layout.py --write    # 実測尺でタイムライン再計算
python tools/build-audio.py       # 音楽とミックスして opening.m4a を作る
python tools/apply-timeline.py --write   # index.html の CLIP / S / TOTAL を更新
bash   tools/optimize-cine.sh && bash tools/optimize-cine.sh apply  # 動画を新しい尺に
```

台本は `tools/narration.json` の一箇所だけ。音声側もHTML側も同じファイルを読むので、
**S[] を手で編集してはいけない**（声と絵がズレる）。

## 効いた知見

**TTS は「文字を読む速さ」では喋れない。** 元の55秒タイムラインは画面表示用に組まれており、
そのまま読み上げると 1.20倍の圧縮が必要だった。尺を77秒に伸ばして解消している。

**Inworld の出力には前後 0.25〜0.86秒の無音が付く。** 28行で合計約16秒。
`silenceremove` で落とすだけで、必要な尺が大幅に減る。

**素材尺が構成を縛る。** クリップは `inp + シーン尺` までしか使えない（5秒素材→最大4.5秒、
10秒素材→最大9.5秒）。シーンを伸ばしたいときは、クリップの無いシーン（暗転・トリプティク・
タイトルカード）で吸収する。新規動画を生成せずに 55→77秒 に伸ばせたのはこのため。

**音声を基準時計にすること。** rAF は裏タブや高負荷で止まる。素の `now-last` で時間を進めると
絵だけが飛び、ナレーションと合わなくなる。鳴っている間は `audio.currentTime` を正とする。

```js
if(musicOn && !audio.paused) time=Math.min(TOTAL,audio.currentTime);
else                        time=Math.min(TOTAL,time+Math.min(0.1,(now-last)/1000));
```

**▶ のクリックはユーザー操作なので自動再生制限に掛からない。** オープニングは
`cine=1` パラメータが無ければボタン起動なので、そこを起点にすれば音を最初から鳴らせる。
♪ ボタンは「音楽オン/オフ」ではなくミュート切替に役割変更した。

## ハマりどころ（追加）

| 症状 | 原因と対処 |
|---|---|
| Higgsfield CLI が全滅する | 音声名が空でも黙って失敗する。`--voice` を渡す前に必ず検証する |
| 生成 URL が拾えない | 音楽は `.m4a` で返る。grep を `(wav\|mp3\|m4a\|aac)` にする |
| python がパスを開けない | Git Bash の `/c/...` は Windows python が解釈できない。引数で渡す（Bash が変換する） |
| heredoc でバックスラッシュが消える | `\` を含む python は heredoc で書かず、ファイルに直接書く |
| ブラウザ検証で `time` が進まない | ペインが隠れている間は rAF が止まる。ページの不具合ではない。`cineSeek` は同期的に `render` するので、DOM を読んで検証する |

---

# 終盤の作り直し（16シーン / 76.5秒）とその過程で見つけた不具合

GPT-6 に工程を相談し、その指摘で**実害3件**が見つかった。いずれも「動くが間違っている」類で、
目視や単体テストでは気付けなかったもの。

## 見つかった不具合

**1. 見せ場の尺が台詞尺で決まってしまう**
モンタージュ6カットを置いたシーンが、担当する台詞が短いという理由で 3.2秒しか確保されず、
1カット 0.47〜0.74秒まで詰まっていた。映像の見せ場は台詞の長さとは独立に尺が要る。
→ `narration.json` のシーンに `min` を持たせ、`layout.py` がそれを下限として尊重するようにした。

**2. 宣言中に打撃音を被せていた**
「世は、まさに――」(66.62-67.73s) の途中 67.40s に、タイトル前の大きな一撃が着弾していた。
音を聴けないので気付けず、**配信する m4a を Whisper に通して初めて分かった**
（単体では「世はまさに」と正しく認識されるのに、ミックスでは「要は」に化けていた）。
→ 直前の台詞の終了後・タイトルコールの語頭を埋めない位置へ移動。

**3. 壊れた素材のまま再エンコードして気付かない**
Higgsfield からのダウンロードが途中で切れた `tripbg.mp4` は、再エンコード候補が全滅して
「切りのみ(無劣化) -0%」として素通りしていた。`phonebg.mp4` は取得自体が失敗して欠落。
→ `optimize-cine.sh` の先頭で `ffmpeg -f null -` によるデコード検査を行い、
   壊れた素材があれば **apply させずに異常終了**するようにした。
   生成スクリプト側でもダウンロード直後に検査し、壊れていれば自動で取り直す。

## 検証の作り方（音を聴けない場合）

`tools/audio-qc.py` は**配信する m4a を再デコードして**測る。エンコード前の WAV で合格しても、
AAC の先頭パディングや末尾処理を含む実再生の状態は保証できない。

| 層 | 方法 | 分かること |
|---|---|---|
| 尺 | ffprobe | 台本の total を満たすか |
| 内容 | Whisper で文字起こし＋行ごとの類似度 | 脱落・誤読・**混ぜた途端に落ちる箇所** |
| 音量 | loudnorm の input_i / input_tp | ラウドネス(-17.5〜-13 LUFS)、true peak(-0.8dBTP以下) |
| 無音 | silencedetect | 途中の異常な空白、末尾切れ |
| 重なり | 台本の cue と実尺から計算 | 行が次の行に食い込んでいないか |

**照合は完全一致にしないこと。**「いまは/今は」「アマゾン/amazon」「返る/帰る」で誤検出が出る。
正規化して行ごとの最良一致で見る。

**同音異義は最後まで残る。**「世は/要は」は音響指標が全て正常でも Whisper が文脈で選び分ける。
ここは機械では詰められないので、**技術QA合格**と**演出品質**は分けて報告する。

## 声の選び方（実測）

同じ台詞を各モデルで生成し、抑揚（F0変動・F0レンジ）と発音（Whisper文字起こし）で比較した。

| モデル | F0変動 | F0レンジ | 発音 | 判定 |
|---|---|---|---|---|
| **text2speech_v2 / elevenlabs** | **0.487** | **18.7半音** | 正確 | **採用** |
| text2speech_v2 / minimax | 0.482 | 15.7半音 | 正確 | 次点 |
| qwen_audio_tts（演技指示可） | 0.436 | 10.4半音 | 正確 | 指示を渡せる利点はあるが抑揚は伸びず |
| inworld / Satoshi | 0.294 | 13.2半音 | 正確 | 平坦。口上には向かない |
| text2speech_v2 / seed_speech | 0.410 | 12.4半音 | **崩壊**（「ゆすければ」「サンクサ」） | 論外 |

`inworld_text_to_speech` は**声を選ぶだけで演技指示のパラメータが無い**。抑揚が要るなら最初から
別モデルを選ぶこと。なお Inworld は前後に 0.25〜0.86秒の無音を付けるが、ElevenLabs は付けない。

---

# 携帯で映像だけが止まる問題（H.264 level）

**症状:** 特定の位置で映像が消え、音声だけ流れる。倍速にしても同じ位置で止まる。
**原因:** `veryslow` が参照フレームを16枚使い、1080p クリップが **level 5.1** になっていた。
携帯のハードウェアデコーダは 1080p を level 4.1〜4.2（参照4枚）までしか保証せず、
遠い参照フレームを要求する最初のフレームでデコードが止まる。だから時間ではなく
**フレーム位置**で決まり、倍速でも同じ場所で止まる。

**なぜ気付きにくかったか:** 先行する 1080p クリップ（intro / tripbg / phonebg）も同じ条件で
止まっていたはずだが、暗い抽象映像なので「消えた」と分からない。最初の絵が明確な
1080p クリップ（legacy）で初めて症状として見える。

**確認方法:**
```bash
ffprobe -v error -select_streams v:0 -show_entries stream=level -of csv=p=0 x.mp4   # 41 以下か
ffmpeg -v trace -i x.mp4 -t 0.1 -c copy -bsf:v trace_headers -f null - 2>&1 | grep -m1 max_num_ref_frames
# 値は Exp-Golomb。000010001 = 16 枚
```

**対処:** すべてのエンコードに `-profile:v high -level 4.1 -x264-params ref=4:bframes=2` を必須にした
（optimize-cine.sh / build-montage.py / recompat.sh）。x264 は level を指定すると参照枚数を
自動で収めるが、明示しておく。画質への影響は VMAF で 1 未満。

**教訓:** ffmpeg で「デコードできる」ことと、端末のハードウェアで「再生できる」ことは別。
配信前に level と参照枚数を必ず検査する。

---

# 再生部をゼロから作り直した（単一動画方式）

**結論:** 2本の `<video>` を切り替える旧エンジンは、携帯と PC の両方で「特定の位置で映像だけ止まり
音声は続く」症状を出し、5回の修正でも直らなかった。撤去して、**映像＋音声を1本の MP4 に焼き込み
`<video>` 1つで標準再生する**方式に置き換えた。時計は `video.currentTime` だけ、字幕はそれを見て出すだけ。
シーン切替・先読み・同期補正・3D演出・rAF タイムラインは持たない。

```bash
python tools/build-flat.py            # narration.json のシーン順に opening-flat.mp4 を焼く
python tools/build-player.py --write  # プレーヤー(markup/CSS/字幕/操作)を index.html に生成
```
台本を直したら build-audio → build-flat → build-player の順で流す。旧 `#cine` markup は撤去済みで、
旧スクリプトは先頭の `if(!cine) return;` で何もしない。

**失ったもの:** 3D の fold/sweep/zoom トランジション、粒子、水平線の演出。
**得たもの:** 端末で再生できることを、端末の標準機能に保証させられること。

## 検証ハーネスで踏んだ罠（再現できない原因の大半はこれだった）

| 罠 | 何が起きるか | 対処 |
|---|---|---|
| JS の `.click()` は実操作ではない | 音声つき `play()` が `NotAllowedError` で拒否され「動画が読み込まれない」ように見える | 実クリック（computer ツール）で試す。muted なら自動再生は通る |
| 非表示タブは renderer/rAF/timer が止まる・凍結する | タイムラインが進まない、記録が空、`Runtime.evaluate` がタイムアウト | タブを前面にする。時計を動画に持たせておけば描画停止は同期に影響しない |
| `python -m http.server` は Range 非対応 | シークすると先頭に戻る（本番の Pages は `Accept-Ranges: bytes` で正常） | シークの検証は必ず本番ホストで行う |
| ffmpeg でデコードできても端末で再生できるとは限らない | level 5.1 の 1080p が携帯で止まる | `-level 4.1 -x264-params ref=4` を必須に（これは切替方式時代の知見。単一動画でも同じ制約で焼いている） |
| `grep` はエスケープ表記を見ない | `秒` で書かれた「55秒」が残った | `scan-labels.py` でエスケープを展開して検査 |

**最大の教訓:** 実機で再現できないまま修正を重ねると、修正自体が次の不具合を生む（保持ロジックが先読みに
消される、dt 上限で絵が取り残される、定数を宣言前に評価して NaN）。再現できない時は、原因を追うより
**失敗の余地そのものを取り除く作りに変える**方が速い。

## 単一動画の仕上げで足したもの

- **カット間のディゾルブ**は動画側に焼き込む（`build-flat.py` の `XFADE = {'cutin': 0.8}`）。
  前カットをフェード秒だけ長く切り出して重ねるので全体尺は変わらず、字幕の cue もずれない。
  そのため合成カットイン（`build-montage.py`）は +1.3秒 長く作る。
- `xfade` は両入力の timebase / fps が一致していないと EINVAL (`4294967274`) で落ちる。
  `settb=AVTB,fps=24` を両入力に入れてから繋ぐ。
- `subprocess.check_call` は ffmpeg の stderr を例外に含めない。`-v error` と組み合わせると
  原因が全く分からない。`subprocess.run(capture_output=True)` で stderr を必ず出す。
- 終わりは動画→LP へ溶ける（overlay の不透明度を残り 2.4 秒で落とす。`build-player.py` の `FADE`）。
- `?cine=1` の自動起動は撤去。音声つき再生は入口ボタンのクリックからだけ。
  URL を配った先で勝手に鳴り続ける事故を防ぐため。
- 単一動画の CRF は `CRF=28 python tools/build-flat.py`（既定 23）。実測: CRF23 22.3MB / CRF26 16.4MB・VMAF94.3 / **CRF28 13.5MB・VMAF92.7 を採用**。
