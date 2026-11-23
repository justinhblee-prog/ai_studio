(function(){
  var d=document, r=d.documentElement;
  function get(k){try{return localStorage.getItem(k)}catch(e){return null}}
  function set(k,v){try{localStorage.setItem(k,v)}catch(e){}}
  // 새 페이지는 항상 맨 위에서 시작 (해시 이동 제외). 미리보기 iframe에서는 바깥 화면도 함께 올림
  try{if('scrollRestoration' in history) history.scrollRestoration='manual'}catch(e){}
  function toTop(){if(location.hash&&location.hash.length>1) return; window.scrollTo(0,0); try{r.scrollIntoView({block:'start'})}catch(e){}}
  toTop(); d.addEventListener('DOMContentLoaded',toTop); window.addEventListener('load',toTop); window.addEventListener('pageshow',function(e){if(e.persisted) toTop()});
  // theme
  function nm(){var m=/(?:^|;)aisTheme=(dark|light)/.exec(window.name||'');return m?m[1]:null}
  function setNm(v){window.name=(window.name||'').replace(/(?:^|;)aisTheme=(dark|light)/,'')+';aisTheme='+v}
  var t=get('theme'); if(t!=='dark'&&t!=='light') t=nm(); if(t==='dark'||t==='light') r.setAttribute('data-theme',t);
  var tb=d.getElementById('theme');
  if(tb) tb.addEventListener('click',function(){
    var cur=r.getAttribute('data-theme');
    if(!cur) cur=(window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light';
    var n=cur==='dark'?'light':'dark'; set('theme',n); setNm(n); window.__aisTheme=n; r.setAttribute('data-theme',n);
  });
  // carry theme in internal links (fallback when storage is blocked)
  d.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[href]');if(!a||e.defaultPrevented)return;var h=a.getAttribute('href');if(!h||/^(https?:|mailto:|tel:|#|javascript:)/i.test(h)||a.target==='_blank'||a.hasAttribute('download'))return;var th=r.getAttribute('data-theme');if(th!=='dark'&&th!=='light')return;var x=h.split('#'),u=x[0].replace(/([?&])th=(dark|light)&?/,'$1').replace(/[?&]$/,'');a.setAttribute('href',u+(u.indexOf('?')>-1?'&':'?')+'th='+th+(x[1]?'#'+x[1]:''))},true);
  // language preference
  d.querySelectorAll('[data-set-lang]').forEach(function(a){a.addEventListener('click',function(){set('lang',a.getAttribute('data-set-lang'))})});
  // reveal
  var els=d.querySelectorAll('.reveal');
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}})},{threshold:.12});
    els.forEach(function(e){io.observe(e)});
  } else els.forEach(function(e){e.classList.add('in')});
  // compare slider
  var rg=d.getElementById('cmpRange'), c=d.getElementById('cmp');
  if(rg&&c) rg.addEventListener('input',function(){c.style.setProperty('--pos',rg.value+'%')});
  // copy mail
  var cb=d.getElementById('copyMail');
  if(cb) cb.addEventListener('click',function(){
    var m=d.getElementById('mail'); var txt=m?m.textContent.trim():'';
    var done=function(){var o=cb.textContent;cb.textContent=cb.getAttribute('data-ok');setTimeout(function(){cb.textContent=o},1800)};
    if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(txt).then(done,function(){sel(m)})} else sel(m);
    function sel(n){var rg=d.createRange();rg.selectNodeContents(n);var s=getSelection();s.removeAllRanges();s.addRange(rg)}
  });
  // library filter
  var f=d.getElementById('libFilters'), g=d.getElementById('libGallery');
  if(f&&g) f.addEventListener('click',function(e){
    var b=e.target.closest('button[data-f]'); if(!b) return;
    f.querySelectorAll('button').forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false')});
    var v=b.getAttribute('data-f');
    g.querySelectorAll('.card').forEach(function(cd){var cat=cd.getAttribute('data-cat');cd.hidden=!(v==='all'||cat===v||cat==='all')});
  });
  // image deterrents (not a security boundary; see security page)
  d.addEventListener('contextmenu',function(e){if(e.target&&e.target.tagName==='IMG')e.preventDefault()});
  d.addEventListener('dragstart',function(e){if(e.target&&e.target.tagName==='IMG')e.preventDefault()});
})();
(function(){var d=document.querySelector('.dd details');if(!d)return;
document.addEventListener('click',function(e){if(d.open&&!d.contains(e.target))d.open=false});
document.addEventListener('keydown',function(e){if(e.key==='Escape')d.open=false});})();

/* 시연: 단계 자동 재생 — 화면 밖이거나 마우스를 올리면 막대와 타이머가 함께 멈추고, 다시 보이면 남은 시간부터 이어 갑니다 */
(function(){var D=document.querySelectorAll('.demo');if(!D.length)return;
D.forEach(function(el){var li=[].slice.call(el.querySelectorAll('.dm-steps li')),sc=[].slice.call(el.querySelectorAll('.dm-sc')),cur=el.querySelector('.dm-cur'),i=-1,timer=null,vis=false,hov=false,DUR=4200,left=DUR,t0=0;
function hold(){return !vis||hov}
function stop(){if(timer){clearTimeout(timer);timer=null;left=Math.max(250,left-(Date.now()-t0))}el.classList.add('paused')}
function tick(){clearTimeout(timer);timer=null;if(hold()){el.classList.add('paused');return}el.classList.remove('paused');t0=Date.now();timer=setTimeout(function(){timer=null;go(i+1);tick()},left)}
function go(n){i=(n+sc.length)%sc.length;left=DUR;li.forEach(function(x,k){x.classList.toggle('on',k===i);var p=x.querySelector('.dm-prog');if(p){p.style.animation='none';void p.offsetWidth;p.style.animation=''}});
sc.forEach(function(x,k){x.classList.toggle('on',k===i)});el.style.setProperty('--dur',DUR+'ms');
var s=sc[i];if(cur){cur.style.left=s.getAttribute('data-cx')+'%';cur.style.top=s.getAttribute('data-cy')+'%';cur.classList.remove('click');setTimeout(function(){cur.classList.add('click')},1500)}
var st=el.querySelector('.dm-steps');if(st&&st.scrollWidth>st.clientWidth&&li[i]){st.scrollTo({left:li[i].offsetLeft-12,behavior:'smooth'})}}
function sync(){if(hold())stop();else tick()}
li.forEach(function(x,k){x.addEventListener('click',function(){go(k);left=DUR;tick()})});
document.addEventListener('click',function(e){if(e.target.closest&&e.target.closest('[role=tab],.htab,.ht'))setTimeout(check,60)});document.addEventListener('visibilitychange',function(){vis=!document.hidden&&inView();sync()});
go(0);el.classList.add('paused');
function inView(){var r=el.getBoundingClientRect(),h=window.innerHeight||document.documentElement.clientHeight;var vh=Math.min(r.bottom,h)-Math.max(r.top,0);return vh>Math.min(160,r.height*.4)}
function check(){var v=inView();if(v!==vis){vis=v;sync()}}
if('IntersectionObserver' in window){new IntersectionObserver(check,{threshold:[0,.05,.1,.2,.35,.5,.75,1]}).observe(el)}
window.addEventListener('scroll',check,{passive:true});window.addEventListener('resize',check);check()})})();

(function(){var T=document.querySelectorAll('.ht');if(!T.length)return;T.forEach(function(b){b.addEventListener('click',function(){var k=b.getAttribute('data-t');T.forEach(function(x){var on=x===b;x.classList.toggle('on',on);x.setAttribute('aria-selected',on?'true':'false')});document.querySelectorAll('.hp').forEach(function(p){var on=p.getAttribute('data-p')===k;p.hidden=!on;p.classList.toggle('on',on)})})})})();
