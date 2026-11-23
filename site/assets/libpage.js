/* 라이브러리 v2: 사진 중심 갤러리 + 오른쪽 상세 창 (2026-11-23)
   위: 보기 범위·검색·올리기 / 가운데: 종류 탭 + 사진 갤러리 / 카드 클릭: 오른쪽 상세 창 */
(function(){
var KO=document.documentElement.lang==='ko';function T(a,b){return KO?a:b}
var $=function(i){return document.getElementById(i)};
var C=AISCAT.cats;
var CATS=['hair','hcolor','htex','face','eyes','brow','nose','lip','tone','skin','body','mood','acc','bg','cam','lite'];
var TABS=[['all',T('전체','All')],['model',T('모델','Models')],['garment',T('의류','Clothing')],['prop',T('소품','Props')],['bg',T('배경','Backgrounds')],['pose',T('포즈','Poses')],['3d',T('3D 파일','3D files')],['render',T('작업 결과','Results')],['cat',T('스타일 도감','Style catalog')]];
var GSUB=[['all',T('전체','All')],['top',T('상의','Tops')],['bot',T('하의','Bottoms')],['dress',T('원피스','Dresses')]];
var st={tab:'all',sub:'all',cat:'hair',q:'',type:'f',pick:null};
function el(t,c,h){var e=document.createElement(t);if(c)e.className=c;if(h!=null)e.innerHTML=h;return e}
function nm(c){return KO?c.ko:c.en}
function esc(s){return String(s||'').replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
/* 도감 사진: 고른 화풍·지역 사진이 없으면 실사·동양 사진으로 대체 */
function catImg(cat,it){var raw=it.id.replace(/^[a-z]+-/,'');return {a:'../'+AISCAT.img(cat,raw,AISCAT.style(),AISCAT.region()),b:'../'+AISCAT.img(cat,raw,'photo','east')}}
function typeOk(it){if(!it.t||it.t==='all')return true;if(st.type==='n'||st.type==='c')return true;return it.t===st.type}
function libItems(){var A=AISLIB.all();if(st.tab==='all')return A.filter(function(x){return x.kind!=='render'||true});return A.filter(function(x){if(x.kind!==st.tab)return false;if(st.tab==='garment'&&st.sub!=='all')return AISLIB.slotOf(x)===st.sub;return true})}
function catItems(){var c=C[st.cat];if(!c)return [];if(AISLIB.scope&&AISLIB.scope()==='ours')return [];return c.items.filter(typeOk).map(function(it){var im=catImg(st.cat,it);return {id:it.id,name:KO?it.ko:it.en,src:im.a,alt:im.b,cat:st.cat,_c:it,origin:'ai'}})}
function list(){var L=st.tab==='cat'?catItems():libItems();if(st.q){var q=st.q.toLowerCase();L=L.filter(function(x){return ((x.name||'')+' '+(x.attrs?Object.keys(x.attrs).map(function(k){return x.attrs[k]}).join(' '):'')).toLowerCase().indexOf(q)>=0})}return L}
var KN={model:T('모델','Model'),garment:T('의류','Clothing'),prop:T('소품','Prop'),bg:T('배경','Background'),pose:T('포즈','Pose'),'3d':'3D',render:T('작업 결과','Result')};
function badge(x){if(x.origin&&x.origin!=='ai')return '<em class="lg-b mine">'+T('우리 자료','Ours')+'</em>';return '<em class="lg-b">AI</em>'}
function card(x){var c=el('button','lg-card'+(st.pick&&st.pick.id===x.id?' on':''));c.type='button';
 c.innerHTML='<span class="lg-im"><img alt="" loading="lazy" src="'+esc(x.src)+'">'+badge(x)+(st.tab==='all'?'<i class="lg-k">'+(KN[x.kind]||'')+'</i>':'')+'</span><b>'+esc(x.name)+'</b><small>'+esc(sub(x))+'</small>';
 var im=c.querySelector('img');im.onerror=function(){if(x.alt&&im.src.indexOf(x.alt.replace('../',''))<0){im.src=x.alt}else{im.remove();c.querySelector('.lg-im').classList.add('ph')}};
 c.onclick=function(){st.pick=x;draw();openD(x)};return c}
function sub(x){if(x._c)return x._c.desc?(KO?x._c.desc:(x._c.descEn||'')):nm(C[x.cat]);var a=x.attrs||{};return [a.type,a.season,a.sku].filter(Boolean).join(' · ')}
/* 상단 */
function head(m){var h=el('div','lg-head');
 var left=el('div','lg-hl');left.appendChild(AISLIB.scopeBar());h.appendChild(left);
 var sr=el('input','lg-q');sr.type='search';sr.placeholder=T('이름·태그·품번으로 찾기','Search name, tag or SKU');sr.value=st.q;sr.oninput=function(){st.q=sr.value.trim();grid();};h.appendChild(sr);
 var up=el('div','lg-up');var cb=el('label','lg-r','<input type="checkbox" id="librights"> <span>'+T('올리는 파일을 사용할 권리가 있습니다','I have the right to use these files')+'</span>');up.appendChild(cb);
 var bt=el('button','btn btn-primary sm',T('＋ 우리 자료 올리기','＋ Upload ours'));bt.type='button';bt.style.color='var(--violet-ink)';
 bt.onclick=function(){var r=$('librights');if(!r.checked){cb.classList.add('warn');setTimeout(function(){cb.classList.remove('warn')},1600);r.focus();return}var kind=(st.tab==='all'||st.tab==='cat'||st.tab==='render'||st.tab==='3d')?'garment':st.tab;var fi=document.createElement('input');fi.type='file';fi.accept='image/*';fi.multiple=true;fi.onchange=function(){var fs=[].slice.call(fi.files||[]);if(fs.length)AISLIB.register(kind,fs,function(){draw()})};fi.click()};
 up.appendChild(bt);h.appendChild(up);m.appendChild(h)}
function tabs(m){var t=el('div','lg-tabs');TABS.forEach(function(x){var n=x[0]==='cat'?CATS.reduce(function(s,k){return s+(C[k]?C[k].items.filter(typeOk).length:0)},0):(x[0]==='all'?AISLIB.all().length:AISLIB.all().filter(function(y){return y.kind===x[0]}).length);var b=el('button',st.tab===x[0]?'on':'','<span>'+x[1]+'</span><em>'+n+'</em>');b.type='button';b.onclick=function(){st.tab=x[0];st.sub='all';st.pick=null;closeD();draw()};t.appendChild(b)});m.appendChild(t);
 var s=el('div','lg-sub');
 if(st.tab==='garment')GSUB.forEach(function(x){var b=el('button','chip',x[1]);b.type='button';b.setAttribute('aria-pressed',st.sub===x[0]);b.onclick=function(){st.sub=x[0];draw()};s.appendChild(b)});
 if(st.tab==='cat'){[['f',T('여성','Female')],['m',T('남성','Male')],['n',T('중성적','Neutral')]].forEach(function(x){var b=el('button','chip lg-ty',x[1]);b.type='button';b.setAttribute('aria-pressed',st.type===x[0]);b.onclick=function(){st.type=x[0];draw()};s.appendChild(b)});s.appendChild(el('i','lg-dv'));
  CATS.forEach(function(k){if(!C[k])return;var b=el('button','chip',nm(C[k]));b.type='button';b.setAttribute('aria-pressed',st.cat===k);if(AISCAT.get()[k])b.classList.add('picked');b.onclick=function(){st.cat=k;st.pick=null;closeD();draw()};s.appendChild(b)})}
 if(s.children.length)m.appendChild(s)}
var G=null;function grid(){if(!G)return;G.innerHTML='';var L=list();if(!L.length){G.appendChild(el('p','lg-empty',AISLIB.scope&&AISLIB.scope()==='ours'?T('우리 자료가 아직 없습니다. 위의 "우리 자료 올리기"로 등록하세요.','No items of yours yet. Use "Upload ours" above.'):T('맞는 항목이 없습니다.','No matching items.')));return}L.forEach(function(x){G.appendChild(card(x))})}
/* 오른쪽 상세 창 */
var D=null;
function openD(x){if(!D){D=el('aside','lg-detail');document.body.appendChild(D)}var isCat=!!x._c,a=x.attrs||{};
 var rows=isCat?[[T('분류','Group'),nm(C[x.cat])],[T('화풍','Style'),AISCAT.style()],[T('지역','Region'),AISCAT.region()]]:[[T('종류','Type'),a.type||KN[x.kind]],[T('색','Color'),a.color?'<i class="lg-sw" style="background:'+esc(a.color)+'"></i>'+esc(a.color):''],[T('계절','Season'),a.season],[T('품번','SKU'),a.sku],[T('컬렉션','Collection'),a.collection],[T('출처','Source'),x.origin==='ai'?T('기본 제공 (AI 생성)','Provided (AI-generated)'):(x.origin==='work'?T('작업 결과','Work result'):T('우리 팀 업로드','Uploaded by your team'))]];
 var picked=isCat&&AISCAT.get()[x.cat]===x.id;
 D.innerHTML='<button type="button" class="lg-x" aria-label="'+T('닫기','Close')+'">×</button><div class="lg-dim"><img alt="" src="'+esc(x.full||x.src)+'">'+badge(x)+'</div><h3>'+esc(x.name)+'</h3>'+(isCat&&x._c.desc?'<p class="fine">'+esc(KO?x._c.desc:(x._c.descEn||''))+'</p>':'')
  +'<dl>'+rows.filter(function(r){return r[1]}).map(function(r){return '<div><dt>'+r[0]+'</dt><dd>'+r[1]+'</dd></div>'}).join('')+'</dl>'
  +(isCat?'<button type="button" class="btn btn-primary lg-pick" style="color:var(--violet-ink)">'+(picked?T('선택 해제','Unselect'):T('이 스타일 선택','Select this style'))+'</button><p class="fine">'+T('고른 스타일은 캐릭터·가상 착장·3D 작업실에서 그대로 쓰입니다.','Selected styles carry into Character, Try-on and 3D.')+'</p>':'')
  +'<b class="lg-use">'+T('작업실에서 쓰기','Use in a workroom')+'</b><div class="lg-go">'+[['studio-3d.html','3D Studio'],['tryon-studio.html','Virtual Try-on'],['studio.html','Photo Studio'],['studio-video.html','Video Studio']].map(function(g){return '<a href="'+g[0]+'">'+g[1]+' →</a>'}).join('')+'</div>'
  +(x.origin&&x.origin!=='ai'&&!isCat?'<button type="button" class="lg-del">'+T('이 자료 삭제','Delete this item')+'</button>':'');
 D.querySelector('.lg-x').onclick=closeD;var im=D.querySelector('.lg-dim img');im.onerror=function(){if(x.alt&&im.src.indexOf(x.alt.replace('../',''))<0)im.src=x.alt};
 var pk=D.querySelector('.lg-pick');if(pk)pk.onclick=function(){AISCAT.set(x.cat,picked?null:x.id);openD(x);draw()};
 var dl=D.querySelector('.lg-del');if(dl)dl.onclick=function(){if(dl.dataset.c){if(AISLIB.removeUser)AISLIB.removeUser(x.id);else if(AISLIB.remove)AISLIB.remove(x.id);closeD();st.pick=null;draw()}else{dl.dataset.c='1';dl.textContent=T('한 번 더 누르면 삭제됩니다','Click again to delete')}};
 requestAnimationFrame(function(){D.classList.add('on')});document.body.classList.add('lg-open')}
function closeD(){if(D)D.classList.remove('on');document.body.classList.remove('lg-open')}
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeD()});
function draw(){var root=$('lmain');if(!root)return;var nv=$('lnav');if(nv)nv.style.display='none';root.innerHTML='';root.classList.add('lg');head(root);tabs(root);G=el('div','lg-grid');root.appendChild(G);grid()}
window.addEventListener('ais-libscope',function(){draw()});window.addEventListener('ais-lib-changed',function(){draw()});
draw();
})();
