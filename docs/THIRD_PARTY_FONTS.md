# 서드파티 글꼴 (자막용)

| 항목 | 내용 |
|---|---|
| 용도 | MP4 영상의 자막을 그림으로 굽는 데 사용(`app/video_subtitles.py`) |
| 글꼴 | Noto Sans CJK(한국어 글자모양 사용: `NotoSansCJK-Regular.ttc`, 모음집 번호 1) |
| 공급 방식 | **저장소에 글꼴 파일을 넣지 않는다.** 서버·CI에 Debian/Ubuntu 패키지 `fonts-noto-cjk`를 설치한다(CI가 쓴 버전: `1:20230817+repack1-3`). 다른 글꼴을 쓰려면 환경 변수 `SUBTITLE_FONT_PATH`(필요하면 `SUBTITLE_FONT_INDEX`) |
| 라이선스 | 이 패키지가 알리는 라이선스(SIL Open Font License 계열)의 **원문은 같은 폴더의 `licenses/NOTO_SANS_CJK_debian_copyright.txt`**(패키지의 `/usr/share/doc/fonts-noto-cjk/copyright`를 CI에서 그대로 가져온 것, 수정 없음) |
| 회신 57 A② | 상용 유료 글꼴은 쓰지 않는다 — 이 글꼴은 오픈 글꼴이다 |

## 확인하지 않은 것 (사용자·법무 결정)
- **글꼴 파일을 제품(설치본·컨테이너 이미지)에 함께 넣어 배포할 때 요구되는 고지·표기 방식**은 검토하지 않았다. 지금은 서버가 패키지를 설치해 쓰는 방식이라 파일을 직접 배포하지 않는다.
- 글꼴로 그린 글자가 들어간 영상(결과물)에 대한 라이선스 조건은 검토하지 않았다(글꼴 제작자가 정한 조건을 법무가 확인해야 함).
- 위 원문 파일은 Debian 패키지의 저작권 정리 문서이며, 글꼴 제작자 원본 `OFL.txt`와 같은지 대조하지 않았다.

## 글꼴이 없을 때
자막을 요청하면 `SUBTITLE_FONT_MISSING`으로 실패한다(다른 글꼴로 조용히 바꾸지 않음). 글꼴이 못 그리는 글자(이모지 등)는 네모로 나오는 대신 `SUBTITLE_GLYPH_MISSING`으로 거부한다.
