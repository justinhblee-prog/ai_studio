/* AIS adapter. 개발 창이 서버를 연결하면 페이지보다 먼저 window.AIS_API 를 정의하면 된다.
   window.AIS_API = {
     engines: ['openai','gemini','fashn','claude', ...],            // 켜진 엔진 id
     run: function(req){ return Promise<{image?:dataURL,text?:string,glb?:url,video?:url}> },
        // req = {task, engine, ...payload}  task: auto:* | tryon | character-scene | 3d-generate | video-generate | describe | market-buy | team-invite | apikey.create | webhook.save
     library: function(){ return Promise<[{id,name,src,attrs:{skin,hair,body,age,region}}]> },   // 선택
     market:  { list(): Promise<[...]>, publish(item): Promise<...> }                            // 선택
   }
    session: {user:{name,email}, company, role}|null,   // 서버가 로그인 상태를 알려 줌. role: owner|admin|approver|editor|viewer — 역할은 계정이 정하며 화면에서 고르지 않는다
   auth: {signup(data), login(data), logout()}          // 각각 Promise<session>, data={name,email,password,company|code}
  AIS_API 가 없으면 화면은 로컬(브라우저) 기능만 쓰고, 서버가 필요한 동작은 안내 문구만 보인다. */
(function(){
function g(k,d){try{var v=JSON.parse(localStorage.getItem(k));return v==null?d:v}catch(e){return d}}
function s(k,v){try{localStorage.setItem(k,JSON.stringify(v));return true}catch(e){return false}}
/* 유입경로(마케팅 통계용): 첫 방문 때 한 번만 기록. 개인정보 없음(출처·캠페인·첫 화면만). 개인정보 처리방침에 안내 필요. */
(function(){try{if(localStorage.getItem('ais_acq'))return;var q=new URLSearchParams(location.search),ref='',rh='';try{if(document.referrer){var u=new URL(document.referrer);if(u.origin!==location.origin){ref=document.referrer.slice(0,200);rh=u.hostname.replace(/^www\./,'')}}}catch(e){}
var us=(q.get('utm_source')||'').toLowerCase(),um=(q.get('utm_medium')||'').toLowerCase(),ch='direct';
var H=rh+' '+us;if(/cpc|paid|ppc|display|ad/.test(um))ch='ads';else if(/google|naver|daum|bing|yahoo|duckduckgo|zum/.test(H))ch='search';else if(/instagram|facebook|youtube|tiktok|twitter|x\.com|t\.co|linkedin|kakao|threads|pinterest|blog|band/.test(H))ch='social';else if(/mail|newsletter|stibee/.test(um+us))ch='email';else if(rh)ch='referral';
localStorage.setItem('ais_acq',JSON.stringify({t:Date.now(),ch:ch,ref:rh,src:us,med:um,camp:(q.get('utm_campaign')||'').slice(0,60),landing:location.pathname.split('/').pop()||'index.html'}))}catch(e){}})();
window.AIS={
 get:g,set:s,
 api:function(){return window.AIS_API||null},
 engines:function(){var a=this.api();return a&&a.engines?a.engines:[]},
 connected:function(id){return this.engines().indexOf(id)>=0},
 run:function(task,payload){var a=this.api();if(!a||!a.run)return Promise.reject({code:'NO_API'});return a.run(Object.assign({task:task},payload||{}))},
 log:function(ev){var l=g('ais_usage',[]);ev.t=Date.now();try{var se=AIS.session();if(se){ev.user=ev.user||(se.user&&se.user.email)||se.email||'';ev.company=ev.company||se.company||''}}catch(e){}l.push(ev);if(l.length>500)l=l.slice(-500);s('ais_usage',l)},
 img2data:function(img,max){var c=document.createElement('canvas'),k=Math.min(1,(max||1200)/Math.max(img.naturalWidth||img.width,img.naturalHeight||img.height));c.width=Math.round((img.naturalWidth||img.width)*k);c.height=Math.round((img.naturalHeight||img.height)*k);c.getContext('2d').drawImage(img,0,0,c.width,c.height);return c.toDataURL('image/png')},
 file2img:function(f){return new Promise(function(ok){var u=URL.createObjectURL(f),im=new Image();im.onload=function(){ok(im)};im.src=u})},
 url2img:function(u){return new Promise(function(ok){var im=new Image();im.onload=function(){ok(im)};im.src=u})},
 download:function(href,name){var a=document.createElement('a');a.download=name;a.href=href;document.body.appendChild(a);a.click();a.remove()}
};

var KO=(document.documentElement.lang||'ko')==='ko';
var CAN={viewer:[],editor:['edit','request','export'],approver:['edit','request','approve','export'],admin:['edit','request','approve','export','admin'],owner:['edit','request','approve','export','admin']};
var RN={owner:['소유자','Owner'],admin:['관리자','Admin'],approver:['승인자','Approver'],editor:['편집자','Editor'],viewer:['열람자','Viewer']};
AIS.roleName=function(r){return (RN[r]||RN.viewer)[KO?0:1]};
AIS.session=function(){var a=this.api();if(a&&a.session!==undefined)return a.session;return g('ais_session',null)};
AIS.can=function(act){var s=this.session();return !!s&&(CAN[s.role]||[]).indexOf(act)>=0};
function rid(n){var c='ABCDEFGHJKLMNPQRSTUVWXYZ23456789',o='';for(var i=0;i<n;i++)o+=c[Math.floor(Math.random()*c.length)];return o}
AIS.auth={
 signup:function(d){var a=window.AIS_API;if(a&&a.auth&&a.auth.signup)return a.auth.signup(d);
  var acc=g('ais_accounts',[]);if(acc.some(function(x){return x.email===d.email}))return Promise.reject({code:'EXISTS'});
  var role='owner',company=d.company;if(d.code){var inv=g('ais_invites',[]),f=inv.filter(function(x){return x.code===d.code.trim().toUpperCase()&&!x.used})[0];if(!f)return Promise.reject({code:'BADCODE'});f.used=true;s('ais_invites',inv);role=f.role;company=f.company}else if(!company)return Promise.reject({code:'NOCOMPANY'});
  var acq=null;try{acq=JSON.parse(localStorage.getItem('ais_acq'))}catch(e){}var now=Date.now();var u={email:d.email,name:d.name,company:company,role:role,verified:false,joined:now,acq:acq,survey:d.survey||null,plan:'pilot',contract:{start:now,end:null,status:'trial'}};acc.push(u);s('ais_accounts',acc);AIS.auth._code(d.email);return Promise.resolve({pending:true,email:d.email})},
 _code:function(email){var c=String(Math.floor(100000+Math.random()*900000));s('ais_verify',{email:email,code:c,exp:Date.now()+10*60000,sent:Date.now(),tries:0});return c},
 verify:function(d){var a=window.AIS_API;if(a&&a.auth&&a.auth.verify)return a.auth.verify(d);var v=g('ais_verify',null);if(!v||v.email!==d.email)return Promise.reject({code:'NOCODE'});if(Date.now()>v.exp)return Promise.reject({code:'EXPIRED'});if(v.tries>=5)return Promise.reject({code:'TOOMANY'});if(String(d.code).trim()!==v.code){v.tries++;s('ais_verify',v);return Promise.reject({code:'BADCODE',left:5-v.tries})}
  var acc=g('ais_accounts',[]),u=acc.filter(function(x){return x.email===d.email})[0];if(!u)return Promise.reject({code:'NOUSER'});u.verified=true;s('ais_accounts',acc);try{localStorage.removeItem('ais_verify')}catch(e){}s('ais_session',u);return Promise.resolve(u)},
 resend:function(email){var a=window.AIS_API;if(a&&a.auth&&a.auth.resend)return a.auth.resend({email:email});var v=g('ais_verify',null);if(v&&v.email===email&&Date.now()-v.sent<60000)return Promise.reject({code:'WAIT',sec:Math.ceil((60000-(Date.now()-v.sent))/1000)});AIS.auth._code(email);return Promise.resolve({})},
 pendingCode:function(email){var v=g('ais_verify',null);return v&&v.email===email?v.code:null},
 login:function(d){var a=window.AIS_API;if(a&&a.auth&&a.auth.login)return a.auth.login(d);
  var u=g('ais_accounts',[]).filter(function(x){return x.email===d.email})[0];if(!u)return Promise.reject({code:'NOUSER'});if(u.verified===false){if(!AIS.auth.pendingCode(u.email))AIS.auth._code(u.email);return Promise.reject({code:'UNVERIFIED',email:u.email})}s('ais_session',u);return Promise.resolve(u)},
 changePassword:function(d){var a=window.AIS_API;if(a&&a.auth&&a.auth.changePassword)return a.auth.changePassword(d);return Promise.resolve({preview:true})},
 logout:function(){var a=window.AIS_API;if(a&&a.auth&&a.auth.logout)return a.auth.logout().then(function(){location.href='index.html'});try{localStorage.removeItem('ais_session')}catch(e){}location.href='index.html';return Promise.resolve()},
 invite:function(name,role){var s0=AIS.session();var inv=g('ais_invites',[]);var code='INV-'+rid(6);inv.push({code:code,role:role,name:name,company:s0?s0.company:'',used:false});s('ais_invites',inv);return code}
};
AIS.gate=function(){if(/[?&]embed=1/.test(location.search)){document.documentElement.classList.add('embed');return true}var se=this.session();if(se){var r=document.getElementById('myrole');if(r){r.textContent=(KO?'내 역할: ':'My role: ')+AIS.roleName(se.role)}return true}
 var m=document.getElementById('main');if(!m)return false;Array.prototype.forEach.call(m.querySelectorAll(':scope > section'),function(x){x.hidden=true});
 var d=document.createElement('section');d.style.paddingBlock='48px';d.innerHTML='<div class="wrap"><div class="fgrp" style="max-width:520px"><h3>'+(KO?'로그인이 필요합니다':'Please sign in')+'</h3><p>'+(KO?'작업실은 가입한 회사 계정으로 사용합니다. 역할은 로그인한 계정이 정합니다.':'Workspaces are used with your company account. Your role comes from your account.')+'</p><div class="row"><a class="btn btn-primary" href="login.html" style="color:var(--violet-ink)">'+(KO?'로그인':'Log in')+'</a><a class="btn btn-ghost" href="signup.html">'+(KO?'가입하기':'Sign up')+'</a></div></div></div>';m.appendChild(d);return false};
function hdr(){var el=document.getElementById('acct');if(!el)return;if(document.body.hasAttribute('data-ops')){var o=AIS.ops.session();if(o){el.innerHTML='<span class="who">'+(KO?'운영자 · ':'Operator · ')+o.email+'</span> <button type="button" class="lo" id="lo">'+(KO?'로그아웃':'Log out')+'</button>';var q=document.getElementById('lo');if(q)q.onclick=function(){AIS.ops.logout()}}return}var se=AIS.session();if(!se)return;
 el.innerHTML='<a class="nl" href="workspace.html"><svg class="ni" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M3 9h18M8 14h3"/></svg>'+(KO?'내 작업':'My work')+'</a> <a class="nl" href="account.html"><svg class="ni" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 20c1-4 4-6 8-6s7 2 8 6"/></svg>'+(KO?'내 계정':'My account')+'</a> <span class="who" title="'+(se.company||'')+'">'+se.name+' · '+AIS.roleName(se.role)+'</span> <button type="button" class="lo" id="lo">'+(KO?'로그아웃':'Log out')+'</button>';var b=document.getElementById('lo');if(b)b.onclick=function(){AIS.auth.logout()}}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',hdr);else hdr();window.addEventListener('ais:session',hdr);

/* 내 작업(작업 기록): 서버가 붙으면 AIS_API.work = {list(), upsert(item), remove(id)} 로 대체 */
var SL={draft:['작성 중','Draft'],req:['검수 요청됨','Review requested'],ok:['승인됨','Approved'],chg:['변경 요청됨','Changes requested'],rej:['반려됨','Rejected'],done:['완료','Done']};
AIS.statusName=function(k){return (SL[k]||SL.draft)[KO?0:1]};
AIS.shrink=function(d,max,q){return new Promise(function(ok){var im=new Image();im.onload=function(){var k=Math.min(1,max/Math.max(im.width,im.height)),c=document.createElement('canvas');c.width=Math.max(1,Math.round(im.width*k));c.height=Math.max(1,Math.round(im.height*k));c.getContext('2d').drawImage(im,0,0,c.width,c.height);ok(c.toDataURL('image/jpeg',q||.7))};im.onerror=function(){ok('')};im.src=d})};
AIS.work={
 list:function(){var se=AIS.session();var l=g('ais_work',[]);return l.filter(function(w){return !se||w.company===se.company}).sort(function(a,b){return b.updated-a.updated})},
 get:function(id){return g('ais_work',[]).filter(function(w){return w.id===id})[0]||null},
 upsert:function(it){var se=AIS.session();if(!se)return null;var l=g('ais_work',[]);var i=l.findIndex(function(w){return w.id===it.id});it.company=se.company;it.by=se.name;it.updated=Date.now();if(i>=0)l[i]=Object.assign(l[i],it);else{it.created=it.updated;l.push(it)}
  if(l.length>40)l=l.slice(-40);if(!s('ais_work',l)){l=l.map(function(w){var c=Object.assign({},w);delete c.data;return c});s('ais_work',l)}
  var a=window.AIS_API;if(a&&a.work&&a.work.upsert)a.work.upsert(it);return it},
 remove:function(id){var l=g('ais_work',[]).filter(function(w){return w.id!==id});s('ais_work',l)},
 newId:function(){return 'w'+Date.now().toString(36)+Math.floor(Math.random()*1e4).toString(36)},
 param:function(){try{return new URLSearchParams(location.search).get('w')}catch(e){return null}}
};

/* 앱 셸: 로그인한 상태의 작업 화면에 왼쪽 메뉴를 붙인다 */
AIS.ops={
 session:function(){return g('ais_ops_session',null)},
 staff:function(){return g('ais_ops_staff',[])},
 bootstrap:function(d){var a=window.AIS_API;if(a&&a.ops&&a.ops.auth)return Promise.reject({code:'SERVER'});var l=g('ais_ops_staff',[]);if(l.length)return Promise.reject({code:'EXISTS'});l.push({id:'S'+Date.now().toString(36),em:d.email,name:d.name,role:'lead',t:Date.now()});s('ais_ops_staff',l);return Promise.resolve({})},
 login:function(d){var a=window.AIS_API;if(a&&a.ops&&a.ops.auth&&a.ops.auth.login)return a.ops.auth.login(d);var u=g('ais_ops_staff',[]).filter(function(x){return x.em===d.email})[0];if(!u)return Promise.reject({code:'NOTSTAFF'});var c=String(Math.floor(100000+Math.random()*900000));s('ais_ops_verify',{email:d.email,code:c,exp:Date.now()+5*60000,tries:0});return Promise.resolve({need:'code'})},
 pendingCode:function(e){var v=g('ais_ops_verify',null);return v&&v.email===e?v.code:null},
 verify:function(d){var a=window.AIS_API;if(a&&a.ops&&a.ops.auth&&a.ops.auth.verify)return a.ops.auth.verify(d);var v=g('ais_ops_verify',null);if(!v||v.email!==d.email)return Promise.reject({code:'NOCODE'});if(Date.now()>v.exp)return Promise.reject({code:'EXPIRED'});if(v.tries>=5)return Promise.reject({code:'TOOMANY'});if(String(d.code).trim()!==v.code){v.tries++;s('ais_ops_verify',v);return Promise.reject({code:'BADCODE',left:5-v.tries})}
  var u=g('ais_ops_staff',[]).filter(function(x){return x.em===d.email})[0];if(!u)return Promise.reject({code:'NOTSTAFF'});try{localStorage.removeItem('ais_ops_verify')}catch(e){}var se={email:u.em,name:u.name||u.em,role:u.role,t:Date.now()};s('ais_ops_session',se);return Promise.resolve(se)},
 logout:function(){try{localStorage.removeItem('ais_ops_session')}catch(e){}location.href='ops-login.html'}
};
AIS.isOps=function(){return !!AIS.ops.session()};

AIS.applySite=function(){var c=g('ais_site_cfg',{}),h=g('ais_site_hero',{});
 var band=document.querySelector('.pvband');if(band){if(c.bon===false)band.hidden=true;else{band.hidden=false;if(c.btx)band.textContent=c.btx}}
 var x=document.getElementById('ais-notice');if(x)x.remove();
 function bar(id,txt,bg){var d=document.createElement('div');d.id=id;d.setAttribute('role','status');d.textContent=txt;d.style.cssText='text-align:center;padding:8px 12px;font-size:13.5px;font-weight:600;color:#fff;background:'+bg;var hd=document.querySelector('header.nav');if(hd&&hd.parentNode)hd.parentNode.insertBefore(d,hd.nextSibling);else document.body.insertBefore(d,document.body.firstChild)}
 var m=document.getElementById('ais-maint');if(m)m.remove();
 if(c.mon&&c.mtx)bar('ais-maint',c.mtx,'#b4531a');
 if(c.non&&c.ntx&&(!c.nun||Date.now()<=new Date(c.nun).getTime()+864e5))bar('ais-notice',c.ntx,'#2a2354');
 var h1=document.querySelector('.hero-copy h1'),ld=document.querySelector('.hero-copy .lead');if(h1&&h.h1)h1.textContent=h.h1;if(ld&&h.lead)ld.textContent=h.lead};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',AIS.applySite);else AIS.applySite();
var SI={'workspace.html':'<svg class="ni" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M3 9h18M8 14h3"/></svg>','studio.html':'<svg class="ni" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 8h3l1.6-2.2h6.8L17 8h3v11H4z"/><circle cx="12" cy="13" r="3.6"/></svg>','tryon-studio.html':'<svg class="ni" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 4-5.5 3 2 4 2-1V20h9V10l2 1 2-4L15 4a3.2 3.2 0 0 1-6 0z"/></svg>','character-studio.html':'<svg class="ni" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="8.5" r="3.6"/><path d="M5 20c.8-3.8 3.6-5.8 7-5.8s6.2 2 7 5.8"/></svg>','studio-3d.html':'<svg class="ni" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3.5 19.5 7.8v8.4L12 20.5 4.5 16.2V7.8z"/><path d="M4.8 8 12 12.2 19.2 8M12 12.2V20"/></svg>','studio-video.html':'<svg class="ni" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3.5" y="5" width="17" height="14" rx="3"/><path d="m10.5 9.2 4.3 2.8-4.3 2.8z"/></svg>','market.html':'<svg class="ni" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 8h14l-1 12H6zM9 8V6.5a3 3 0 0 1 6 0V8"/></svg>','library.html':'<svg class="ni" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4 3.5 8.5 12 13l8.5-4.5z"/><path d="m3.5 12.5 8.5 4.5 8.5-4.5M3.5 16.5 12 21l8.5-4.5"/></svg>','dashboard.html':'<svg class="ni" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 20V11M12 20V5M19 20v-7"/></svg>'};
function shell(){var b=document.body;if(!b.hasAttribute('data-app')||b.hasAttribute('data-ops')||!AIS.session())return;var m=document.getElementById('main');if(!m||m.querySelector('.appshell'))return;
 var items=[['workspace.html',KO?'작업실 홈':'Workspace home'],['studio.html','Photo Studio'],['tryon-studio.html','Virtual Try-on'],['character-studio.html','Character Studio'],['studio-3d.html','3D Studio'],['studio-video.html','Video Studio'],['market.html','Marketplace'],['library.html',KO?'라이브러리':'Library'],['dashboard.html',KO?'사용량·팀·연동':'Usage, team and integrations']];
 var cur=location.pathname.split('/').pop()||'';var nav=document.createElement('nav');nav.className='side';nav.setAttribute('aria-label',KO?'작업실 메뉴':'Workspace menu');
 items.forEach(function(x,i){var a=document.createElement('a');a.href=x[0];a.innerHTML=SI[x[0]]+'<span>'+x[1]+'</span>';if(x[0]===cur)a.setAttribute('aria-current','page');if(i===1||i===7||x[0]==='ops.html'){a.className='sep'}nav.appendChild(a)});
 var box=document.createElement('div');box.className='appmain';while(m.firstChild)box.appendChild(m.firstChild);var wrap=document.createElement('div');wrap.className='appshell';wrap.appendChild(nav);wrap.appendChild(box);m.appendChild(wrap)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',shell);else shell();
})();

(function(){function back(){var b=document.body;if(!b.hasAttribute('data-back'))return;var m=document.getElementById('main');if(!m||m.querySelector('.backbar'))return;
 var d=document.createElement('div');d.className='backbar';var w=document.createElement('div');w.className='wrap';var x=document.createElement('button');x.type='button';x.className='btn btn-ghost sm';x.textContent=(document.documentElement.lang==='ko'?'← 이전 화면으로 돌아가기':'← Back to the previous page');
 x.onclick=function(){var ref=document.referrer,same=false;try{same=ref&&new URL(ref).origin===location.origin}catch(e){}if(same&&history.length>1)history.back();else location.href='index.html'};w.appendChild(x);d.appendChild(w);m.insertBefore(d,m.firstChild)}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',back);else back()})();
/* AI CREATOR STUDIO — 기본 모델(남·여) 공용 모듈. 서버 호출 없음, three.js 필요.
   상태(성별·룩·옷 색)는 localStorage 'ais_fig'에 저장되어 3D·가상 착장 작업실이 같은 착장을 이어 씁니다.
   임시 저폴리 모델: 정식 GLB가 오면 이 모듈의 build()만 GLB 로드로 바꿉니다. */
(function(){
var KEY='ais_fig';
var DEF={g:'f',look:0,top:0xf4f1fa,bot:0x2c2a5e,acc:0x7a5cf5,skin:0,ts:'tee',bs:'pants',hs:-1,hc:-1,ax:0,bg:'default'};
var STR={ts:1,bs:1,bg:1};
var SK=[0xf1d9c6,0xe3b99a,0xc68e6a,0x8d5a3b];
var TS={tee:1,tank:1,long:1,jacket:1,dress:1},BS={pants:1,shorts:1,skirt:1};
function load(){var s={};try{s=JSON.parse(localStorage.getItem(KEY)||'{}')||{}}catch(e){}
 var o={};for(var k in DEF){if(k==='g')o.g=s.g==='m'?'m':'f';else if(STR[k])o[k]=typeof s[k]==='string'?s[k]:DEF[k];else o[k]=typeof s[k]==='number'?s[k]:DEF[k]}
 if(!TS[o.ts])o.ts='tee';if(!BS[o.bs])o.bs='pants';return o}
function save(o){try{localStorage.setItem(KEY,JSON.stringify(o))}catch(e){}}
function create(THREE){
 var st=load(),listeners=[];
 var group=new THREE.Group(),fig=new THREE.Group();group.add(fig);
 var V=THREE.Vector3,UP=new V(0,1,0);
 function M(c,r,mt){return new THREE.MeshStandardMaterial({color:c,roughness:r==null?.65:r,metalness:mt||0})}
 function add(o){o.castShadow=true;fig.add(o);return o}
 function ell(m,x,y,z,rx,ry,rz){var o=new THREE.Mesh(new THREE.SphereGeometry(1,28,20),m);o.position.set(x,y,z);o.scale.set(rx,ry,rz);return add(o)}
 function limb(m,a,b,r1,r2){var v=new V(b[0]-a[0],b[1]-a[1],b[2]-a[2]),len=v.length();var o=new THREE.Mesh(new THREE.CylinderGeometry(r2,r1,len,22),m);o.position.set((a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2);o.quaternion.setFromUnitVectors(UP,v.normalize());return add(o)}
 function lerpR(P,y){for(var i=0;i<P.length-1;i++){var a=P[i],b=P[i+1];if(y>=a[1]&&y<=b[1]){var t=(y-a[1])/((b[1]-a[1])||1);return a[0]+(b[0]-a[0])*t}}return P[P.length-1][0]}
 function lathe(m,P,y0,y1,grow,zs){var pts=[new THREE.Vector2(0.001,y0)];pts.push(new THREE.Vector2(lerpR(P,y0)+grow,y0));P.forEach(function(p){if(p[1]>y0&&p[1]<y1)pts.push(new THREE.Vector2(p[0]+grow,p[1]))});pts.push(new THREE.Vector2(lerpR(P,y1)+grow,y1));pts.push(new THREE.Vector2(0.001,y1));
  var o=new THREE.Mesh(new THREE.LatheGeometry(pts,36),m);o.scale.set(1,1,zs||.66);return add(o)}
 function build(){
  while(fig.children.length)fig.remove(fig.children[0]);
  var f=st.g==='f',ts=st.ts,bs=st.bs;
  var skin=M(SK[st.skin]||SK[0],.8),tm=M(st.top),bm=M(st.bot),am=M(st.acc,.5),gold=M(0xd4a73a,.3,.8),dark=M(0x1c1a22,.4);
  var hc=st.hc>=0?st.hc:(f?0x3b2a24:0x2a2420),hm=M(hc,.85);
  var shx=f?.2:.25,hs=st.hs>=0?st.hs:(f?0:2);
  var TP=f?[[.0,.9],[.13,.9],[.165,.98],[.135,1.12],[.15,1.3],[.165,1.42],[.1,1.52],[.05,1.57]]:[[.0,.9],[.14,.9],[.15,.98],[.145,1.12],[.17,1.3],[.2,1.42],[.11,1.52],[.05,1.57]];
  // body
  lathe(skin,TP,.9,1.57,0,.62);
  var hx=f?.095:.09;
  [-1,1].forEach(function(s){
   limb(skin,[s*hx,.96,0],[s*(hx+.012),.52,0],f?.082:.078,.058);limb(skin,[s*(hx+.012),.52,0],[s*(hx+.012),.09,0],.058,.04);
   ell(skin,s*(hx+.012),.52,0,.06,.06,.06);
   ell(am,s*(hx+.012),.04,.045,.055,.04,.105);
   var sx=s*shx;limb(skin,[sx,1.46,0],[s*(shx+.05),1.2,0],.05,.04);limb(skin,[s*(shx+.05),1.2,0],[s*(shx+.09),.95,.02],.04,.03);
   ell(skin,sx,1.47,0,.055,.055,.055);ell(skin,s*(shx+.09),.92,.025,.034,.045,.03);
  });
  // head
  limb(skin,[0,1.52,0],[0,1.62,0],.045,.042);
  ell(skin,0,1.7,0,.088,.115,.1);
  [-1,1].forEach(function(s){ell(dark,s*.035,1.7,.09,.009,.011,.008)});
  // hair
  if(hs===0){ell(hm,0,1.715,-.012,.098,.122,.108);limb(hm,[0,1.68,-.07],[0,1.33,-.075],.09,.07)}
  else if(hs===1){ell(hm,0,1.715,-.012,.098,.122,.108);limb(hm,[0,1.66,-.07],[0,1.52,-.075],.092,.088)}
  else if(hs===2){ell(hm,0,1.722,-.012,.094,.118,.104)}
  else{ell(hm,0,1.718,-.012,.096,.12,.106);ell(hm,0,1.85,-.045,.045,.045,.045)}
  // top
  var topc=(ts==='dress')?tm:tm;
  if(ts==='tank'){lathe(tm,TP,1.0,1.46,.01,.62)}
  else if(ts==='tee'||ts==='long'||ts==='jacket'||ts==='dress'){
   lathe(tm,TP,ts==='jacket'?.92:1.0,1.5,.012,.62);
   [-1,1].forEach(function(s){var sx=s*shx,ex=s*(shx+.05),wx=s*(shx+.09);
    if(ts==='tee'||ts==='dress'){limb(tm,[sx,1.46,0],[sx+(ex-sx)*.5,1.33,0],.062,.055);ell(tm,sx,1.47,0,.062,.062,.062)}
    else{limb(tm,[sx,1.46,0],[ex,1.2,0],.058,.048);limb(tm,[ex,1.2,0],[wx,.99,.02],.048,.04);ell(tm,sx,1.47,0,.062,.062,.062)}});
   if(ts==='jacket')lathe(am,TP,.96,1.5,.016,.62).scale.set(.18,1,.7)
  }
  // bottom
  if(ts==='dress'){
   var o=new THREE.Mesh(new THREE.CylinderGeometry(.16,.3,.62,36,1,true),tm.clone());o.material.side=THREE.DoubleSide;o.position.set(0,.83,0);o.scale.set(1,1,.85);add(o);
   lathe(tm,TP,.98,1.12,.012,.62);
  }else if(bs==='skirt'){
   var k=new THREE.Mesh(new THREE.CylinderGeometry(.15,.26,.46,36,1,true),bm.clone());k.material.side=THREE.DoubleSide;k.position.set(0,.84,0);k.scale.set(1,1,.82);add(k);lathe(bm,TP,.98,1.1,.012,.62)
  }else{
   lathe(bm,TP,.88,1.1,.014,.64);
   [-1,1].forEach(function(s){
    if(bs==='shorts'){limb(bm,[s*hx,.96,0],[s*(hx+.008),.68,0],(f?.082:.078)+.014,.07)}
    else{limb(bm,[s*hx,.96,0],[s*(hx+.012),.52,0],(f?.082:.078)+.014,.07);limb(bm,[s*(hx+.012),.52,0],[s*(hx+.012),.1,0],.07,.05);ell(bm,s*(hx+.012),.52,0,.07,.06,.07)}
   })}
  // accessories
  var ax=st.ax|0;
  if(ax&1){var c=new THREE.Mesh(new THREE.CylinderGeometry(.095,.1,.085,32),am);c.position.set(0,1.81,0);add(c);var b=new THREE.Mesh(new THREE.CylinderGeometry(.17,.17,.012,40),am);b.position.set(0,1.77,.01);add(b)}
  if(ax&2){[-1,1].forEach(function(s){var r=new THREE.Mesh(new THREE.TorusGeometry(.03,.004,10,24),dark);r.position.set(s*.037,1.7,.097);add(r)});var br=new THREE.Mesh(new THREE.BoxGeometry(.02,.004,.004),dark);br.position.set(0,1.703,.098);add(br)}
  if(ax&4){[-1,1].forEach(function(s){ell(gold,s*.09,1.66,0,.012,.018,.012)})}
  if(ax&8){var n=new THREE.Mesh(new THREE.TorusGeometry(.062,.006,10,32),gold);n.rotation.x=Math.PI/2.4;n.position.set(0,1.51,.012);add(n);ell(gold,0,1.445,.06,.012,.012,.012)}
  if(ax&16){var sc=new THREE.Mesh(new THREE.TorusGeometry(.068,.02,12,32),am);sc.rotation.x=Math.PI/2.2;sc.position.set(0,1.52,.005);add(sc);var tail=new THREE.Mesh(new THREE.BoxGeometry(.05,.2,.018),am);tail.position.set(.04,1.41,.095);tail.rotation.z=.06;add(tail)}
 }
 function emit(){listeners.forEach(function(fn){try{fn(st)}catch(e){}})}
 function set(p,quiet){
  if(p.look!==undefined&&p.ts===undefined&&p.bs===undefined){var f=(p.g||st.g)==='f',l=p.look;p.ts=l===1?'jacket':(l===2?(f?'dress':'tee'):'tee');p.bs=l===1?(f?'skirt':'pants'):(l===2&&!f?'shorts':'pants')}
  for(var k in p)st[k]=p[k];save(st);build();if(!quiet)emit()}
 window.addEventListener('storage',function(e){if(e.key===KEY){st=load();build();emit()}});
 build();
 return {group:group,state:function(){return st},set:set,build:build,on:function(fn){listeners.push(fn)},
  hex:function(n){return '#'+('000000'+n.toString(16)).slice(-6)},num:function(h){return parseInt(String(h).slice(1),16)}};
}
window.AISFIG={create:create,load:load};
})();
