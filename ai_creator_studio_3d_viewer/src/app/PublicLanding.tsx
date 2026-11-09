import './PublicLanding.css';

type PublicLandingProps = {
  onLogin: () => void;
  onSignup: () => void;
};

const capabilities = [
  { number: '01', icon: '◉', title: '가상 피팅 워크플로', description: '의류와 모델 에셋을 프로젝트 단위로 관리하고, 피팅 작업을 구성하는 제작 흐름.' },
  { number: '02', icon: '✳', title: '캐릭터 일관성', description: '캐릭터 참조 자료와 버전을 관리해 캠페인 전반의 시각적 연속성을 유지하는 구조.' },
  { number: '03', icon: '◇', title: '3D 프리뷰', description: 'GLB·glTF 에셋을 불러와 회전·확대하고 제작 자산을 검토하는 뷰어.' },
  { number: '04', icon: '▧', title: '포토 제작 관리', description: '원본 에셋, 작업 초안, 결과 버전과 검수 기록을 하나의 흐름으로 관리.' },
  { number: '05', icon: '▣', title: '룩북 구성', description: '프로젝트·상품·이미지 에셋을 연결해 룩북 초안과 순서를 구성.' },
  { number: '06', icon: '⇄', title: '팀 단위 협업', description: 'Workspace와 역할 기반 권한을 중심으로 프로젝트 자산을 정리.' },
];

export default function PublicLanding({ onLogin, onSignup }: PublicLandingProps) {
  return <div className="public-site">
    <header className="public-nav">
      <a className="public-brand" href="#top" aria-label="AI Creator Studio 홈"><span>✦</span><b>AI CREATOR STUDIO</b></a>
      <nav aria-label="주요 메뉴"><a href="#platform">플랫폼</a><a href="#workflow">제작 흐름</a><a href="#business">기업 활용</a></nav>
      <div className="public-nav-actions"><button className="public-login" onClick={onLogin}>로그인</button><button className="public-cta" onClick={onSignup}>워크스페이스 시작 ↗</button></div>
    </header>

    <main id="top">
      <section className="public-hero">
        <div className="public-hero-copy"><div className="public-eyebrow"><i/> AI CREATIVE PRODUCTION PLATFORM</div>
          <h1>패션과 캐릭터 콘텐츠,<br/><em>하나의 스튜디오</em>에서.</h1>
          <p>브랜드 자료와 제품 이미지에서 프로젝트 관리, 제작 작업, 결과 검수까지. 전문 제작 워크플로를 한곳에서 연결합니다.</p>
          <div className="public-hero-actions"><button className="public-cta large" onClick={onSignup}>나만의 Workspace 만들기 <span>↗</span></button><a href="#platform">플랫폼 살펴보기 ↓</a></div>
          <div className="public-proof"><span>01 / PROJECT</span><span>02 / ASSET</span><span>03 / CREATE</span><span>04 / REVIEW</span></div>
        </div>
        <div className="public-hero-visual" aria-label="크리에이티브 스튜디오 워크플로 개념 화면">
          <div className="visual-topline"><span>STUDIO OVERVIEW</span><span>WORKSPACE / 001</span></div>
          <div className="visual-stage"><div className="visual-orbit orbit-a"/><div className="visual-orbit orbit-b"/><div className="visual-silhouette"><div className="silhouette-head"/><div className="silhouette-body"/><div className="silhouette-leg leg-a"/><div className="silhouette-leg leg-b"/></div><div className="visual-tag tag-left"><small>CHARACTER</small><b>MODEL / A01</b></div><div className="visual-tag tag-right"><small>PRODUCT</small><b>LOOK / 04</b></div></div>
          <div className="visual-bottom"><div><small>CREATIVE PROJECT</small><b>SPRING / FORM STUDY</b></div><div className="visual-progress"><i/><i/><i/><i/></div><strong>04 MODULES</strong></div>
        </div>
      </section>

      <section className="public-strip"><span>BUILT FOR CREATIVE TEAMS</span><b>FASHION</b><i>✳</i><b>CHARACTER</b><i>✳</i><b>PRODUCT</b><i>✳</i><b>CAMPAIGN</b><i>✳</i><b>CONTENT</b></section>

      <section className="public-section" id="platform"><div className="public-section-heading"><div><small>ONE CONNECTED WORKSPACE</small><h2>제작의 각 단계를<br/>하나의 흐름으로.</h2></div><p>작업별로 흩어진 자료와 도구를 프로젝트 중심으로 연결합니다. 아래 기능은 제품 모듈의 구성 범위이며, AI Provider·실제 가상 피팅 등 외부 엔진 연동은 별도 검증 및 활성화가 필요합니다.</p></div>
        <div className="capability-grid">{capabilities.map(item => <article className="capability-card" key={item.number}><div className="capability-top"><span>{item.number}</span><b>{item.icon}</b></div><h3>{item.title}</h3><p>{item.description}</p><span className="capability-line"/></article>)}</div>
      </section>

      <section className="public-workflow" id="workflow"><div className="public-workflow-heading"><small>FROM SOURCE TO DELIVERY</small><h2>자료에서 결과물까지,<br/><em>명확한 제작 흐름.</em></h2></div><div className="workflow-steps">
        {[
          ['01','UPLOAD','소스 자료 등록','상품 이미지, 브랜드 자료, 캐릭터와 3D 에셋을 Workspace에 정리합니다.'],
          ['02','ORGANIZE','프로젝트 구성','프로젝트와 상품, 모델, 제작 에셋을 연결합니다.'],
          ['03','CREATE','작업 실행','지원되는 제작 모듈과 연결된 AI 엔진을 통해 작업을 실행합니다.'],
          ['04','REVIEW','검수 및 전달','결과 버전과 검수 이력을 확인하고 승인된 결과물을 관리합니다.'],
        ].map(step => <article className="workflow-step" key={step[0]}><span>{step[0]}</span><small>{step[1]}</small><h3>{step[2]}</h3><p>{step[3]}</p></article>)}
      </div></section>

      <section className="public-business" id="business"><div><small>FOR BRANDS & CREATIVE BUSINESSES</small><h2>브랜드와 제작팀을 위한<br/>공통 작업 기반.</h2><p>패션 브랜드, 이커머스 팀, 콘텐츠 에이전시가 프로젝트와 제작 자료를 함께 관리할 수 있도록 설계합니다.</p><button className="public-cta large" onClick={onSignup}>기업 Workspace 시작하기 <span>↗</span></button></div><div className="business-list"><div><span>01</span><b>브랜드 인하우스 팀</b><small>상품·캠페인 콘텐츠 운영</small></div><div><span>02</span><b>패션·이커머스 사업자</b><small>SKU·이미지·룩북 제작 관리</small></div><div><span>03</span><b>크리에이티브 에이전시</b><small>고객사별 프로젝트 및 협업</small></div></div></section>
    </main>
    <footer className="public-footer"><a className="public-brand" href="#top"><span>✦</span><b>AI CREATOR STUDIO</b></a><span>CREATIVE WORKFLOW, CONNECTED.</span><button onClick={onLogin}>계정 로그인 ↗</button></footer>
  </div>;
}
