import pytest

from qwen_commit import prompts


def test_all_styles_defined():
    assert set(prompts.STYLE_SPECS) == {"conventional", "plain", "emoji"}


def test_user_prompt_carries_diff_and_log():
    system, user = prompts.build_messages("conventional", "DIFFTEXT", "abc1234 old change")
    assert "DIFFTEXT" in user
    assert "abc1234 old change" in user
    assert "72 characters or fewer" in system


def test_fresh_repo_placeholder():
    _, user = prompts.build_messages("plain", "DIFF", "")
    assert "(new repository)" in user


def test_style_spec_reaches_system_prompt():
    system, _ = prompts.build_messages("conventional", "d", "")
    assert "Conventional Commits" in system
    system, _ = prompts.build_messages("emoji", "d", "")
    assert "emoji" in system


def test_unknown_style_raises():
    with pytest.raises(KeyError):
        prompts.build_messages("pirate", "d", "")
