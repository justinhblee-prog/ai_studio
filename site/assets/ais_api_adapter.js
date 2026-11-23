/* AIS_API 어댑터 — D1-1 인증 (초안, 기본 꺼짐)
   목적: 개발 계약표(R-068 연결표)대로 Supabase Auth 세션을 홈페이지의 AIS.session / AIS.auth 에 연결한다.
   - 이 파일은 키·URL·비밀을 갖지 않는다. 개발 쪽 부트스트랩이 Supabase 클라이언트를 만들어 install() 에 넘긴다.
   - install() 을 부르지 않으면(또는 window.AIS_API 가 이미 있으면) 아무것도 바꾸지 않는다 → 기존 로컬(모의) 동작 유지.
   - 사용: AIS_ADAPTER.install({ supabase, loadMembership, memberApi? })
       supabase       : @supabase/supabase-js 클라이언트(주입). 사용 메서드 = auth.signUp / verifyOtp / resend / signInWithPassword / signOut / getSession / onAuthStateChange
       loadMembership : async (accessToken) => ({ company, role })  role ∈ owner|admin|editor|viewer (approver 없음, 회신 39)
       memberApi      : (선택) { add(email, role, name), list(), remove(id), setRole(id, role) } — 서버의 "소유자·관리자가 멤버 추가" 호출. 계약 경로 미확인(아래 TODO).
   화면이 기대하는 오류 코드(ais.js): EXISTS, NOUSER, UNVERIFIED{email}, NOCODE, EXPIRED, TOOMANY, BADCODE{left}, WAIT{sec}, NOCOMPANY, BADCODE(초대 코드 폐기)  */
(function(){
var cur=null;           // 동기 session (AIS.session() 이 동기 호출이라 캐시)
var OPT=null;
function emit(){try{window.dispatchEvent(new Event('ais:session'))}catch(e){}}
function err(code,extra){var e={code:code};if(extra)for(var k in extra)e[k]=extra[k];return e}
function mapErr(e,email){
  var m=((e&&(e.code||e.name||''))+' '+(e&&e.message||'')).toLowerCase();
  if(/user_already_exists|already registered|already been registered/.test(m))return err('EXISTS');
  if(/email_not_confirmed|not confirmed/.test(m))return err('UNVERIFIED',{email:email});
  if(/invalid_credentials|invalid login|user not found/.test(m))return err('NOUSER');
  if(/otp_expired|expired/.test(m))return err('EXPIRED');
  if(/over_email_send_rate_limit|rate limit|too many/.test(m)){var s=(m.match(/(\d+)\s*sec/)||[])[1];return err('WAIT',{sec:s?+s:60})}
  if(/otp|token/.test(m)&&/invalid/.test(m))return err('BADCODE',{left:null});
  return err('SERVER',{message:e&&e.message||''});
}
async function build(sess){
  if(!sess||!sess.user){cur=null;return null}
  var md=sess.user.user_metadata||{},m={company:md.company||'',role:'viewer'};
  try{var x=await OPT.loadMembership(sess.access_token);if(x){m.company=x.company||m.company;m.role=x.role||m.role}}catch(e){/* 멤버십 조회 실패 → 가장 약한 역할 */}
  cur={user:{name:md.name||sess.user.email,email:sess.user.email},email:sess.user.email,name:md.name||sess.user.email,company:m.company,role:m.role,verified:true};
  return cur;
}
var AUTH={
  signup:async function(d){
    if(d.code)throw err('BADCODE');           // 초대 코드(INV-…) 폐기: 멤버는 소유자·관리자가 추가
    if(!d.company)throw err('NOCOMPANY');
    var r=await OPT.supabase.auth.signUp({email:d.email,password:d.password,options:{data:{name:d.name,company:d.company}}});
    if(r.error)throw mapErr(r.error,d.email);
    if(r.data&&r.data.user&&Array.isArray(r.data.user.identities)&&!r.data.user.identities.length)throw err('EXISTS'); // Supabase 는 중복 가입을 오류 없이 빈 identities 로 알림
    return {pending:true,email:d.email};
  },
  verify:async function(d){
    var r=await OPT.supabase.auth.verifyOtp({email:d.email,token:String(d.code).trim(),type:'signup'});
    if(r.error)throw mapErr(r.error,d.email);
    var s=await build(r.data&&r.data.session);emit();return s;
  },
  resend:async function(d){
    var email=typeof d==='string'?d:d.email;
    var r=await OPT.supabase.auth.resend({type:'signup',email:email});
    if(r.error)throw mapErr(r.error,email);
    return {};
  },
  changePassword:async function(d){
    var se=(await OPT.supabase.auth.getSession()).data.session;if(!se||!se.user)throw {code:'NOSESSION'};
    var chk=await OPT.supabase.auth.signInWithPassword({email:se.user.email,password:d.current});
    if(chk.error)throw {code:'BADPW'};
    var r=await OPT.supabase.auth.updateUser({password:d.next});
    if(r.error)throw mapErr(r.error,se.user.email);
    return {};
  },
  login:async function(d){
    var r=await OPT.supabase.auth.signInWithPassword({email:d.email,password:d.password});
    if(r.error)throw mapErr(r.error,d.email);
    var s=await build(r.data&&r.data.session);emit();return s;
  },
  logout:async function(){
    try{await OPT.supabase.auth.signOut()}catch(e){}
    cur=null;emit();
  }
};
window.AIS_ADAPTER={
  /* 설치: 이미 AIS_API 가 있으면 건드리지 않는다. */
  install:async function(opt){
    if(!opt||!opt.supabase)throw new Error('AIS_ADAPTER.install: supabase client required');
    if(window.AIS_API&&!window.AIS_API.__adapter)return false;
    OPT=opt;
    var api=window.AIS_API||{};api.__adapter=true;
    api.auth=AUTH;
    Object.defineProperty(api,'session',{configurable:true,enumerable:true,get:function(){return cur}});
    if(opt.memberApi)api.members=opt.memberApi;
    window.AIS_API=api;
    try{var g=await opt.supabase.auth.getSession();await build(g&&g.data&&g.data.session)}catch(e){cur=null}
    try{opt.supabase.auth.onAuthStateChange(async function(ev,sess){await build(sess);emit()})}catch(e){}
    emit();return true;
  },
  uninstall:function(){if(window.AIS_API&&window.AIS_API.__adapter)delete window.AIS_API;cur=null;emit()}
};
/* TODO(계약 미확인 — 개발 확인 후 memberApi 로 연결): 멤버 추가 화면에 필요한 호출
   1) 멤버 추가(이메일·역할[·이름]) — 서버 "소유자·관리자가 멤버 추가" 경로·본문·초대 메일 여부
   2) 멤버 목록(이름·이메일·역할·상태) — 이름·이메일은 서버가 모름(R-068 ①) → Supabase 프로필에서 어댑터가 채워야 하는지
   3) 역할 변경, 4) 멤버 제거(archive?), 5) 가입 직후 작업공간 생성(소유자 = 가입자)과 company 이름 저장 위치
   6) 현재 사용자의 작업공간·역할 조회(loadMembership 이 부를 경로)  */
})();
