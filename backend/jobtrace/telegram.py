"""Telegram Bot notifications module for JobTrace.

Handles instant opening alerts, formatted weekly digests, chunking (respecting
Telegram's 4096-character limit), HTML formatting, and API verification.
"""
from __future__ import annotations

import html
import os
import re
import time
from typing import Any

import requests

TELEGRAM_API_BASE = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4000


def get_bot_token(cfg: dict) -> str:
    """Retrieve Telegram bot token from config or environment variables."""
    t_cfg = cfg.get("telegram") or {}
    return (
        os.environ.get("TELEGRAM_BOT_TOKEN")
        or str(t_cfg.get("bot_token") or "")
    ).strip()


def get_chat_ids(cfg: dict) -> list[str]:
    """Retrieve all configured Telegram chat/user IDs as a clean list of strings.
    
    Supports single ID, comma/newline-separated strings, or lists in config/env.
    """
    t_cfg = cfg.get("telegram") or {}
    raw_candidates = [
        os.environ.get("TELEGRAM_CHAT_IDS"),
        os.environ.get("TELEGRAM_CHAT_ID"),
        t_cfg.get("chat_ids"),
        t_cfg.get("chat_id"),
    ]
    ids: list[str] = []
    for raw in raw_candidates:
        if not raw:
            continue
        if isinstance(raw, (list, tuple, set)):
            for item in raw:
                s = str(item).strip()
                if s and s not in ids:
                    ids.append(s)
        elif isinstance(raw, str):
            for part in re.split(r"[,;\n\s]+", raw):
                s = part.strip()
                if s and s not in ids:
                    ids.append(s)
        elif isinstance(raw, int):
            s = str(raw)
            if s not in ids:
                ids.append(s)

    return ids


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
        "🚨 <b>JOBTRACE: New Openings Detected</b>",
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
        "📡 <b>JOBTRACE: Weekly Digest</b>",
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
            lines.append(f"• <s>{c_title}</s> - {c_co}")
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
    """Broadcast new opening alert to all configured Telegram recipients."""
    bot_token = get_bot_token(cfg)
    chat_ids = get_chat_ids(cfg)
    if not bot_token or not chat_ids:
        raise ValueError("Telegram bot_token and at least one chat_id must be configured.")

    msg = render_alert(rows, label)
    for cid in chat_ids:
        send_chunked(bot_token, cid, msg)


def send_digest(
    cfg: dict,
    new_jobs: list[Any],
    closed_jobs: list[Any],
    period_label: str,
    notes: list[str] | None = None,
) -> None:
    """Broadcast weekly digest to all configured Telegram recipients."""
    bot_token = get_bot_token(cfg)
    chat_ids = get_chat_ids(cfg)
    if not bot_token or not chat_ids:
        raise ValueError("Telegram bot_token and at least one chat_id must be configured.")

    msg = render_digest(new_jobs, closed_jobs, period_label, notes)
    for cid in chat_ids:
        send_chunked(bot_token, cid, msg)


TOKEN_RE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{20,}$")


def detect_chats(bot_token: str) -> tuple[bool, list[dict], str]:
    """Find chats that recently messaged the bot, so users do not have to look up their chat ID."""
    token = (bot_token or "").strip()
    if not TOKEN_RE.match(token):
        return False, [], "That does not look like a bot token. It should look like 123456789:ABC..."
    try:
        r = requests.get(f"{TELEGRAM_API_BASE}/bot{token}/getUpdates", params={"limit": 50, "timeout": 0}, timeout=15)
    except requests.RequestException:
        return False, [], "Could not reach Telegram. Check your internet connection."
    if r.status_code == 401:
        return False, [], "Telegram rejected this bot token."
    if r.status_code != 200:
        return False, [], f"Telegram returned HTTP {r.status_code}."

    chats: dict[str, dict] = {}
    for update in r.json().get("result", []):
        msg = update.get("message") or update.get("edited_message") or update.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if "id" not in chat:
            continue
        name = chat.get("title") or " ".join(
            p for p in (chat.get("first_name"), chat.get("last_name")) if p
        ) or chat.get("username") or "Unknown"
        chats[str(chat["id"])] = {"id": str(chat["id"]), "name": name, "type": chat.get("type", "private")}
    if not chats:
        return True, [], "No messages found yet. Open your bot in Telegram, press Start, then try again."
    return True, list(chats.values()), f"Found {len(chats)} chat(s)."


def test_telegram(
    cfg: dict,
    bot_token: str | None = None,
    chat_ids: list[str] | str | None = None,
) -> tuple[bool, str]:
    """Test Telegram connection by calling getMe and sending a ping to each configured recipient."""
    token = (bot_token or get_bot_token(cfg)).strip()

    targets: list[str] = []
    if chat_ids is not None:
        if isinstance(chat_ids, (list, tuple, set)):
            targets = [str(x).strip() for x in chat_ids if str(x).strip()]
        elif isinstance(chat_ids, str):
            targets = [p.strip() for p in re.split(r"[,;\n\s]+", chat_ids) if p.strip()]
    else:
        targets = get_chat_ids(cfg)

    if not token or not targets:
        return False, "Bot token and at least one Telegram chat ID must be specified."

    # 1. Test bot validity
    try:
        r = requests.get(f"{TELEGRAM_API_BASE}/bot{token}/getMe", timeout=15)
        if r.status_code != 200:
            return False, f"Invalid bot token (HTTP {r.status_code}): {r.text}"
        data = r.json()
        bot_user = data.get("result", {}).get("username", "unknown")
    except Exception as e:
        return False, f"Network error contacting Telegram: {str(e).replace(token, '***')}"

    # 2. Test sending message to all target chat IDs
    successes: list[str] = []
    failures: list[str] = []
    for cid in targets:
        try:
            text = (
                f"✅ <b>JobTrace: Telegram Bot Connected!</b>\n"
                f"🤖 Bot: @{bot_user}\n"
                f"💬 Chat ID: <code>{cid}</code>\n"
                f"⏰ Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"Your daily alerts and weekly digests will arrive in this chat."
            )
            send_message(token, cid, text)
            successes.append(cid)
        except Exception as e:
            failures.append(f"{cid} ({e})")

    if not failures:
        return True, f"Success! Verified bot @{bot_user} and delivered test ping to {len(successes)} recipient(s): {', '.join(successes)}."
    elif successes:
        return True, f"Partial success with bot @{bot_user}: Sent to {', '.join(successes)}, but failed for {', '.join(failures)}."
    else:
        return False, f"Bot token valid (@{bot_user}) but failed to deliver to all chat ID(s): {', '.join(failures)}."

