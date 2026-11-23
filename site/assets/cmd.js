/* 말로 요청하기 — 화면의 버튼·견본·슬라이더·선택 목록을 이름으로 찾아 대신 조작한다.
   서버가 연결되면 window.AIS_API.assist.interpret({text,page,controls}) → [{action,target,value}] 를 먼저 쓰고,
   없거나 실패하면 이 파일의 규칙 해석기를 쓴다. 비용이 드는 동작(생성·내보내기·삭제)은 항상 한 번 더 확인한다. */
(function(){
'use strict';
var d=document,b=d.body;
if(!b||!b.hasAttribute('data-app')||b.hasAttribute('data-ops'))return;
if(window.AIS&&AIS.session&&!AIS.session())return;
var KO=(d.documentElement.lang||'ko').indexOf('ko')===0;
var page=(location.pathname.split('/').pop()||'').replace('.html','');
var T=function(k,e){return KO?k:e};

/* ---------- 이름 정규화 ---------- */
function norm(s){return String(s||'').toLowerCase().replace(/[\s·.,!?'"“”‘’()\[\]~\-_/]+/g,'')}
var ENDINGS=/(해줘요?|해주세요|해 ?줘|해봐|해볼래|하게|하도록|좀|제발|부탁(해요|드려요|해)?|주세요|줄래|으로|로|를|을|은|는|이|가|에서|에게|에|도|만)/g;
function clean(s){return norm(s).replace(ENDINGS,'')}

/* ---------- 화면에서 조작 가능한 것 모으기 ---------- */
function vis(e){if(e.closest('#aisCmd'))return false;if(e.closest('.mbp'))return !e.closest('[hidden]:not(.mbp)');if(e.closest('.pop'))return !e.closest('[hidden]:not(.pop)');return !!(e.offsetWidth||e.offsetHeight||e.getClientRects().length)&&!e.closest('[hidden]')}
function nameOf(e){
  var n=e.getAttribute('aria-label')||e.getAttribute('title')||'';
  if(!n){var t=(e.innerText||e.textContent||'').replace(/\s+/g,' ').trim();if(t.length<=40)n=t}
  return n.trim();
}
function groupOf(e){
  var g=e.closest('.chs-g,.fgrp,fieldset,.pop,.tool,.panel,section,aside,.opgrp');
  if(!g)return '';
  var h=g.querySelector('legend,h3,h4,b,strong');
  return h?(h.textContent||'').replace(/\s+/g,' ').trim().slice(0,30):'';
}
function controls(){
  var out=[],sel='.appmain button,.appmain [role=button],.appmain label,.appmain summary,.appmain a.btn,.appmain .chip,.appmain .sw,.appmain .lk,.appmain input[type=checkbox],.appmain input[type=radio]';
  [].forEach.call(d.querySelectorAll(sel),function(e){
    if(!vis(e)||e.disabled)return;
    var n=nameOf(e);if(!n||norm(n).length<1)return;
    out.push({el:e,name:n,group:groupOf(e),kind:'click'});
  });
  [].forEach.call(d.querySelectorAll('.appmain input[type=range]'),function(e){
    if(!vis(e)||e.disabled)return;
    var l=e.getAttribute('aria-label')||'';
    if(!l&&e.id){var lb=d.querySelector('label[for="'+e.id+'"]');if(lb)l=lb.textContent}
    if(!l){var lb2=e.closest('label');if(lb2)l=lb2.textContent}
    if(!l&&e.previousElementSibling)l=e.previousElementSibling.textContent||'';
    out.push({el:e,name:(l||e.id||'').replace(/\s+/g,' ').replace(/[-+]?\d+(\.\d+)?\s*(%|px|cm|°)?\s*$/,'').trim(),group:groupOf(e),kind:'range'});
  });
  [].forEach.call(d.querySelectorAll('.appmain select'),function(e){
    if(!vis(e)||e.disabled)return;
    var l=e.getAttribute('aria-label')||'';
    if(!l&&e.id){var lb=d.querySelector('label[for="'+e.id+'"]');if(lb)l=lb.textContent}
    if(!l){var lb2=e.closest('label');if(lb2)l=lb2.textContent.replace(e.textContent,'')}
    out.push({el:e,name:(l||e.id||'').replace(/\s+/g,' ').trim(),group:groupOf(e),kind:'select'});
  });
  return out;
}
function navLinks(){
  return [].map.call(d.querySelectorAll('nav.side a'),function(a){return {el:a,name:a.textContent.trim(),href:a.getAttribute('href')}});
}

/* ---------- 별칭: 말 → 화면 이름 ---------- */
var NAVALIAS=[
  [/(가상\s?피팅|피팅|착용|try-?on)/i,'tryon-studio.html'],[/(사진|포토|photo)/i,'studio.html'],[/(캐릭터|character)/i,'character-studio.html'],
  [/(3d|삼디|아바타)/i,'studio-3d.html'],[/(영상|비디오|video)/i,'studio-video.html'],[/(마켓|market)/,'market.html'],
  [/(라이브러리|library)/i,'library.html'],[/(사용량|팀|연동|대시보드|usage)/i,'dashboard.html'],[/(내\s?작업|홈|workspace)/i,'workspace.html']
];
var ACTIONIDS=[
  {re:/(되돌|돌려놔|undo|실행취소|취소해)/i,ids:['undo'],label:T('되돌리기','Undo')},
  {re:/(다시\s?실행|redo|앞으로)/i,ids:['redo'],label:T('다시 실행','Redo')},
  {re:/(생성|만들어|만들기|실행|시작해|generate|create|run)/i,ids:['go','gen','autogo'],label:T('생성 실행','Generate'),confirm:T('AI 생성은 이번 달 건수를 사용합니다. 실행할까요?','AI generation uses monthly credits. Run it?')},
  {re:/(내보내|다운로드|내려받|export|download)/i,ids:['exp'],label:T('내보내기','Export'),confirm:T('승인된 결과만 내려받을 수 있습니다. 진행할까요?','Only approved results can be exported. Continue?')},
  {re:/(초기화|리셋|reset|처음부터|모두\s?지워)/i,ids:['reset','rst'],label:T('초기화','Reset'),confirm:T('지금 설정을 지웁니다. 진행할까요?','This clears the current settings. Continue?')},
  {re:/(검수\s?요청|리뷰\s?요청|request review)/i,ids:['rq'],label:T('검수 요청','Request review')},
  {re:/(승인해|승인\s?처리|approve)/i,ids:['ap'],label:T('승인','Approve')},
  {re:/(비교)/,ids:['cmp'],label:T('비교','Compare')},
  {re:/(확대|zoom in|크게 보)/i,ids:['zin'],label:T('확대','Zoom in')},{re:/(축소|zoom out|작게 보)/i,ids:['zout'],label:T('축소','Zoom out')},
  {re:/(화면\s?맞춤|꽉\s?차게|fit)/i,ids:['zfit'],label:T('화면 맞춤','Fit')}
];
var RANGEALIAS=[
  [/(밝|어둡|brightness|exposure|노출)/i,/(밝기|노출|brightness|exposure)/i,function(p){return /어둡/.test(p)?-1:1}],
  [/(대비|contrast)/i,/(대비|contrast)/i,function(p){return /(약하|줄|낮|부드)/.test(p)?-1:1}],
  [/(채도|선명한 색|saturation)/i,/(채도|saturation)/i,function(p){return /(줄|낮|연하|흐리)/.test(p)?-1:1}],
  [/(선명|샤프|sharp)/i,/(선명|샤프|sharp)/i,function(p){return /(줄|낮|부드)/.test(p)?-1:1}],
  [/(따뜻|warm|색온도)/i,/(온도|temp|warm)/i,function(p){return /(차갑|시원|cool)/.test(p)?-1:1}],
  [/(차갑|시원|cool)/i,/(온도|temp|warm)/i,function(){return -1}],
  [/(그림자|shadow)/i,/(그림자|shadow)/i,function(p){return /(약하|줄|낮|연하)/.test(p)?-1:1}],
  [/(하이라이트|highlight)/i,/(하이라이트|highlight)/i,function(p){return /(약하|줄|낮|내려)/.test(p)?-1:1}],
  [/(허리)/,/(허리|waist)/i,function(p){return /(줄|좁|가늘|낮|작)/.test(p)?-1:1}],[/(가슴)/,/(가슴|chest|bust)/i,function(p){return /(줄|좁|낮|작)/.test(p)?-1:1}],
  [/(엉덩이|힙)/,/(엉덩이|hip)/i,function(p){return /(줄|좁|낮|작)/.test(p)?-1:1}],[/(키)(?!워)/,/(키|height)/i,function(p){return /(줄|낮|작)/.test(p)?-1:1}]
];
var MORE=/(더|많이|훨씬|확|크게|세게|강하게)/,LESS=/(조금|살짝|약간|슬쩍)/;

/* ---------- 한 문장 해석 ---------- */
function score(c,u){
  var n=clean(c.name);if(!n)return 0;
  var s=0;
  if(n.length>=2&&u.indexOf(n)>-1)s=n.length*3;
  else if(n.length===1&&/^(s|m|l)$/.test(n)&&new RegExp('(^|[^a-z])'+n+'(사이즈|size|$)').test(u))s=4;
  else{
    var toks=(c.name||'').toLowerCase().split(/[\s·/]+/).filter(function(t){return t.length>=2});
    toks.forEach(function(t){var tn=clean(t);if(tn.length>=2&&u.indexOf(tn)>-1)s+=tn.length});
    if(!s&&n.length>=3){var st=n.slice(0,2);if(u.indexOf(st)>-1)s=4}
  }
  if(s&&c.group){var g=clean(c.group);if(g.length>=2&&u.indexOf(g)>-1)s+=4}
  return s;
}
function best(list,u,filter){
  var top=null,ts=0;
  list.forEach(function(c){if(filter&&!filter(c))return;var s=score(c,u);if(s>ts){ts=s;top=c}});
  return ts>=2?top:null;
}
function numberIn(p){var m=/(-?\d+(?:\.\d+)?)\s*(%|퍼센트|px|cm)?/.exec(p);return m?parseFloat(m[1]):null}
function setRange(e,v){
  var mn=parseFloat(e.min||0),mx=parseFloat(e.max||100);v=Math.max(mn,Math.min(mx,v));
  e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));
}

/* ---------- 분위기(무드) 스케치: "가을 분위기로 옷과 배경을 스케치해줘" ---------- */
var MOODS=[
 {re:/(가을|autumn|fall)/i,n:T('가을','Autumn'),pal:['#7a2e2e','#c9962b','#6b6b2f','#b9824a','#e3d2b4'],
  cl:T('버건디 니트·카멜 코트·체크 스커트·가죽 부츠','Burgundy knit, camel coat, plaid skirt, leather boots'),bg:T('단풍 든 가로수길, 따뜻한 오후 햇빛, 낮은 채도의 갈색 톤','Tree-lined street in fall colors, warm afternoon light, muted brown tones'),
  pr:T('가을 분위기, 버건디·카멜·머스타드 계열 의상, 단풍과 따뜻한 오후 햇빛이 있는 배경','autumn mood, burgundy / camel / mustard outfit, background with fall foliage and warm afternoon light'),warm:75,bgsel:/(우드|wood|따뜻|warm)/i},
 {re:/(봄|spring)/i,n:T('봄','Spring'),pal:['#f4c6d0','#cfe3b0','#fff3c4','#bcd9f5','#ffffff'],
  cl:T('파스텔 가디건·플리츠 스커트·트렌치','Pastel cardigan, pleated skirt, trench coat'),bg:T('벚꽃이 핀 공원, 맑은 낮, 밝은 톤','Park with cherry blossoms, clear daylight, bright tones'),
  pr:T('봄 분위기, 파스텔 톤 의상, 꽃이 핀 공원 배경','spring mood, pastel outfit, park background with blossoms'),warm:55,bgsel:/(하늘|sky|흰|white)/i},
 {re:/(여름|summer)/i,n:T('여름','Summer'),pal:['#ffffff','#7fc8e8','#f2c14e','#e8765f','#2f6f8f'],
  cl:T('린넨 셔츠·와이드 팬츠·샌들','Linen shirt, wide pants, sandals'),bg:T('푸른 바다와 밝은 햇빛','Blue sea and bright sunlight'),
  pr:T('여름 분위기, 린넨 소재 밝은 의상, 바다와 강한 햇빛 배경','summer mood, light linen outfit, sea background with strong sunlight'),warm:60,bgsel:/(하늘|sky)/i},
 {re:/(겨울|winter)/i,n:T('겨울','Winter'),pal:['#1f2a44','#8a9bb5','#e6ecf2','#6b2c3e','#ffffff'],
  cl:T('울 롱코트·터틀넥·머플러·부츠','Long wool coat, turtleneck, scarf, boots'),bg:T('눈 내린 거리, 차가운 푸른 빛','Snowy street with cool blue light'),
  pr:T('겨울 분위기, 울 코트와 머플러, 눈 내린 거리 배경','winter mood, wool coat and scarf, snowy street background'),warm:30,bgsel:/(하늘|sky|스튜디오|studio)/i}
];
function moodOf(p){
  if(!/(분위기|느낌|무드|컨셉|콘셉트|mood|vibe|feel)/i.test(p))return null;
  if(!/(옷|의상|배경|코디|스케치|구상|시안|추천|outfit|clothes|background|sketch)/i.test(p))return null;
  for(var i=0;i<MOODS.length;i++)if(MOODS[i].re.test(p))return MOODS[i];
  return null;
}
function moodStep(m,raw){
  return {kind:'mood',desc:m.n+T(' 분위기 스케치',' mood sketch'),run:function(){
    var pf=d.getElementById('prompt')||d.getElementById('aiprompt')||d.getElementById('aitext');
    if(pf&&vis(pf)){pf.value=(pf.value?pf.value+' ':'')+m.pr;pf.dispatchEvent(new Event('input',{bubbles:true}))}
    cs0=controls();cs0.filter(function(c){return c.kind==='range'&&/(색온도|따뜻|warm)/i.test(c.name+' '+c.el.id)}).forEach(function(c){var e=c.el,mn=parseFloat(e.min||0),mx=parseFloat(e.max||100);setRange(e,mn+(mx-mn)*m.warm/100)});
    cs0.filter(function(c){return c.kind==='select'&&/(배경|background|bg)/i.test(c.name+' '+c.el.id)}).forEach(function(c){var o=[].filter.call(c.el.options,function(o){return m.bgsel.test(o.textContent+o.value)})[0];if(o){c.el.value=o.value;c.el.dispatchEvent(new Event('change',{bubbles:true}));c.el.dispatchEvent(new Event('input',{bubbles:true}))}});
    var sw=m.pal.map(function(c){return '<i style="display:inline-block;width:34px;height:34px;border-radius:8px;background:'+c+';border:1px solid rgba(0,0,0,.12)"></i>'}).join('');
    var gb=d.getElementById('go')||d.getElementById('generate')||d.getElementById('run');
    var r=add('<span class="cm-ok">✦</span><span style="display:block;min-width:0"><b>'+esc(m.n+T(' 분위기 스케치',' mood sketch'))+'</b><span style="display:flex;gap:6px;margin:8px 0">'+sw+'</span><span style="display:block"><b>'+esc(T('옷','Clothes'))+'</b> '+esc(m.cl)+'</span><span style="display:block"><b>'+esc(T('배경','Background'))+'</b> '+esc(m.bg)+'</span><span class="cm-q" style="display:block;margin-top:6px">'+esc(T('이 스케치는 방향 제안입니다. 지시 칸과 보정값, 배경이 이 분위기로 채워졌습니다. 실제 이미지는 확인 후 생성하세요.','This sketch is a direction. The instruction box, adjustments and background were filled in. Generate the real image after you check.'))+'</span>'+(gb&&vis(gb)?'<span class="cm-cf" style="margin-top:8px"><button class="go" type="button">'+esc(T('이 방향으로 만들기','Generate this direction'))+'</button></span>':'')+'</span>');
    var b=r.querySelector('button');if(b)b.onclick=function(){gb.click()};
  }};
}
var cs0=[];
function parseOne(raw){
  var p=raw.trim();if(!p)return null;
  var u=clean(p),low=p.toLowerCase();
  var mo=moodOf(p);if(mo)return moodStep(mo,p);

  /* 1. 화면 이동 */
  if(/(열어|이동|가줘|가자|으로 가|로 가|들어가|보여줘|켜줘|go to|open)/i.test(p)){
    var links=navLinks();
    for(var i=0;i<NAVALIAS.length;i++){
      if(NAVALIAS[i][0].test(p)){
        var l=links.filter(function(x){return x.href===NAVALIAS[i][1]})[0];
        if(l&&!/(밝게|어둡게|크게|작게)/.test(p)&&!(best(controls(),u)&&score(best(controls(),u),u)>=6))
          return {kind:'nav',desc:T('「'+l.name+'」로 이동','Go to '+l.name),run:function(){location.href=l.href}};
      }
    }
  }
  /* 2. 검색 */
  var si=d.querySelector('.appmain input[type=search],.appmain input[placeholder*="검색"],.appmain input[placeholder*="earch"],.appmain input[id*="search"],.appmain input[id="q"]');
  if(si&&/(검색|찾아|찾기|search|find)/i.test(p)){
    var q=p.replace(/(검색해?줘?|검색|찾아줘|찾아|찾기|search|find|해줘|해 줘|좀)/gi,'').trim();
    return {kind:'search',desc:T('검색: '+q,'Search: '+q),run:function(){si.focus();si.value=q;si.dispatchEvent(new Event('input',{bubbles:true}));si.dispatchEvent(new Event('change',{bubbles:true}))}};
  }
  /* 3. 정해진 동작(생성·내보내기·되돌리기 …) */
  for(var k=0;k<ACTIONIDS.length;k++){
    var A=ACTIONIDS[k];
    if(A.re.test(p)){
      var el=null;for(var j=0;j<A.ids.length&&!el;j++){var x=d.getElementById(A.ids[j]);if(x&&vis(x)&&!x.disabled)el=x}
      var dis=null;for(var j2=0;j2<A.ids.length&&!dis;j2++){var x2=d.getElementById(A.ids[j2]);if(x2&&x2.disabled)dis=x2}
      if(!el&&dis)return {kind:'noop',desc:A.label+T(' — 지금은 할 수 없어요',' — not available right now'),run:function(){}};
      if(el&&!(best(controls(),u)&&score(best(controls(),u),u)>=9&&!/(생성|만들어)/.test(p)))
        return {kind:'act',desc:A.label,confirm:A.confirm,run:function(e2){return function(){e2.click()}}(el)};
    }
  }
  var wishy=/(싶|원해|입혀|입고|입은|처럼|느낌|스타일|분위기|로 바꿔)/.test(p)&&p.length>10;
  var cs=controls();
  /* 4. 슬라이더: "더 밝게", "허리 줄여줘", "대비 60" */
  var rs=cs.filter(function(c){return c.kind==='range'});
  if(rs.length){
    var tgt=null,dir=1;
    for(var r=0;r<RANGEALIAS.length&&!tgt;r++){
      if(RANGEALIAS[r][0].test(p)){var hit=rs.filter(function(c){return RANGEALIAS[r][1].test(c.name+' '+c.el.id)})[0];if(hit){tgt=hit;dir=RANGEALIAS[r][2](p)}}
    }
    if(!tgt){var bs=best(rs,u);if(bs){tgt=bs;dir=/(줄|낮|내려|작게|약하|좁|줄이)/.test(p)?-1:1}}
    if(tgt){
      var e=tgt.el,mn=parseFloat(e.min||0),mx=parseFloat(e.max||100),rng=mx-mn;
      var num=numberIn(p.replace(tgt.name,''));
      var hasDir=/(올려|높여|키워|늘려|더|크게|세게|강하게|많이|밝게|따뜻|내려|낮춰|줄여|줄이|작게|약하게|어둡게|좁게|차갑)/.test(p);
      if(num!==null&&!hasDir){var vv=num;if(/%|퍼센트/.test(p))vv=mn+rng*num/100;return {kind:'set',desc:tgt.name+' → '+Math.round(vv*10)/10,run:function(){setRange(e,vv)}}}
      var step=Math.max(parseFloat(e.step||1),rng*(LESS.test(p)?0.05:(MORE.test(p)?0.2:0.1)))*dir;
      return {kind:'set',desc:tgt.name+(dir>0?' ▲':' ▼'),run:function(){setRange(e,parseFloat(e.value)+step)}};
    }
  }
  /* 5. 선택 목록 */
  var ss=cs.filter(function(c){return c.kind==='select'});
  for(var q2=0;q2<ss.length;q2++){
    var sel=ss[q2].el,opt=[].filter.call(sel.options,function(o){var on=clean(o.textContent);return on.length>=1&&u.indexOf(on)>-1}).sort(function(a,b){return b.textContent.length-a.textContent.length})[0];
    if(opt&&(score(ss[q2],u)>0||!wishy)){
      (function(sl,op,nm){q2=99;ss._hit={kind:'select',desc:(nm||T('선택','Select'))+': '+op.textContent.trim(),run:function(){sl.value=op.value;sl.dispatchEvent(new Event('change',{bubbles:true}));sl.dispatchEvent(new Event('input',{bubbles:true}))}}})(sel,opt,ss[q2].name)
    }
  }
  if(ss._hit)return ss._hit;
  /* 6. 버튼·견본·칩 이름으로 누르기 */
  var cl=best(cs,u,function(c){return c.kind==='click'});
  if(cl){
    var off=/(꺼|끄|해제|빼|없애)/.test(p),on=/(켜|적용|넣어|추가)/.test(p),el2=cl.el,pr=el2.getAttribute('aria-pressed');
    if(pr!==null&&((off&&pr==='false')||(on&&pr==='true')))return {kind:'noop',desc:cl.name+T(' (이미 그 상태)',' (already)'),run:function(){}};
    var inp=el2.tagName==='LABEL'?el2.querySelector('input'):null;
    var clickStep={kind:'click',desc:(cl.group?cl.group+' · ':'')+cl.name,run:function(){var mp=el2.closest&&el2.closest('.mbp');if(mp&&mp.hidden){var tb=d.getElementById(mp.getAttribute('data-tab'));if(tb)tb.click()}var tg=d.getElementById(el2.id)&&el2.id?el2:null;if(mp){var re=[].filter.call(d.querySelectorAll('.mbp:not([hidden]) .opt'),function(x){return x.title===el2.title&&x.closest('.chs-g').querySelector('b').textContent===el2.closest('.chs-g').querySelector('b').textContent})[0];if(re){re.click();return}}(inp||el2).click()}};
    var pf0=d.getElementById('prompt')||d.getElementById('aiprompt')||d.getElementById('aitext');
    if(pf0&&vis(pf0)&&/(싶|원해|입혀|입고|입은|처럼|느낌|스타일|분위기|로 바꿔)/.test(p)&&p.length>10){
      if(score(cl,u)<12)return {kind:'fill',desc:T('요청 문장을 지시 칸에 넣기','Put the request in the instruction box'),run:function(){pf0.value=(pf0.value?pf0.value+' ':'')+p;pf0.dispatchEvent(new Event('input',{bubbles:true}))}};
      return [clickStep,{kind:'fill',desc:T('요청 문장을 지시 칸에 넣기','Put the request in the instruction box'),run:function(){pf0.value=(pf0.value?pf0.value+' ':'')+p;pf0.dispatchEvent(new Event('input',{bubbles:true}))}}];}
    return clickStep;
  }
  /* 7. 이해 못 함 → 요청 문장을 지시 칸에 넣어 둔다 */
  var pf=d.getElementById('prompt')||d.getElementById('aiprompt')||d.getElementById('aitext')||d.querySelector('.appmain textarea');
  if(pf&&vis(pf))return {kind:'fill',desc:T('요청 문장을 지시 칸에 넣기','Put the request in the instruction box'),run:function(){pf.value=(pf.value?pf.value+' ':'')+p;pf.dispatchEvent(new Event('input',{bubbles:true}));pf.focus()}};
  return null;
}
function interpret(text){
  var parts=text.split(/\s*(?:,|，|그리고|하고\s|그 다음|그다음|한 다음|한 뒤|(?<=[가-힣])[과와](?=\s)|\bthen\b|\band\b)\s*/i).filter(Boolean);
  var out=[];parts.forEach(function(pt){var r=parseOne(pt);if(Array.isArray(r))r.forEach(function(x){out.push({raw:pt,step:x})});else out.push({raw:pt,step:r})});return out;
}

/* ---------- 서버 해석(연결 시) ---------- */
function viaServer(text){
  var a=window.AIS_API&&AIS_API.assist&&AIS_API.assist.interpret;if(!a)return Promise.reject();
  var names=controls().map(function(c){return (c.group?c.group+' · ':'')+c.name}).slice(0,200);
  return Promise.resolve(a({text:text,page:page,controls:names})).then(function(r){
    if(!Array.isArray(r))throw 0;
    return r.map(function(s){
      var cs=controls(),u=clean(s.target||''),c=best(cs,u);
      if(s.action==='nav'){return {raw:s.target,step:{kind:'nav',desc:s.target,run:function(){location.href=s.target}}}}
      if(!c)return {raw:s.target||text,step:null};
      if(s.action==='set'&&c.kind==='range')return {raw:s.target,step:{kind:'set',desc:c.name+' → '+s.value,run:function(){setRange(c.el,Number(s.value))}}};
      if(s.action==='fill'){return {raw:s.target,step:{kind:'fill',desc:c.name,run:function(){c.el.value=s.value;c.el.dispatchEvent(new Event('input',{bubbles:true}))}}}}
      return {raw:s.target,step:{kind:'click',desc:c.name,confirm:s.confirm,run:function(){c.el.click()}}};
    });
  });
}

/* ---------- 화면(UI) ---------- */
var EX={
  studio:T(['가을 분위기로 옷과 배경을 스케치해줘','밝게 해줘','대비를 조금 올려','따뜻한 느낌으로','흑백으로 보여줘','되돌려줘','확대해줘'],['sketch clothes and background with an autumn mood','brighter','a bit more contrast','warm look','black and white','undo','zoom in']),
  'tryon-studio':T(['가을 분위기로 옷과 배경을 스케치해줘','상의로 해줘','해상도 높여줘','후보 2장으로','만들어줘','내보내기'],['sketch clothes and background with an autumn mood','top','higher resolution','2 candidates','generate','export']),
  'character-studio':T(['피부톤 베이지','곱슬머리','골든아워 조명','전신 구도','안경과 귀걸이','지정 모두 지워줘'],['skin beige','curly hair','golden hour light','full body','glasses and earrings','clear all']),
  'studio-3d':T(['허리 줄여줘','L 사이즈로','측면으로 돌려줘','자동 회전 켜줘','이미지로 저장'],['smaller waist','size L','side view','auto-rotate on','save image']),
  'studio-video':T(['만들어줘','내보내기'],['generate','export']),
  market:T(['프리셋 검색','무료만 보여줘'],['search presets','free only']),
  library:T(['원피스 검색','내 업로드만'],['search dress','my uploads only']),
  workspace:T(['가상 피팅 열어줘','캐릭터 스튜디오로 가줘','라이브러리 열어줘'],['open try-on','go to Character Studio','open library']),
  dashboard:T(['내 작업으로 가줘','사진 스튜디오 열어줘'],['go to my work','open Photo Studio'])
};
var css=d.createElement('style');
css.textContent='#aisCmd{position:fixed;left:50%;transform:translateX(-50%);bottom:max(14px,env(safe-area-inset-bottom,0px));z-index:40;width:min(760px,calc(100vw - 24px));font-family:var(--f-body)}body[data-app]::after{content:"";position:fixed;left:0;right:0;bottom:0;height:var(--cmdh,120px);background:linear-gradient(180deg,transparent,var(--bg) 38%);pointer-events:none;z-index:39}'
+'#aisCmd .cm-log{max-height:36vh;overflow:auto;margin-bottom:8px;background:var(--paper);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);padding:10px 12px;display:none;font-size:14px}'
+'#aisCmd.open .cm-log{display:block}'
+'#aisCmd .cm-row{display:flex;gap:10px;align-items:flex-start;padding:6px 0;border-top:1px solid var(--line)}#aisCmd .cm-row:first-child{border-top:0}'
+'#aisCmd .cm-q{color:var(--muted);font-size:12.5px}#aisCmd .cm-ok{color:var(--ok)}#aisCmd .cm-no{color:var(--warn)}'
+'#aisCmd .cm-ex{display:flex;gap:6px;flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;margin-bottom:8px;padding-bottom:2px}#aisCmd .cm-ex::-webkit-scrollbar{display:none}#aisCmd .cm-ex button{flex:0 0 auto;white-space:nowrap;min-height:34px;padding:0 12px;border-radius:999px;border:1px solid var(--line);background:var(--paper);color:var(--ink);font:inherit;font-size:13px;cursor:pointer}'
+'#aisCmd form{display:flex;gap:8px;align-items:center;background:var(--paper);border:1px solid color-mix(in srgb,var(--ink) 22%,transparent);border-radius:999px;padding:6px 8px 6px 16px;box-shadow:var(--shadow)}'
+'#aisCmd form:focus-within{border-color:var(--violet);box-shadow:0 0 0 3px color-mix(in srgb,var(--violet) 25%,transparent),var(--shadow)}'
+'#aisCmd .cm-i{font-size:17px;color:var(--violet)}#aisCmd input{flex:1;min-width:0;border:0;background:transparent;color:var(--ink);font:inherit;font-size:15px;min-height:40px;outline:0}'
+'#aisCmd .cm-b{min-width:44px;min-height:44px;border-radius:999px;border:0;background:var(--ink);color:var(--bg);font:inherit;font-weight:700;cursor:pointer;padding:0 16px}#aisCmd .cm-m{background:transparent;color:var(--ink);border:1px solid var(--line);padding:0}'
+'#aisCmd .cm-cf{display:flex;gap:8px;align-items:center;flex-wrap:wrap}#aisCmd .cm-cf button{min-height:36px;padding:0 14px;border-radius:999px;border:1px solid var(--line);background:var(--paper);color:var(--ink);cursor:pointer;font:inherit}#aisCmd .cm-cf .go{background:var(--violet);color:var(--violet-ink);border-color:transparent}'
+'body[data-app]{padding-bottom:var(--cmdh,120px)}body[data-app] .dctl,body[data-app] .lnav,body[data-app] .wb .wb-lib,body[data-app] .wb .wb-ctl,body[data-app] .tryon3 .dopt{max-height:calc(100vh - 92px - var(--cmdh,120px))!important}@media(max-width:560px){#aisCmd .cm-m{display:none}}';
d.head.appendChild(css);

var root=d.createElement('div');root.id='aisCmd';root.setAttribute('role','search');
root.innerHTML='<div class="cm-log" id="cmLog" aria-live="polite"></div><div class="cm-ex" id="cmEx"></div>'
+'<form id="cmForm"><span class="cm-i" aria-hidden="true">✦</span><input id="cmIn" type="text" autocomplete="off" aria-label="'+T('말로 요청하기','Ask in words')+'" placeholder="'+T('말로 요청해 보세요 — 예: 밝게 해줘 · 단발에 베이지 피부','Ask in words — e.g. brighter · beige skin, short hair')+'">'
+'<button class="cm-b cm-m" id="cmMic" type="button" aria-label="'+T('말로 입력','Voice input')+'" hidden>🎤</button><button class="cm-b" type="submit">'+T('실행','Go')+'</button></form>';
d.body.appendChild(root);(function(){function m(){var h=root.offsetHeight||0;d.documentElement.style.setProperty('--cmdh',(h+24)+'px');window.dispatchEvent(new Event('resize'))}if(window.ResizeObserver){new ResizeObserver(function(){clearTimeout(m.t);m.t=setTimeout(m,50)}).observe(root)}setTimeout(m,0)})();
var log=d.getElementById('cmLog'),inp=d.getElementById('cmIn'),ex=d.getElementById('cmEx');
(EX[page]||EX.workspace).forEach(function(t){var bt=d.createElement('button');bt.type='button';bt.textContent=t;bt.onclick=function(){inp.value=t;run(t)};ex.appendChild(bt)});
function add(html){var r=d.createElement('div');r.className='cm-row';r.innerHTML=html;log.appendChild(r);root.classList.add('open');log.scrollTop=log.scrollHeight;return r}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function exec(items,q){
  items.forEach(function(it){
    var st=it.step;
    if(!st){add('<span class="cm-no">?</span><span>'+esc(T('이해하지 못했어요: ','Could not understand: '))+'“'+esc(it.raw)+'” <span class="cm-q">'+esc(T('이 화면에서 보이는 버튼 이름으로 말해 보세요.','Try using a button name visible on this screen.'))+'</span></span>');return}
    if(st.confirm){
      var r=add('<span class="cm-no">!</span><span>'+esc(st.desc)+' — '+esc(st.confirm)+'<span class="cm-cf" style="margin-top:6px"><button class="go" type="button">'+T('실행','Run')+'</button><button type="button">'+T('취소','Cancel')+'</button></span></span>');
      var bs=r.querySelectorAll('button');
      bs[0].onclick=function(){try{st.run()}catch(e){}r.innerHTML='<span class="cm-ok">✓</span><span>'+esc(st.desc)+'</span>'};
      bs[1].onclick=function(){r.innerHTML='<span class="cm-q">'+esc(T('취소했어요: ','Cancelled: ')+st.desc)+'</span>'};
      return;
    }
    try{st.run();add('<span class="cm-ok">✓</span><span>'+esc(st.desc)+(st.kind==='fill'?' <span class="cm-q">'+esc(T('(직접 확인하고 실행하세요)','(check, then run)'))+'</span>':'')+'</span>')}
    catch(e){add('<span class="cm-no">!</span><span>'+esc(T('실행하지 못했어요: ','Could not run: ')+st.desc)+'</span>')}
  });
}
function run(text){
  text=(text||'').trim();if(!text)return;
  add('<span class="cm-q">›</span><span class="cm-q">'+esc(text)+'</span>');
  var go=function(items){exec(items,text);if(window.AIS&&AIS.log)try{AIS.log({service:'assist',status:'success'})}catch(e){}};
  viaServer(text).then(go,function(){go(interpret(text))});
  inp.value='';
}
d.getElementById('cmForm').addEventListener('submit',function(e){e.preventDefault();run(inp.value)});
d.addEventListener('keydown',function(e){
  var t=e.target&&e.target.tagName;
  if((e.key==='/'&&t!=='INPUT'&&t!=='TEXTAREA'&&t!=='SELECT')||((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k')){e.preventDefault();inp.focus()}
  if(e.key==='Escape'&&root.contains(d.activeElement)){root.classList.remove('open');inp.blur()}
});
inp.addEventListener('focus',function(){if(log.children.length)root.classList.add('open')});
d.addEventListener('click',function(e){if(!root.contains(e.target))root.classList.remove('open')});
/* 음성 입력(브라우저가 지원할 때만) */
var SR=window.SpeechRecognition||window.webkitSpeechRecognition,mic=d.getElementById('cmMic');
if(SR&&mic){mic.hidden=false;mic.onclick=function(){try{var r=new SR();r.lang=KO?'ko-KR':'en-US';r.onresult=function(ev){var t=ev.results[0][0].transcript;inp.value=t;run(t)};r.start()}catch(e){}}}
window.AIS=window.AIS||{};AIS.assist={run:run,interpret:interpret,controls:controls};
})();

/* 전체 화면(wide)용 왼쪽 접이식 메뉴 + 현재 작업실 표시 */
(function(){function build(){var side=document.querySelector('.appshell>.side');if(!side||document.querySelector('.ws-rail'))return;var links=[].slice.call(side.querySelectorAll('a[href]'));if(!links.length)return;
 var here=(location.pathname.split('/').pop()||'').toLowerCase(),cur=null;
 var r=document.createElement('nav');r.className='ws-rail';r.setAttribute('aria-label',document.documentElement.lang==='ko'?'작업실 메뉴':'Workroom menu');
 links.forEach(function(a){var h=(a.getAttribute('href')||'').split('#')[0].split('?')[0].toLowerCase(),b=document.createElement('a');b.href=a.getAttribute('href');var ic=a.querySelector('svg');b.innerHTML=(ic?ic.outerHTML:'<i></i>')+'<span>'+a.textContent.trim()+'</span>';if(h&&h===here){b.className='on';cur=a.textContent.trim()}r.appendChild(b)});
 var pin=document.createElement('button');pin.type='button';pin.className='ws-pin';pin.setAttribute('aria-label',document.documentElement.lang==='ko'?'메뉴 펼침 고정':'Pin menu');pin.innerHTML='<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 6l6 6-6 6"/></svg>';pin.onclick=function(){r.classList.toggle('pinned')};r.insertBefore(pin,r.firstChild);
 document.body.appendChild(r);
 var main=document.querySelector('.appmain')||document.querySelector('main');var h1=document.querySelector('.page-head h1');var nm=cur||(h1&&h1.textContent.trim())||document.title;
 if(main&&!document.querySelector('.ws-crumb')){var c=document.createElement('div');c.className='ws-crumb';c.innerHTML='<span>'+(document.documentElement.lang==='ko'?'작업실':'Workrooms')+'</span><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6"/></svg><b>'+nm+'</b>';main.insertBefore(c,main.firstChild)}}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',build);else build();setTimeout(build,600)})();
