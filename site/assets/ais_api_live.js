/* AIS_API 실연결(라이브) — 3D 작업실 ↔ 서버 (답신 73 D-1)
   원칙(설계 창 지시): 화면 HTML은 고치지 않고, 화면이 부르는 함수 이름에 서버 구현을 끼운다.
   서버가 꺼져 있거나 설정이 없거나 기능 플래그(RENDER3D_ENABLED)가 닫혀 있으면 **조용히 null** 을 돌려준다 → 호출한 쪽은 "지금 로컬 동작 그대로" 진행한다(오류 화면 금지).
   서버가 일부러 거절한 것(잘못된 값 422 등)은 {code,message} 로 던진다.

   설정: AIS_LIVE.configure({ base:'https://api…', token:'…' | function(){return '…'}, workspaceId:'ws…' })
         (이 파일은 키·URL·비밀을 갖지 않는다. 부트스트랩이 넣는다. window.AIS_LIVE_CONFIG 가 있으면 첫 호출 때 읽는다.)
   제공 함수(전부 Promise):
     AIS_API.studio3d.poses()                       → [{id,label_ko,label_en}] | null           (M5, GET …/render3d-jobs/poses)
     AIS_API.studio3d.render({modelId|sex, garments:[kind|{kind}], pose, angles:[0,45,90,180,270], measurements?, bg?, renderer?='photo'})
                                                    → {job_id, images:[{angle,asset_id,url}], qc, ms} | null   (E-03 사진 렌더 job; url 은 이 브라우저의 blob 주소)
     AIS_API.studio3d.fitCheck({sex,kind,measurements?,nominal?}) → §15 응답 | null            (POST …/fit-check)
     AIS_API.studio3d.export({assetId, versionId?, format:'glb'}) → {blob,url,sha256,filename} | null   (§14 E-05)
     AIS_API.studio3d.saveToLibrary(images, {name?})→ [library item]                           (POST …/library/attach, kind=render)
     AIS_API.studio3d.toVideo({itemIds, aspect?, duration?, motion?}) → {job_id,status,…} | null (POST …/video-jobs, 라이브러리 항목 → 영상) */
(function(){
var CFG=null,STATE={up:null,checked:0};
var POLL_MS=700,POLL_MAX_MS=240000;
function cfg(){
  if(!CFG&&window.AIS_LIVE_CONFIG)CFG=normalize(window.AIS_LIVE_CONFIG);
  return CFG;
}
function normalize(c){
  if(!c||!c.base||!c.workspaceId)return null;
  return {base:String(c.base).replace(/\/+$/,''),token:c.token,workspaceId:String(c.workspaceId)};
}
function token(){var t=CFG&&CFG.token;return typeof t==='function'?t():t}
function wsUrl(path){return CFG.base+'/v1/workspaces/'+encodeURIComponent(CFG.workspaceId)+path}
function headers(extra){var h=extra||{};var t=token();if(t)h['Authorization']='Bearer '+t;return h}
function fail(code,message,status){var e={code:code,message:message||code};if(status)e.status=status;return e}
function detail(r,body){
  var d=body&&body.detail;
  if(d&&typeof d==='object'&&d.code)return fail(d.code,d.message,r.status);
  return fail(r.status===401||r.status===403?'FORBIDDEN':(r.status===422?'INVALID':'SERVER'),typeof d==='string'?d:(d?JSON.stringify(d).slice(0,300):('HTTP '+r.status)),r.status);   /* 422 의 본문(필드별 오류)을 그대로 싣는다 */
}
/* 서버를 부를 수 없는 경우(설정 없음·꺼짐·플래그 닫힘)와 거절을 구분한다. */
async function call(method,url,body,opts){
  var init={method:method,headers:headers(body&&!(body instanceof FormData)?{'Content-Type':'application/json'}:{})};
  if(body)init.body=body instanceof FormData?body:JSON.stringify(body);
  var r;
  try{r=await fetch(url,init)}catch(e){STATE.up=false;return {unavailable:true,why:'NETWORK'}}
  STATE.up=true;
  if(opts&&opts.raw&&r.ok)return {ok:true,response:r};
  var j=null;try{j=await r.json()}catch(e){}
  if(r.ok)return {ok:true,json:j,response:r};
  if(r.status===409&&j&&j.detail&&j.detail.code==='RENDER3D_CLOSED')return {unavailable:true,why:'CLOSED'};
  if(r.status===401||r.status===403||r.status===404)return {unavailable:true,why:'NOACCESS',status:r.status};   // 로그인·권한·작업공간이 없으면 로컬로 대체
  throw detail(r,j);
}
function ready(){return !!cfg()}
function sexOf(o){
  if(o.sex==='male'||o.sex==='female')return o.sex;
  var id=String(o.modelId||'');
  return /^(mf|cw|f|female|woman)/i.test(id)?'female':'male';
}
function kindsOf(list){return (list||[]).map(function(g){return typeof g==='string'?{kind:g}:{kind:g.kind}})}
function sleep(ms){return new Promise(function(r){setTimeout(r,ms)})}
async function poll(url){
  var t0=Date.now();
  for(;;){
    var x=await call('GET',url);
    if(x.unavailable)return x;
    var s=x.json&&x.json.status;
    if(s==='succeeded'||s==='failed'||s==='cancelled')return x;
    if(Date.now()-t0>POLL_MAX_MS)throw fail('TIMEOUT','The server did not finish in time');
    await sleep(POLL_MS);
  }
}
async function blobUrl(assetId){
  /* 사진 바이트는 서명된 짧은 수명 주소로 받는다(POST …/preview-url → GET 그 주소). */
  var u=await call('POST',CFG.base+'/v1/assets/'+encodeURIComponent(assetId)+'/preview-url');
  if(u.unavailable)return null;
  var r=await fetch(CFG.base+u.json.url);
  if(!r.ok)throw fail('SERVER','HTTP '+r.status,r.status);
  var b=await r.blob();
  return {blob:b,url:URL.createObjectURL(b)};
}

var S3={
  poses:async function(){
    if(!ready())return null;
    var x=await call('GET',wsUrl('/render3d-jobs/poses'));
    return x.unavailable?null:x.json.poses;
  },
  render:async function(o){
    if(!ready())return null;
    o=o||{};
    var t0=Date.now();
    var body={sex:sexOf(o),garments:kindsOf(o.garments),pose:o.pose||'standing',renderer:o.renderer||'photo',mp4:!!o.mp4,bg:o.bg||'studio',angles:o.angles&&o.angles.length?o.angles:[0,45,90,180,270]};
    if(o.measurements)body.measurements=o.measurements;
    var x=await call('POST',wsUrl('/render3d-jobs'),body);
    if(x.unavailable)return null;
    var done=await poll(wsUrl('/render3d-jobs/'+encodeURIComponent(x.json.job_id)));
    if(done.unavailable)return null;
    var job=done.json;
    if(job.status!=='succeeded')throw fail(job.error_code||'RENDER_FAILED','The 3D render did not succeed');
    var images=[];
    for(var i=0;i<job.images.length;i++){
      var b=await blobUrl(job.images[i].asset_id);
      images.push({angle:job.images[i].angle,asset_id:job.images[i].asset_id,url:b?b.url:null,blob:b?b.blob:null});
    }
    return {job_id:job.job_id,images:images,qc:job.qc,pose:body.pose,renderer:body.renderer,ms:Date.now()-t0};
  },
  fitCheck:async function(o){
    if(!ready())return null;
    var x=await call('POST',wsUrl('/fit-check'),o||{});
    return x.unavailable?null:x.json;
  },
  export:async function(o){
    if(!ready())return null;
    o=o||{};
    if((o.format||'glb')!=='glb')throw fail('EXPORT_FORMAT','Only glb is exported');
    var versionId=o.versionId;
    if(!versionId){
      var v=await call('GET',CFG.base+'/v1/assets/'+encodeURIComponent(o.assetId)+'/versions');
      if(v.unavailable)return null;
      var items=v.json.items||[];versionId=items.length&&items[0].version_id;
    }
    var x=await call('GET',CFG.base+'/v1/assets/'+encodeURIComponent(o.assetId)+'/versions/'+encodeURIComponent(versionId)+'/export',null,{raw:true});
    if(x.unavailable)return null;
    var b=await x.response.blob();
    var cd=x.response.headers.get('content-disposition')||'';
    var m=/filename="?([^";]+)"?/.exec(cd);
    return {blob:b,url:URL.createObjectURL(b),sha256:x.response.headers.get('x-content-sha256'),filename:m?m[1]:'model.glb',bytes:b.size};
  },
  saveToLibrary:async function(images,o){
    if(!ready())return null;
    var out=[];o=o||{};
    for(var i=0;i<(images||[]).length;i++){
      var im=images[i];
      var x=await call('POST',wsUrl('/library/attach'),{asset_id:im.asset_id,kind:'render',name:((o.name||'3D')+' '+(im.angle!=null?im.angle+'°':(i+1))).slice(0,120)});
      if(x.unavailable)return null;
      out.push(x.json);
    }
    return out;
  },
  toVideo:async function(o){
    if(!ready())return null;
    o=o||{};
    var x=await call('POST',wsUrl('/video-jobs'),{input_item_ids:o.itemIds,aspect:o.aspect||'9:16',duration_seconds:o.duration||6,motion:o.motion||'slow_zoom'});
    if(x.unavailable)return null;
    var done=await poll(wsUrl('/video-jobs/'+encodeURIComponent(x.json.job_id)));
    return done.unavailable?null:done.json;
  }
};

window.AIS_LIVE={
  configure:function(c){CFG=normalize(c);STATE.up=null;return !!CFG},
  enabled:function(){return !!cfg()},
  /* 서버가 지금 닿는지(설정이 있고 /health 에 답하는지). 화면이 "서버 연결됨" 표시를 할 때 쓴다. */
  ping:async function(){
    if(!cfg())return false;
    try{var r=await fetch(CFG.base+'/health');STATE.up=r.ok;return r.ok}catch(e){STATE.up=false;return false}
  }
};
window.AIS_API=window.AIS_API||{};
window.AIS_API.studio3d=Object.assign(window.AIS_API.studio3d||{},S3);
})();
