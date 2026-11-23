# 오류 코드 → 안내 문구 표 (자동 생성 — 직접 고치지 않음)

버전 `2026-11-17.1`. 원본은 `ai_creator_studio_backend_starter/app/error_catalog.py`, 같은 내용을 `GET /v1/error-catalog?lang=ko|en`(로그인 불필요)이 JSON으로 줍니다. `python scripts/generate_error_codes_doc.py`로 다시 만들고, 시험이 이 문서가 최신인지와 **서버가 보내는 모든 코드가 표에 있는지**를 확인합니다.

- **종류**: `limit` = 한도·속도 제한·용량(429 또는 그에 준함, 응답에 `retry_after_seconds`·`retry_at`이 있을 수 있음), `error` = 그 밖의 오류.
- **법무성 문구는 비어 있음**(`[결정 필요: 법무]`): `EXTERNAL_NOTICE_REQUIRED`, `LEGAL_ACCEPTANCE_REQUIRED`, `TAKEDOWN_ACTIVE`, `ASSET_UNDER_REVIEW`, `LIBRARY_RIGHTS_NOT_CONFIRMED`, `RIGHTS_CONFIRMATION_REQUIRED`, `MARKET_RIGHTS_REQUIRED`, `MARKET_LICENSE_REQUIRED`. 이 코드들은 `message: null`, `needs_decision: true`이며 홈페이지는 **HTTP 상태별 기본 문구**를 대신 보여 주세요.
- 코드가 **없는** 응답(예: 권한 없음 403의 글자 한 줄)은 아래 "HTTP 상태별 기본 문구"를 쓰세요.

## 코드별 문구

| 코드 | 영역 | 종류 | 한국어 | English |
|---|---|---|---|---|
| `ACQ_DATE_INVALID` | customers | error | 날짜 형식이 올바르지 않습니다. | The date is not valid. |
| `ACQ_HOST_INVALID` | customers | error | 주소는 도메인 이름만 쓸 수 있습니다. | Only a plain domain name is allowed. |
| `ACQ_LANDING_INVALID` | customers | error | 경로는 /로 시작하는 단순한 경로여야 합니다. | The path must be a plain path starting with /. |
| `ACQ_TOKEN_INVALID` | customers | error | 값에는 글자·숫자와 . _ ~ + - 만 쓸 수 있습니다. | Values may use letters, digits and . _ ~ + - only. |
| `AI_JOBS_DISABLED` | general | limit | AI 기능이 일시적으로 꺼져 있습니다. | AI features are temporarily switched off. |
| `ASSET_DATA_URI_TOO_LARGE` | file | error | 3D 파일에 포함된 내장 데이터가 너무 큽니다. | The embedded data in the 3D file is too large. |
| `ASSET_EMPTY` | file | error | 파일이 비어 있습니다. | The file is empty. |
| `ASSET_EXTERNAL_URI_BLOCKED` | file | error | 3D 파일이 바깥 주소를 참조합니다. 자체 포함 파일만 올릴 수 있습니다. | The 3D file points to outside addresses. Only self-contained files can be uploaded. |
| `ASSET_FORMAT_UNSUPPORTED` | file | error | 지원하지 않는 파일 형식입니다. | This file format is not supported. |
| `ASSET_IN_USE` | file | error | 다른 곳에서 쓰고 있어 지울 수 없습니다. | It is in use elsewhere and cannot be deleted. |
| `ASSET_JSON_TOO_LARGE` | file | error | 3D 파일의 설명 부분이 너무 큽니다. | The description part of the 3D file is too large. |
| `ASSET_KIND_MISMATCH` | file | error | 이 종류의 파일을 여기에 쓸 수 없습니다. | This kind of file cannot be used here. |
| `ASSET_MEDIA_TYPE_UNSUPPORTED` | file | error | 지원하지 않는 파일 종류입니다. | This kind of file is not supported. |
| `ASSET_NOT_FOUND` | file | error | 해당 그림을 찾을 수 없습니다. | That picture was not found. |
| `ASSET_PARSE_FAILED` | file | error | 파일을 읽지 못했습니다. 손상되었을 수 있습니다. | The file could not be read. It may be damaged. |
| `ASSET_SIGNATURE_INVALID` | file | error | 파일 내용이 형식과 맞지 않습니다. | The file content does not match its format. |
| `ASSET_TOO_LARGE` | file | error | 파일이 너무 큽니다. | The file is too large. |
| `ASSET_UNDER_REVIEW` | file | error | **[결정 필요: 법무]** | **[decision needed: legal]** |
| `ASSET_VERSION_INTEGRITY_FAILED` | file | error | 저장된 파일이 손상되었습니다. 지원팀에 문의해 주세요. | The stored file is damaged. Please contact support. |
| `ASSET_VIDEO_INVALID` | file | error | 영상 파일이 온전한 MP4가 아닙니다. | The video file is not a complete MP4. |
| `ASSIST_LIMIT` | assist | limit | 오늘 쓸 수 있는 AI 해석 횟수를 모두 썼습니다. | Today's AI interpretation limit has been used up. |
| `ASSIST_RATE_LIMITED` | assist | limit | 도움말 요청이 너무 잦습니다. 잠시 뒤 다시 시도해 주세요. | Too many assistant requests. Please try again shortly. |
| `ASSIST_TEXT_REQUIRED` | assist | error | 요청할 내용을 글로 적어 주세요. | Please type what you need. |
| `ATTRS_INVALID` | attributes | error | 속성은 이름과 값의 묶음이어야 합니다. | Attributes must be a set of names and values. |
| `ATTRS_TOO_MANY` | attributes | error | 속성이 너무 많습니다. | Too many attributes. |
| `ATTR_FILTER_INVALID` | attributes | error | 필터는 '이름:값' 모양이어야 합니다. | A filter must look like name:value. |
| `ATTR_KEY_INVALID` | attributes | error | 속성 이름은 소문자·숫자·밑줄만 쓸 수 있습니다. | Attribute names may use lowercase letters, digits and underscores only. |
| `ATTR_VALUE_INVALID` | attributes | error | 속성 값은 짧은 글이나 작은 정수여야 합니다. | Attribute values must be short text or a small whole number. |
| `AUDIO_ENCODER_MISSING` | general | error | 이 서버의 영상 도구에 소리를 넣는 기능이 없습니다. | This server's video tool cannot encode sound. |
| `AUDIO_INVALID` | general | error | 소리 파일은 16비트 WAV(최대 50MB·10분)여야 하고, 영상에 이미 소리가 없어야 합니다. | The sound must be a 16-bit WAV (up to 50 MB and 10 minutes) and the video must have no sound yet. |
| `AUTO_ROUTING_NOT_APPROVED` | provider | error | 자동 선택은 아직 승인되지 않았습니다. | Automatic selection is not approved yet. |
| `BATCH_DUPLICATE_ASSET` | general | error | 같은 그림을 두 번 넣을 수 없습니다. | Each picture can be listed once. |
| `BATCH_RECIPE_REQUIRED` | general | error | 일괄 처리에는 처리 단계 또는 프리셋 중 하나만 지정해 주세요. | Give either the steps or a preset for a batch, not both and not neither. |
| `CAPABILITY_NOT_VERIFIED` | provider | error | 이 기능은 아직 확인되지 않았습니다. | This capability has not been verified yet. |
| `COLLECTION_DISABLED` | customers | error | 이 정보는 지금 수집하지 않습니다. | This information is not being collected right now. |
| `CONTRACT_DATE_INVALID` | customers | error | 날짜는 YYYY-MM-DD 형식이어야 합니다. | Dates must look like YYYY-MM-DD. |
| `CONTRACT_PLAN_INVALID` | customers | error | 요금제 값이 올바르지 않습니다. | The plan value is not valid. |
| `CONTRACT_REASON_INVALID` | customers | error | 사유 값이 올바르지 않습니다. | The reason value is not valid. |
| `DAILY_JOB_LIMIT_EXCEEDED` | general | limit | 오늘 만들 수 있는 작업 수를 모두 썼습니다. | Today's job limit for this workspace has been used up. |
| `DESIGN_KEY_INVALID` | model | error | 속성 이름이 올바르지 않습니다. | A design value name is not valid. |
| `DESIGN_REQUIRED` | model | error | 속성을 하나 이상 지정해 주세요. | Give at least one design value. |
| `DESIGN_TOO_MANY` | model | error | 속성이 너무 많습니다. | Too many design values. |
| `DESIGN_VALUE_INVALID` | model | error | 속성 값은 짧은 글이나 0~9999의 정수여야 합니다. | Design values must be short text or a whole number from 0 to 9999. |
| `DOWNLOAD_MONTHLY_LIMIT` | general | limit | 이번 달 내려받기 한도에 도달했습니다. | The monthly download limit has been reached. |
| `EXPORT_FAILED` | export | error | 모델을 내보낼 수 있게 준비하지 못했습니다. | The model could not be prepared for export. |
| `EXPORT_GONE` | export | limit | 내보내기 파일의 보관 기간이 끝났습니다. 새로 만들어 주세요. | This export has expired. Please create a new one. |
| `EXPORT_LIMIT` | export | limit | 내보내기는 하루에 정해진 횟수까지만 할 수 있습니다. | Exports are limited per day. |
| `EXPORT_NOT_GLB` | export | error | 3D 모델(.glb)만 내보낼 수 있습니다. | Only .glb 3D models can be exported. |
| `EXPORT_TOO_LARGE` | export | limit | 내보낼 파일이 너무 큽니다. 지원팀에 나눠서 내보내기를 요청해 주세요. | The files are too large to export at once. Ask support for a split export. |
| `EXTERNAL_NOTICE_REQUIRED` | legal | error | **[결정 필요: 법무]** | **[decision needed: legal]** |
| `FFMPEG_FAILED` | general | error | 영상 파일을 만드는 중 오류가 났습니다. 잠시 뒤 다시 시도해 주세요. | The video file could not be encoded. Please try again shortly. |
| `FFMPEG_MISSING` | general | error | 이 서버에 영상 변환 도구가 설치되어 있지 않아 MP4를 만들 수 없습니다. | The video encoder is not installed on this server, so MP4 output is not available. |
| `FIT_CHECK_INVALID` | general | error | 사이즈 비교에 넣은 값을 확인해 주세요(몸 치수나 기준 둘레가 허용 범위를 벗어났습니다). | Please check the values for the size comparison (a measurement or the reference circumference is out of range). |
| `FIT_REFUSED` | general | error | 입력한 몸 치수에 옷을 맞출 수 없습니다. 치수를 확인해 주세요. | The garment cannot be fitted to the measurements entered. Please check them. |
| `GLB_INVALID` | general | error | 만들어진 3D 파일이 검사를 통과하지 못했습니다. | The generated 3D file did not pass the check. |
| `GLOBAL_MONTHLY_LIMIT` | general | limit | 이번 달 서비스 전체 작업 한도에 도달했습니다. | The service-wide job limit for this month has been reached. |
| `IMAGE_ANIMATION_UNSUPPORTED` | file | error | 움직이는 그림은 올릴 수 없습니다. | Animated pictures cannot be uploaded. |
| `IMAGE_DECODE_FAILED` | file | error | 그림을 열 수 없습니다. 다른 파일로 시도해 주세요. | The picture could not be opened. Try another file. |
| `IMAGE_DIMENSIONS_UNSUPPORTED` | file | error | 그림의 가로·세로가 허용 범위를 넘었습니다. | The picture's width or height is out of range. |
| `IMAGE_EXTENSION_MISMATCH` | file | error | 파일 확장자가 실제 형식과 다릅니다. | The file extension does not match the real format. |
| `IMAGE_FORMAT_UNSUPPORTED` | file | error | PNG, JPEG, WebP 그림만 올릴 수 있습니다. | Only PNG, JPEG and WebP pictures can be uploaded. |
| `IMAGE_UNREADABLE` | file | error | 그림을 읽을 수 없습니다. | The picture cannot be read. |
| `IMPORT_EMPTY` | general | error | 모델에 면(삼각형)이 없습니다. | The model has no triangles. |
| `IMPORT_KIND` | general | error | 지원하지 않는 옷 종류입니다. | That garment kind is not supported. |
| `IMPORT_SCALE_AMBIGUOUS` | general | error | 모델의 단위(cm·mm 등)를 확인해 주세요. | Please confirm the unit of the model (cm, mm, ...). |
| `IMPORT_SCALE_IMPLAUSIBLE` | general | error | 어떤 단위로도 옷 크기로 보이지 않습니다. 파일을 확인해 주세요. | No unit makes this a plausible garment size. Please check the file. |
| `IMPORT_SCALE_INVALID` | general | error | 배율 값이 올바르지 않습니다. | The scale value is not valid. |
| `IMPORT_SKINNED` | general | error | 뼈대(스킨)나 모프가 있는 모델은 지원하지 않습니다. | Models with a skin or morph targets are not supported. |
| `IMPORT_SLEEVE_REQUIRED` | general | error | 재킷은 소매 길이를 입력해 주세요. | A jacket needs its sleeve length. |
| `IMPORT_TOO_LARGE` | general | error | 모델의 면 수가 너무 많습니다. | The model has too many triangles. |
| `IMPORT_UNSUPPORTED` | general | error | 이 모델 형식의 일부는 지원하지 않습니다. | Part of this model format is not supported. |
| `INTERNAL_ADAPTER_ERROR` | general | error | 서비스 내부 오류입니다. 잠시 뒤 다시 시도해 주세요. | An internal error occurred. Please try again shortly. |
| `INVALID_MONTH` | general | error | 월 형식이 올바르지 않습니다(예: 2026-11). | The month is not valid (for example 2026-11). |
| `INVALID_RANGE` | general | error | 기간 형식이 올바르지 않습니다. | The date range is not valid. |
| `INVALID_ROUTING_MODE` | provider | error | 선택 방식이 올바르지 않습니다. | The selection mode is not valid. |
| `JOB_NOT_FINISHED` | tryon | error | 작업이 아직 끝나지 않았습니다. | The job has not finished yet. |
| `JOB_QC_FAILED` | tryon | error | 결과가 품질 검사를 통과하지 못했습니다. | The result did not pass the quality check. |
| `LEGAL_ACCEPTANCE_REQUIRED` | legal | error | **[결정 필요: 법무]** | **[decision needed: legal]** |
| `LIBRARY_3D_FULL` | library | limit | 3D 항목을 더 넣을 수 없습니다. | No more 3D items can be added. |
| `LIBRARY_ALREADY_FILED` | library | error | 이미 라이브러리에 있는 항목입니다. | This is already in the library. |
| `LIBRARY_ATTRIBUTE_INVALID` | library | error | 속성 값이 올바르지 않습니다. | An attribute value is not valid. |
| `LIBRARY_ATTRIBUTE_MISSING` | library | error | 필요한 속성이 빠졌습니다. | A required attribute is missing. |
| `LIBRARY_ATTRIBUTE_NOT_ALLOWED` | library | error | 이 종류에서는 쓸 수 없는 속성입니다. | This attribute is not allowed for this kind. |
| `LIBRARY_CATEGORY_INVALID` | library | error | 분류가 올바르지 않습니다. | The category is not valid. |
| `LIBRARY_FIELD_REQUIRED` | library | error | 필수 항목이 비어 있습니다. | A required field is empty. |
| `LIBRARY_FIELD_TOO_LONG` | library | error | 입력한 글이 너무 깁니다. | The text is too long. |
| `LIBRARY_FILE_CORRUPT` | library | error | 항목의 파일이 손상되었습니다. | The item's file is damaged. |
| `LIBRARY_FILE_UNAVAILABLE` | library | error | 항목의 파일을 지금 사용할 수 없습니다. | The item's file is not available right now. |
| `LIBRARY_FULL` | library | limit | 라이브러리가 가득 찼습니다. 안 쓰는 항목을 정리해 주세요. | The library is full. Please remove items you no longer need. |
| `LIBRARY_ID_INVALID` | library | error | 항목 번호가 올바르지 않습니다. | The item id is not valid. |
| `LIBRARY_INFO_KIND` | library | error | 3D 항목에만 있는 정보입니다. | This information exists for 3D items only. |
| `LIBRARY_KIND_MISMATCH` | library | error | 이 종류에는 맞지 않는 파일입니다. 3D는 모델 파일, 나머지는 그림이어야 합니다. | That file does not fit this kind. 3D needs a model file, everything else a picture. |
| `LIBRARY_NAME_REQUIRED` | library | error | 이름을 입력해 주세요. | Please enter a name. |
| `LIBRARY_NOTHING_TO_CHANGE` | library | error | 바꿀 내용이 없습니다. | There is nothing to change. |
| `LIBRARY_NOT_FOUND` | library | error | 라이브러리 항목을 찾을 수 없습니다. | The library item was not found. |
| `LIBRARY_PREVIEW_EXPIRED` | library | error | 미리보기 주소가 만료되었습니다. 새로 받아 주세요. | The preview address has expired. Please get a new one. |
| `LIBRARY_RIGHTS_NOT_CONFIRMED` | library | error | **[결정 필요: 법무]** | **[decision needed: legal]** |
| `LIBRARY_SIGNING_NOT_CONFIGURED` | library | error | 미리보기를 만들 수 없는 설정입니다. 지원팀에 문의해 주세요. | Previews are not set up. Please contact support. |
| `LIBRARY_SOURCE_INVALID` | library | error | 출처 정보가 올바르지 않습니다. | The source information is not valid. |
| `LIBRARY_STATUS_INVALID` | library | error | 상태 값이 올바르지 않습니다. | The status is not valid. |
| `LIBRARY_TAGS_INVALID` | library | error | 태그 형식이 올바르지 않습니다. | The tags are not valid. |
| `LIBRARY_TAG_TOO_LONG` | library | error | 태그가 너무 깁니다. | A tag is too long. |
| `LIBRARY_THUMBNAIL_KIND` | library | error | 이 항목에는 미리보기 그림을 올릴 수 없습니다. | A preview picture cannot be set for this item. |
| `LOOKBOOK_ENTITY_MISSING_OR_CROSS_WORKSPACE` | lookbook | error | 다른 작업공간의 항목이거나 없는 항목입니다. | That item belongs to another workspace or does not exist. |
| `LOOKBOOK_IMAGE_ASSET_REQUIRED` | lookbook | error | 룩북에는 그림 파일이 필요합니다. | A lookbook needs picture files. |
| `MARKET_AI_FLAG_REQUIRED` | market | error | AI로 만든 것인지 예/아니오로 표시해 주세요. | Please say whether this was made with AI (yes or no). |
| `MARKET_CHANGED` | market | error | 다른 사람이 먼저 바꿨습니다. 새로고침해 주세요. | Someone else changed this listing. Please reload. |
| `MARKET_COVER_INVALID` | market | error | 표지는 이 작업공간의 그림이어야 합니다. | The cover must be a picture of this workspace. |
| `MARKET_KIND_INVALID` | market | error | 종류 값이 올바르지 않습니다. | The kind is not valid. |
| `MARKET_LICENSE_REQUIRED` | market | error | **[결정 필요: 법무]** | **[decision needed: legal]** |
| `MARKET_NOTHING_TO_CHANGE` | market | error | 바꿀 내용이 없습니다. | There is nothing to change. |
| `MARKET_PAYLOAD_INVALID` | market | error | 내용 데이터 형식이 올바르지 않습니다. | The content data is not valid. |
| `MARKET_PAYLOAD_TOO_LARGE` | market | error | 내용 데이터가 너무 큽니다. | The content data is too large. |
| `MARKET_PRICE_INVALID` | market | error | 가격은 0 이상의 정수여야 합니다. | The price must be a whole number, 0 or more. |
| `MARKET_PROFILE_INVALID` | market | error | 이름과 소개에는 링크·이메일·태그를 넣을 수 없습니다. | The name and introduction cannot contain links, e-mail addresses or markup. |
| `MARKET_RIGHTS_REQUIRED` | market | error | **[결정 필요: 법무]** | **[decision needed: legal]** |
| `MARKET_TAG_INVALID` | market | error | 태그 형식이 올바르지 않습니다. | A tag is not valid. |
| `MARKET_TEXT_REQUIRED` | market | error | 필수 항목이 비어 있습니다. | A required field is empty. |
| `MARKET_TEXT_TOO_LONG` | market | error | 입력한 글이 너무 깁니다. | The text is too long. |
| `MEMBER_OWNER_PROTECTED` | general | error | 소유자의 역할은 여기서 바꾸거나 없앨 수 없습니다. | The owner's role cannot be changed or removed here. |
| `MEMBER_ROLE_FORBIDDEN` | general | error | 이 멤버에 대해서는 그 작업을 할 수 없습니다. 관리자 지정·해제는 소유자만 할 수 있습니다. | You cannot do that for this member. Only the owner can make or unmake an admin. |
| `MODEL_DRAFT_ALREADY_CHOSEN` | model | error | 이 시안은 이미 선택되었습니다. | A candidate was already chosen for this draft. |
| `MODEL_DRAFT_LIMIT` | model | limit | 열려 있는 모델 시안이 너무 많습니다. 하나를 선택하거나 지워 주세요. | Too many open model drafts. Pick or remove one. |
| `MODEL_NAME_REQUIRED` | model | error | 모델 이름을 입력해 주세요. | Please enter a model name. |
| `MODEL_PROVIDER_NOT_CONNECTED` | model | error | 외부 AI 서비스로 모델을 만드는 기능은 아직 연결되지 않았습니다. | Model generation by an external AI service is not connected yet. |
| `MODEL_REAL_PERSON_BLOCKED` | model | error | 실존 인물을 닮게 만드는 요청은 받을 수 없습니다. 표현을 바꿔 다시 적어 주세요. | Requests to look like a real person are not accepted. Please rephrase. |
| `MODEL_UNREADABLE` | model | error | 3D 모델 파일을 읽을 수 없습니다. | The 3D model file cannot be read. |
| `MP4_INVALID` | general | error | 영상 파일이 온전하지 않습니다. | The video file is not a complete MP4. |
| `OUTPUT_NOT_APPROVED` | tryon | error | 결과를 승인한 뒤에 사용할 수 있습니다. | The result can be used after it is approved. |
| `OUTPUT_NOT_LINKED` | tryon | error | 결과가 아직 저장되지 않았습니다. 잠시 뒤 다시 시도해 주세요. | The result is not saved yet. Please try again shortly. |
| `OUTPUT_SAVE_REQUIRES_REVIEW` | tryon | error | 결과는 검수를 거친 뒤에 저장됩니다. | Results are saved after review. |
| `OUTPUT_UNAVAILABLE` | tryon | error | 결과 파일이 더는 없습니다. | The result file is no longer available. |
| `PHOTO_GARMENT_CLIPPED` | photo | error | 옷이 사진 가장자리에 닿았습니다. 옷 전체가 보이게 물러서서 찍어 주세요. | The garment touches the edge of the photo. Step back so the whole garment is in view. |
| `PHOTO_GARMENT_FRAGMENTED` | photo | error | 옷이 여러 조각으로 잘리거나 다른 물건이 함께 찍혔습니다. 옷 전체와 대비되는 배경에서 다시 찍어 주세요. | The garment came out in pieces, or something else is in the photo. Shoot it on a background that contrasts with the whole garment. |
| `PHOTO_GARMENT_NOT_FOUND` | photo | error | 배경과 옷이 구분되지 않습니다. 단색 배경에서 다시 찍어 주세요. | The garment cannot be told from the background. Shoot it on a plain background. |
| `PHOTO_IMAGE_ASSET_REQUIRED` | photo | error | 사진 작업에는 그림 파일이 필요합니다. | Photo work needs a picture file. |
| `PHOTO_KIND` | photo | error | 지원하지 않는 옷 종류입니다. | That garment kind is not supported. |
| `PHOTO_LOCAL_PROCESSING_FAILED` | photo | error | 사진 처리에 실패했습니다. 다른 사진으로 시도해 주세요. | Photo processing failed. Try another picture. |
| `PHOTO_REFERENCE_NOT_FOUND` | photo | error | 옷 옆에 놓은 카드(또는 A4)를 찾지 못했습니다. 옷과 겹치지 않게 옆에 평평하게 놓아 주세요. | The card (or A4) beside the garment was not found. Lay it flat next to the garment, not overlapping. |
| `PHOTO_REFERENCE_UNKNOWN` | photo | error | 기준 물체는 카드 또는 A4 중에서 골라 주세요. | Choose the reference object: card or A4. |
| `PHOTO_SIZE_IMPLAUSIBLE` | photo | error | 사진에서 잰 치수가 옷으로는 비정상입니다. 기준 물체와 촬영 조건을 확인해 주세요. | The size measured from the photo is not plausible for a garment. Check the reference object and the shooting conditions. |
| `PHOTO_TOO_LARGE` | photo | error | 사진이 너무 큽니다. | The photo is too large. |
| `PHOTO_UNREADABLE` | photo | error | 읽을 수 없는 사진 파일입니다. | The photo file cannot be read. |
| `PRESET_LIMIT` | photo | limit | 저장할 수 있는 프리셋 수를 넘었습니다. | The preset limit has been reached. |
| `PRESET_NAME_REQUIRED` | photo | error | 프리셋 이름을 입력해 주세요. | Please enter a preset name. |
| `PRESET_NAME_TAKEN` | photo | error | 같은 이름의 프리셋이 이미 있습니다. | A preset with this name already exists. |
| `PRODUCT_IMAGE_ASSET_REQUIRED` | product | error | 상품에는 그림 파일이 필요합니다. | A product needs a picture file. |
| `PROVIDER_NOT_PRODUCTION_READY` | provider | error | 이 AI 서비스는 아직 실제로 쓸 수 없습니다. | This AI service is not ready for real use. |
| `PROVIDER_RATE_LIMITED` | provider | limit | AI 서비스가 바빠 잠시 뒤 다시 시도합니다. | The AI service is busy and will be retried shortly. |
| `PROVIDER_SUSPENDED` | provider | error | 이 AI 서비스는 지금 중지되어 있습니다. | This AI service is currently suspended. |
| `RATE_LIMITED` | general | limit | 요청이 너무 잦습니다. 잠시 뒤 다시 시도해 주세요. | Too many requests. Please try again shortly. |
| `REFERENCE_DUPLICATE` | model | error | 같은 참조 사진이 중복되었습니다. | A reference picture is listed twice. |
| `REFERENCE_INVALID` | model | error | 참조 사진이 올바르지 않습니다. | A reference picture is not valid. |
| `RENDER3D_CLOSED` | general | error | 3D 돌려보기 작업은 아직 열리지 않았습니다. | The 3D render job is not open yet. |
| `RENDER3D_DAILY_LIMIT` | general | limit | 오늘 만들 수 있는 3D 돌려보기 작업 수를 모두 썼습니다. | Today's 3D render job limit has been used up. |
| `RENDER3D_GARMENT_CONFLICT` | general | error | 같이 입을 수 없는 옷 조합이거나 같은 종류를 두 번 골랐습니다. | These garments cannot be worn together, or the same kind was chosen twice. |
| `RENDER3D_GARMENT_UNKNOWN` | general | error | 지금은 기본 샘플 옷만 3D로 볼 수 있습니다. | Only the built-in sample garments can be shown in 3D for now. |
| `RENDER3D_MEASUREMENT_INVALID` | general | error | 입력한 몸 치수가 허용 범위를 벗어났습니다. 치수를 확인해 주세요. | A body measurement is out of the allowed range. Please check them. |
| `REPORT_DAILY_LIMIT` | general | limit | 오늘 접수할 수 있는 신고 수를 모두 썼습니다. | Today's report limit has been used up. |
| `REVIEW_ALREADY_OPEN` | review | error | 이 파일은 이미 검수 중입니다. | This file is already under review. |
| `REVIEW_CHANGED` | review | error | 다른 사람이 먼저 처리했습니다. 새로고침해 주세요. | Someone else already handled this. Please reload. |
| `REVIEW_COMMENT_REQUIRED` | review | error | 의견을 적어 주세요. | Please write a comment. |
| `REVIEW_NOT_APPROVED` | review | error | 검수에서 승인된 파일만 내보낼 수 있습니다. | Only approved files can be exported. |
| `REVIEW_SELF_APPROVAL_FORBIDDEN` | review | error | 직접 요청한 검수는 직접 승인할 수 없습니다. | You cannot approve a review you requested yourself. |
| `REVIEW_TRANSITION_INVALID` | review | error | 지금 상태에서는 할 수 없는 동작입니다. | That action is not possible in the current state. |
| `RIGHTS_CONFIRMATION_REQUIRED` | legal | error | **[결정 필요: 법무]** | **[decision needed: legal]** |
| `SETTINGS_NOTHING_TO_CHANGE` | review | error | 바꿀 설정을 켬 또는 끔으로 보내 주세요. | Send at least one setting as on or off. |
| `SOURCE_ASSET_INVALID` | tryon | error | 원본으로 지정한 파일은 이 작업공간의 파일이어야 합니다. | Source files must belong to this workspace. |
| `STEPS_REQUIRED` | photo | error | 처리 단계를 하나 이상 넣어 주세요. | Add at least one processing step. |
| `STEPS_TOO_MANY` | photo | error | 처리 단계가 너무 많습니다. | Too many processing steps. |
| `STEP_COLOR_INVALID` | photo | error | 색 값이 올바르지 않습니다. | The colour is not valid. |
| `STEP_FAILED` | photo | error | 이 그림의 처리에 실패했습니다. | Processing this picture failed. |
| `STEP_NEEDS_TRANSPARENCY` | photo | error | 이 단계는 배경이 투명한 그림에서만 쓸 수 있습니다. | This step needs a picture with a transparent background. |
| `STEP_PARAMETER_INVALID` | photo | error | 처리 단계의 값이 올바르지 않습니다. | A step value is not valid. |
| `STEP_PARAMETER_UNKNOWN` | photo | error | 처리 단계에 없는 설정입니다. | That setting does not exist for this step. |
| `STEP_RESULT_TOO_LARGE` | photo | error | 확대하면 결과 그림이 너무 커집니다. 배율을 줄여 주세요. | The enlarged picture would be too large. Please use a smaller factor. |
| `STEP_UNKNOWN` | photo | error | 알 수 없는 처리 단계입니다. | Unknown processing step. |
| `SUBTITLE_FONT_MISSING` | general | error | 이 서버에 자막용 글꼴이 설치되어 있지 않아 자막을 넣을 수 없습니다. | The subtitle font is not installed on this server, so subtitles are not available. |
| `SUBTITLE_GLYPH_MISSING` | general | error | 자막에 이 서비스의 글꼴이 그릴 수 없는 글자가 있습니다. | A subtitle contains a character the service font cannot draw. |
| `SUBTITLE_INVALID` | general | error | 자막은 글, 시작 시각, 끝 시각으로 이루어지며 영상 길이 안에 있어야 합니다. | A subtitle needs text, a start and an end time inside the video. |
| `SUBTITLE_OVERLAP` | general | error | 자막의 시간이 서로 겹칩니다. | Subtitle times overlap. |
| `SUBTITLE_TOO_LONG` | general | error | 자막이 너무 길어 두 줄에 들어가지 않습니다. | A subtitle is too long to fit in two lines. |
| `SURVEY_SIZE_INVALID` | customers | error | 규모는 짧은 코드(예: 1-5, 50+)여야 합니다. | The size must be a short code such as 1-5 or 50+. |
| `SURVEY_TOKEN_INVALID` | customers | error | 값에는 글자·숫자와 . _ ~ + - 만 쓸 수 있습니다. | Values may use letters, digits and . _ ~ + - only. |
| `TAKEDOWN_ACTIVE` | legal | error | **[결정 필요: 법무]** | **[decision needed: legal]** |
| `THREED_DAILY_LIMIT` | general | limit | 오늘 만들 수 있는 3D 작업 수를 모두 썼습니다. | Today's 3D job limit has been used up. |
| `THREED_INPUT_GONE` | general | limit | 선택한 그림의 파일이 더는 없습니다. | The selected picture's file no longer exists. |
| `THREED_INPUT_KIND` | general | error | 3D로 바꿀 수 있는 것은 그림 항목뿐입니다(너무 큰 그림도 안 됩니다). | Only picture items can be turned into 3D (and not very large ones). |
| `THREED_INPUT_NOT_FOUND` | general | error | 선택한 그림 항목을 찾을 수 없습니다. | The selected picture item was not found. |
| `THREED_PROVIDER_NOT_CONNECTED` | general | error | 외부 AI 서비스로 3D를 만드는 기능은 아직 연결되지 않았습니다. | Making 3D models with an external AI service is not connected yet. |
| `TRYON_INPUT_GONE` | tryon | limit | 선택한 사진이 더는 없습니다. 다시 골라 주세요. | A selected picture no longer exists. Please choose again. |
| `TRYON_INPUT_KIND` | tryon | error | 모델·의류 자리에 맞지 않는 항목입니다. | That item does not fit the model / garment slot. |
| `TRYON_INPUT_NOT_FOUND` | tryon | error | 선택한 항목을 찾을 수 없습니다. | The selected item was not found. |
| `TRYON_PUBLIC_URL_MISSING` | tryon | error | 외부 AI 서비스를 쓰기 위한 설정이 아직 없습니다. 지원팀에 문의해 주세요. | The setup for the external AI service is missing. Please contact support. |
| `UNKNOWN_PROVIDER` | provider | error | 알 수 없는 AI 서비스입니다. | Unknown AI service. |
| `UNKNOWN_REQUEST` | general | error | 해당 요청을 찾을 수 없습니다. | That request was not found. |
| `UNSUPPORTED_CAPABILITY` | provider | error | 이 AI 서비스가 지원하지 않는 기능입니다. | This AI service does not support that. |
| `UNSUPPORTED_PROVIDER` | provider | error | 지원하지 않는 AI 서비스입니다. | This AI service is not supported. |
| `UPSCALE_METHOD_UNKNOWN` | general | error | 알 수 없는 확대 방식입니다. | That enlargement method is not known. |
| `VALIDATION_ERROR` | general | error | 입력한 값이 올바르지 않습니다. 내용을 확인해 주세요. | Some of the values are not valid. Please check them. |
| `VIDEO_ASPECT_INVALID` | video | error | 영상 비율은 9:16, 4:5, 16:9 중에서 고를 수 있습니다. | The video aspect must be 9:16, 4:5 or 16:9. |
| `VIDEO_COMMENT_INVALID` | video | error | 영상 파일에 넣을 설명 글이 비었거나 너무 길거나 여러 줄입니다. | The text to put inside the video file is empty, too long or more than one line. |
| `VIDEO_DAILY_LIMIT` | video | limit | 오늘 만들 수 있는 영상 수를 모두 썼습니다. | Today's video limit has been used up. |
| `VIDEO_DURATION_INVALID` | video | error | 영상 길이는 5초, 10초, 15초 중에서 고를 수 있습니다. | The video length must be 5, 10 or 15 seconds. |
| `VIDEO_FRAME_SIZE` | video | error | 프레임 크기가 영상 크기와 다릅니다. | A frame does not have the size of the video. |
| `VIDEO_INPUT_COUNT` | video | error | 그림은 1장부터 8장까지 넣을 수 있습니다. | Use between 1 and 8 pictures. |
| `VIDEO_INPUT_DUPLICATE` | video | error | 같은 그림을 두 번 넣을 수 없습니다. | Each picture can be used once. |
| `VIDEO_INPUT_GONE` | video | limit | 선택한 그림이 더는 없습니다. | A selected picture no longer exists. |
| `VIDEO_INPUT_KIND` | video | error | 영상에는 그림 항목만 쓸 수 있습니다. | Only picture items can be used for a video. |
| `VIDEO_INPUT_NOT_FOUND` | video | error | 선택한 그림을 찾을 수 없습니다. | A selected picture was not found. |
| `VIDEO_MOTION_INVALID` | video | error | 움직임은 줌, 팬, 회전 중에서 고를 수 있습니다. | The motion must be zoom, pan or rotate. |
| `VIDEO_NOT_CANCELLABLE` | video | error | 이미 끝난 영상 작업이라 취소할 것이 없습니다. | The video job has already finished, so there is nothing to cancel. |
| `VIDEO_POSTER_NOT_AVAILABLE` | video | error | 이 작업에는 표지를 뽑을 MP4 영상이 없습니다. | This job has no MP4 video to take a cover from. |
| `VIDEO_POSTER_POSITION` | video | error | 표지 그림을 뽑을 위치는 0부터 1 사이 숫자여야 합니다. | The position of the cover picture must be a number from 0 to 1. |
| `VIDEO_PROVIDER_NOT_CONNECTED` | video | error | 외부 AI 서비스로 영상을 만드는 기능은 아직 연결되지 않았습니다. | Video generation by an external AI service is not connected yet. |
| `VIDEO_RETRY_NOT_FAILED` | video | error | 실패한 영상만 다시 시도할 수 있습니다. | Only a failed video can be retried. |
| `VIDEO_SIZE_INVALID` | video | error | 영상의 가로·세로는 짝수여야 합니다. | The video width and height must be even numbers. |
| `VIDEO_TRANSITION_INVALID` | video | error | 장면 전환은 컷 또는 크로스페이드만 쓸 수 있습니다. | The transition must be cut or crossfade. |
| `VIDEO_TURNTABLE_INVALID` | video | error | 회전 영상에는 크기가 같은 회전 그림 8~360장과 1~3바퀴 설정이 필요합니다. | A rotation video needs 8 to 360 rotation pictures of one size and 1 to 3 turns. |
| `WINDOW_TOO_DEEP` | general | limit | 너무 뒤쪽까지 요청했습니다. 기간을 좁혀 주세요. | That reaches too far back. Narrow the time range. |
| `WORKSPACE_MONTHLY_LIMIT` | general | limit | 이번 달 작업공간의 작업 한도를 모두 썼습니다. | This workspace has used its job limit for the month. |
| `WORK_ASSET_INVALID` | work | error | 연결한 파일은 이 작업공간의 파일이어야 합니다. | Linked files must belong to this workspace. |
| `WORK_ITEMS_FULL` | work | limit | 작업 항목을 더 만들 수 없습니다. | No more work items can be created. |
| `WORK_ITEM_ARCHIVED` | work | error | 보관된 항목입니다. 복원한 뒤 바꿀 수 있습니다. | This item is archived. Restore it before changing it. |
| `WORK_ITEM_CHANGED` | work | error | 다른 사람이 먼저 바꿨습니다. 새로고침해 주세요. | Someone else changed this item. Please reload. |
| `WORK_KIND_INVALID` | work | error | 종류 값이 올바르지 않습니다. | The kind is not valid. |
| `WORK_NOTHING_TO_CHANGE` | work | error | 바꿀 내용이 없습니다. | There is nothing to change. |
| `WORK_STATUS_INVALID` | work | error | 상태 값이 올바르지 않습니다. | The status is not valid. |
| `WORK_TITLE_INVALID` | work | error | 제목은 1~120자여야 합니다. | The title must be 1 to 120 characters. |

## HTTP 상태별 기본 문구

| 상태 | 한국어 | English |
|---|---|---|
| 400 | 요청을 처리할 수 없습니다. | The request could not be processed. |
| 401 | 로그인이 필요합니다. | Please sign in. |
| 403 | 이 작업을 할 권한이 없습니다. | You do not have permission to do this. |
| 404 | 찾을 수 없습니다. | Not found. |
| 409 | 지금 상태에서는 할 수 없습니다. | That is not possible in the current state. |
| 410 | 더는 사용할 수 없습니다. | This is no longer available. |
| 413 | 파일이 너무 큽니다. | The file is too large. |
| 415 | 지원하지 않는 형식입니다. | This format is not supported. |
| 422 | 입력한 값이 올바르지 않습니다. | Some of the values are not valid. |
| 429 | 요청이 너무 잦거나 한도에 도달했습니다. 잠시 뒤 다시 시도해 주세요. | Too many requests or a limit was reached. Please try again shortly. |
| 500 | 서버에 문제가 생겼습니다. 잠시 뒤 다시 시도해 주세요. | Something went wrong on our side. Please try again shortly. |
| 503 | 서비스를 지금 사용할 수 없습니다. 잠시 뒤 다시 시도해 주세요. | The service is not available right now. Please try again shortly. |
