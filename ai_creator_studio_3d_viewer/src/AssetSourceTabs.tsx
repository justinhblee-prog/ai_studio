import { ReactNode, useState } from 'react';
import './LibraryBrowser.css';

type Props = {
  label: string;
  mine: ReactNode;                                 // the existing "my assets" picker, including "내 사진 올리기" (shown first)
  library: (done: () => void) => ReactNode;        // the library view; call done() after a pick to return to "내 자산"
};

// R-033: "내 자산 / 라이브러리" tabs for an asset picker. "내 자산" is the default so uploading stays right there.
export default function AssetSourceTabs({ label, mine, library }: Props) {
  const [tab, setTab] = useState<'mine' | 'library'>('mine');
  return <div className="lib-picker" role="group" aria-label={`${label} 고르기`}>
    <div className="lib-tabs" role="tablist" aria-label={`${label} 출처`}>
      <button type="button" role="tab" aria-selected={tab === 'mine'} onClick={() => setTab('mine')}>내 자산</button>
      <button type="button" role="tab" aria-selected={tab === 'library'} onClick={() => setTab('library')}>라이브러리</button>
    </div>
    <div role="tabpanel" hidden={tab !== 'mine'} aria-label={`${label} 내 자산`}>{mine}</div>
    {tab === 'library' && <div role="tabpanel" aria-label={`${label} 라이브러리`}>{library(() => setTab('mine'))}</div>}
  </div>;
}
