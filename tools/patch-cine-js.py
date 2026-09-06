# -*- coding: utf-8 -*-
"""
index.html の演出・音声まわりを新オープニング仕様に合わせる（1回だけ流す想定）。

  1. fx() に直書きされていた絶対時刻(43.0 / 49.95 など)を CINE_ROGER / CINE_TITLE 参照へ
  2. ▶ を押したら音声(ナレーション＋音楽)が自動で鳴るように
  3. ♪ ボタンを「音楽オン/オフ」から「ミュート切替」へ
  4. 入口カードの尺表記を実尺に

  python tools/patch-cine-js.py --write
"""
import re, sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(ROOT, 'index.html')
src = open(p, encoding='utf-8').read()
total = json.load(open(os.path.join(ROOT, 'tools', 'narration.json'), encoding='utf-8'))['total']
secs = int(round(total))

REPL = [
    # --- 1. 演出の絶対時刻を定数参照に ---
    ("if(t>=43.0&&t<43.6){ var k=(t-43.0)/0.6;",
     "if(t>=CINE_ROGER&&t<CINE_ROGER+0.6){ var k=(t-CINE_ROGER)/0.6;"),
    ("if(t>=42.8&&t<43.0){",
     "if(t>=CINE_ROGER-0.2&&t<CINE_ROGER){"),
    ("if(t>=49.9&&t<50.5){ var k2=(t-49.9)/0.6;",
     "if(t>=CINE_TITLE&&t<CINE_TITLE+0.6){ var k2=(t-CINE_TITLE)/0.6;"),
    ("if(t>=48.5&&t<49.95){ var dd=0.35*Math.min(1,(t-48.5)/0.8);",
     "if(t>=CINE_TITLE-1.45&&t<CINE_TITLE){ var dd=0.35*Math.min(1,(t-(CINE_TITLE-1.45))/0.8);"),
    ("var burst=(t>=43&&t<43.6)||(t>=49.95&&t<50.6);",
     "var burst=(t>=CINE_ROGER&&t<CINE_ROGER+0.6)||(t>=CINE_TITLE&&t<CINE_TITLE+0.65);"),

    # --- 2. ▶ で音声も一緒に始める（クリックはユーザー操作なので自動再生制限に掛からない） ---
    ("rep.addEventListener('click',function(){ play(); cine.scrollIntoView({block:'start'}); "
     "if(musicOn){ try{audio.currentTime=0; audio.play();}catch(e){} } });",
     "rep.addEventListener('click',function(){ play(); cine.scrollIntoView({block:'start'}); startAudio(0); });"),

    # --- 3. ♪ をミュート切替に ---
    ("""  musicBtn.addEventListener('click',function(){
    if(musicOn){ audio.pause(); musicOn=false; }
    else { try{ audio.currentTime=Math.min(time,54.9); var p=audio.play(); if(p&&p.then) p.then(function(){musicOn=true; musicBtn.classList.add('on'); musicBtn.textContent='♪ 音楽オフ'; musicBtn.setAttribute('aria-pressed','true');}).catch(function(){}); return; }catch(e){} }
    musicBtn.classList.toggle('on',musicOn); musicBtn.textContent=musicOn?'♪ 音楽オフ':'♪ 音楽オン'; musicBtn.setAttribute('aria-pressed',String(musicOn));
  });""",
     """  // 音声はナレーションと音楽を1本に焼き込んである。▶ の操作を起点に鳴らし、♪ はミュート切替。
  function syncBtn(){ musicBtn.classList.toggle('on',musicOn); musicBtn.textContent=musicOn?'\\u266a \\u97f3\\u58f0\\u30aa\\u30d5':'\\u266a \\u97f3\\u58f0\\u30aa\\u30f3'; musicBtn.setAttribute('aria-pressed',String(musicOn)); }
  function startAudio(at){
    try{ audio.currentTime=Math.min(at,TOTAL-0.1); }catch(e){}
    audio.muted=false;
    var p=audio.play();
    if(p&&p.then) p.then(function(){ musicOn=true; syncBtn(); }).catch(function(){ musicOn=false; syncBtn(); });
  }
  musicBtn.addEventListener('click',function(){
    if(musicOn){ audio.muted=true; audio.pause(); musicOn=false; syncBtn(); }
    else { startAudio(time); }
  });"""),

    # --- 4. 入口カードの尺表記 ---
    ("OPENING MOVIE ｜ 55 SEC", "OPENING MOVIE ｜ %d SEC" % secs),
    ("55秒の映像で、ご覧いただけます。", "%d秒の映像で、ご覧いただけます。" % secs),
]

miss, done = [], 0
for old, new in REPL:
    if old in src:
        src = src.replace(old, new, 1); done += 1
    elif new in src:
        print('  (適用済み) %s' % old[:38])
    else:
        miss.append(old[:60])

# ♪ の初期表示も「音声オン」に
src = src.replace('>♪ 音楽オン<', '>♪ 音声オン<')

print('置換 %d/%d' % (done, len(REPL)))
if miss:
    print('!! 見つからなかった箇所:')
    for m in miss: print('   ', m)
    sys.exit(1)
if '--write' in sys.argv:
    open(p, 'w', encoding='utf-8').write(src); print('index.html を書き換えました。')
else:
    print('(--write で反映)')
