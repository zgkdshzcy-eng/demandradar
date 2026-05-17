from app.analyzer.prompts import load_prompt, render


def test_load_pain_extract_prompt_has_system_and_user() -> None:
    system, user = load_prompt("pain_extract")
    assert system  # non-empty
    assert "{{INPUT_JSON}}" in user


def test_render_substitutes_placeholders() -> None:
    out = render("hello {{NAME}}, age {{AGE}}", NAME="alice", AGE="30")
    assert out == "hello alice, age 30"
