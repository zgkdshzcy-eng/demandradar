from app.pipeline.clean import (
    clean_payload,
    detect_lang,
    is_blocked,
    normalize,
    signal_strength,
)


def test_normalize_strips_urls_and_whitespace() -> None:
    raw = "Check this out  https://example.com/foo  it is\n\n cool"
    assert normalize(raw) == "Check this out it is cool"


def test_detect_lang_zh() -> None:
    assert detect_lang("有没有工具能批量处理") == "zh"


def test_detect_lang_en() -> None:
    assert detect_lang("is there a tool for batch processing") == "en"


def test_detect_lang_unknown() -> None:
    assert detect_lang("") == "unknown"
    assert detect_lang("   ") == "unknown"


def test_is_blocked_negative() -> None:
    assert is_blocked("normal text about productivity") is False


def test_signal_strength_strong_en() -> None:
    assert signal_strength("is there a tool for X?", "en") == "strong"


def test_signal_strength_strong_zh() -> None:
    assert signal_strength("求推荐能批量去水印的小工具", "zh") == "strong"


def test_signal_strength_weak() -> None:
    assert signal_strength("hello world", "en") == "weak"


def test_clean_payload_combo() -> None:
    text, lang, blocked = clean_payload("有没有工具 https://x.com/abc 求推荐")
    assert lang == "zh"
    assert blocked is False
    assert "https://" not in text
