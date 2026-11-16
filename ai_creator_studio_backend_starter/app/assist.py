"""R-048: server side of "말로 요청하기": ``POST /v1/assist/interpret`` turns a sentence into screen actions (reply 27 contract).

In:  {workspace_id, text, page, controls: [visible control NAMES]}   Out: {actions: [{action, target, value?, confirm?}], interpreter, understood}
Privacy: ONLY the sentence, the page key and the control names are used. Never images, ids of people or workspace data. The sentence itself is not
stored (the usage log keeps lengths and counts only).
Safety: a returned ``target`` is always one of the control names that was sent (the server cannot invent a button), values are short, and anything that
costs money or cannot be undone (create, export, reset, delete, buy ...) is forced to ``confirm: true`` no matter who produced the action.
Interpreters: the RULE interpreter below (local, no external call, no cost) and an optional LLM adapter slot (``ASSIST_INTERPRETER_MODE=llm``). No LLM
adapter is connected, so that mode falls back to the rules and says so (``fallback: true``); a connected adapter would be an external transfer and goes
through the external-transfer notice, a per-workspace daily limit and the kill switch.
"""
from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Protocol

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import config
from app.assets import store
from app.assets.routes import current_user, require_role

router = APIRouter(prefix="/v1/assist", tags=["assist"])
MAX_TEXT, MAX_CONTROLS, MAX_NAME, MAX_VALUE, MAX_ACTIONS = 500, 200, 60, 120, 5
ACTIONS = ("click", "set", "fill", "nav")
RISKY = re.compile(r"(생성|만들|내보내|초기화|삭제|지우|지워|결제|구매|발행|제출|publish|export|delete|reset|buy|create)", re.I)
PROMPT_FIELD = re.compile(r"(지시|프롬프트|요청|설명|prompt|instruction)", re.I)
POLITE = re.compile(r"(해\s*주세요|해\s*줘요?|해\s*라|해\s*요|해\s*봐|주세요|줘요?|부탁(해요?|드려요?|합니다)?|할래|하자|좀|더|한번|제발)")
SPLIT = re.compile(r"\s*(?:,|，|\.|;|그리고|하고|한 뒤|한뒤|다음에|및|랑|이랑)\s*")
SUFFIX = re.compile(r"(으로|로|을|를|이|가|은|는|에|도|만)$")
VERBISH = re.compile(r"(여|어|아|해|하|려|라|봐|요|다|세요|줘|꿔|워|켜|와)$")   # "줄여", "열어", "만들어": the action word, never the value


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s.lower())


def _bigrams(s: str) -> set[str]:
    s = _squash(s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _coverage(clause: str, name: str) -> float:
    """How much of the control's name is found in the clause (0..1). One-character names must appear as a whole word."""
    n = _squash(name)
    if not n:
        return 0.0
    if len(n) == 1:
        return 1.0 if re.search(rf"(?<![\w가-힣]){re.escape(n)}(?![\w가-힣])", clause.lower()) else 0.0
    if n in _squash(clause):
        return 1.0
    b = _bigrams(n)
    return len(b & _bigrams(clause)) / len(b) if b else 0.0


def _clean_value(tokens: list[str], name: str) -> str:
    """What is left of the clause after the control's name and the polite endings: the value for a 'set'."""
    rest = []
    name_sq = _squash(name)
    for t in tokens:
        t2 = SUFFIX.sub("", POLITE.sub("", t)).strip()
        if not t2 or _squash(t2) in name_sq or name_sq in _squash(t2) or VERBISH.search(t2):
            continue
        rest.append(t2)
    return " ".join(rest)[:MAX_VALUE]


def interpret_rules(text: str, controls: list[str]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    names = [c for c in dict.fromkeys(controls) if c.strip()]
    for clause in [c for c in SPLIT.split(text) if c.strip()]:
        scored = sorted(((_coverage(clause, n), len(_squash(n)), n) for n in names if n != ""), reverse=True)
        if not scored or scored[0][0] < 0.5:
            continue
        top = [t for t in scored if t[0] == scored[0][0]]
        name = max(top, key=lambda t: t[1])[2]       # equal coverage: the longer (more specific) name wins
        if any(a["target"] == name for a in actions):
            continue
        value = _clean_value(clause.split(), name)
        act = {"action": "set", "target": name, "value": value} if value else {"action": "click", "target": name}
        if RISKY.search(clause) or RISKY.search(name):
            act["confirm"] = True
        actions.append(act)
        if len(actions) >= MAX_ACTIONS:
            break
    if not actions:   # not understood: park the sentence in an instruction box if the screen has one (the person confirms it there)
        box = next((n for n in names if PROMPT_FIELD.search(n)), None)
        if box:
            actions.append({"action": "fill", "target": box, "value": text.strip()[:MAX_VALUE * 4]})
    return actions


def sanitize(raw: Any, controls: list[str]) -> list[dict[str, Any]]:
    """Whatever an interpreter returns, only well-formed actions on REAL controls get out, and risky ones always need a confirmation."""
    allowed = set(controls)
    out: list[dict[str, Any]] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or item.get("action") not in ACTIONS or item.get("target") not in allowed:
            continue
        act: dict[str, Any] = {"action": item["action"], "target": item["target"]}
        value = item.get("value")
        if item["action"] in ("set", "fill"):
            if not isinstance(value, str) or not value.strip():
                continue
            act["value"] = value.strip()[:MAX_VALUE * 4 if item["action"] == "fill" else MAX_VALUE]
        elif value is not None:
            continue
        if item.get("confirm") is True or RISKY.search(item["target"]) or RISKY.search(str(act.get("value", ""))):
            act["confirm"] = True
        out.append(act)
        if len(out) >= MAX_ACTIONS:
            break
    return out


class LlmInterpreter(Protocol):
    name: str
    data_policy: dict[str, Any]
    def interpret(self, text: str, page: str, controls: list[str]) -> list[dict[str, Any]]: ...


def get_llm_adapter() -> LlmInterpreter | None:
    """No adapter is connected (NEED_USER: provider, key, cost cap, notice wording). Tests replace this."""
    return None


class InterpretIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]+$")
    text: str = Field(min_length=1, max_length=MAX_TEXT)
    page: str = Field(default="", max_length=40)
    controls: list[str] = Field(default_factory=list, max_length=MAX_CONTROLS)


class ActionOut(BaseModel):
    action: Literal["click", "set", "fill", "nav"]
    target: str
    value: str | None = None
    confirm: bool | None = None


class InterpretOut(BaseModel):
    actions: list[ActionOut]
    interpreter: Literal["rules", "llm"]
    understood: bool
    fallback: bool = False


_recent: dict[str, deque] = defaultdict(deque)


def _rate_limited(user_id: str) -> bool:
    now, window = time.monotonic(), _recent[user_id]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= config.ASSIST_PER_MINUTE:
        return True
    window.append(now)
    return False


def _log(db, workspace_id: str, user_id: str, interpreter: str, understood: bool, n_actions: int, text_len: int) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS assist_usage (workspace_id TEXT NOT NULL, user_id TEXT NOT NULL, interpreter TEXT NOT NULL,
        understood INTEGER NOT NULL, n_actions INTEGER NOT NULL, text_len INTEGER NOT NULL, created_at TEXT NOT NULL)""")
    db.execute("INSERT INTO assist_usage VALUES (?,?,?,?,?,?,?)", (workspace_id, user_id, interpreter, int(understood), n_actions, text_len,
                                                                   datetime.now(timezone.utc).isoformat()))


def _llm_used_today(db, workspace_id: str) -> int:
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    return db.execute("SELECT COUNT(*) AS n FROM assist_usage WHERE workspace_id=? AND interpreter='llm' AND created_at>=?", (workspace_id, since)).fetchone()["n"]


@router.post("/interpret", response_model=InterpretOut, response_model_exclude_none=True, operation_id="assistInterpret")
async def interpret(body: InterpretIn, user_id: str = Depends(current_user)):
    require_role(body.workspace_id, user_id, {"owner", "admin", "editor"})
    if _rate_limited(user_id):
        raise HTTPException(status_code=429, headers={"Retry-After": "30"}, detail={"code": "ASSIST_RATE_LIMITED", "message": "too many requests; try again shortly"})
    controls = [c.strip()[:MAX_NAME] for c in body.controls if isinstance(c, str) and c.strip()]
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail={"code": "ASSIST_TEXT_REQUIRED", "message": "text must not be blank"})
    interpreter, fallback, actions = "rules", False, None
    if config.ASSIST_INTERPRETER_MODE == "llm":
        adapter = get_llm_adapter()
        if adapter is None:
            fallback = True    # not connected: answer with the rules and SAY so
        else:
            from app import cost_cap
            from app.external_notice import acknowledged
            if cost_cap.kill_switch_on():
                raise HTTPException(status_code=429, detail={"code": "AI_JOBS_DISABLED", "message": "external AI features are switched off"})
            if config.EXTERNAL_NOTICE_REQUIRED and not acknowledged(body.workspace_id, user_id, adapter.name):
                raise HTTPException(status_code=409, detail={"code": "EXTERNAL_NOTICE_REQUIRED", "provider": adapter.name, "data_policy": adapter.data_policy,
                                                            "message": "Acknowledge that the sentence and the control names are sent to the external AI service."})
            with store._connect() as db:
                if _llm_used_today(db, body.workspace_id) >= config.ASSIST_LLM_DAILY_LIMIT:
                    raise HTTPException(status_code=429, detail={"code": "ASSIST_LIMIT", "message": "today's limit for AI interpretation is used up",
                                                                "limit": config.ASSIST_LLM_DAILY_LIMIT})
            try:
                actions = sanitize(adapter.interpret(text, body.page, controls), controls)
                interpreter = "llm"
            except Exception:  # noqa: BLE001 - an adapter failure falls back to the rules (the contract: "없거나 오류면 규칙 해석기")
                fallback = True
    if actions is None:
        actions = sanitize(interpret_rules(text, controls), controls)
    understood = bool(actions) and not (len(actions) == 1 and actions[0]["action"] == "fill")
    with store._connect() as db:
        _log(db, body.workspace_id, user_id, interpreter, understood, len(actions), len(text))
    return {"actions": actions, "interpreter": interpreter, "understood": understood, "fallback": fallback}
