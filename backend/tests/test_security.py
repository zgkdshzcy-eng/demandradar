"""Stateless tokens (JWT-style HS256) used by auth + billing."""
from __future__ import annotations

import pytest

from app.core import security as sec


def test_jwt_round_trip() -> None:
    token = sec.encode_jwt({"foo": "bar", "exp": sec._now_ts() + 60})
    payload = sec.decode_jwt(token)
    assert payload["foo"] == "bar"


def test_jwt_bad_signature_rejected() -> None:
    token = sec.encode_jwt({"foo": "bar", "exp": sec._now_ts() + 60})
    head, body, _sig = token.split(".")
    tampered = f"{head}.{body}.AAAAAAAA"
    with pytest.raises(sec.TokenError):
        sec.decode_jwt(tampered)


def test_jwt_expired_rejected() -> None:
    token = sec.encode_jwt({"foo": "bar", "exp": sec._now_ts() - 1})
    with pytest.raises(sec.TokenError):
        sec.decode_jwt(token)


def test_session_token_kind_and_subject() -> None:
    tok = sec.issue_session_token(42, "alice@example.com", ttl_days=1)
    payload = sec.decode_jwt(tok)
    assert payload["kind"] == "session"
    assert payload["sub"] == "42"
    assert payload["email"] == "alice@example.com"


def test_redeem_code_round_trip() -> None:
    code = sec.issue_redeem_code("weekly_pro", days=30)
    payload = sec.parse_redeem_code(code)
    assert payload["plan"] == "weekly_pro"
    assert payload["days"] == 30
    assert "nonce" in payload


def test_redeem_code_brief_oneoff_carries_brief_id() -> None:
    code = sec.issue_redeem_code("brief_oneoff", days=0, brief_id=7)
    payload = sec.parse_redeem_code(code)
    assert payload["plan"] == "brief_oneoff"
    assert payload["brief_id"] == 7


def test_redeem_code_invalid_plan_rejected() -> None:
    with pytest.raises(ValueError):
        sec.issue_redeem_code("garbage")


def test_parse_redeem_code_rejects_session_token() -> None:
    tok = sec.issue_session_token(1, "x@y.com")
    with pytest.raises(sec.TokenError):
        sec.parse_redeem_code(tok)
