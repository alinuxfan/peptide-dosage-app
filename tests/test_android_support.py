"""Android helpers must be inert (and import cleanly) off Android."""

from peptide_dosage import android_support


def test_not_android_on_desktop():
    assert android_support.is_android() is False


def test_back_handler_is_noop_off_android():
    calls = []
    handler = android_support.BackHandler(None, can_go_back=lambda: calls.append("can") or True, go_back=lambda: None)
    assert handler.sync() is False
    assert calls == []  # never even queries the stack


def test_share_text_returns_false_off_android():
    assert android_support.share_text(None, "hello", subject="x") is False
