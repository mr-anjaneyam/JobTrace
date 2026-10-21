import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobtrace import telegram


def test_telegram_formatting():
    jobs = [
        {
            "id": "1",
            "title": "Software Engineer <Full-Stack>",
            "company": "Acme & Co",
            "url": "https://example.com/job/1",
            "location": "San Francisco, CA",
            "score": 9,
            "reason": "Strong React & Python background",
        },
        {
            "id": "2",
            "title": "Backend Developer",
            "company": "Globex",
            "url": "https://example.com/job/2",
            "location": "Remote",
            "score": 7,
            "reason": "Matches PostgreSQL and APIs",
        },
    ]

    # Alert rendering
    alert_html = telegram.render_alert(jobs, "12 Oct 2026, 09:30")
    assert "JOBTRACE — New Openings Detected" in alert_html
    # Must properly escape HTML tags in title & company
    assert "&lt;Full-Stack&gt;" in alert_html
    assert "Acme &amp; Co" in alert_html
    assert "[9/10]" in alert_html
    assert "href=\"https://example.com/job/1\"" in alert_html

    # Digest rendering
    digest_html = telegram.render_digest(jobs, [{"title": "Old Role", "company": "Stripe"}], "Week of 12 Oct")
    assert "JOBTRACE — Weekly Digest" in digest_html
    assert "<s>Old Role</s>" in digest_html
    print("[OK] telegram formatting tests pass")


def test_telegram_chunking():
    # Construct message that exceeds 4,000 characters
    long_line = "This is a line of job details with plenty of information to test chunking.\n"
    huge_message = long_line * 80
    assert len(huge_message) > 4000

    sent_payloads = []

    def mock_send(bot_token, chat_id, text, parse_mode="HTML", disable_preview=True):
        assert len(text) <= telegram.MAX_MESSAGE_LENGTH
        sent_payloads.append(text)
        return True

    orig_send = telegram.send_message
    telegram.send_message = mock_send
    try:
        chunks = telegram.send_chunked("mock_token", "mock_chat", huge_message)
        assert chunks > 1
        assert len(sent_payloads) == chunks
    finally:
        telegram.send_message = orig_send

    print("[OK] telegram chunking tests pass")


def test_telegram_multi_chat_ids():
    cfg1 = {"telegram": {"chat_ids": ["123", "456", "789"]}}
    assert telegram.get_chat_ids(cfg1) == ["123", "456", "789"]

    cfg2 = {"telegram": {"chat_id": "111, 222; 333\n444"}}
    assert telegram.get_chat_ids(cfg2) == ["111", "222", "333", "444"]

    print("[OK] telegram multi-chat ID tests pass")


if __name__ == "__main__":
    test_telegram_formatting()
    test_telegram_chunking()
    test_telegram_multi_chat_ids()
    print("All Telegram tests PASSED!")

