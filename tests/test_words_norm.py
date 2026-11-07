import pytest

from vedit.words import norm, tokens


@pytest.mark.parametrize(
    "a,b",
    [
        ("أحمد", "احمد"),
        ("إسلام", "اسلام"),
        ("آمن", "امن"),
        ("ٱلله", "الله"),
        ("على", "علي"),
        ("مدرسة", "مدرسه"),
        ("مؤمن", "مومن"),
        ("شائع", "شايع"),
        ("كَتَبَ", "كتب"),
        ("كتــاب", "كتاب"),
        ("Hello,", "hello"),
        ("٢٠٢٥", "2025"),
    ],
)
def test_norm(a, b):
    assert norm(a) == b


def test_norm_values():
    assert norm("«أُحسِبُهُ،»") == "احسبه"
    assert norm("PowerTeleBot.com") == "powertelebotcom".replace(" ", "")
    assert norm("١٢") == "12"
    assert norm("...") == ""


def test_tokens_drop_empty():
    assert tokens("يعني  ... شنو؟") == ["يعني", "شنو"]


@pytest.mark.parametrize(
    "w,expected",
    [
        ("سalam", True),
        ("alamس", True),
        ("hello", False),
        ("سلام", False),
        ("٢٠٢٥", False),
        ("a1", False),
        ("", False),
    ],
)
def test_mixed_script(w, expected):
    from vedit.words.norm import mixed_script

    assert mixed_script(w) is expected
