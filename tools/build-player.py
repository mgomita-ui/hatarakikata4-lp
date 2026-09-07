# -*- coding: utf-8 -*-
"""
オープニングの再生部をゼロから組み込む（旧エンジンは撤去）。

  python tools/build-player.py --write

設計:
  - 映像＋音声を 1 本にした opening-flat.mp4 を <video> で標準再生する
  - 時計は video.currentTime だけ。字幕はそれを見て出すだけで、何も同期しない
  - シーン切替・先読み・同期補正・3D 演出・rAF タイムラインは持たない
  - 操作: ▶入口 / ⏸停止 / ⏩2倍 / 🔊消音 / スキップ / シークバー
  - 再生中はページ全体を覆い、終わったら閉じる
  字幕データは narration.json から生成するので、台本を直したらこれを流し直す。

旧エンジンの扱い:
  #cine ブロック（markup）だけを取り除く。旧スクリプトは先頭で
  `if(!cine) return;` するので、要素が無ければ何もしない。
"""
import json, re, sys, os, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'index.html')
START, END = '<!-- op:start -->', '<!-- op:end -->'


def remove_element(src, open_tag_re):
    """開始タグに一致する要素を、入れ子を数えて閉じタグまで丸ごと取り除く"""
    m = re.search(open_tag_re, src)
    if not m:
        return src, False
    i = m.start(); pos = m.end(); depth = 1
    tag = re.compile(r'<(/?)div\b[^>]*>', re.I)
    while depth:
        t = tag.search(src, pos)
        if not t:
            raise SystemExit('閉じタグが見つかりません')
        depth += -1 if t.group(1) else 1
        pos = t.end()
    return src[:i] + src[pos:], True


def build_block(d):
    S = []
    for s in d['scenes']:
        lines = [[round(l['cue'] - s['t0'], 2), l['text'], l.get('cls', '')]
                 for l in d['lines'] if s['t0'] <= l['cue'] < s['t1']]
        S.append({'t0': s['t0'], 'lines': lines})
    secs = int(round(d['total']))
    scenes_js = json.dumps(S, ensure_ascii=False, separators=(',', ':'))

    css = """
<style>
/* ---- opening player (single video) ---- */
html.op-on{overflow:hidden}
.op{position:fixed;inset:0;z-index:9999;background:#07141F;color:#F3F5EF;font-family:'Noto Sans JP',sans-serif}
.op video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;background:#000}
.op-copy{position:absolute;inset:0;padding:0 6%;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;pointer-events:none}
.op-ln{margin:0 0 .5em;max-width:100%;overflow-wrap:anywhere;font-size:clamp(20px,2.6vw,34px);font-weight:700;line-height:1.5;letter-spacing:.02em;text-shadow:0 2px 18px #031116,0 0 2px rgba(15,95,82,.6);opacity:0;transform:translateY(10px);transition:opacity .28s,transform .3s}
.op-ln.in{opacity:1;transform:none}
.op-ln b{color:#FFD700;font-weight:900}
.op-ln.sm{font-size:clamp(12px,1.3vw,16px);font-weight:500;color:rgba(243,245,239,.72);letter-spacing:.2em}
.op-ln.mid{font-size:clamp(24px,3.4vw,46px);font-weight:900;line-height:1.3}
.op-ln.big{font-size:clamp(26px,4vw,52px);font-weight:900;line-height:1.25}
.op-ln.huge{font-size:clamp(34px,6vw,86px);font-weight:900;line-height:1.15;color:#FFD700;text-shadow:0 0 34px rgba(255,215,0,.35),0 6px 22px rgba(0,0,0,.5)}
.op-ln.huge .br{display:none}
/* 画面下の操作バー。動画プレーヤーの標準形: 再生/停止・時間・シーク・音声・速度・スキップ */
.op-bar{position:absolute;left:0;right:0;bottom:0;z-index:2;display:flex;align-items:center;gap:10px;padding:14px 16px max(14px,env(safe-area-inset-bottom));background:linear-gradient(to top,rgba(0,0,0,.72),rgba(0,0,0,.35) 70%,transparent)}
.op-bar button{flex:none;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.4);color:#fff;border-radius:999px;padding:9px 14px;font-size:13px;font-weight:700;cursor:pointer;font-family:inherit;white-space:nowrap}
.op-bar button.on{background:#FFD700;color:#1a1a1a;border-color:#FFD700}
.op-time{flex:none;font-size:13px;font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:.04em;color:#fff;min-width:7.5em;text-align:center}
.op-seek{flex:1;min-width:80px;height:24px;margin:0;cursor:pointer;-webkit-appearance:none;appearance:none;background:transparent;--p:0%}
.op-seek::-webkit-slider-runnable-track{height:6px;border-radius:3px;background:linear-gradient(to right,#FFD700 var(--p),rgba(255,255,255,.3) var(--p))}
.op-seek::-webkit-slider-thumb{-webkit-appearance:none;width:18px;height:18px;border-radius:50%;background:#FFD700;border:2px solid #fff;margin-top:-6px;box-shadow:0 2px 8px rgba(0,0,0,.5)}
.op-seek::-moz-range-track{height:6px;border-radius:3px;background:rgba(255,255,255,.3)}
.op-seek::-moz-range-progress{height:6px;border-radius:3px;background:#FFD700}
.op-seek::-moz-range-thumb{width:18px;height:18px;border:2px solid #fff;border-radius:50%;background:#FFD700}
.op-copy{bottom:64px}
@media (max-width:600px){
  .op-copy{padding:0 4%}
  .op-ln{font-size:clamp(17px,4.6vw,24px)}
  .op-ln.mid{font-size:clamp(20px,5.4vw,30px)}
  .op-ln.big{font-size:clamp(22px,5.8vw,34px)}
  .op-ln.huge{font-size:clamp(28px,8.6vw,52px)}
  .op-ln.huge .br{display:inline}
  .op-bar{gap:6px;padding:10px 10px max(10px,env(safe-area-inset-bottom));flex-wrap:wrap}
  .op-bar button{padding:8px 10px;font-size:12px}
  .op-time{font-size:12px;min-width:6.5em}
  .op-seek{flex-basis:100%;order:-1}
  .op-copy{bottom:92px}
}
</style>
"""
    markup = """
<div class="op" id="op" hidden>
  <video id="opV" playsinline preload="metadata" src="media/cine/opening-flat.mp4"></video>
  <div class="op-copy" id="opCopy"></div>
  <div class="op-bar">
    <button type="button" id="opPause" aria-label="一時停止">⏸ 停止</button>
    <span class="op-time" id="opTime">0:00 / 0:00</span>
    <input class="op-seek" id="opSeek" type="range" min="0" max="1000" value="0" aria-label="再生位置">
    <button type="button" id="opMute" aria-pressed="false" aria-label="消音">🔊</button>
    <button type="button" id="opFF" aria-pressed="false" aria-label="早送り">2倍</button>
    <button type="button" id="opSkip">スキップ ›</button>
  </div>
</div>
"""
    js = r"""
<script>
(function(){
  var $=function(id){return document.getElementById(id)};
  var op=$('op'),v=$('opV'),copy=$('opCopy'),seek=$('opSeek'),tm=$('opTime'),
      bPause=$('opPause'),bFF=$('opFF'),bMute=$('opMute'),bSkip=$('opSkip'),entry=$('cineReplay');
  if(!op||!v) return;
  var S=__SCENES__, SECS=__SECS__, FADE=2.4, cur=-1, els=[], raf=null;
  var gate=$('cineGate'); if(gate&&gate.parentNode) gate.parentNode.removeChild(gate);

  // 字幕: 今のシーンの行を、cue を過ぎた順に出すだけ。時計は動画。
  function render(t){
    var i=-1; for(var k=0;k<S.length;k++){ if(t>=S[k].t0) i=k; }
    if(i!==cur){ cur=i; copy.innerHTML=''; els=[];
      if(i>=0) S[i].lines.forEach(function(l){ var p=document.createElement('p'); p.className='op-ln '+(l[2]||''); p.innerHTML=l[1]; copy.appendChild(p); els.push(p); }); }
    if(i>=0) S[i].lines.forEach(function(l,j){ if(t>=S[i].t0+l[0]) els[j].classList.add('in'); });
    // 最後の街のカットから LP へ溶け込む: 残り FADE 秒で overlay の不透明度を落とす
    if(v.duration){ var left=v.duration-t; op.style.opacity=left<FADE?Math.max(0,left/FADE).toFixed(3):''; }
    if(v.duration){ var r=t/v.duration; seek.style.setProperty('--p',(r*100)+'%'); if(document.activeElement!==seek) seek.value=Math.round(r*1000);
      tm.textContent=fmt(t)+' / '+fmt(v.duration); }
  }
  function fmt(s){ s=Math.max(0,Math.floor(s)); return Math.floor(s/60)+':'+('0'+(s%60)).slice(-2); }
  function loop(){ render(v.currentTime); raf=v.paused?null:requestAnimationFrame(loop); }
  v.addEventListener('play',function(){ if(!raf) raf=requestAnimationFrame(loop); syncPause(); });
  v.addEventListener('pause',syncPause);
  // timeupdate では必ず描く。rAF はタブが隠れると止まるが、raf 変数は残るので
  // 「rAF が無いときだけ」にすると字幕が固まる（68秒で冒頭の字幕のまま、を実測）。
  v.addEventListener('timeupdate',function(){ render(v.currentTime); });
  v.addEventListener('seeked',function(){ cur=-1; render(v.currentTime); });
  v.addEventListener('ended',close);
  v.addEventListener('error',function(){ close(); });

  function open(){
    document.documentElement.classList.add('op-on'); op.hidden=false; op.style.opacity='';
    v.playbackRate=1; bFF.classList.remove('on'); bFF.textContent='2倍';
    v.muted=true; syncMute();   // 既定は音声オフ。🔊 ボタンで解除する
    try{ v.currentTime=0; }catch(e){}
    var p=v.play(); if(p&&p.catch) p.catch(function(){});
  }
  function close(){
    v.pause(); op.hidden=true; op.style.opacity=''; document.documentElement.classList.remove('op-on');
    cur=-1; copy.innerHTML='';
    entry.innerHTML='▶ オープニングをもう一度'; entry.classList.add('show');
    try{ sessionStorage.setItem('cineSeen','1'); }catch(e){}
  }
  function syncPause(){ bPause.innerHTML=v.paused?'▶ 再生':'⏸ 停止'; }
  function syncMute(){ bMute.classList.toggle('on',v.muted); bMute.innerHTML=v.muted?'🔇':'🔊'; bMute.setAttribute('aria-pressed',String(v.muted)); }

  entry.addEventListener('click',function(){ open(); });
  bPause.addEventListener('click',function(){ if(v.paused){ var p=v.play(); if(p&&p.catch)p.catch(function(){}); } else v.pause(); });
  bFF.addEventListener('click',function(){ var on=v.playbackRate===1; v.playbackRate=on?2:1; bFF.classList.toggle('on',on); bFF.innerHTML=on?'等倍':'2倍'; bFF.setAttribute('aria-pressed',String(on)); });
  bMute.addEventListener('click',function(){ v.muted=!v.muted; syncMute(); });
  bSkip.addEventListener('click',close);
  seek.addEventListener('input',function(){ if(v.duration){ v.currentTime=seek.value/1000*v.duration; } });
  document.addEventListener('keydown',function(e){ if(op.hidden) return; if(e.key==='Escape') close(); if(e.key===' '){ e.preventDefault(); bPause.click(); }
    if(e.key==='ArrowRight'&&v.duration){ v.currentTime=Math.min(v.duration,v.currentTime+5); }
    if(e.key==='ArrowLeft'){ v.currentTime=Math.max(0,v.currentTime-5); } });

  var seen=false; try{ seen=sessionStorage.getItem('cineSeen')==='1'; }catch(e){}
  entry.innerHTML=seen?'▶ オープニングをもう一度':'▶ '+SECS+'秒の映像で見る';
  entry.classList.add('show');
  // 自動起動はしない。音声つきの再生は入口ボタンのクリックからだけ始める。
})();
</script>
"""
    js = js.replace('__SCENES__', scenes_js).replace('__SECS__', str(secs))
    return START + css + markup + js + END


def main(write=False):
    d = json.load(open(os.path.join(ROOT, 'tools', 'narration.json'), encoding='utf-8'))
    src = open(P, encoding='utf-8').read()
    block = build_block(d)

    out, removed = remove_element(src, r'<div class="cine" id="cine"[^>]*>')
    if START in out:
        out = re.sub(re.escape(START) + r'.*?' + re.escape(END), lambda m: block, out, flags=re.S)
        how = '既存ブロックを更新'
    else:
        out = out.replace('</body>', block + '\n</body>', 1)
        how = '新規に挿入'
    assert '<div class="cine" id="cine"' not in out
    assert 'id="cineReplay"' in out, '入口ボタン #cineReplay が必要です'
    print('旧 #cine ブロック: %s / 新プレーヤー: %s / 字幕 %d シーン %d 行 / %d 秒'
          % ('撤去' if removed else '無し', how, len(d['scenes']), len(d['lines']), int(round(d['total']))))
    if write:
        open(P, 'w', encoding='utf-8').write(out); print('index.html を書き換えました。')
    else:
        print('(--write で反映)')


if __name__ == '__main__':
    main('--write' in sys.argv)
