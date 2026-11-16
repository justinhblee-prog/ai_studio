"""R-048: the "ask in words" interpreter endpoint: rules, safety of the output, limits, privacy, the (unconnected) LLM slot."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import assist, config
from app.main import app
from tests.test_photo_steps_api import auth, env  # noqa: F401  (wa: owner a + viewer c, wb: owner b)

client = TestClient(app)
CONTROLS = ["밝게", "허리 줄이기", "피부톤", "L 사이즈", "가상 피팅", "만들기", "내보내기", "지시 입력", "M 사이즈"]


@pytest.fixture(autouse=True)
def fresh_rate_window():
    assist._recent.clear()
    yield
    assist._recent.clear()


def ask(text, controls=None, who="a", ws="wa", page="studio"):
    return client.post("/v1/assist/interpret", headers=auth(who), json={"workspace_id": ws, "text": text, "page": page, "controls": CONTROLS if controls is None else controls})


@pytest.mark.parametrize("text, expected", [
    ("밝게 해줘", [{"action": "click", "target": "밝게"}]),
    ("허리 줄여줘", [{"action": "click", "target": "허리 줄이기"}]),
    ("피부톤 베이지", [{"action": "set", "target": "피부톤", "value": "베이지"}]),
    ("피부톤을 베이지로 해줘", [{"action": "set", "target": "피부톤", "value": "베이지"}]),
    ("L 사이즈로", [{"action": "click", "target": "L 사이즈"}]),
    ("가상 피팅 열어줘", [{"action": "click", "target": "가상 피팅"}]),
    ("밝게 하고 허리 줄여줘", [{"action": "click", "target": "밝게"}, {"action": "click", "target": "허리 줄이기"}]),
])
def test_the_rule_interpreter_understands_the_examples_of_the_design(env, text, expected):
    body = ask(text).json()
    assert body["actions"] == expected and body["understood"] is True and body["interpreter"] == "rules" and body["fallback"] is False


def test_anything_that_costs_money_or_cannot_be_undone_needs_a_confirmation(env):
    for text, target in (("만들어줘", "만들기"), ("내보내기 해줘", "내보내기")):
        actions = ask(text).json()["actions"]
        assert actions == [{"action": "click", "target": target, "confirm": True}], text
    assert ask("밝게 해줘").json()["actions"][0].get("confirm") is None


def test_a_sentence_it_cannot_follow_is_parked_in_the_instruction_box_when_there_is_one(env):
    body = ask("봄 느낌으로 전체적으로 어울리게").json()
    assert body["actions"] == [{"action": "fill", "target": "지시 입력", "value": "봄 느낌으로 전체적으로 어울리게"}] and body["understood"] is False
    none = ask("봄 느낌으로 전체적으로 어울리게", controls=["밝게", "내보내기"]).json()
    assert none["actions"] == [] and none["understood"] is False


def test_targets_are_always_real_control_names_and_the_count_is_bounded(env):
    for text in ("밝게 해줘", "없는버튼 눌러줘", "밝게 허리 줄이기 피부톤 베이지 L 사이즈 가상 피팅 만들기 내보내기"):
        for a in ask(text).json()["actions"]:
            assert a["target"] in CONTROLS
    many = ["항목%d" % i for i in range(30)]
    text = " 그리고 ".join(many)
    assert len(ask(text, controls=many).json()["actions"]) <= 5


def test_sanitize_drops_invented_targets_bad_shapes_and_forces_confirmation():
    raw = [{"action": "click", "target": "없는 버튼"}, {"action": "delete", "target": "밝게"}, "string", {"action": "set", "target": "피부톤"},
           {"action": "set", "target": "피부톤", "value": "  베이지  "}, {"action": "click", "target": "밝게", "value": "x"},
           {"action": "click", "target": "만들기"}, {"action": "fill", "target": "지시 입력", "value": "x" * 1000}, {"action": "nav", "target": "가상 피팅", "confirm": True}]
    out = assist.sanitize(raw, CONTROLS)
    assert {"action": "set", "target": "피부톤", "value": "베이지"} in out
    assert {"action": "click", "target": "만들기", "confirm": True} in out, "risky even if the interpreter forgot to say so"
    assert {"action": "nav", "target": "가상 피팅", "confirm": True} in out
    assert all(a["target"] in CONTROLS for a in out) and len(out) <= 5
    assert next(a for a in out if a["action"] == "fill")["value"] and len(next(a for a in out if a["action"] == "fill")["value"]) <= 480
    assert assist.sanitize("not a list", CONTROLS) == []


@pytest.mark.parametrize("body", [
    {"workspace_id": "wa", "text": "", "controls": []}, {"workspace_id": "wa", "text": "x" * 501, "controls": []},
    {"workspace_id": "wa", "text": "x", "controls": ["c"] * 201}, {"workspace_id": "wa", "text": "x", "extra": 1},
    {"workspace_id": "wa", "text": "   ", "controls": []}, {"text": "x"},
])
def test_bad_requests_are_refused(env, body):
    assert client.post("/v1/assist/interpret", headers=auth("a"), json=body).status_code == 422


def test_roles_and_membership(env):
    assert client.post("/v1/assist/interpret", json={"workspace_id": "wa", "text": "x"}).status_code == 401
    assert ask("밝게 해줘", who="c").status_code == 403, "a viewer cannot work, so cannot ask"
    assert ask("밝게 해줘", who="b").status_code in (403, 404), "not a member"
    assert ask("밝게 해줘", ws="wb", who="a").status_code in (403, 404)


def test_the_per_minute_limit_answers_429_with_retry_after(env, monkeypatch):
    monkeypatch.setattr(config, "ASSIST_PER_MINUTE", 3)
    assert [ask("밝게 해줘").status_code for _ in range(3)] == [200, 200, 200]
    r = ask("밝게 해줘")
    assert r.status_code == 429 and r.json()["detail"]["code"] == "ASSIST_RATE_LIMITED" and r.headers["Retry-After"] == "30"
    assert ask("밝게 해줘", who="a", ws="wa").status_code == 429


def test_the_usage_log_keeps_counts_and_lengths_never_the_sentence(env):
    secret = "내 비밀 문장 밝게 해줘"
    ask(secret)
    rows = sqlite3.connect(env["tmp"] / "a.sqlite3").execute("SELECT * FROM assist_usage").fetchall()
    assert len(rows) == 1
    assert rows[0][:5] == ("wa", "user-a", "rules", 1, 1) and rows[0][5] == len(secret)
    dump = " ".join(str(c) for c in rows[0])
    assert "비밀" not in dump and "밝게" not in dump


def test_llm_mode_without_an_adapter_falls_back_to_the_rules_and_says_so(env, monkeypatch):
    monkeypatch.setattr(config, "ASSIST_INTERPRETER_MODE", "llm")
    body = ask("밝게 해줘").json()
    assert body["interpreter"] == "rules" and body["fallback"] is True and body["actions"] == [{"action": "click", "target": "밝게"}]


class FakeLlm:
    name = "fake-llm"
    data_policy = {"trains_on_data": False}
    def __init__(self, result):
        self.result, self.seen = result, []
    def interpret(self, text, page, controls):
        self.seen.append((text, page, list(controls)))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def connect(monkeypatch, adapter, notice=False):
    monkeypatch.setattr(config, "ASSIST_INTERPRETER_MODE", "llm")
    monkeypatch.setattr(assist, "get_llm_adapter", lambda: adapter)
    monkeypatch.setattr(config, "EXTERNAL_NOTICE_REQUIRED", notice)


def test_a_connected_llm_gets_only_the_sentence_the_page_and_the_names_and_its_output_is_sanitised(env, monkeypatch):
    fake = FakeLlm([{"action": "click", "target": "만들기"}, {"action": "click", "target": "환각 버튼"}, {"action": "set", "target": "피부톤", "value": "황갈색"}])
    connect(monkeypatch, fake)
    body = ask("봄 분위기로 만들어").json()
    assert body["interpreter"] == "llm" and body["fallback"] is False
    assert body["actions"] == [{"action": "click", "target": "만들기", "confirm": True}, {"action": "set", "target": "피부톤", "value": "황갈색"}]
    assert fake.seen == [("봄 분위기로 만들어", "studio", CONTROLS)], "nothing else is handed over"


def test_an_llm_failure_falls_back_to_the_rules(env, monkeypatch):
    connect(monkeypatch, FakeLlm(RuntimeError("boom")))
    body = ask("밝게 해줘").json()
    assert body["interpreter"] == "rules" and body["fallback"] is True and body["actions"][0]["target"] == "밝게"


def test_an_external_interpreter_needs_the_transfer_notice_the_kill_switch_and_the_daily_limit(env, monkeypatch):
    fake = FakeLlm([{"action": "click", "target": "밝게"}])
    connect(monkeypatch, fake, notice=True)
    r = ask("밝게 해줘")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "EXTERNAL_NOTICE_REQUIRED" and r.json()["detail"]["provider"] == "fake-llm"
    assert fake.seen == [], "nothing was sent before the notice was acknowledged"
    connect(monkeypatch, fake, notice=False)
    monkeypatch.setattr(config, "ASSIST_LLM_DAILY_LIMIT", 2)
    assert ask("밝게 해줘").status_code == 200 and ask("밝게 해줘").status_code == 200
    limited = ask("밝게 해줘")
    assert limited.status_code == 429 and limited.json()["detail"]["code"] == "ASSIST_LIMIT"
    from app import cost_cap
    monkeypatch.setattr(cost_cap, "kill_switch_on", lambda: True)
    killed = ask("밝게 해줘")
    assert killed.status_code == 429 and killed.json()["detail"]["code"] == "AI_JOBS_DISABLED"
