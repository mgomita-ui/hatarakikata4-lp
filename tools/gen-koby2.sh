#!/usr/bin/env bash
# 「時間がもったいない」v2。ユーザー確定の9場面構成で24カット。
#
#   bash tools/gen-koby2.sh          # 足りないものだけ全部
#   bash tools/gen-koby2.sh v16      # 指定カットだけ
#   JOBS=4 bash tools/gen-koby2.sh   # 並列数
#
# 構成（ユーザー確定）:
#   (1) 現場の実情  (2) 提案・伸びる期日・制約  (3) それでも契約  (4) 若者が割って入る
#   (5) 現場がフラッシュバック  (6) 何を言っているんだと腕を掴まれる  (7) 赤髪の男が登場
#   (8) 助成金を使わない研修の特徴  (9) その場に免じて仕切り直し
#
# v1の失敗を踏まえた設計:
#   - 720p を引き伸ばしてぼけた → 1080p で生成する
#   - shallow depth of field と書いてぼけた → LOOK に deep focus を入れる
#   - start_image は「動作の前」の状態。到達点は渡さない
#   - プロンプトは 開始状態 → 主動作 → 物理的な結果 → 着地点 → カメラ の順
#   - generate_audio false。音楽とナレーションは別で足す
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMG="$ROOT/media/cine/koby/v2"; OUT="$ROOT/media/cine/koby/v2clip"
mkdir -p "$OUT"
JOBS=${JOBS:-3}

LOOK="Live-action Japanese office drama, one continuous shot, restrained naturalistic performance, realistic body weight and object contact, consistent faces and wardrobe, DEEP FOCUS - sharp foreground to background. No text, no subtitles, no watermark, no logos. "

gen(){ # gen <name> <duration> <start.png> <prompt>
  local f="$OUT/$1.mp4"
  [ -s "$f" ] && { echo "  skip $1"; return; }
  local u
  u=$(higgsfield generate create seedance_2_5 \
        --mode omni_reference --duration "$2" --aspect-ratio 16:9 \
        --resolution 1080p --generate-audio false \
        --start-image "$IMG/$3" --prompt "$LOOK$4" \
        --wait --wait-timeout 25m 2>&1 | grep -oE 'https://[^ ]+\.mp4' | tail -1)
  [ -z "$u" ] && { echo "  !! FAIL $1"; return; }
  curl -sSL -o "$f.dl" "$u" && ffmpeg -v error -i "$f.dl" -f null - 2>/dev/null \
    && mv "$f.dl" "$f" && echo "  ok $1 $(du -h "$f"|cut -f1)" || echo "  !! broken DL $1"
}

run(){ case $1 in
# ---- (1) 現場の実情 ----
 v01) gen v01 5 g1_night.png "The lone worker keeps typing, then his hands stop on the keyboard. He sits back, presses the heels of both palms against his eyes, holds, and lowers them. He ends staring at the screen without moving. Locked-off camera, very slow push in.";;
 v02) gen v02 5 g4_minutes.png "The person keeps typing from the paper notepad, glances up at the wall clock, looks back down and resumes typing at the same pace. The shoulders drop slightly. Locked-off camera.";;
 v03) gen v03 5 g2_retype.png "The hands keep copying numbers from the paper ledger to the keyboard, pause to find the place with a fingertip, then resume. The stack beside them does not get smaller. Overhead locked-off camera.";;
 v04) gen v04 5 quad_a.png "All four panels stay locked in place and each one moves independently and continuously: the people keep working, papers shift, a hand reaches. The four panel borders never move. No cuts, no transitions, no camera move.";;
# ---- (2) 提案・伸びる期日・制約 ----
 v05) gen v05 6 b2_room_a.png "The standing consultant finishes a sentence, places one hand on the thick stack of forms and slides it across the table toward the seated president, then releases it. The stack comes to rest in front of the president. He looks at it without touching it. The closed laptop beside him never moves. Locked-off camera.";;
 v06) gen v06 5 b3_forms.png "A hand enters from the top of frame, presses down flat on the thick stack of forms, and lifts away, leaving the stack settled. The paper edges compress and spring back slightly. Overhead locked-off camera.";;
 v07) gen v07 6 h5_calendar.png "A fingertip enters from the right, touches the calendar, and slides slowly from one marked date across to a later marked date in the following month, then lifts away. The calendar page itself does not move. Overhead locked-off camera, very slight push in.";;
 v08) gen v08 5 b7_laptops.png "The camera TRACKS steadily forward along the row of desks, passing one closed laptop after another, each lid sliding through frame from foreground to background. Behind the desks a person walks past the window wall from left to right. None of the lids opens. Continuous dolly move, no cut.";;
# ---- (3) それでも契約 ----
 v09) gen v09 5 e1_reach.png "The hand continues reaching, closes its fingers around the seal, lifts it clear of the table and brings it back over the document, stopping just above the paper. Low-angle locked-off camera at table height.";;
 v10) gen v10 5 b8_stamp.png "The hand presses the seal down onto the document, holds for a beat, then lifts it straight up and sets it down on the desk beside the paper. The paper dimples under the pressure and flattens again. Locked-off camera.";;
# ---- (4) 若者が割って入る ----
 v11) gen v11 6 f1_stand_start.png "Starting fully seated, the young man in the grey shirt plants both feet, presses his palms on the table edge, lifts his hips clear of the seat and rises to full standing. The chair rolls back a few centimetres. He ends upright, facing down the table, hands falling to his sides. The camera tilts up to keep his face framed.";;
 v12) gen v12 6 f2_face_start.png "The young man draws a breath that lifts his chest, leans forward from the waist, brings one hand up off the table and holds it open in front of him, and speaks with his jaw moving throughout. His head turns a few degrees to fix on someone further down the table. He ends leaning in, hand still raised, mid-sentence. The camera pushes in steadily.";;
 v13) gen v13 5 f3_pres_hit.png "The seated president unfolds his hands, sits back against the chair so it rocks slightly, turns his head away from the speaker and lowers his gaze to the table. One hand comes up and rubs across his mouth, then drops to the table. He ends looking down. The camera drifts slowly to the left.";;
# ---- (5) フラッシュバック ----
 v14) gen v14 4 quad_b.png "All four panels stay locked in place and each moves independently and continuously at a faster pace than before. The four panel borders never move. No cuts, no transitions, no camera move.";;
# ---- (6) 腕を掴まれる ----
 v15) gen v15 5 i1_grab.png "The navy-suited man's grip tightens on the young man's wrist and pulls the arm down several centimetres. The young man's shoulder drops with it and his mouth closes. Both men end frozen, neither looking away. The seated people do not move. Locked-off camera.";;
# ---- (7) 赤髪の男が登場 ----
 v16) gen v16 5 i2_catch.png "A THIRD arm in a CHARCOAL OVERCOAT sleeve SWINGS IN fast from the empty right side of frame, and its hand CLAMPS around the navy-suited wrist. The navy forearm is driven downward several centimetres by the impact and strains upward against the grip. The navy hand NEVER LETS GO of the pale grey shirt sleeve it is holding. ALL THREE ARMS stay fully in frame until the end of the shot, locked in a tight diagonal: grey wrist held by the navy hand, navy wrist held by the charcoal hand. The camera pushes in hard.";;
 v17) gen v17 4 i3_release.png "The navy-suited fingers open fully and release the grey sleeve. The two arms separate and draw apart. The charcoal sleeve withdraws last. Locked-off camera.";;
 v18) gen v18 6 e3_reveal.png "The red-haired man straightens, drawing his extended arm up from the bottom of frame and letting it settle at his side beside the hat. His coat shifts with the movement. He ends standing tall and still, looking down the table. The seated heads in the foreground tilt further up to follow him. Low-angle camera, slow push in.";;
# ---- (8) 助成金を使わない研修の特徴 ----
 v19) gen v19 6 d5_speaking.png "The red-haired man begins to speak, jaw moving, and lifts one hand from the table in a small flat gesture, then lets it return to the table. He ends mid-sentence, still looking at the president. The seated foreground figures stay still. Locked-off camera.";;
 v20) gen v20 5 d6_doc.png "The hand slides forward across the document and the fingertip comes down onto the highlighted band, stopping there and pressing slightly. The paper shifts a few millimetres under the finger. Overhead locked-off camera.";;
 v21) gen v21 6 d7_two_sheets.png "The hand grips the edge of the upper sheet and slides it to the right until both sheets lie fully side by side with no overlap, then lets go and withdraws. The lower sheet stays where it is. Overhead locked-off camera.";;
# ---- (9) 仕切り直し ----
 v22) gen v22 5 d8_cons_folder.png "The consultant closes the open folder with both hands, brings it up against his chest and takes one clear step BACKWARD away from the table, his weight settling onto the back foot. He lowers his chin once. He ends standing a pace back from the table, folder held, giving up the floor. The camera stays locked off and he moves within frame.";;
 v23) gen v23 5 i5_pres_turn.png "The seated president turns his head a little further toward the standing figure off-frame left, straightens his back and slides both forearms forward on the table. He ends leaning in, listening. Locked-off camera, slow push in.";;
 v24) gen v24 6 d9_laptop.png "The man steadies the base of the laptop with one palm, lifts the front edge of the lid with the other hand and rotates it smoothly around the rear hinge to a normal working angle. The base stays flat on the table throughout. The screen lights and casts a glow on his hands. His hands relax once it is open. Locked-off camera.";;
# ---- 引きの差し替え。手元のアップだけでは誰が誰を止めたか分からなかった ----
 w1) gen w1 5 j1_grab_wide.png "Starting with a clear gap of air between them, the navy-suited consultant closes the distance, takes hold of the grey-shirted young man's forearm and pulls it firmly DOWN to waist height. The young man's shoulder drops with it and his mouth closes. The seated grey-suited president turns his head toward them. All of them stay in frame and end frozen in place. Locked-off wide camera, no zoom.";;
 w2) gen w2 6 j2_catch_wide.png "Starting several paces away at the RIGHT of frame, the red-haired man in the charcoal overcoat WALKS briskly across the room toward the two struggling men on the left, covers the whole distance, reaches them and CLOSES one hand around the navy-suited consultant's gripping wrist, stopping it dead. He ends standing beside them with his arm extended. The seated president's head turns to follow him all the way across the room. Everyone stays in frame. Locked-off wide camera, no zoom.";;
 w3) gen w3 6 j3_both_back.png "TWO movements happen AT THE SAME TIME. The navy-suited consultant OPENS his hand, releases the young man's forearm, draws his arm back to his own side and takes one step away. Simultaneously the seated grey-suited president leans BACK from the table into his chair and lowers both hands to his lap. The red-haired man in the centre does not move at all throughout. Everyone stays in frame and ends still. Locked-off wide camera, no zoom.";;
# ---- つながりの差し替え。前半の商談が後半と別の部屋・別の人だった ----
 n1) gen n1 6 n1_shodan.png "The standing consultant is mid-explanation: his raised open hand moves once as he finishes a sentence, then comes down onto the clipped set of papers. He SLIDES the papers across the dark wood table toward the seated president and releases them; they come to rest in front of him. The president looks down at them without touching them, then back up at the consultant. The young man keeps his eyes down. The closed laptop never moves. Locked-off camera, everyone stays in frame.";;
 n2) gen n2 5 n2_sign.png "The seated president lowers the seal in his hand onto the document, presses it down, holds for a beat, then lifts it away and sets it on the table. His shoulders drop slightly as he sits back. The standing consultant behind him straightens up. The whole man, the table and the window wall stay in frame throughout - no zoom, no cut to a close-up. Locked-off camera.";;
# ---- 書面の作り直し。束が分厚すぎ、寄りが履歴書に見えた ----
 n3) gen n3 5 n3_forms.png "A hand enters from the top of frame, comes down flat onto the top application form, presses it once so the paper edges compress, then slides the sheet a few centimetres toward the camera and lifts away. The fanned sheets behind it shift slightly with the movement and settle. The binder clip stays in place. Overhead locked-off camera.";;
# ---- 冒頭の作り直し。紙とExcelをやめ、疲れを姿勢で出す ----
 p1) gen p1 5 p1_late.png "The man keeps the heels of both palms pressed into his eyes for a beat, then drags them slowly down his face, lets his hands fall onto the desk and lifts his head to look at the monitors again. His shoulders stay collapsed. He does not go back to typing. The dark office behind him is still. Locked-off camera, very slow push in.";;
 p2) gen p2 5 p2_calls.png "The woman keeps her head tipped back against the chair, draws one long breath that lifts her chest, then rolls her head forward and to one side, opens her eyes and reaches one hand back toward the keyboard without enthusiasm. On the monitor the call tiles keep moving throughout. Locked-off camera.";;
 p3) gen p3 5 p3_retype.png "The man's eyes flick from the phone in his left hand down to the laptop, his right hand types a short burst, then his eyes flick back up to the phone and he types again. The cycle repeats once more. His expression never changes. Locked-off camera, tight on hands and face.";;
 p4) gen p4 5 p4_minutes.png "The lone man keeps typing, stops, rubs the back of his neck hard with one hand while still looking at the screen, drops the hand and resumes typing. Nobody else enters. The empty chairs do not move. Evening light. Locked-off camera, slow push in.";;
 pq) gen pq 5 quad_new.png "All four panels stay locked in place and each one moves independently and continuously: the man lowers his hands from his eyes, the woman rolls her head forward, the hands type and switch between phone and laptop, the lone man rubs his neck. The four panel borders never move. No cuts, no transitions, no camera move.";;
# ---- 若手。顔面いっぱいをやめた中距離 ----
 y1) gen y1 6 y1_speak_mid.png "The young man in the grey shirt draws a breath that lifts his chest, leans forward from the waist, brings one hand up open in front of him and speaks, his jaw moving throughout. The seated people around him turn their heads toward him. He ends leaning in, hand still raised, mid-sentence. Locked-off camera at his eye level - the framing stays at waist-up and never pushes into his face.";;
# ---- 締め ----
 x1) gen x1 6 x1_hat.png "The red-haired man closes his hand around the brim of the hat on the table, lifts it, raises it to his head and SETS IT ON, settling it with a small tug at the brim. He then turns his shoulders away from the table and takes one step toward the empty floor on his left. The young man behind him watches. Locked-off camera, he moves within frame.";;
 z1) gen z1 6 z1_team.png "The five of them hold their ground and only small things move: the red-haired man in front lifts his chin very slightly; the woman shifts her weight; the man with the laptop closes it against his forearm and looks up; the young man at the right pushes off the window frame and straightens; the older man tightens his grip on the rolled papers. Nobody walks, nobody smiles. The camera pushes in slowly and steadily on the group. Backlit, wide, imposing.";;
# ---- 締めをもう1本。引き伸ばし1.57倍の警告が出たため ----
 z2) gen z2 6 z1_team.png "The camera PUSHES IN slowly and steadily on the group from a slightly low angle, ending on the red-haired man in front framed from the chest up with his colleagues still visible behind him. Only small things move: he lifts his chin a fraction; the woman shifts her weight; the man with the laptop closes it against his forearm; the young man at the right straightens off the window frame. Nobody walks, nobody smiles. Backlit throughout.";;
esac }

ALL="p1 p2 p3 p4 pq y1 x1 z1 n1 n2 n3 w1 w2 w3 v01 v02 v03 v04 v05 v06 v07 v08 v09 v10 v11 v12 v13 v14 v15 v16 v17 v18 v19 v20 v21 v22 v23 v24"
n=0
for k in ${*:-$ALL}; do run "$k" & n=$((n+1)); [ $((n % JOBS)) -eq 0 ] && wait; done
wait
echo "--- generated:"; ls "$OUT"/*.mp4 2>/dev/null | wc -l
