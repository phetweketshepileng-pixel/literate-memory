from app.core.email import render_html
from app.modules.auth import router as auth


def test_reset_email_flood_limit_per_address():
    auth._link_email_log.clear()
    assert [auth._link_email_allowed("a@x.com", 1000.0 + i) for i in range(4)] == [True, True, True, False]
    assert auth._link_email_allowed("b@x.com", 1001.0)          # other addresses unaffected
    assert auth._link_email_allowed("a@x.com", 1000.0 + 3601)   # allowed again after an hour


def test_email_html_escapes_content_and_link():
    out = render_html("Hello <b>you</b>\n\nSecond", "Go", 'https://site/#reset=abc"><script>')
    assert "<b>you</b>" not in out and "&lt;b&gt;you&lt;/b&gt;" in out
    assert "<script>" not in out and "&quot;&gt;&lt;script&gt;" in out
    assert out.count("<p") >= 3
