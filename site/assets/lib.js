/* AISLIB — 라이브러리(모델·의류·소품·배경·포즈) 데이터와 고르기 패널. 서버가 연결되면 AIS_API.library()가 같은 모양의 목록을 돌려주면 된다. */
(function(){
var KO=(document.documentElement.lang||'ko')==='ko';
function T(a,b){return KO?a:b}
function svg(body,bg){return 'data:image/svg+xml;utf8,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" fill="'+(bg||'#f3effc')+'"/>'+body+'</svg>')}
var SH={
 tee:'20,18 38,26 62,26 80,18 100,40 84,54 76,48 76,92 24,92 24,48 16,54 0,40',
 shirt:'18,18 40,24 50,34 60,24 82,18 100,48 86,60 78,52 78,92 22,92 22,52 14,60 0,48',
 jacket:'16,16 40,22 50,40 60,22 84,16 100,50 86,62 80,54 80,94 20,94 20,54 14,62 0,50',
 knit:'18,18 40,24 50,38 60,24 82,18 100,48 88,62 80,54 80,92 20,92 20,54 12,62 0,48',
 dress:'30,12 42,20 58,20 70,12 76,40 98,94 2,94 24,40',
 coat:'14,14 40,20 50,38 60,20 86,14 100,52 88,66 82,58 82,96 18,96 18,58 12,66 0,52',
 pants:'24,12 76,12 86,94 54,94 50,40 46,94 14,94',
 skirt:'26,14 74,14 98,92 2,92'
};
function garSvg(sh,c){var dark=/^#[0-4]/.test(c);return svg('<polygon points="'+SH[sh]+'" fill="'+c+'" stroke="'+(dark?'#6b6580':'#00000022')+'" stroke-width="1" transform="translate(10 4) scale(.8)"/>')}
function propSvg(k,c){
 var b={bag:'<rect x="24" y="42" width="52" height="38" rx="6" fill="'+c+'"/><path d="M36 42 Q50 14 64 42" fill="none" stroke="'+c+'" stroke-width="5"/>',
 hat:'<ellipse cx="50" cy="62" rx="40" ry="9" fill="'+c+'"/><path d="M26 62 Q28 24 50 24 Q72 24 74 62Z" fill="'+c+'"/>',
 glasses:'<circle cx="32" cy="52" r="15" fill="'+c+'"/><circle cx="68" cy="52" r="15" fill="'+c+'"/><rect x="44" y="49" width="12" height="4" fill="'+c+'"/>',
 scarf:'<path d="M26 28 Q50 44 74 28 L80 46 Q50 62 20 46Z" fill="'+c+'"/><rect x="58" y="46" width="14" height="36" rx="3" fill="'+c+'"/>',
 earring:'<circle cx="34" cy="40" r="5" fill="'+c+'"/><ellipse cx="34" cy="60" rx="7" ry="11" fill="'+c+'"/><circle cx="66" cy="40" r="5" fill="'+c+'"/><ellipse cx="66" cy="60" rx="7" ry="11" fill="'+c+'"/>',
 belt:'<rect x="8" y="42" width="84" height="14" rx="3" fill="'+c+'"/><rect x="42" y="38" width="16" height="22" rx="2" fill="none" stroke="#d4b25a" stroke-width="4"/>',
 watch:'<rect x="40" y="10" width="20" height="80" rx="6" fill="'+c+'"/><circle cx="50" cy="50" r="20" fill="#fff" stroke="'+c+'" stroke-width="6"/><path d="M50 50 L50 38 M50 50 L58 54" stroke="#222" stroke-width="3"/>',
 shoes:'<path d="M14 66 Q16 44 40 44 L56 56 Q84 56 88 70 L88 76 L14 76Z" fill="'+c+'"/>'};
 return svg(b[k]||b.bag)}
function bgSvg(k){
 var m={white:'<rect width="100" height="100" fill="#ffffff"/>',gray:'<rect width="100" height="100" fill="#d9d8de"/><rect y="78" width="100" height="22" fill="#c8c6d0"/>',beige:'<rect width="100" height="100" fill="#efe3d1"/><rect y="76" width="100" height="24" fill="#e1d0b8"/>',lilac:'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ece6ff"/><stop offset="1" stop-color="#cfc4f5"/></linearGradient></defs><rect width="100" height="100" fill="url(#g)"/>',
 showroom:'<rect width="100" height="100" fill="#e9e4f3"/><rect x="8" y="14" width="2" height="60" fill="#8e84b0"/><rect x="8" y="14" width="46" height="2" fill="#8e84b0"/><rect y="76" width="100" height="24" fill="#cfc7e3"/>',
 street:'<defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#bcd7f5"/><stop offset="1" stop-color="#e8f0fa"/></linearGradient></defs><rect width="100" height="100" fill="url(#s)"/><rect x="6" y="30" width="26" height="50" fill="#a9a1bd"/><rect x="38" y="20" width="30" height="60" fill="#b9b2cd"/><rect y="80" width="100" height="20" fill="#8f8aa0"/>',
 dusk:'<defs><linearGradient id="d" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a2f6b"/><stop offset="1" stop-color="#e0a7a0"/></linearGradient></defs><rect width="100" height="100" fill="url(#d)"/>',
 brick:'<rect width="100" height="100" fill="#b86f5a"/><path d="M0 20H100M0 40H100M0 60H100M0 80H100M25 0V20M75 20V40M25 40V60M75 60V80" stroke="#8a4d3d" stroke-width="2"/>'};
 return svg(m[k]||m.white,'#fff')}
function poseSvg(k){
 var P={front:'<circle cx="50" cy="18" r="8"/><path d="M50 26V60M50 34L30 52M50 34L70 52M50 60L38 92M50 60L62 92"/>',side:'<circle cx="52" cy="18" r="8"/><path d="M50 26V60M50 34L48 56M50 60L44 92M50 60L58 92"/>',walk:'<circle cx="50" cy="18" r="8"/><path d="M50 26V58M50 34L34 54M50 34L66 48M50 58L36 90M50 58L66 86"/>',hip:'<circle cx="50" cy="18" r="8"/><path d="M50 26V60M50 34L32 46L40 58M50 34L68 46L60 58M50 60L40 92M50 60L60 92"/>',cross:'<circle cx="50" cy="18" r="8"/><path d="M50 26V60M50 36L36 48L62 48M50 36L64 48L38 48M50 60L40 92M50 60L60 92"/>',sit:'<circle cx="40" cy="22" r="8"/><path d="M40 30V60L70 60L70 92M40 38L56 52M40 60L36 92"/>'};
 return svg('<g fill="#5436f0" stroke="#5436f0" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill-opacity="1">'+(P[k]||P.front).replace(/<path /g,'<path fill="none" ')+'</g>')}
var D=[];
function add(o){o.src=o.src;D.push(o)}
[['model-01','서윤','20대','보통','베이지','긴 생머리'],['model-02','도윤','20대','슬림','웜','짧은 컷'],['model-03','하나','30대','플러스','올리브','짧은 곱슬'],['mk-model','리아','20대','보통','라이트','긴 머리'],['card-character','은빛','20대','슬림','라이트','은빛 긴 웨이브'],['card-3d','유나','20대','보통','웜','긴 머리']].forEach(function(m,i){
 add({id:'m'+i,kind:'model',name:m[1],src:'../img/'+m[0]+'-480.webp',full:'../img/'+m[0]+'-960.webp',origin:'ai',attrs:{age:m[2],body:m[3],skin:m[4],hair:m[5]}})});
/* 실사 의류 36벌(2026-11-22 생성, 자산 저장소) */
[['tee','화이트 티셔츠','White T-shirt','상의','#f4f4f2','사계절','d21430873f30ddb973ddd1fe3cc50d8f'],
['tee','블랙 티셔츠','Black T-shirt','상의','#1c1c1e','사계절','c0b4ba7e3894f3748ed01c6b65860dcb'],
['shirt','옥스퍼드 셔츠','Oxford shirt','상의','#b8cde8','봄·가을','5aa506668e0d8eb33aa186c5b26f03a3'],
['shirt','실크 블라우스','Silk blouse','상의','#f1d9d6','봄·여름','53f37e7e4ce33a2cdfaf95b96c216e1a'],
['knit','케이블 니트','Cable knit','상의','#efe6d2','가을·겨울','55303e97b97e5fc798a949befecfb9f8'],
['knit','네이비 니트','Navy knit','상의','#1f2540','가을·겨울','62f335cbb93ddf8b5efdb155211fd379'],
['jacket','테일러드 블레이저','Tailored blazer','아우터','#1a1a1c','봄·가을','0ae625035068ae3b8c95cfc78e16a2b7'],
['coat','트렌치코트','Trench coat','아우터','#c9a97c','봄·가을','1b0c3a398087782b24d8b31082611971'],
['coat','울 롱코트','Wool long coat','아우터','#3b3d42','겨울','48b47f8b1d79f7252e0733e313e28a33'],
['hoodie','그레이 후드티','Grey hoodie','상의','#a7a8aa','봄·가을','25a03c308ae71e7e45d8827bc2a8486c'],
['jacket','데님 재킷','Denim jacket','아우터','#5b7ea8','봄·가을','cd62a1b2605d31a7ea9de69c5bf51ab0'],
['jacket','레더 재킷','Leather jacket','아우터','#1d1d1f','봄·가을','57e43ecf523ac58d9736085aae02bef2'],
['shirt','화이트 셔츠','White shirt','상의','#f7f7f5','사계절','f8fd5757c395870e4d31da8933a76c70'],
['tee','스트라이프 롱슬리브','Striped long sleeve','상의','#1f2a4a','봄·가을','5357e595a6a320b117f8471b49289151'],
['jacket','봄버 재킷','Bomber jacket','아우터','#5e6b3e','봄·가을','0c5ca9255b55cda73d0038c169746360'],
['knit','카멜 가디건','Camel cardigan','상의','#b88552','가을','e2b5ba1dab637c1dbb29ccdb8c2dffe0'],
['knit','블랙 터틀넥','Black turtleneck','상의','#1a1a1c','가을·겨울','a75462e222ae07f41cc8313b6ef88aad'],
['coat','블랙 패딩','Black puffer','아우터','#1b1c1f','겨울','d54d446a75468526e46041f557d15db9'],
['pants','스트레이트 청바지','Straight jeans','하의','#4f6f9c','사계절','170d54212dabb3a7dae2bb9f61bcaf18'],
['pants','블랙 슬림 진','Black slim jeans','하의','#1c1c1e','사계절','bc69dfe31d3fe6de295a55d6c58ece0b'],
['pants','와이드 치노','Wide chinos','하의','#d6c3a0','봄·가을','2cb4111957db649010520178d348161d'],
['pants','울 슬랙스','Wool slacks','하의','#5a5c60','가을·겨울','c24804e974f701b982c5fa0974b36288'],
['skirt','플리츠 미디스커트','Pleated midi skirt','하의','#1a1a1a','사계절','99e46da34f59f0340f4f52da1068b372'],
['skirt','A라인 미디스커트','A-line midi skirt','하의','#efe5cf','봄·여름','8732cb8cf65b7e8dd767834cc397949e'],
['skirt','데님 미니스커트','Denim mini skirt','하의','#a9bdd3','여름','640c0c196eb050ab1387fe3877c0377a'],
['pants','카고 팬츠','Cargo pants','하의','#c2ad84','사계절','f79197b9060cf84f4b089dbb3566fcaa'],
['shorts','네이비 쇼츠','Navy shorts','하의','#1f2638','여름','bf3e2db8c78c875c97593c3e8f6625c5'],
['dress','새틴 슬립 원피스','Satin slip dress','원피스','#151515','사계절','f478b4746fe42638dfcfeceb95fb3e1f'],
['dress','플로럴 랩 원피스','Floral wrap dress','원피스','#8a6e6a','봄·여름','2a11345028673f1ae1197c7a8f2bf415'],
['dress','린넨 셔츠 원피스','Linen shirt dress','원피스','#f3f1ec','여름','a7186cda535ca47733acdc203fb10caa'],
['dress','니트 원피스','Knit dress','원피스','#1d2236','가을·겨울','8077055d693dc23d617474a54b9256d9'],
['dress','에메랄드 새틴 원피스','Emerald satin dress','원피스','#1e6b52','사계절','6abfc6da98651c8e9f3b3e609b584ab3'],
['dress','라벤더 플리츠 원피스','Lavender pleated dress','원피스','#b9a3dc','봄·여름','37733b591031637932ee6318a2d68659'],
['dress','스트라이프 선드레스','Striped sundress','원피스','#9db7dc','여름','1e090644e434e890304a04e2f833afc7'],
['dress','트렌치 원피스','Trench dress','원피스','#cbb08a','봄·가을','feaeddf9a390e24beb6991a75eafca7b'],
['dress','버건디 맥시 원피스','Burgundy maxi dress','원피스','#6a1f2a','가을·겨울','5c28732f80ae2bc52d401fb8d2f8ffa5']].forEach(function(g,i){
 add({id:'gp'+i,kind:'garment',name:g[1],en:g[2],src:'/_blob/'+g[6],full:'/_blob/'+g[6],origin:'ai',attrs:{type:g[3],color:g[4],season:g[5]},shape:g[0],color:g[4]})});
[['bag','핸드백','#24212f'],['bag','토트백','#b9a07a'],['hat','모자','#e8dcc4'],['glasses','선글라스','#24212f'],['scarf','스카프','#b9a8ff'],['earring','귀걸이','#d4b25a'],['belt','벨트','#5a3a26'],['watch','시계','#24212f'],['shoes','신발','#f4f1ea']].forEach(function(p,i){
 add({id:'p'+i,kind:'prop',name:p[1],src:propSvg(p[0],p[2]),origin:'ai',attrs:{type:'소품'}})});
[['white','스튜디오 흰색'],['gray','스튜디오 회색'],['beige','베이지 벽'],['lilac','라벤더 그라데이션'],['showroom','쇼룸'],['street','거리'],['dusk','노을'],['brick','벽돌']].forEach(function(b,i){
 add({id:'b'+i,kind:'bg',name:b[1],src:bgSvg(b[0]),origin:'ai',attrs:{type:i<4?'스튜디오':'장소'}})});
[['studio-white','스튜디오 화이트 (사진)'],['studio-grey','스튜디오 그레이 (사진)'],['cafe','카페 (사진)'],['city','도시 거리 (사진)'],['nature','자연 (사진)'],['sunset','노을 (사진)']].forEach(function(b,i){
 add({id:'bp'+i,kind:'bg',name:b[1],src:'../img/cat/bg-'+b[0]+'.webp',full:'../img/cat/bg-'+b[0]+'.webp',origin:'ai',attrs:{type:'사진'}})});
(function(){var M={p2:'hat',p3:'glasses',p4:'scarf',p5:'earring'};D.forEach(function(x){if(M[x.id]){x.src='../img/cat/acc-'+M[x.id]+'.webp';x.full=x.src}})})();
[['necklace','목걸이'],['ring','반지']].forEach(function(a,i){add({id:'p'+(9+i),kind:'prop',name:a[1],src:'../img/cat/acc-'+a[0]+'.webp',full:'../img/cat/acc-'+a[0]+'.webp',origin:'ai',attrs:{type:'소품'}})});
[['front','정면 서기'],['side','측면'],['walk','걷기'],['hip','손 허리'],['cross','팔짱'],['sit','앉기']].forEach(function(p,i){
 add({id:'s'+i,kind:'pose',name:p[1],src:poseSvg(p[0]),origin:'ai',attrs:{type:'포즈'}})});

function cube(){return svg('<path d="M50 14 L84 32 L84 68 L50 86 L16 68 L16 32Z" fill="#cfc6ff" stroke="#5436f0" stroke-width="3"/><path d="M50 14 L50 50 L16 32 M50 50 L84 32 M50 50 L50 86" fill="none" stroke="#5436f0" stroke-width="3"/>')}
if(!KO){var EN={'서윤':'Seoyun','도윤':'Doyun','하나':'Hana','리아':'Ria','은빛':'Eunbit','유나':'Yuna','20대':'20s','30대':'30s','보통':'Regular','슬림':'Slim','플러스':'Plus','베이지':'Beige','웜':'Warm','올리브':'Olive','라이트':'Light','단발':'Bob','짧은 컷':'Short cut','웨이브':'Wavy','긴 머리':'Long hair','스트레이트 청바지':'Straight jeans','블랙 슬림 진':'Black slim jeans','와이드 치노':'Wide chinos','울 슬랙스':'Wool slacks','플리츠 미디스커트':'Pleated midi skirt','A라인 미디스커트':'A-line midi skirt','데님 미니스커트':'Denim mini skirt','카고 팬츠':'Cargo pants','네이비 쇼츠':'Navy shorts','새틴 슬립 원피스':'Satin slip dress','플로럴 랩 원피스':'Floral wrap dress','린넨 셔츠 원피스':'Linen shirt dress','니트 원피스':'Knit dress','에메랄드 새틴 원피스':'Emerald satin dress','라벤더 플리츠 원피스':'Lavender pleated dress','스트라이프 선드레스':'Striped sundress','트렌치 원피스':'Trench dress','버건디 맥시 원피스':'Burgundy maxi dress','화이트 티셔츠':'White T-shirt','블랙 티셔츠':'Black T-shirt','옥스퍼드 셔츠':'Oxford shirt','실크 블라우스':'Silk blouse','케이블 니트':'Cable knit','네이비 니트':'Navy knit','테일러드 블레이저':'Tailored blazer','트렌치코트':'Trench coat','울 롱코트':'Wool long coat','그레이 후드티':'Grey hoodie','데님 재킷':'Denim jacket','레더 재킷':'Leather jacket','화이트 셔츠':'White shirt','스트라이프 롱슬리브':'Striped long sleeve','봄버 재킷':'Bomber jacket','카멜 가디건':'Camel cardigan','블랙 터틀넥':'Black turtleneck','블랙 패딩':'Black puffer','스튜디오 화이트 (사진)':'Studio white (photo)','스튜디오 그레이 (사진)':'Studio grey (photo)','카페 (사진)':'Cafe (photo)','도시 거리 (사진)':'City street (photo)','자연 (사진)':'Nature (photo)','노을 (사진)':'Sunset (photo)','목걸이':'Necklace','반지':'Ring','사진':'Photo','긴 생머리':'Long straight','짧은 곱슬':'Short curly','은빛 긴 웨이브':'Silver long wavy','은빛 단발':'Silver bob','티셔츠':'T-shirt','오버핏 셔츠':'Oversized shirt','셔츠':'Shirt','니트':'Knit','테일러드 재킷':'Tailored jacket','재킷':'Jacket','롱 코트':'Long coat','코트':'Coat','플리츠 원피스':'Pleated dress','원피스':'Dress','상의':'Top','아우터':'Outerwear','하의':'Bottom','봄·여름':'Spring-summer','사계절':'All seasons','봄·가을':'Spring-autumn','가을·겨울':'Autumn-winter','겨울':'Winter','핸드백':'Handbag','토트백':'Tote bag','모자':'Hat','선글라스':'Sunglasses','스카프':'Scarf','귀걸이':'Earrings','벨트':'Belt','시계':'Watch','신발':'Shoes','소품':'Accessory','스튜디오 흰색':'Studio white','스튜디오 회색':'Studio gray','베이지 벽':'Beige wall','라벤더 그라데이션':'Lavender gradient','쇼룸':'Showroom','거리':'Street','노을':'Dusk','벽돌':'Brick','스튜디오':'Studio','장소':'Location','정면 서기':'Standing front','측면':'Side','걷기':'Walking','손 허리':'Hand on hip','팔짱':'Arms crossed','앉기':'Sitting','포즈':'Pose','와이드 팬츠':'Wide pants','데님 팬츠':'Denim pants','A라인 스커트':'A-line skirt','스커트':'Skirt','가을':'Autumn'};
D.forEach(function(o){o.name=EN[o.name]||o.name;for(var k in o.attrs){var v=o.attrs[k];if(EN[v])o.attrs[k]=EN[v]}})}
var UK='ais_lib_user';
function users(){try{return JSON.parse(localStorage.getItem(UK)||'[]')}catch(e){return[]}}
function saveUsers(a){try{localStorage.setItem(UK,JSON.stringify(a))}catch(e){}}
var L={
 kinds:{model:T('모델','Models'),garment:T('의류','Clothing'),prop:T('소품','Props'),bg:T('배경','Backgrounds'),pose:T('포즈','Poses'),'3d':T('3D 파일','3D files'),render:T('작업 결과','Results')},
 all:function(){var v=L.scope?L.scope():'all',A=D.concat(users());return v==='ours'?A.filter(function(x){return x.origin!=='ai'}):(v==='base'?A.filter(function(x){return x.origin==='ai'}):A)},
 get:function(id){return L.all().filter(function(x){return x.id===id})[0]},
 addUser:function(kind,name,src,attrs){var a=users();var it={id:'u'+Date.now(),kind:kind,name:name,src:src,full:src,origin:'upload',attrs:attrs||{}};a.push(it);saveUsers(a);return it},

 updateUser:function(id,patch){var a=users();a.forEach(function(x){if(x.id===id)for(var k in patch)x[k]=patch[k]});saveUsers(a)},
 shrinkImg:function(src,max,q){return new Promise(function(res){var im=new Image();im.onload=function(){var m=Math.min(1,(max||720)/Math.max(im.width,im.height));var c=document.createElement('canvas');c.width=Math.round(im.width*m);c.height=Math.round(im.height*m);c.getContext('2d').drawImage(im,0,0,c.width,c.height);res(c.toDataURL('image/jpeg',q||.82))};im.onerror=function(){res(src)};im.src=src})},
 addRender:function(name,src,attrs){return L.shrinkImg(src,720,.82).then(function(d){var a=users();var it={id:'r'+Date.now()+Math.floor(Math.random()*999),kind:'render',name:name,src:d,full:d,origin:'work',attrs:attrs||{}};a.push(it);saveUsers(a);setTimeout(function(){window.dispatchEvent(new Event('ais-lib-changed'))},0);return it})},
 idb:function(){return new Promise(function(res,rej){try{var r=indexedDB.open('ais_lib',1);r.onupgradeneeded=function(){r.result.createObjectStore('glb')};r.onsuccess=function(){res(r.result)};r.onerror=function(){rej(r.error)}}catch(e){rej(e)}})},
 saveGlb:function(file,name){var id='g3'+Date.now();return L.idb().then(function(db){return new Promise(function(res,rej){var t=db.transaction('glb','readwrite');t.objectStore('glb').put(file,id);t.oncomplete=function(){var a=users();var it={id:id,kind:'3d',name:name,src:cube(),full:cube(),origin:'upload',attrs:{type:T('3D 업로드','3D upload'),size:Math.round(file.size/1024)+'KB'},glb:true};a.push(it);saveUsers(a);res(it)};t.onerror=function(){rej(t.error)}})})},
 getGlbUrl:function(id){return L.idb().then(function(db){return new Promise(function(res,rej){var q=db.transaction('glb').objectStore('glb').get(id);q.onsuccess=function(){q.result?res(URL.createObjectURL(q.result)):rej('none')};q.onerror=function(){rej(q.error)}})})},
 removeUser:function(id){saveUsers(users().filter(function(x){return x.id!==id}))},
 pngOf:function(it,size){return new Promise(function(res,rej){var im=new Image();im.onload=function(){var c=document.createElement('canvas');c.width=c.height=size||768;var x=c.getContext('2d');x.drawImage(im,0,0,c.width,c.height);res(c.toDataURL('image/png'))};im.onerror=rej;im.src=it.src})},
 chips:{model:[['gender',T('성별 표현','Gender')],['age',T('연령대','Age')],['body',T('체형','Body')],['skin',T('피부톤','Skin')],['hair',T('헤어','Hair')],['region',T('지역','Region')]],garment:[['type',T('종류','Type')],['season',T('계절','Season')],['fit',T('핏','Fit')],['material',T('소재','Material')],['brand',T('브랜드','Brand')]],prop:[['type',T('종류','Type')]],bg:[['type',T('종류','Type')],['mood',T('분위기','Mood')]],pose:[],'3d':[['type',T('종류','Type')]],render:[['type',T('종류','Type')],['style',T('화풍','Style')]]},
 opts:{
  model:[['gender',T('성별 표현','Gender'),[T('여성','Female'),T('남성','Male'),T('중성','Neutral')]],['age',T('연령대','Age'),['10s','20s','30s','40s','50s','60s+'].map(function(v){return KO?v.replace('s','대'):v})],['body',T('체형','Body'),[T('슬림','Slim'),T('보통','Average'),T('플러스','Plus'),T('근육형','Athletic')]],['region',T('지역','Region'),[T('동양','East Asian'),T('서양','Western'),T('동남아','Southeast Asian'),T('남아시아','South Asian'),T('중동','Middle East'),T('중남미','Latin'),T('아프리카','African'),T('혼합','Mixed')]]],
  garment:[['type',T('종류','Type'),[T('상의','Top'),T('하의','Bottom'),T('원피스','Dress'),T('아우터','Outerwear'),T('신발','Shoes'),T('기타','Other')]],['season',T('계절','Season'),[T('봄·여름','Spring/Summer'),T('가을·겨울','Fall/Winter'),T('사계절','All seasons')]],['fit',T('핏','Fit'),[T('슬림','Slim'),T('레귤러','Regular'),T('오버','Oversized')]],['material',T('소재','Material'),[T('면','Cotton'),T('울','Wool'),T('린넨','Linen'),T('데님','Denim'),T('가죽','Leather'),T('합성','Synthetic')]]],
  bg:[['type',T('종류','Type'),[T('스튜디오','Studio'),T('장소','Location')]],['mood',T('분위기','Mood'),[T('밝은','Bright'),T('따뜻한','Warm'),T('차분한','Calm'),T('도시적','Urban')]]],
  prop:[['type',T('종류','Type'),[T('가방','Bag'),T('모자','Hat'),T('안경','Eyewear'),T('주얼리','Jewelry'),T('신발','Shoes'),T('기타','Other')]]],
  '3d':[['type',T('종류','Type'),[T('의류','Clothing'),T('소품','Prop'),T('배경','Scene')]]]
 }
};



/* 결과 만들기 독(작업실 공통): 휴대폰 카메라처럼 모드를 고르고 셔터를 누릅니다. modes:[{label,icon,btn(id)|run}] */
var DIC={shot:'<circle cx="12" cy="13" r="4"/><path d="M4 8h3l1.6-2h6.8L17 8h3v11H4z"/>',angles:'<rect x="3" y="6" width="5" height="12" rx="1"/><rect x="9.5" y="5" width="5" height="14" rx="1"/><rect x="16" y="6" width="5" height="12" rx="1"/>',turn:'<path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v4h-4"/><path d="M10 9l5 3-5 3z"/>',send:'<path d="M4 12h12M12 6l6 6-6 6"/><rect x="2" y="4" width="4" height="16" rx="1"/>',spark:'<path d="M12 3l2.2 5.8L20 11l-5.8 2.2L12 19l-2.2-5.8L4 11l5.8-2.2z"/>',save:'<path d="M5 4h11l3 3v13H5z"/><path d="M8 4v5h7V4M8 20v-6h8v6"/>',vary:'<path d="M4 7h11l-3-3M20 17H9l3 3"/>',export:'<path d="M12 3v12M7 10l5 5 5-5"/><path d="M5 19h14"/>'};
L.dock=function(stage,o){if(!stage)return null;var modes=o.modes||[],cur=0;var d=document.createElement('div');d.className='sd-dock';stage.appendChild(d);
 function sv(k){return '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(DIC[k]||DIC.shot)+'</svg>'}
 function results(){return L.all().filter(function(x){return x.kind==='render'})}
 function draw(){var R=results(),last=R[R.length-1];
  d.innerHTML='<div class="sd-modes" role="tablist">'+modes.map(function(m,i){return '<button type="button" role="tab" aria-selected="'+(i===cur)+'" class="'+(i===cur?'on':'')+'" data-i="'+i+'">'+m.label+'</button>'}).join('')+'</div><div class="sd-row"><span class="sd-sp"></span><button type="button" class="sd-shut" aria-label="'+modes[cur].label+'"><span>'+sv(modes[cur].icon)+'</span></button><a class="sd-res" href="library.html" title="'+T('작업 결과 보기','Open results')+'">'+(last&&last.src?'<img alt="" src="'+last.src+'">':'<i></i>')+'<b>'+R.length+'</b></a></div><small class="sd-tip">'+(modes[cur].tip||'')+'</small>'}
 d.addEventListener('click',function(e){var t=e.target.closest('button');if(!t)return;if(t.hasAttribute('data-i')){cur=+t.getAttribute('data-i');draw();return}
  if(t.classList.contains('sd-shut')){var m=modes[cur];d.classList.add('fire');setTimeout(function(){d.classList.remove('fire')},380);var b=m.btn&&document.getElementById(m.btn);if(b)b.click();else if(m.run)m.run();setTimeout(draw,1200);setTimeout(draw,4000)}});
 d.addEventListener('wheel',function(e){if(Math.abs(e.deltaX)+Math.abs(e.deltaY)<20)return;e.preventDefault();cur=(cur+(e.deltaY>0||e.deltaX>0?1:-1)+modes.length)%modes.length;draw()},{passive:false});
 window.addEventListener('ais-lib-changed',draw);draw();
 (o.hide||[]).forEach(function(id){var b=document.getElementById(id);if(b){var row=b.closest('.row');(row||b).classList.add('sd-hidden')}});
 return {redraw:draw}};
/* 공용 고르개(작업실 공통): 부위 칸 + 항목 창. 3D 스튜디오와 같은 방식. */
L.SHGROUP={top:['tee','shirt','knit','hoodie'],outer:['jacket','coat'],bot:['pants','skirt','shorts'],dress:['dress'],shoes:['shoes'],bag:['bag']};
L.slotOf=function(x){if(x.kind!=='garment')return x.kind;var sh=x.shape;for(var g in L.SHGROUP)if(L.SHGROUP[g].indexOf(sh)>=0)return g==='outer'?'top':g;var t=(x.attrs&&x.attrs.type)||'';if(/하의|Bottom/.test(t))return 'bot';if(/원피스|Dress/.test(t))return 'dress';return 'top'};
var PIC={garment:'<path d="m9 4-5.5 3 2 4 2-1V20h9V10l2 1 2-4L15 4a3.2 3.2 0 0 1-6 0z"/>',render:'<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M9 15l2-3 2 2 2-3 2 4"/>',model:'<circle cx="12" cy="8" r="3.4"/><path d="M5 20c.8-3.6 3.4-5.4 7-5.4s6.2 1.8 7 5.4"/>',top:'<path d="m9 4-5.5 3 2 4 2-1V20h9V10l2 1 2-4L15 4a3.2 3.2 0 0 1-6 0z"/>',bot:'<path d="M7 4h10l1 16h-4l-2-10-2 10H6z"/>',dress:'<path d="M9 3h6l-1 5 4 13H6l4-13z"/>',prop:'<path d="M5 9h14l-1 11H6zM9 9V7a3 3 0 0 1 6 0v2"/>',bg:'<rect x="3.5" y="5" width="17" height="14" rx="2"/><path d="m4 16 5-5 4 4 3-3 4 4"/>',pose:'<circle cx="12" cy="5" r="2"/><path d="M12 7v7l-3 6M12 14l3 6M7 10l5-2 5 2"/>'};
var PNM={garment:T('상품·의류','Products'),render:T('작업 결과','Results'),model:T('모델','Model'),top:T('상의','Top'),bot:T('하의','Bottom'),dress:T('원피스','Dress'),prop:T('소품','Props'),bg:T('배경','Background'),pose:T('포즈','Pose')};
var SHN={tee:T('티셔츠','T-shirt'),shirt:T('셔츠','Shirt'),knit:T('니트','Knit'),hoodie:T('후드','Hoodie'),jacket:T('재킷','Jacket'),coat:T('코트','Coat'),dress:T('원피스','Dress'),pants:T('팬츠','Pants'),skirt:T('스커트','Skirt'),shorts:T('쇼츠','Shorts')};
L.picker=function(stage,o){o=o||{};var slots=o.slots||['model','top','bot','dress','prop','bg','pose'];var lp=o.lp;if(!stage||!lp)return null;
 stage.classList.add('pk-stage');var rail=document.createElement('div');rail.className='pk-rail';stage.appendChild(rail);
 var pnl=document.createElement('aside');pnl.className='fz-pnl pk-pnl';stage.appendChild(pnl);var cur=null,q='',fsh='all';
 function kindOf(k){return (k==='top'||k==='bot'||k==='dress')?'garment':k}
 function list(k){var kd=kindOf(k);return L.all().filter(function(x){return x.kind===kd&&(kd!=='garment'||k==='garment'||L.slotOf(x)===k)}).filter(function(x){return (!q||(x.name||'').indexOf(q)>=0)&&(fsh==='all'||x.shape===fsh)})}
 function chosen(k){var kd=kindOf(k),ids=(lp.sel[kd]||[]);return ids.map(L.get).filter(function(x){return x&&(kd!=='garment'||k==='garment'||L.slotOf(x)===k)})}
 function svg(k){return '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+PIC[k]+'</svg>'}
 function drawRail(){rail.innerHTML='';slots.forEach(function(k){var c=chosen(k)[0],b=document.createElement('button');b.type='button';b.className='pk-slot'+(cur===k?' on':'')+(c?' has':'');b.innerHTML=(c&&c.src?'<img alt="" src="'+c.src+'">':svg(k))+'<small>'+PNM[k]+(chosen(k).length>1?' +'+(chosen(k).length-1):'')+'</small>';b.title=PNM[k]+(c?' · '+c.name:'');b.onclick=function(){open(k)};rail.appendChild(b)})}
 function pick(k,x){var kd=kindOf(k),ids=(lp.sel[kd]||[]).slice(),i=ids.indexOf(x.id);
  if(kd==='garment'&&k==='garment'&&!(o.multi&&o.multi.garment)){ids=i>=0?[]:[x.id]}
  else if(kd==='garment'){if(i>=0)ids.splice(i,1);else{ids=ids.filter(function(id){var y=L.get(id);if(!y)return false;var sl=L.slotOf(y);if(sl===k)return false;if(k==='dress'&&(sl==='top'||sl==='bot'))return false;if((k==='top'||k==='bot')&&sl==='dress')return false;return true});ids.push(x.id)}}
  else if(kd==='prop'&&!(o.single&&o.single.prop)){if(i>=0)ids.splice(i,1);else ids.push(x.id)}else ids=i>=0?[]:[x.id];
  lp.setSel(kd,ids);drawRail();drawP()}
 function drawP(){var k=cur;if(!k)return;var L0=list(k),all=L.all().filter(function(x){return x.kind===kindOf(k)&&(kindOf(k)!=='garment'||k==='garment'||L.slotOf(x)===k)}),shapes=[];all.forEach(function(x){if(x.shape&&shapes.indexOf(x.shape)<0)shapes.push(x.shape)});var ch=chosen(k).map(function(x){return x.id});
  pnl.innerHTML='<div class="fz-ph"><b>'+PNM[k]+'</b><small>'+all.length+T('개','')+'</small><button type="button" class="fz-pc" aria-label="'+T('닫기','Close')+'">×</button></div><input class="fz-q" type="search" placeholder="'+T('이름으로 찾기','Search by name')+'" value="'+q+'">'+(shapes.length>1?'<div class="fz-f"><button type="button" data-f="all" class="'+(fsh==='all'?'on':'')+'">'+T('전체','All')+'</button>'+shapes.map(function(s2){return '<button type="button" data-f="'+s2+'" class="'+(fsh===s2?'on':'')+'">'+(SHN[s2]||s2)+'</button>'}).join('')+'</div>':'')
   +'<div class="fz-g">'+L0.map(function(x){return '<div class="fz-cd'+(ch.indexOf(x.id)>=0?' sel':'')+'"><button type="button" class="fz-im" data-id="'+x.id+'">'+(x.src?'<img alt="" src="'+x.src+'">':'<i>'+svg(k)+'</i>')+'</button><b>'+(x.name||'')+'</b>'+(x.origin&&x.origin!=='ai'?'<em>'+T('내 것','Mine')+'</em>':'')+'</div>'}).join('')+(L0.length?'':'<p class="fine">'+(L.scope()==='ours'?T('우리 자료가 아직 없습니다. 아래에서 올려 등록하세요.','No items of yours yet. Upload below.'):T('맞는 항목이 없습니다.','No matching items.'))+'</p>')+'</div>'+(o.extra&&o.extra[k]?'<button type="button" class="fz-more pk-x">'+o.extra[k].label+'</button>':'')+'<button type="button" class="fz-more">'+T('올려서 등록하기','Upload and register')+'</button>';
  pnl.insertBefore(L.scopeBar(),pnl.children[1])}
 function open(k){cur=k;q='';fsh='all';drawRail();drawP();pnl.classList.add('on')}
 function close(){cur=null;pnl.classList.remove('on');drawRail()}
 pnl.addEventListener('click',function(e){var t=e.target.closest('button');if(!t)return;if(t.classList.contains('fz-pc'))return close();if(t.classList.contains('pk-x')){o.extra[cur].fn();close();return}if(t.hasAttribute('data-f')){fsh=t.getAttribute('data-f');drawP();return}
  if(t.classList.contains('fz-more')){var fi=document.createElement('input');fi.type='file';fi.accept='image/*';fi.multiple=true;fi.onchange=function(){var fs=[].slice.call(fi.files||[]);if(!fs.length)return;if(o.rightsEl&&!o.rightsEl.checked){if(o.onUploadBlocked)o.onUploadBlocked();return}L.register(kindOf(cur),fs,function(ids){drawP();drawRail()})};fi.click();return}
  if(t.hasAttribute('data-id')){var x=L.get(t.getAttribute('data-id'));if(x)pick(cur,x)}});
 pnl.addEventListener('input',function(e){if(e.target.classList.contains('fz-q')){q=e.target.value.trim();var ps=e.target.selectionStart;drawP();var n=pnl.querySelector('.fz-q');n.focus();n.setSelectionRange(ps,ps)}});
 window.addEventListener('ais-libscope',function(){drawP()});window.addEventListener('ais-lib-changed',function(){drawRail();drawP()});
 if(o.regionEl)o.regionEl.addEventListener('click',function(e){var r=o.regionEl.getBoundingClientRect(),y=(e.clientY-r.top)/r.height;var hasDress=chosen('dress').length;open(y<.18?'model':(y<.52?(hasDress?'dress':'top'):(hasDress?'dress':'bot')))});
 var rT=0;function rshow(v){clearTimeout(rT);if(v)stage.classList.add('pk-on');else rT=setTimeout(function(){if(!pnl.classList.contains('on'))stage.classList.remove('pk-on')},250)}stage.addEventListener('pointermove',function(e){if(e.target.closest&&e.target.closest('.pk-rail'))return rshow(true);var r=stage.getBoundingClientRect(),x=(e.clientX-r.left)/r.width;rshow(x>.18&&x<.9)});stage.addEventListener('pointerleave',function(){rshow(false)});
 drawRail();return {open:open,close:close,refresh:function(){drawRail();drawP()}}};
/* 우리 자료 등록: 카테고리(세부 종류)·색·계절·품번·컬렉션을 받아 저장. 3D·가상 착장이 종류로 형태를 정합니다. */
L.SHAPES=[['tee',T('티셔츠','T-shirt'),'top'],['shirt',T('셔츠·블라우스','Shirt / blouse'),'top'],['knit',T('니트·가디건','Knit / cardigan'),'top'],['hoodie',T('후드·맨투맨','Hoodie / sweatshirt'),'top'],['jacket',T('재킷','Jacket'),'outer'],['coat',T('코트·패딩','Coat / puffer'),'outer'],['dress',T('원피스','Dress'),'dress'],['pants',T('팬츠','Pants'),'bottom'],['skirt',T('스커트','Skirt'),'bottom'],['shorts',T('쇼츠','Shorts'),'bottom'],['shoes',T('신발','Shoes'),'shoes'],['bag',T('가방','Bag'),'other'],['other',T('기타','Other'),'other']];
var TYPEN={top:T('상의','Top'),outer:T('아우터','Outerwear'),bottom:T('하의','Bottom'),dress:T('원피스','Dress'),shoes:T('신발','Shoes'),other:T('기타','Other')};
function avgColor(c){try{var x=c.getContext('2d'),w=c.width,h=c.height,d=x.getImageData(0,0,w,h).data,r=0,g=0,b=0,n=0,st=Math.max(4,Math.floor(w*h/4000))*4;for(var i=0;i<d.length;i+=st){var R=d[i],G=d[i+1],B=d[i+2],mx=Math.max(R,G,B),mn=Math.min(R,G,B);if(mx>238&&mx-mn<14)continue;r+=R;g+=G;b+=B;n++}if(!n)return '#f2f2f2';return '#'+[r,g,b].map(function(v){return ('0'+Math.round(v/n).toString(16)).slice(-2)}).join('')}catch(e){return '#888888'}}
function loadImg(file){return new Promise(function(res){var r=new FileReader();r.onload=function(){var im=new Image();im.onload=function(){var c=document.createElement('canvas'),m=Math.min(1,900/Math.max(im.width,im.height));c.width=Math.round(im.width*m);c.height=Math.round(im.height*m);c.getContext('2d').drawImage(im,0,0,c.width,c.height);res({src:c.toDataURL('image/jpeg',.85),color:avgColor(c),name:file.name.replace(/\.[^.]+$/,'').slice(0,24)})};im.onerror=function(){res(null)};im.src=r.result};r.readAsDataURL(file)})}
L.register=function(kind,files,done){Promise.all(files.map(loadImg)).then(function(list){list=list.filter(Boolean);if(!list.length)return done([]);
 var ov=document.createElement('div');ov.className='lr-ov';var opt=L.opts[kind]||[];
 var shapeSel=kind==='garment'?'<label class="lr-f lr-req"><span>'+T('세부 종류 (모두 적용)','Category (apply to all)')+' *</span><select id="lrShape"><option value="">'+T('골라 주세요','Choose')+'</option>'+L.SHAPES.map(function(x){return '<option value="'+x[0]+'">'+TYPEN[x[2]]+' · '+x[1]+'</option>'}).join('')+'</select></label>':'';
 var extra=opt.filter(function(o2){return !(kind==='garment'&&o2[0]==='type')}).map(function(o2){return '<label class="lr-f"><span>'+o2[1]+'</span><select data-k="'+o2[0]+'"><option value="">-</option>'+o2[2].map(function(v){return '<option>'+v+'</option>'}).join('')+'</select></label>'}).join('');
 ov.innerHTML='<div class="lr-box" role="dialog" aria-modal="true" aria-label="'+T('우리 자료 등록','Register your items')+'"><div class="lr-h"><b>'+T('우리 자료 등록','Register your items')+'</b><small>'+list.length+T('개 · '+L.kinds[kind],' item(s) · '+L.kinds[kind])+'</small></div>'
  +'<div class="lr-th">'+list.map(function(x,i){return '<figure><img alt="" src="'+x.src+'"><input data-i="'+i+'" value="'+x.name.replace(/"/g,'')+'" aria-label="'+T('이름','Name')+'">'+(kind==='garment'?'<select class="lr-si" data-si="'+i+'" aria-label="'+T('세부 종류','Category')+'"><option value="">'+T('종류 선택','Category')+'</option>'+L.SHAPES.map(function(z){return '<option value="'+z[0]+'">'+z[1]+'</option>'}).join('')+'</select><label class="lr-c"><input type="color" data-ci="'+i+'" value="'+x.color+'"><span>'+T('대표색(자동)','Main color (auto)')+'</span></label>':'')+'</figure>'}).join('')+'</div>'
  +'<div class="lr-fs">'+shapeSel+extra+'<label class="lr-f"><span>'+T('품번(SKU)','SKU')+'</span><input id="lrSku" placeholder="BAG-001"></label><label class="lr-f"><span>'+T('컬렉션·시즌','Collection / season')+'</span><input id="lrCol" placeholder="'+T('예: 26 S/S','e.g. 26 S/S')+'"></label></div>'
  +'<p class="lr-msg" id="lrMsg"></p><div class="lr-a"><button type="button" class="btn btn-ghost sm" id="lrNo">'+T('취소','Cancel')+'</button><button type="button" class="btn btn-primary sm" id="lrOk" style="color:var(--violet-ink)">'+T('등록','Register')+'</button></div></div>';
 document.body.appendChild(ov);var q=function(s2){return ov.querySelector(s2)};
 q('#lrNo').onclick=function(){ov.remove();done([])};
 if(q('#lrShape'))q('#lrShape').onchange=function(){var v=this.value;[].forEach.call(ov.querySelectorAll('.lr-si'),function(z){z.value=v})};
 q('#lrOk').onclick=function(){var sh=q('#lrShape')?q('#lrShape').value:'';var miss=[].some.call(ov.querySelectorAll('.lr-si'),function(z){return !z.value});if(kind==='garment'&&miss){q('#lrMsg').textContent=T('세부 종류를 골라 주세요. 3D와 가상 착장이 이 값으로 입히는 방식을 정합니다.','Choose a category. 3D and try-on use it to dress the model.');q('#lrShape').focus();return}
  var at={};[].forEach.call(ov.querySelectorAll('select[data-k]'),function(se){if(se.value)at[se.getAttribute('data-k')]=se.value});
  var sku=q('#lrSku').value.trim(),col=q('#lrCol').value.trim();if(sku)at.sku=sku;if(col)at.collection=col;
  var ids=list.map(function(x,i){var nm=(ov.querySelector('input[data-i="'+i+'"]').value||x.name).slice(0,30),ci=ov.querySelector('input[data-ci="'+i+'"]'),si=ov.querySelector('select[data-si="'+i+'"]'),a2=Object.assign({},at),s2=si?si.value:sh;var sp=L.SHAPES.filter(function(z){return z[0]===s2})[0];if(sp)a2.type=TYPEN[sp[2]];if(ci)a2.color=ci.value;var it=L.addUser(kind,nm,x.src,a2);if(s2){L.updateUser(it.id,{shape:s2,color:a2.color})}return it.id});
  ov.remove();window.dispatchEvent(new Event('ais-lib-changed'));done(ids)};
 setTimeout(function(){var f0=q('#lrShape')||q('#lrOk');f0&&f0.focus()},50)})};
/* 보기 범위: all(전체) / base(기본 제공만) / ours(우리 팀 자료만). 지금은 이 브라우저에 저장, 서버 연결 후 작업공간 설정으로 이동 */
L.scope=function(){try{return localStorage.getItem('ais_libscope')||'all'}catch(e){return 'all'}};
L.setScope=function(v){try{localStorage.setItem('ais_libscope',v)}catch(e){}window.dispatchEvent(new Event('ais-libscope'))};
L.scopeBar=function(){var d=document.createElement('div');d.className='lp-scope';d.setAttribute('role','group');d.setAttribute('aria-label',T('보기 범위','Show'));[['all',T('전체','All')],['base',T('기본 제공','Provided')],['ours',T('우리 자료','Ours')]].forEach(function(o){var b=document.createElement('button');b.type='button';b.textContent=o[1];if(L.scope()===o[0])b.className='on';b.onclick=function(){L.setScope(o[0])};d.appendChild(b)});return d};
/* mount(el,{kinds:[..],multi:{garment:true},onChange(sel),rightsEl,onUploadBlocked}) */
L.mount=function(el,o){
 o=o||{};var kinds=o.kinds||['model','garment','prop','bg','pose'];var tab=kinds[0];var sel={};var q='';var fl={};
 kinds.forEach(function(k){sel[k]=[]});
 el.classList.add('lp');window.addEventListener('ais-libscope',function(){draw()});
 function emit(){if(o.onChange)o.onChange(sel)}
 function items(){return L.all().filter(function(x){return x.kind===tab}).filter(function(x){if(q&&(x.name+' '+Object.keys(x.attrs).map(function(k){return x.attrs[k]}).join(' ')).toLowerCase().indexOf(q)<0)return false;for(var k in fl){if(fl[k]&&x.attrs[k]!==fl[k])return false}return true})}
 function draw(){
  el.innerHTML='';el.appendChild(L.scopeBar());
  var tb=document.createElement('div');tb.className='lp-tabs';kinds.forEach(function(k){var n=L.all().filter(function(x){return x.kind===k}).length;var b=document.createElement('button');b.type='button';b.className='lp-tab'+(k===tab?' on':'');b.innerHTML=L.kinds[k]+' <span>'+n+'</span>'+(sel[k].length?' <i>'+sel[k].length+'</i>':'');b.onclick=function(){tab=k;fl={};draw()};tb.appendChild(b)});el.appendChild(tb);
  var bar=document.createElement('div');bar.className='lp-bar';var s=document.createElement('input');s.type='search';s.placeholder=T('이름·태그 검색','Search name or tag');s.value=q;s.oninput=function(){q=s.value.trim().toLowerCase();grid()};bar.appendChild(s);
  (L.chips[tab]||[]).forEach(function(c){var vals={};L.all().filter(function(x){return x.kind===tab&&x.attrs[c[0]]}).forEach(function(x){vals[x.attrs[c[0]]]=1});if(!Object.keys(vals).length)return;var se=document.createElement('select');se.setAttribute('aria-label',c[1]);var op=document.createElement('option');op.value='';op.textContent=c[1];se.appendChild(op);Object.keys(vals).forEach(function(v){var po=document.createElement('option');po.value=v;po.textContent=v;se.appendChild(po)});se.value=fl[c[0]]||'';se.onchange=function(){fl[c[0]]=se.value;grid()};bar.appendChild(se)});
  if(tab==='3d'){var f3=document.createElement('input');f3.type='file';f3.accept='.glb,.gltf';f3.hidden=true;var u3=document.createElement('button');u3.type='button';u3.className='btn btn-ghost sm';u3.textContent=T('3D 파일(GLB) 올리기','Upload 3D file (GLB)');u3.onclick=function(){if(o.rightsEl&&!o.rightsEl.checked){if(o.onUploadBlocked)o.onUploadBlocked();return}f3.click()};f3.onchange=function(){var file=f3.files[0];if(!file)return;L.saveGlb(file,file.name.replace(/\.[^.]+$/,'').slice(0,24)).then(function(it){sel[tab]=[it.id];emit();draw()}).catch(function(){if(o.onUploadBlocked)o.onUploadBlocked()});f3.value=''};bar.appendChild(u3);bar.appendChild(f3)}
  if(tab==='model'||tab==='garment'||tab==='prop'||tab==='bg'){var f=document.createElement('input');f.type='file';f.accept='image/*';f.hidden=true;var up=document.createElement('button');up.type='button';up.className='btn btn-ghost sm';up.textContent=T('내 이미지 올리기','Upload mine');up.onclick=function(){if(o.rightsEl&&!o.rightsEl.checked){if(o.onUploadBlocked)o.onUploadBlocked();return}f.click()};f.multiple=true;f.onchange=function(){var fs=[].slice.call(f.files||[]);f.value='';if(!fs.length)return;L.register(tab,fs,function(ids){if(!ids.length)return;sel[tab]=o.multi&&o.multi[tab]?sel[tab].concat(ids):[ids[ids.length-1]];emit();draw()})};bar.appendChild(up);bar.appendChild(f)}
  el.appendChild(bar);
  (function(){var id=sel[tab]&&sel[tab].length===1?sel[tab][0]:null;var it=id&&L.get(id);if(!it||it.origin==='ai'||!L.opts[tab])return;
   var d=document.createElement('details');d.className='lp-edit';d.open=true;var sm=document.createElement('summary');sm.textContent=T('선택한 항목의 속성 · ','Attributes of selected · ')+it.name;d.appendChild(sm);
   var w=document.createElement('div');w.className='lp-edrow';
   L.opts[tab].forEach(function(o2){var se=document.createElement('select');se.setAttribute('aria-label',o2[1]);var z=document.createElement('option');z.value='';z.textContent=o2[1];se.appendChild(z);o2[2].forEach(function(v){var po=document.createElement('option');po.value=v;po.textContent=v;se.appendChild(po)});se.value=it.attrs[o2[0]]||'';se.onchange=function(){var at=Object.assign({},it.attrs);if(se.value)at[o2[0]]=se.value;else delete at[o2[0]];it.attrs=at;L.updateUser(it.id,{attrs:at});grid()};w.appendChild(se)});
   var tg=document.createElement('input');tg.placeholder=T('태그(쉼표로 구분)','Tags (comma separated)');tg.maxLength=60;tg.value=it.attrs.tags||'';tg.onchange=function(){var at=Object.assign({},it.attrs);if(tg.value.trim())at.tags=tg.value.trim();else delete at.tags;it.attrs=at;L.updateUser(it.id,{attrs:at});grid()};w.appendChild(tg);
   var br=document.createElement('input');br.placeholder=T('브랜드·시즌명','Brand or season');br.maxLength=40;br.value=it.attrs.brand||'';br.onchange=function(){var at=Object.assign({},it.attrs);if(br.value.trim())at.brand=br.value.trim();else delete at.brand;it.attrs=at;L.updateUser(it.id,{attrs:at});grid()};if(tab==='garment'||tab==='prop')w.appendChild(br);
   d.appendChild(w);el.appendChild(d)})();
  var g=document.createElement('div');g.className='lp-grid';g.id='lpgrid';el.appendChild(g);
  var note=document.createElement('p');note.className='fine';note.textContent=T('"AI"는 AI로 만든 라이브러리 이미지, "내 업로드"는 AI 표시 없음입니다.','"AI" marks AI-made library images; "My upload" carries no AI label.');el.appendChild(note);
  grid()};
 function grid(){var g=el.querySelector('#lpgrid');g.innerHTML='';var a=items();if(!a.length){g.innerHTML='<p class="fine" style="grid-column:1/-1">'+T('조건에 맞는 항목이 없습니다. 필터를 줄여 보세요.','Nothing matches. Try fewer filters.')+'</p>';return}
  a.forEach(function(x){var b=document.createElement('button');b.type='button';var on=sel[tab].indexOf(x.id)>=0;b.className='lp-card'+(on?' on':'');b.setAttribute('aria-pressed',on);var asp=x.kind==='model'?'3/4':'1/1';b.innerHTML='<span class="lp-im" style="aspect-ratio:'+asp+'"><img alt="" src="'+x.src+'">'+((x.kind==='pose'||x.kind==='bg'||x.kind==='prop')&&x.origin!=='upload'?'':'<em class="'+(x.origin==='upload'?'up':'ai')+'">'+(x.origin==='upload'?T('내 업로드','Mine'):(x.origin==='work'?T('작업 결과','Result'):'AI'))+'</em>')+'</span><b>'+x.name+'</b><small>'+Object.keys(x.attrs).filter(function(k){return k!=='color'&&k!=='sku'&&k!=='collection'}).map(function(k){return x.attrs[k]}).slice(0,3).join(' · ')+'</small>';
   b.onclick=function(){var m=o.multi&&o.multi[tab];var i=sel[tab].indexOf(x.id);if(m){if(i>=0)sel[tab].splice(i,1);else sel[tab].push(x.id)}else sel[tab]=i>=0?[]:[x.id];emit();draw()};g.appendChild(b)})}
 draw();
 var api={sel:sel,redraw:draw,clear:function(){kinds.forEach(function(k){sel[k]=[]});emit();draw()},setSel:function(k,ids){if(!sel[k])return;sel[k]=ids.slice();if(k!==tab&&kinds.indexOf(k)>=0)tab=k;emit();draw()}};el._lp=api;return api;
};
window.AISLIB=L;
})();

/* AISLAYOUT — 결과 이미지에 글·판형을 얹어 잡지·신문·광고 지면으로 내보내기. 서버 필요 없음(브라우저 캔버스). */
(function(){
var KO=(document.documentElement.lang||'ko')==='ko';function T(a,b){return KO?a:b}
var SZ=[['a4p',T('A4 세로 (잡지 표지·내지)','A4 portrait (cover / page)'),2480,3508],['a4l',T('A4 가로 (펼침면 한쪽)','A4 landscape'),3508,2480],['tab',T('신문 타블로이드 세로','Tabloid newspaper'),2250,3000],['sq',T('정사각 (SNS·카탈로그)','Square (social / catalog)'),2400,2400]];
var TP=[['none',T('글 없음','No text')],['cover',T('잡지 표지','Magazine cover')],['ad',T('패션 광고','Fashion ad')],['news',T('신문 기사','Newspaper')],['look',T('룩북 캡션','Lookbook caption')]];
var FN={serif:'"Nanum Myeongjo","Fraunces",serif',sans:'"IBM Plex Sans KR","Fraunces",sans-serif'};
function load(src){return new Promise(function(r,j){var i=new Image();i.onload=function(){r(i)};i.onerror=j;i.src=src})}
function cover(cx,im,x,y,w,h){var s=Math.max(w/im.width,h/im.height),sw=w/s,sh=h/s;cx.drawImage(im,(im.width-sw)/2,(im.height-sh)*.35,sw,sh,x,y,w,h)}
function wrap(cx,t,x,y,mw,lh,max){var lines=[],cur='';String(t||'').split('\n').forEach(function(par){cur='';for(var i=0;i<par.length;i++){var n=cur+par[i];if(cx.measureText(n).width>mw&&cur){lines.push(cur);cur=par[i]}else cur=n}lines.push(cur)});if(max&&lines.length>max){lines=lines.slice(0,max);lines[max-1]=lines[max-1].replace(/.$/,'…')}lines.forEach(function(l,i){cx.fillText(l,x,y+i*lh)});return y+lines.length*lh}
function font(cx,w,px,f){cx.font=w+' '+Math.round(px)+'px '+FN[f]}
async function draw(cv,o){
 var W=o.W,H=o.H,k=o.scale||1;cv.width=Math.round(W*k);cv.height=Math.round(H*k);var cx=cv.getContext('2d');cx.scale(k,k);cx.textBaseline='alphabetic';
 try{await Promise.all([document.fonts.load('700 40px "Nanum Myeongjo"'),document.fonts.load('600 40px "IBM Plex Sans KR"')])}catch(e){}
 var im=o.img?await load(o.img):null,u=W/2480,tp=o.tp,f=o.font,pad=130*u*(W>H?.8:1);
 var ink=o.color==='white'?'#fff':o.color==='black'?'#14121c':o.color==='violet'?'#5b3fd6':null;
 cx.fillStyle='#fff';cx.fillRect(0,0,W,H);
 if(tp==='news'){
  cx.fillStyle='#f3eee2';cx.fillRect(0,0,W,H);var c=ink||'#14121c';cx.fillStyle=c;cx.textAlign='center';
  var np=W*.075;font(cx,'700',np,'serif');var nw=cx.measureText(o.mast||'').width;if(nw>W-2*pad){np=np*(W-2*pad)/nw;font(cx,'700',np,'serif')}cx.fillText(o.mast||'',W/2,pad+W*.075);
  cx.fillRect(pad,pad+W*.1,W-2*pad,4*u);cx.fillRect(pad,pad+W*.1+14*u,W-2*pad,1.5*u);
  cx.textAlign='left';font(cx,'700',W*.058,'serif');var y=wrap(cx,o.head||'',pad,pad+W*.2,W-2*pad,W*.07,3);
  font(cx,'400',W*.026,'serif');cx.globalAlpha=.8;y=wrap(cx,o.sub||'',pad,y+W*.01,W-2*pad,W*.036,2);cx.globalAlpha=1;
  var ih=H*.36;if(im)cover(cx,im,pad,y+W*.02,W-2*pad,ih);y=y+W*.02+ih;
  font(cx,'400',W*.018,'sans');cx.globalAlpha=.7;cx.fillText(o.cap||'',pad,y+W*.03);cx.globalAlpha=1;y+=W*.07;
  var cols=W>H?4:3,gap=40*u,cw=(W-2*pad-gap*(cols-1))/cols;font(cx,'400',W*.0215,'serif');
  var body=String(o.body||'');for(var i=0;i<cols;i++){var part=body.slice(Math.floor(i*body.length/cols),Math.floor((i+1)*body.length/cols));wrap(cx,part,pad+i*(cw+gap),y,cw,W*.034,Math.max(1,Math.floor((H-pad-y)/(W*.034))));if(i)cx.fillRect(pad+i*(cw+gap)-gap/2,y-W*.025,1.5*u,H-pad-y+W*.02)}
 }else{
  if(im)cover(cx,im,0,0,W,H);else{cx.fillStyle='#e7e3f1';cx.fillRect(0,0,W,H)}
  if(tp==='cover'){var g=cx.createLinearGradient(0,0,0,H*.28);g.addColorStop(0,'rgba(0,0,0,.45)');g.addColorStop(1,'rgba(0,0,0,0)');cx.fillStyle=g;cx.fillRect(0,0,W,H*.28);
   g=cx.createLinearGradient(0,H*.62,0,H);g.addColorStop(0,'rgba(0,0,0,0)');g.addColorStop(1,'rgba(0,0,0,.62)');cx.fillStyle=g;cx.fillRect(0,H*.62,W,H*.38);
   cx.fillStyle=ink||'#fff';cx.textAlign='center';var mp=W*.14;font(cx,'700',mp,'serif');var mw=cx.measureText(o.mast||'').width;if(mw>W-2*pad){mp=mp*(W-2*pad)/mw;font(cx,'700',mp,'serif')}cx.fillText(o.mast||'',W/2,pad+W*.13);
   cx.textAlign='left';font(cx,'700',W*.07,f);var y=wrap(cx,o.head||'',pad,H-pad-W*.17,W-2*pad,W*.085,3);font(cx,'400',W*.032,f);wrap(cx,o.sub||'',pad,y+W*.005,W-2*pad,W*.045,3);
   font(cx,'400',W*.02,'sans');cx.globalAlpha=.85;cx.fillText(o.cap||'',pad,H-pad*.55);cx.globalAlpha=1}
  if(tp==='ad'){var bh=H*.2;cx.fillStyle=ink==='#fff'?'#14121c':'#fff';cx.fillRect(0,H-bh,W,bh);cx.fillStyle=ink==='#fff'?'#fff':(ink||'#14121c');cx.textAlign='left';
   font(cx,'700',W*.05,f);var y2=wrap(cx,o.head||'',pad,H-bh+pad*.9,W*.6,W*.062,2);font(cx,'400',W*.025,f);wrap(cx,o.sub||'',pad,y2+W*.004,W*.6,W*.036,2);
   cx.textAlign='right';font(cx,'600',W*.03,'serif');cx.fillText(o.mast||'',W-pad,H-bh+pad*.9);font(cx,'400',W*.018,'sans');cx.globalAlpha=.7;cx.fillText(o.cap||'',W-pad,H-pad*.5);cx.globalAlpha=1}
  if(tp==='look'){cx.strokeStyle='rgba(255,255,255,.9)';cx.lineWidth=10*u;cx.strokeRect(50*u,50*u,W-100*u,H-100*u);var g2=cx.createLinearGradient(0,H*.78,0,H);g2.addColorStop(0,'rgba(0,0,0,0)');g2.addColorStop(1,'rgba(0,0,0,.5)');cx.fillStyle=g2;cx.fillRect(0,H*.78,W,H*.22);
   cx.fillStyle=ink||'#fff';cx.textAlign='left';font(cx,'600',W*.022,'sans');cx.fillText((o.mast||'LOOKBOOK').toUpperCase(),pad,H-pad-W*.085);font(cx,'700',W*.04,f);var y3=wrap(cx,o.head||'',pad,H-pad-W*.03,W-2*pad,W*.05,1);font(cx,'400',W*.021,f);wrap(cx,(o.sub||'')+(o.cap?'  ·  '+o.cap:''),pad,H-pad+W*.015,W-2*pad,W*.03,1)}
 }
 if(o.mark){cx.textAlign='right';cx.font='500 '+Math.round(W*.0155)+'px '+FN.sans;var tx=T('AI 생성 이미지','AI-generated image'),tw=cx.measureText(tx).width;cx.fillStyle='rgba(20,18,28,.62)';cx.fillRect(W-tw-W*.05,H-W*.045,tw+W*.03,W*.03);cx.fillStyle='#fff';cx.fillText(tx,W-W*.035,H-W*.0235)}
}
var L={SZ:SZ,TP:TP,draw:draw};
L.mount=function(el,o){
 o=o||{};var st={sz:0,tp:'cover',font:'serif',color:'auto'};el.classList.add('lay');
 var h='<div class="lay-h">'+T('지면 레이아웃 (잡지·신문·광고)','Print layout (magazine · newspaper · ad)')+'</div><div class="chs-g"><b>'+T('판형','Format')+'</b><div class="chips" id="lySz"></div></div><div class="chs-g"><b>'+T('템플릿','Template')+'</b><div class="chips" id="lyTp"></div></div>'+
 '<div class="lay-f"><label class="fld">'+T('매체·잡지 이름','Masthead')+' <input id="lyMast" maxlength="30" value="" placeholder="MAGAZINE"></label><label class="fld">'+T('표제','Headline')+' <input id="lyHead" maxlength="80" placeholder="'+T('이번 시즌, 가장 가벼운 룩','The lightest look of the season')+'"></label><label class="fld">'+T('부제','Subhead')+' <input id="lySub" maxlength="120"></label><label class="fld">'+T('캡션·크레딧','Caption / credit')+' <input id="lyCap" maxlength="80"></label><label class="fld">'+T('본문 (신문 기사용)','Body (newspaper)')+' <textarea id="lyBody" rows="3" maxlength="900"></textarea></label>'+
 '<label class="fld">'+T('글꼴','Font')+' <select id="lyFont"><option value="serif">'+T('명조(세리프)','Serif')+'</option><option value="sans">'+T('고딕(산세리프)','Sans')+'</option></select></label><label class="fld">'+T('글자색','Color')+' <select id="lyCol"><option value="auto">'+T('자동','Auto')+'</option><option value="white">'+T('흰색','White')+'</option><option value="black">'+T('검정','Black')+'</option><option value="violet">'+T('보라','Violet')+'</option></select></label><label class="chk"><input type="checkbox" id="lyMark" checked> <span>'+T('AI 생성 이미지 표시 넣기 (권장)','Add AI-generated label (recommended)')+'</span></label></div>'+
 '<canvas id="lyCv" class="lay-cv"></canvas><div class="row"><button class="btn btn-primary sm" id="lyPng" type="button" style="color:var(--violet-ink)">'+T('PNG로 내려받기 (인쇄 해상도)','Download PNG (print size)')+'</button><button class="btn btn-ghost sm" id="lyJpg" type="button">JPEG</button><button class="btn btn-ghost sm" id="lySave" type="button">'+T('라이브러리에 저장','Save to library')+'</button></div><p class="fine" id="lyNote">'+T('A4 2480×3508px(300dpi). 글은 브라우저에서 합성되며 서버로 보내지지 않습니다. 인쇄 전 색·글자 위치를 확인하세요.','A4 is 2480×3508 px (300 dpi). Text is composited in your browser and not uploaded. Check colors and text position before printing.')+'</p>';
 el.innerHTML=h;var $=function(i){return el.querySelector('#'+i)};
 function chips(id,list,key){var e=$(id);e.innerHTML='';list.forEach(function(c,i){var b=document.createElement('button');b.type='button';b.className='chip';var v=key==='sz'?i:c[0];b.setAttribute('aria-pressed',st[key]===v);b.textContent=c[1];b.onclick=function(){st[key]=v;chips(id,list,key);r()};e.appendChild(b)})}
 chips('lySz',SZ,'sz');chips('lyTp',TP,'tp');
 function vals(full){var s=SZ[st.sz];return{img:o.getImage&&o.getImage(),W:s[2],H:s[3],scale:full?1:Math.min(1,900/Math.max(s[2],s[3])),tp:st.tp,font:st.font,color:st.color,mast:$('lyMast').value,head:$('lyHead').value,sub:$('lySub').value,cap:$('lyCap').value,body:$('lyBody').value,mark:$('lyMark').checked}}
 var tm=0;function r(){clearTimeout(tm);tm=setTimeout(function(){var v=vals(false);if(!v.img){$('lyNote').textContent=T('먼저 결과 이미지를 만들어 주세요.','Generate a result image first.');return}draw($('lyCv'),v).catch(function(){})},120)}
 ['lyMast','lyHead','lySub','lyCap','lyBody','lyMark'].forEach(function(i){$(i).oninput=r;$(i).onchange=r});$('lyFont').onchange=function(){st.font=this.value;r()};$('lyCol').onchange=function(){st.color=this.value;r()};
 async function out(type){var v=vals(true);if(!v.img)return;var c=document.createElement('canvas');await draw(c,v);return c.toDataURL(type,.92)}
 $('lyPng').onclick=async function(){var d=await out('image/png');if(d&&window.AIS&&AIS.download)AIS.download(d,'layout.png')};
 $('lyJpg').onclick=async function(){var d=await out('image/jpeg');if(d&&window.AIS&&AIS.download)AIS.download(d,'layout.jpg')};
 $('lySave').onclick=async function(){var d=await out('image/jpeg');if(d&&window.AISLIB)AISLIB.addRender(T('지면 레이아웃','Print layout'),d,{type:'layout'}).then(function(){$('lyNote').textContent=T('내 라이브러리의 작업 결과에 저장했습니다.','Saved to My library.')}).catch(function(){$('lyNote').textContent=T('저장하지 못했습니다. 브라우저 저장 공간을 확인해 주세요.','Could not save. Check browser storage.')})};
 return{redraw:r}};
window.AISLAYOUT=L})();
