# 스토리 → 영상(길이 지정) (R-ENGINE-17) — `app/story_video.py`

자체 코드(AI·네트워크 없음). 이야기를 문장으로 나눠 장면을 만들고, **전체 길이(1~60초)** 를 장면에 나눠 주고, 문장을 자막으로 넣어 **서버에서 MP4**(H.264, `video_mp4`/ffmpeg)로 만든다. 화면은 지금 WebM만 만들므로 MP4 서버 변환이 핵심 가치다. **API 경로·작업(job) 연결은 아직 없다**(모듈·시험·계약 제안까지; `video_jobs`의 기존 3~15초·mock 경로는 그대로).

## 계획 규칙 (`plan`, 순수·결정적, 전부 제안값)
- 문장 S(`. ! ? 。 ！ ？`와 줄바꿈으로 분할), 사진 N, 장면 = max(S, N). 장면 상한 20(자막 상한), 장면당 최소 0.5초.
- **S ≥ N**: 장면 j는 사진 floor(j·N/S), 자막은 문장 j(연속 장면이 사진을 재사용). **S < N**: 장면 j = 사진 j, 문장 k의 자막은 그 묶음(장면 floor(j·S/N)=k) 전체 구간에 표시.
- 장면 길이 = 전체 길이 ÷ 장면 수. 자막은 40자에서 `…`로 자름. `captions`: `"auto"` / 장면 수만큼의 글 목록(`""`=없음) / `null`.
- `engine`: `local`만 실행, `ai`는 **닫힘**(`STORY_ENGINE_CLOSED`, 경로가 생기면 409) — 외부 AI 영상 공급자는 키·비용 결정 전까지 보류.

## 계약 제안 (경로는 미연결)
`POST /v1/workspaces/{id}/video-jobs` 본문에 `{images:[asset_id], story, total_seconds(1~60), aspect, transitions:'cut'|'crossfade', captions:'auto'|[…]|null, engine:'local'|'ai'}` → 202 → 폴링 → `{mp4, cuts:[{scene, image_index, start, end, caption}], cues}`. 오류: `STORY_*`(`error_catalog`, ko/en), `VIDEO_ASPECT_INVALID`, `FFMPEG_MISSING`(ffmpeg 없음), `SUBTITLE_FONT_MISSING`(한글 폰트 없음).

## 시험 (18개)
총 길이 경계(0·0.5·1·60·61), 숫자가 아닌 값, 문장 수 < / = / > 사진 수 분배, 자막 40자 자르기·직접 지정·끄기, 한도·닫힌 AI 엔진, 결정성, 자막 모듈이 받는 cue 형식, **프레임 수 = 길이×24**. MP4 자체(길이·자막)는 ffmpeg와 한글 폰트가 필요해 **로컬(ffmpeg 없음)에서는 건너뛰고 CI에서 실행**한다(CI 결과는 보고 참조).

## 한계 (정직하게)
- 분배·길이·자막 한도는 제안값이고 이 모듈은 장면 의미를 이해하지 않는다(문장과 사진의 내용이 맞는지 모름). 장면마다 같은 카메라 움직임(zoom/pan/rotate)을 쓴다.
- 오디오 없음. 길이는 프레임(24 fps) 단위로 반올림.
- 이 PC에는 ffmpeg가 없어 **로컬 MP4 생성은 미실행**(구조 시험은 CI).
