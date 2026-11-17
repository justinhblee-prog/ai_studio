"""R-072: the text for every error ``code`` the server sends, in Korean and English: ONE table for the server's answers and the homepage's messages.

Wording is operational and plain. Codes whose wording is a LEGAL statement (deletion, report handling, liability, licence and rights declarations, legal acceptance, external transfer notice)
have NO text on purpose: ``message`` is null and ``needs_decision`` is true until legal decides ("[결정 필요: 법무]"). ``tests/test_error_catalog.py`` fails when a code the server can send
(``scripts/error_codes_scan.py``) has no entry here, so the table cannot fall behind the code.
"""
from __future__ import annotations

# code -> (Korean, English). Placeholders such as {limit} are filled by the client from the response body when it has them; otherwise it shows the text as is.
CODES: dict[str, tuple[str, str]] = {
    # --- request shape and ranges
    "VALIDATION_ERROR": ("입력한 값이 올바르지 않습니다. 내용을 확인해 주세요.", "Some of the values are not valid. Please check them."),
    "INVALID_RANGE": ("기간 형식이 올바르지 않습니다.", "The date range is not valid."),
    "INVALID_MONTH": ("월 형식이 올바르지 않습니다(예: 2026-11).", "The month is not valid (for example 2026-11)."),
    "WINDOW_TOO_DEEP": ("너무 뒤쪽까지 요청했습니다. 기간을 좁혀 주세요.", "That reaches too far back. Narrow the time range."),
    "INTERNAL_ADAPTER_ERROR": ("서비스 내부 오류입니다. 잠시 뒤 다시 시도해 주세요.", "An internal error occurred. Please try again shortly."),
    # --- limits and rates
    "RATE_LIMITED": ("요청이 너무 잦습니다. 잠시 뒤 다시 시도해 주세요.", "Too many requests. Please try again shortly."),
    "ASSIST_RATE_LIMITED": ("도움말 요청이 너무 잦습니다. 잠시 뒤 다시 시도해 주세요.", "Too many assistant requests. Please try again shortly."),
    "ASSIST_LIMIT": ("오늘 쓸 수 있는 AI 해석 횟수를 모두 썼습니다.", "Today's AI interpretation limit has been used up."),
    "DAILY_JOB_LIMIT_EXCEEDED": ("오늘 만들 수 있는 작업 수를 모두 썼습니다.", "Today's job limit for this workspace has been used up."),
    "WORKSPACE_MONTHLY_LIMIT": ("이번 달 작업공간의 작업 한도를 모두 썼습니다.", "This workspace has used its job limit for the month."),
    "GLOBAL_MONTHLY_LIMIT": ("이번 달 서비스 전체 작업 한도에 도달했습니다.", "The service-wide job limit for this month has been reached."),
    "AI_JOBS_DISABLED": ("AI 기능이 일시적으로 꺼져 있습니다.", "AI features are temporarily switched off."),
    "VIDEO_DAILY_LIMIT": ("오늘 만들 수 있는 영상 수를 모두 썼습니다.", "Today's video limit has been used up."),
    "DOWNLOAD_MONTHLY_LIMIT": ("이번 달 내려받기 한도에 도달했습니다.", "The monthly download limit has been reached."),
    "EXPORT_LIMIT": ("내보내기는 하루에 정해진 횟수까지만 할 수 있습니다.", "Exports are limited per day."),
    "EXPORT_TOO_LARGE": ("내보낼 파일이 너무 큽니다. 지원팀에 나눠서 내보내기를 요청해 주세요.", "The files are too large to export at once. Ask support for a split export."),
    "EXPORT_GONE": ("내보내기 파일의 보관 기간이 끝났습니다. 새로 만들어 주세요.", "This export has expired. Please create a new one."),
    "REPORT_DAILY_LIMIT": ("오늘 접수할 수 있는 신고 수를 모두 썼습니다.", "Today's report limit has been used up."),
    "LIBRARY_FULL": ("라이브러리가 가득 찼습니다. 안 쓰는 항목을 정리해 주세요.", "The library is full. Please remove items you no longer need."),
    "LIBRARY_3D_FULL": ("3D 항목을 더 넣을 수 없습니다.", "No more 3D items can be added."),
    "MODEL_DRAFT_LIMIT": ("열려 있는 모델 시안이 너무 많습니다. 하나를 선택하거나 지워 주세요.", "Too many open model drafts. Pick or remove one."),
    "PRESET_LIMIT": ("저장할 수 있는 프리셋 수를 넘었습니다.", "The preset limit has been reached."),
    "WORK_ITEMS_FULL": ("작업 항목을 더 만들 수 없습니다.", "No more work items can be created."),
    # --- uploads and files
    "ASSET_EMPTY": ("파일이 비어 있습니다.", "The file is empty."),
    "ASSET_TOO_LARGE": ("파일이 너무 큽니다.", "The file is too large."),
    "ASSET_FORMAT_UNSUPPORTED": ("지원하지 않는 파일 형식입니다.", "This file format is not supported."),
    "ASSET_MEDIA_TYPE_UNSUPPORTED": ("지원하지 않는 파일 종류입니다.", "This kind of file is not supported."),
    "ASSET_PARSE_FAILED": ("파일을 읽지 못했습니다. 손상되었을 수 있습니다.", "The file could not be read. It may be damaged."),
    "ASSET_SIGNATURE_INVALID": ("파일 내용이 형식과 맞지 않습니다.", "The file content does not match its format."),
    "ASSET_JSON_TOO_LARGE": ("3D 파일의 설명 부분이 너무 큽니다.", "The description part of the 3D file is too large."),
    "ASSET_DATA_URI_TOO_LARGE": ("3D 파일에 포함된 내장 데이터가 너무 큽니다.", "The embedded data in the 3D file is too large."),
    "ASSET_EXTERNAL_URI_BLOCKED": ("3D 파일이 바깥 주소를 참조합니다. 자체 포함 파일만 올릴 수 있습니다.", "The 3D file points to outside addresses. Only self-contained files can be uploaded."),
    "ASSET_VIDEO_INVALID": ("영상 파일이 온전한 MP4가 아닙니다.", "The video file is not a complete MP4."),
    "ASSET_KIND_MISMATCH": ("이 종류의 파일을 여기에 쓸 수 없습니다.", "This kind of file cannot be used here."),
    "ASSET_IN_USE": ("다른 곳에서 쓰고 있어 지울 수 없습니다.", "It is in use elsewhere and cannot be deleted."),
    "ASSET_VERSION_INTEGRITY_FAILED": ("저장된 파일이 손상되었습니다. 지원팀에 문의해 주세요.", "The stored file is damaged. Please contact support."),
    "IMAGE_DECODE_FAILED": ("그림을 열 수 없습니다. 다른 파일로 시도해 주세요.", "The picture could not be opened. Try another file."),
    "IMAGE_UNREADABLE": ("그림을 읽을 수 없습니다.", "The picture cannot be read."),
    "IMAGE_EXTENSION_MISMATCH": ("파일 확장자가 실제 형식과 다릅니다.", "The file extension does not match the real format."),
    "IMAGE_FORMAT_UNSUPPORTED": ("PNG, JPEG, WebP 그림만 올릴 수 있습니다.", "Only PNG, JPEG and WebP pictures can be uploaded."),
    "IMAGE_ANIMATION_UNSUPPORTED": ("움직이는 그림은 올릴 수 없습니다.", "Animated pictures cannot be uploaded."),
    "IMAGE_DIMENSIONS_UNSUPPORTED": ("그림의 가로·세로가 허용 범위를 넘었습니다.", "The picture's width or height is out of range."),
    "UNSUPPORTED_PROVIDER": ("지원하지 않는 AI 서비스입니다.", "This AI service is not supported."),
    # --- library
    "LIBRARY_ALREADY_FILED": ("이미 라이브러리에 있는 항목입니다.", "This is already in the library."),
    "LIBRARY_KIND_MISMATCH": ("이 종류에는 맞지 않는 파일입니다. 3D는 모델 파일, 나머지는 그림이어야 합니다.", "That file does not fit this kind. 3D needs a model file, everything else a picture."),
    "LIBRARY_NAME_REQUIRED": ("이름을 입력해 주세요.", "Please enter a name."),
    "LIBRARY_NOTHING_TO_CHANGE": ("바꿀 내용이 없습니다.", "There is nothing to change."),
    "LIBRARY_TAG_TOO_LONG": ("태그가 너무 깁니다.", "A tag is too long."),
    "LIBRARY_TAGS_INVALID": ("태그 형식이 올바르지 않습니다.", "The tags are not valid."),
    "LIBRARY_INFO_KIND": ("3D 항목에만 있는 정보입니다.", "This information exists for 3D items only."),
    "LIBRARY_THUMBNAIL_KIND": ("이 항목에는 미리보기 그림을 올릴 수 없습니다.", "A preview picture cannot be set for this item."),
    "LIBRARY_NOT_FOUND": ("라이브러리 항목을 찾을 수 없습니다.", "The library item was not found."),
    "LIBRARY_ID_INVALID": ("항목 번호가 올바르지 않습니다.", "The item id is not valid."),
    "LIBRARY_FIELD_REQUIRED": ("필수 항목이 비어 있습니다.", "A required field is empty."),
    "LIBRARY_FIELD_TOO_LONG": ("입력한 글이 너무 깁니다.", "The text is too long."),
    "LIBRARY_ATTRIBUTE_INVALID": ("속성 값이 올바르지 않습니다.", "An attribute value is not valid."),
    "LIBRARY_ATTRIBUTE_MISSING": ("필요한 속성이 빠졌습니다.", "A required attribute is missing."),
    "LIBRARY_ATTRIBUTE_NOT_ALLOWED": ("이 종류에서는 쓸 수 없는 속성입니다.", "This attribute is not allowed for this kind."),
    "LIBRARY_CATEGORY_INVALID": ("분류가 올바르지 않습니다.", "The category is not valid."),
    "LIBRARY_STATUS_INVALID": ("상태 값이 올바르지 않습니다.", "The status is not valid."),
    "LIBRARY_SOURCE_INVALID": ("출처 정보가 올바르지 않습니다.", "The source information is not valid."),
    "LIBRARY_FILE_CORRUPT": ("항목의 파일이 손상되었습니다.", "The item's file is damaged."),
    "LIBRARY_FILE_UNAVAILABLE": ("항목의 파일을 지금 사용할 수 없습니다.", "The item's file is not available right now."),
    "LIBRARY_PREVIEW_EXPIRED": ("미리보기 주소가 만료되었습니다. 새로 받아 주세요.", "The preview address has expired. Please get a new one."),
    "LIBRARY_SIGNING_NOT_CONFIGURED": ("미리보기를 만들 수 없는 설정입니다. 지원팀에 문의해 주세요.", "Previews are not set up. Please contact support."),
    "MODEL_UNREADABLE": ("3D 모델 파일을 읽을 수 없습니다.", "The 3D model file cannot be read."),
    "ATTRS_INVALID": ("속성은 이름과 값의 묶음이어야 합니다.", "Attributes must be a set of names and values."),
    "ATTRS_TOO_MANY": ("속성이 너무 많습니다.", "Too many attributes."),
    "ATTR_KEY_INVALID": ("속성 이름은 소문자·숫자·밑줄만 쓸 수 있습니다.", "Attribute names may use lowercase letters, digits and underscores only."),
    "ATTR_VALUE_INVALID": ("속성 값은 짧은 글이나 작은 정수여야 합니다.", "Attribute values must be short text or a small whole number."),
    "ATTR_FILTER_INVALID": ("필터는 '이름:값' 모양이어야 합니다.", "A filter must look like name:value."),
    # --- jobs, results and try-on inputs
    "JOB_NOT_FINISHED": ("작업이 아직 끝나지 않았습니다.", "The job has not finished yet."),
    "JOB_QC_FAILED": ("결과가 품질 검사를 통과하지 못했습니다.", "The result did not pass the quality check."),
    "OUTPUT_NOT_LINKED": ("결과가 아직 저장되지 않았습니다. 잠시 뒤 다시 시도해 주세요.", "The result is not saved yet. Please try again shortly."),
    "OUTPUT_NOT_APPROVED": ("결과를 승인한 뒤에 사용할 수 있습니다.", "The result can be used after it is approved."),
    "OUTPUT_UNAVAILABLE": ("결과 파일이 더는 없습니다.", "The result file is no longer available."),
    "OUTPUT_SAVE_REQUIRES_REVIEW": ("결과는 검수를 거친 뒤에 저장됩니다.", "Results are saved after review."),
    "SOURCE_ASSET_INVALID": ("원본으로 지정한 파일은 이 작업공간의 파일이어야 합니다.", "Source files must belong to this workspace."),
    "TRYON_INPUT_GONE": ("선택한 사진이 더는 없습니다. 다시 골라 주세요.", "A selected picture no longer exists. Please choose again."),
    "TRYON_INPUT_KIND": ("모델·의류 자리에 맞지 않는 항목입니다.", "That item does not fit the model / garment slot."),
    "TRYON_INPUT_NOT_FOUND": ("선택한 항목을 찾을 수 없습니다.", "The selected item was not found."),
    "TRYON_PUBLIC_URL_MISSING": ("외부 AI 서비스를 쓰기 위한 설정이 아직 없습니다. 지원팀에 문의해 주세요.", "The setup for the external AI service is missing. Please contact support."),
    "EXTERNAL_NOTICE_REQUIRED": None,  # legal wording: filled by legal
    "UNKNOWN_PROVIDER": ("알 수 없는 AI 서비스입니다.", "Unknown AI service."),
    "PROVIDER_RATE_LIMITED": ("AI 서비스가 바빠 잠시 뒤 다시 시도합니다.", "The AI service is busy and will be retried shortly."),
    "PROVIDER_NOT_PRODUCTION_READY": ("이 AI 서비스는 아직 실제로 쓸 수 없습니다.", "This AI service is not ready for real use."),
    "PROVIDER_SUSPENDED": ("이 AI 서비스는 지금 중지되어 있습니다.", "This AI service is currently suspended."),
    "CAPABILITY_NOT_VERIFIED": ("이 기능은 아직 확인되지 않았습니다.", "This capability has not been verified yet."),
    "UNSUPPORTED_CAPABILITY": ("이 AI 서비스가 지원하지 않는 기능입니다.", "This AI service does not support that."),
    "AUTO_ROUTING_NOT_APPROVED": ("자동 선택은 아직 승인되지 않았습니다.", "Automatic selection is not approved yet."),
    "INVALID_ROUTING_MODE": ("선택 방식이 올바르지 않습니다.", "The selection mode is not valid."),
    # --- photo steps, presets, products, lookbook
    "STEPS_REQUIRED": ("처리 단계를 하나 이상 넣어 주세요.", "Add at least one processing step."),
    "STEPS_TOO_MANY": ("처리 단계가 너무 많습니다.", "Too many processing steps."),
    "STEP_UNKNOWN": ("알 수 없는 처리 단계입니다.", "Unknown processing step."),
    "STEP_PARAMETER_INVALID": ("처리 단계의 값이 올바르지 않습니다.", "A step value is not valid."),
    "STEP_PARAMETER_UNKNOWN": ("처리 단계에 없는 설정입니다.", "That setting does not exist for this step."),
    "STEP_COLOR_INVALID": ("색 값이 올바르지 않습니다.", "The colour is not valid."),
    "STEP_NEEDS_TRANSPARENCY": ("이 단계는 배경이 투명한 그림에서만 쓸 수 있습니다.", "This step needs a picture with a transparent background."),
    "PHOTO_IMAGE_ASSET_REQUIRED": ("사진 작업에는 그림 파일이 필요합니다.", "Photo work needs a picture file."),
    "PHOTO_LOCAL_PROCESSING_FAILED": ("사진 처리에 실패했습니다. 다른 사진으로 시도해 주세요.", "Photo processing failed. Try another picture."),
    "PRODUCT_IMAGE_ASSET_REQUIRED": ("상품에는 그림 파일이 필요합니다.", "A product needs a picture file."),
    "LOOKBOOK_IMAGE_ASSET_REQUIRED": ("룩북에는 그림 파일이 필요합니다.", "A lookbook needs picture files."),
    "LOOKBOOK_ENTITY_MISSING_OR_CROSS_WORKSPACE": ("다른 작업공간의 항목이거나 없는 항목입니다.", "That item belongs to another workspace or does not exist."),
    "PRESET_NAME_REQUIRED": ("프리셋 이름을 입력해 주세요.", "Please enter a preset name."),
    "PRESET_NAME_TAKEN": ("같은 이름의 프리셋이 이미 있습니다.", "A preset with this name already exists."),
    # --- models (characters) and design values
    "DESIGN_REQUIRED": ("속성을 하나 이상 지정해 주세요.", "Give at least one design value."),
    "DESIGN_TOO_MANY": ("속성이 너무 많습니다.", "Too many design values."),
    "DESIGN_KEY_INVALID": ("속성 이름이 올바르지 않습니다.", "A design value name is not valid."),
    "DESIGN_VALUE_INVALID": ("속성 값은 짧은 글이나 0~9999의 정수여야 합니다.", "Design values must be short text or a whole number from 0 to 9999."),
    "REFERENCE_INVALID": ("참조 사진이 올바르지 않습니다.", "A reference picture is not valid."),
    "REFERENCE_DUPLICATE": ("같은 참조 사진이 중복되었습니다.", "A reference picture is listed twice."),
    "MODEL_DRAFT_ALREADY_CHOSEN": ("이 시안은 이미 선택되었습니다.", "A candidate was already chosen for this draft."),
    "MODEL_REAL_PERSON_BLOCKED": ("실존 인물을 닮게 만드는 요청은 받을 수 없습니다. 표현을 바꿔 다시 적어 주세요.", "Requests to look like a real person are not accepted. Please rephrase."),
    "MEMBER_OWNER_PROTECTED": ("소유자의 역할은 여기서 바꾸거나 없앨 수 없습니다.", "The owner's role cannot be changed or removed here."),
    "MEMBER_ROLE_FORBIDDEN": ("이 멤버에 대해서는 그 작업을 할 수 없습니다. 관리자 지정·해제는 소유자만 할 수 있습니다.", "You cannot do that for this member. Only the owner can make or unmake an admin."),
    "THREED_PROVIDER_NOT_CONNECTED": ("외부 AI 서비스로 3D를 만드는 기능은 아직 연결되지 않았습니다.", "Making 3D models with an external AI service is not connected yet."),
    "THREED_INPUT_NOT_FOUND": ("선택한 그림 항목을 찾을 수 없습니다.", "The selected picture item was not found."),
    "THREED_INPUT_KIND": ("3D로 바꿀 수 있는 것은 그림 항목뿐입니다(너무 큰 그림도 안 됩니다).", "Only picture items can be turned into 3D (and not very large ones)."),
    "THREED_INPUT_GONE": ("선택한 그림의 파일이 더는 없습니다.", "The selected picture's file no longer exists."),
    "THREED_DAILY_LIMIT": ("오늘 만들 수 있는 3D 작업 수를 모두 썼습니다.", "Today's 3D job limit has been used up."),
    "GLB_INVALID": ("만들어진 3D 파일이 검사를 통과하지 못했습니다.", "The generated 3D file did not pass the check."),
    "MODEL_NAME_REQUIRED": ("모델 이름을 입력해 주세요.", "Please enter a model name."),
    "MODEL_PROVIDER_NOT_CONNECTED": ("외부 AI 서비스로 모델을 만드는 기능은 아직 연결되지 않았습니다.", "Model generation by an external AI service is not connected yet."),
    "VIDEO_PROVIDER_NOT_CONNECTED": ("외부 AI 서비스로 영상을 만드는 기능은 아직 연결되지 않았습니다.", "Video generation by an external AI service is not connected yet."),
    "VIDEO_NOT_CANCELLABLE": ("이미 끝난 영상 작업이라 취소할 것이 없습니다.", "The video job has already finished, so there is nothing to cancel."),
    "VIDEO_RETRY_NOT_FAILED": ("실패한 영상만 다시 시도할 수 있습니다.", "Only a failed video can be retried."),
    "VIDEO_INPUT_DUPLICATE": ("같은 그림을 두 번 넣을 수 없습니다.", "Each picture can be used once."),
    "VIDEO_INPUT_GONE": ("선택한 그림이 더는 없습니다.", "A selected picture no longer exists."),
    "VIDEO_INPUT_KIND": ("영상에는 그림 항목만 쓸 수 있습니다.", "Only picture items can be used for a video."),
    "VIDEO_INPUT_NOT_FOUND": ("선택한 그림을 찾을 수 없습니다.", "A selected picture was not found."),
    # Lane 4 / E-08a: real MP4 output (app/video_mp4.py)
    "FFMPEG_MISSING": ("이 서버에 영상 변환 도구가 설치되어 있지 않아 MP4를 만들 수 없습니다.", "The video encoder is not installed on this server, so MP4 output is not available."),
    "FFMPEG_FAILED": ("영상 파일을 만드는 중 오류가 났습니다. 잠시 뒤 다시 시도해 주세요.", "The video file could not be encoded. Please try again shortly."),
    "MP4_INVALID": ("영상 파일이 온전하지 않습니다.", "The video file is not a complete MP4."),
    "VIDEO_ASPECT_INVALID": ("영상 비율은 9:16, 4:5, 16:9 중에서 고를 수 있습니다.", "The video aspect must be 9:16, 4:5 or 16:9."),
    "VIDEO_DURATION_INVALID": ("영상 길이는 5초, 10초, 15초 중에서 고를 수 있습니다.", "The video length must be 5, 10 or 15 seconds."),
    "VIDEO_MOTION_INVALID": ("움직임은 줌, 팬, 회전 중에서 고를 수 있습니다.", "The motion must be zoom, pan or rotate."),
    "VIDEO_TRANSITION_INVALID": ("장면 전환은 컷 또는 크로스페이드만 쓸 수 있습니다.", "The transition must be cut or crossfade."),
    "VIDEO_INPUT_COUNT": ("그림은 1장부터 8장까지 넣을 수 있습니다.", "Use between 1 and 8 pictures."),
    "VIDEO_SIZE_INVALID": ("영상의 가로·세로는 짝수여야 합니다.", "The video width and height must be even numbers."),
    "VIDEO_FRAME_SIZE": ("프레임 크기가 영상 크기와 다릅니다.", "A frame does not have the size of the video."),
    "VIDEO_POSTER_POSITION": ("표지 그림을 뽑을 위치는 0부터 1 사이 숫자여야 합니다.", "The position of the cover picture must be a number from 0 to 1."),
    "VIDEO_TURNTABLE_INVALID": ("회전 영상에는 크기가 같은 회전 그림 8~360장과 1~3바퀴 설정이 필요합니다.", "A rotation video needs 8 to 360 rotation pictures of one size and 1 to 3 turns."),
    "VIDEO_COMMENT_INVALID": ("영상 파일에 넣을 설명 글이 비었거나 너무 길거나 여러 줄입니다.", "The text to put inside the video file is empty, too long or more than one line."),
    "ASSIST_TEXT_REQUIRED": ("요청할 내용을 글로 적어 주세요.", "Please type what you need."),
    # --- reviews
    "REVIEW_ALREADY_OPEN": ("이 파일은 이미 검수 중입니다.", "This file is already under review."),
    "REVIEW_CHANGED": ("다른 사람이 먼저 처리했습니다. 새로고침해 주세요.", "Someone else already handled this. Please reload."),
    "REVIEW_COMMENT_REQUIRED": ("의견을 적어 주세요.", "Please write a comment."),
    "REVIEW_NOT_APPROVED": ("검수에서 승인된 파일만 내보낼 수 있습니다.", "Only approved files can be exported."),
    "REVIEW_SELF_APPROVAL_FORBIDDEN": ("직접 요청한 검수는 직접 승인할 수 없습니다.", "You cannot approve a review you requested yourself."),
    "REVIEW_TRANSITION_INVALID": ("지금 상태에서는 할 수 없는 동작입니다.", "That action is not possible in the current state."),
    "SETTINGS_NOTHING_TO_CHANGE": ("바꿀 설정을 켬 또는 끔으로 보내 주세요.", "Send at least one setting as on or off."),
    # --- work items
    "WORK_ASSET_INVALID": ("연결한 파일은 이 작업공간의 파일이어야 합니다.", "Linked files must belong to this workspace."),
    "WORK_ITEM_ARCHIVED": ("보관된 항목입니다. 복원한 뒤 바꿀 수 있습니다.", "This item is archived. Restore it before changing it."),
    "WORK_ITEM_CHANGED": ("다른 사람이 먼저 바꿨습니다. 새로고침해 주세요.", "Someone else changed this item. Please reload."),
    "WORK_KIND_INVALID": ("종류 값이 올바르지 않습니다.", "The kind is not valid."),
    "WORK_NOTHING_TO_CHANGE": ("바꿀 내용이 없습니다.", "There is nothing to change."),
    "WORK_STATUS_INVALID": ("상태 값이 올바르지 않습니다.", "The status is not valid."),
    "WORK_TITLE_INVALID": ("제목은 1~120자여야 합니다.", "The title must be 1 to 120 characters."),
    # --- market (pricing unit and licence wording are decisions: see below)
    "MARKET_AI_FLAG_REQUIRED": ("AI로 만든 것인지 예/아니오로 표시해 주세요.", "Please say whether this was made with AI (yes or no)."),
    "MARKET_CHANGED": ("다른 사람이 먼저 바꿨습니다. 새로고침해 주세요.", "Someone else changed this listing. Please reload."),
    "MARKET_COVER_INVALID": ("표지는 이 작업공간의 그림이어야 합니다.", "The cover must be a picture of this workspace."),
    "MARKET_KIND_INVALID": ("종류 값이 올바르지 않습니다.", "The kind is not valid."),
    "MARKET_NOTHING_TO_CHANGE": ("바꿀 내용이 없습니다.", "There is nothing to change."),
    "MARKET_PAYLOAD_INVALID": ("내용 데이터 형식이 올바르지 않습니다.", "The content data is not valid."),
    "MARKET_PAYLOAD_TOO_LARGE": ("내용 데이터가 너무 큽니다.", "The content data is too large."),
    "MARKET_PRICE_INVALID": ("가격은 0 이상의 정수여야 합니다.", "The price must be a whole number, 0 or more."),
    "MARKET_PROFILE_INVALID": ("이름과 소개에는 링크·이메일·태그를 넣을 수 없습니다.", "The name and introduction cannot contain links, e-mail addresses or markup."),
    "MARKET_TAG_INVALID": ("태그 형식이 올바르지 않습니다.", "A tag is not valid."),
    "MARKET_TEXT_REQUIRED": ("필수 항목이 비어 있습니다.", "A required field is empty."),
    "MARKET_TEXT_TOO_LONG": ("입력한 글이 너무 깁니다.", "The text is too long."),
    # --- customers (operator)
    "ACQ_DATE_INVALID": ("날짜 형식이 올바르지 않습니다.", "The date is not valid."),
    "ACQ_HOST_INVALID": ("주소는 도메인 이름만 쓸 수 있습니다.", "Only a plain domain name is allowed."),
    "ACQ_LANDING_INVALID": ("경로는 /로 시작하는 단순한 경로여야 합니다.", "The path must be a plain path starting with /."),
    "ACQ_TOKEN_INVALID": ("값에는 글자·숫자와 . _ ~ + - 만 쓸 수 있습니다.", "Values may use letters, digits and . _ ~ + - only."),
    "SURVEY_SIZE_INVALID": ("규모는 짧은 코드(예: 1-5, 50+)여야 합니다.", "The size must be a short code such as 1-5 or 50+."),
    "SURVEY_TOKEN_INVALID": ("값에는 글자·숫자와 . _ ~ + - 만 쓸 수 있습니다.", "Values may use letters, digits and . _ ~ + - only."),
    "COLLECTION_DISABLED": ("이 정보는 지금 수집하지 않습니다.", "This information is not being collected right now."),
    "CONTRACT_DATE_INVALID": ("날짜는 YYYY-MM-DD 형식이어야 합니다.", "Dates must look like YYYY-MM-DD."),
    "CONTRACT_PLAN_INVALID": ("요금제 값이 올바르지 않습니다.", "The plan value is not valid."),
    "CONTRACT_REASON_INVALID": ("사유 값이 올바르지 않습니다.", "The reason value is not valid."),
    # --- legal wording: NO text until legal decides
    "LEGAL_ACCEPTANCE_REQUIRED": None,
    "TAKEDOWN_ACTIVE": None,
    "ASSET_UNDER_REVIEW": None,
    "LIBRARY_RIGHTS_NOT_CONFIRMED": None,
    "RIGHTS_CONFIRMATION_REQUIRED": None,
    "MARKET_RIGHTS_REQUIRED": None,
    "MARKET_LICENSE_REQUIRED": None,
}
# Codes the source scan cannot see (passed through helper functions or constants) but the server does send.
EXTRA_CODES = ("ACQ_TOKEN_INVALID", "SURVEY_TOKEN_INVALID", "RIGHTS_CONFIRMATION_REQUIRED", "OUTPUT_SAVE_REQUIRES_REVIEW", "PROVIDER_RATE_LIMITED")
NEEDS_DECISION = tuple(code for code, text in CODES.items() if text is None)
AREAS = (("LIBRARY_", "library"), ("MARKET_", "market"), ("WORK_", "work"), ("REVIEW_", "review"), ("SETTINGS_", "review"), ("VIDEO_", "video"), ("MODEL_", "model"), ("DESIGN_", "model"),
         ("REFERENCE_", "model"), ("PHOTO_", "photo"), ("STEP", "photo"), ("PRESET_", "photo"), ("PRODUCT_", "product"), ("LOOKBOOK_", "lookbook"), ("TRYON_", "tryon"), ("OUTPUT_", "tryon"),
         ("JOB_", "tryon"), ("PROVIDER_", "provider"), ("UNKNOWN_PROVIDER", "provider"), ("UNSUPPORTED_", "provider"), ("CAPABILITY_", "provider"), ("AUTO_ROUTING", "provider"),
         ("INVALID_ROUTING", "provider"), ("ASSET_", "file"), ("IMAGE_", "file"), ("EXPORT_", "export"), ("ASSIST_", "assist"), ("ACQ_", "customers"), ("SURVEY_", "customers"),
         ("CONTRACT_", "customers"), ("COLLECTION_", "customers"), ("ATTR", "attributes"), ("SOURCE_", "tryon"), ("LEGAL_", "legal"), ("TAKEDOWN_", "legal"), ("RIGHTS_", "legal"),
         ("EXTERNAL_", "legal"))
LIMIT_CODES = {c for c in CODES if c.endswith(("_LIMIT", "_LIMITED", "_EXCEEDED", "_FULL", "_GONE")) or c in ("AI_JOBS_DISABLED", "WINDOW_TOO_DEEP", "EXPORT_TOO_LARGE")}
HTTP = {  # fallback text by HTTP status for answers that carry no code
    "400": ("요청을 처리할 수 없습니다.", "The request could not be processed."),
    "401": ("로그인이 필요합니다.", "Please sign in."),
    "403": ("이 작업을 할 권한이 없습니다.", "You do not have permission to do this."),
    "404": ("찾을 수 없습니다.", "Not found."),
    "409": ("지금 상태에서는 할 수 없습니다.", "That is not possible in the current state."),
    "410": ("더는 사용할 수 없습니다.", "This is no longer available."),
    "413": ("파일이 너무 큽니다.", "The file is too large."),
    "415": ("지원하지 않는 형식입니다.", "This format is not supported."),
    "422": ("입력한 값이 올바르지 않습니다.", "Some of the values are not valid."),
    "429": ("요청이 너무 잦거나 한도에 도달했습니다. 잠시 뒤 다시 시도해 주세요.", "Too many requests or a limit was reached. Please try again shortly."),
    "500": ("서버에 문제가 생겼습니다. 잠시 뒤 다시 시도해 주세요.", "Something went wrong on our side. Please try again shortly."),
    "503": ("서비스를 지금 사용할 수 없습니다. 잠시 뒤 다시 시도해 주세요.", "The service is not available right now. Please try again shortly."),
}
VERSION = "2026-11-17.1"


def area_of(code: str) -> str:
    for prefix, area in AREAS:
        if code.startswith(prefix):
            return area
    return "general"


def entry(code: str, lang: str) -> dict:
    text = CODES[code]
    return {"message": None if text is None else text[0 if lang == "ko" else 1], "needs_decision": text is None, "area": area_of(code), "kind": "limit" if code in LIMIT_CODES else "error"}


def catalog(lang: str) -> dict:
    """The whole table in one language (codes sorted)."""
    return {"lang": lang, "version": VERSION, "codes": {c: entry(c, lang) for c in sorted(CODES)},
            "http": {status: text[0 if lang == "ko" else 1] for status, text in HTTP.items()},
            "note": ("법무성 문구(삭제·신고 처리·책임·권리·이용 허락·외부 전송 고지)는 법무 결정 전이라 비어 있습니다(needs_decision=true)." if lang == "ko"
                     else "Legal wording (deletion, report handling, liability, rights, licences, external transfer notice) is empty until legal decides (needs_decision=true).")}
