"""Telegram Bot notifications module for JobTrace.

Handles instant opening alerts, formatted weekly digests, chunking (respecting
Telegram's 4096-character limit), HTML formatting, and API verification.
"""
from __future__ import annotations

import html
import os
import time
from typing import Any

import requests

TELEGRAM_API_BASE = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4000


def get_credentials(cfg: dict) -> tuple[str, str]:
    """Retrieve Telegram bot token and chat ID from config or environment variables."""
    t_cfg = cfg.get("telegram") or {}
    token = (
        os.environ.get("TELEGRAM_BOT_TOKEN")
        or t_cfg.get("bot_token")
        or ""
    ).strip()
    chat_id = (
        os.environ.get("TELEGRAM_CHAT_ID")
        or str(t_cfg.get("chat_id") or "")
    ).strip()
    return token, chat_id


def send_message(
    bot_token: str,
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
    disable_preview: bool = True,
    retries: int = 3,
) -> bool:
    """Send a single message via Telegram Bot API with retry and rate-limit handling."""
    if not bot_token or not chat_id:
        raise ValueError("Telegram bot_token and chat_id must be configured.")

    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_preview,
    }

    for attempt in range(retries):
        try:
            resp = requests.post(url, json=payload, timeout=25)
            if resp.status_code == 200:
                return True
            if resp.status_code == 429:
                retry_after = resp.json().get("parameters", {}).get("retry_after", 3)
                time.sleep(retry_after)
                continue
            err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            raise RuntimeError(f"Telegram API error {resp.status_code}: {err_data}")
        except requests.RequestException as e:
            if attempt == retries - 1:
                raise RuntimeError(f"Failed to send Telegram message: {e}") from e
            time.sleep(2 * (attempt + 1))
    return False


def send_chunked(
    bot_token: str,
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
    disable_preview: bool = True,
) -> int:
    """Split long content at line breaks into safe chunks and send sequentially."""
    if len(text) <= MAX_MESSAGE_LENGTH:
        send_message(bot_token, chat_id, text, parse_mode, disable_preview)
        return 1

    lines = text.split("\n")
    chunks = []
    current_chunk: list[str] = []
    current_len = 0

    for line in lines:
        if current_len + len(line) + 1 > MAX_MESSAGE_LENGTH:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_len = 0
        current_chunk.append(line)
        current_len += len(line) + 1

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    sent_count = 0
    for chunk in chunks:
        if chunk.strip():
            send_message(bot_token, chat_id, chunk, parse_mode, disable_preview)
            sent_count += 1
            time.sleep(0.35)  # Be polite to Telegram API rate limits

    return sent_count


# --------------------------------------------------------------------------
# Message Formatters
# --------------------------------------------------------------------------

def format_job_card(job: Any) -> str:
    """Format one job entry as a rich HTML card for Telegram."""
    score = job["score"]
    score_badge = f"<b>[{score}/10]</b> " if score is not None else ""
    title = html.escape(str(job["title"] or "Untitled Role"))
    company = html.escape(str(job["company"] or "Unknown Company"))
    location = html.escape(str(job["location"] or "Location not specified"))
    url = job["url"] or "#"
    reason = html.escape(str(job["reason"] or ""))

    card = [f"🎯 {score_badge}<a href=\"{url}\"><b>{title}</b></a>"]
    card.append(f"🏢 <i>{company}</i> · 📍 {location}")
    if reason:
        card.append(f"💡 <i>{reason}</i>")
    return "\n".join(card)


def render_alert(rows: list[Any], label: str) -> str:
    """Render high-priority daily opening alerts."""
    lines = [
        "🚨 <b>JOBTRACE — New Openings Detected</b>",
        f"📅 <i>{html.escape(label)}</i> · <b>{len(rows)}</b> matching role(s)\n",
    ]
    for r in rows:
        lines.append(format_job_card(r))
        lines.append("")  # Blank line spacer

    lines.append("⚙️ <i>Sent for companies in your alerts shortlist.</i>")
    return "\n".join(lines)


def render_digest(
    new_jobs: list[Any],
    closed_jobs: list[Any],
    period_label: str,
    notes: list[str] | None = None,
) -> str:
    """Render weekly digest message."""
    tracked = [r for r in new_jobs if r.get("source") not in ("remotive", "arbeitnow")]
    discovered = [r for r in new_jobs if r.get("source") in ("remotive", "arbeitnow")]

    lines = [
        "📡 <b>JOBTRACE — Weekly Digest</b>",
        f"🗓️ <i>{html.escape(period_label)}</i>",
        f"📊 <b>{len(new_jobs)}</b> new matches · <b>{len(closed_jobs)}</b> closed roles\n",
    ]

    if tracked:
        lines.append(f"⭐ <b>Watched Companies ({len(tracked)}):</b>")
        for j in tracked:
            lines.append(format_job_card(j))
            lines.append("")

    if discovered:
        lines.append(f"🔍 <b>Discovered from Remote Feeds ({len(discovered)}):</b>")
        for j in discovered:
            lines.append(format_job_card(j))
            lines.append("")

    if not tracked and not discovered:
        lines.append("<i>No new matching roles this week.</i>\n")

    if closed_jobs:
        lines.append(f"❌ <b>Recently Closed ({min(len(closed_jobs), 15)} shown):</b>")
        for c in closed_jobs[:15]:
            c_title = html.escape(str(c["title"]))
            c_co = html.escape(str(c["company"]))
            lines.append(f"• <s>{c_title}</s> — {c_co}")
        if len(closed_jobs) > 15:
            lines.append(f"<i>...and {len(closed_jobs) - 15} more closed.</i>")
        lines.append("")

    if notes:
        lines.append("ℹ️ <b>Notes:</b>")
        for note in notes:
            lines.append(f"• {html.escape(note)}")
        lines.append("")

    lines.append("🤖 <i>JobTrace · Managed locally on your system</i>")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Dispatch Functions
# --------------------------------------------------------------------------

def send_alert(cfg: dict, rows: list[Any], label: str) -> None:
    bot_token, chat_id = get_credentials(cfg)
    msg = render_alert(rows, label)
    send_chunked(bot_token, chat_id, msg)


def send_digest(
    cfg: dict,
    new_jobs: list[Any],
    closed_jobs: list[Any],
    period_label: str,
    notes: list[str] | None = None,
) -> None:
    bot_token, chat_id = get_credentials(cfg)
    msg = render_digest(new_jobs, closed_jobs, period_label, notes)
    send_chunked(bot_token, chat_id, msg)


def test_telegram(cfg: dict) -> tuple[bool, str]:
    """Test Telegram connection by calling getMe and sending a ping."""
    bot_token, chat_id = get_credentials(cfg)
    if not bot_token or not chat_id:
        return False, "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in config.yaml or environment."

    # 1. Test bot validity
    try:
        r = requests.get(f"{TELEGRAM_API_BASE}/bot{bot_token}/getMe", timeout=15)
        if r.status_code != 200:
            return False, f"Invalid bot token (HTTP {r.status_code}): {r.text}"
        data = r.json()
        bot_user = data.get("result", {}).get("username", "unknown")
    except Exception as e:
        return False, f"Network error contacting Telegram: {e}"

    # 2. Test sending message
    try:
        text = (
            f"✅ <b>JobTrace — Telegram Bot Connected!</b>\n"
            f"🤖 Bot: @{bot_user}\n"
            f"💬 Chat ID: <code>{chat_id}</code>\n"
            f"⏰ Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Your daily alerts and weekly digests will arrive in this chat."
        )
        send_message(bot_token, chat_id, text)
        return True, f"Success! Verified bot @{bot_user} and sent test message to chat {chat_id}."
    except Exception as e:
        return False, f"Bot token valid (@{bot_user}) but failed to send message to chat {chat_id}: {e}"
