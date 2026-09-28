"""Hands the day's LinkedIn post to the owner on Telegram, for posting on the page by hand.

Owner's decision, 28 Sep 2026: LinkedIn's page-posting API (Community Management API) is only for
registered companies, and Interview Sarthi is run by an individual. So when there is no LinkedIn token,
the jobs post's card and text go to the owner's Telegram bot (the same bot and chat as the owner
dashboard alerts), and the owner pastes them onto the Interview Sarthi page. Two messages: the card
with the steps, then the text alone so it copies cleanly.
"""

from __future__ import annotations

import pathlib

API = "https://api.telegram.org/bot{token}/{method}"
PAGE_ADMIN = "https://www.linkedin.com/company/144842945/admin/dashboard/"

STEPS = ("Today's LinkedIn post for the Interview Sarthi page.\n\n"
         "1. Save this image.\n"
         "2. Open the page: " + PAGE_ADMIN + "\n"
         "3. Create > Start a post, paste the next message, add the image, Post.\n\n"
         "Post as the page, not as yourself.")


def _call(settings, method: str, **kwargs) -> dict:
    import requests

    response = requests.post(API.format(token=settings.telegram_bot_token, method=method), timeout=60, **kwargs)
    try:
        data = response.json()
    except ValueError:
        data = {}
    if not data.get("ok"):
        # Never echo the URL: it carries the bot token.
        raise RuntimeError(f"Telegram {method} failed (HTTP {response.status_code}: {data.get('description', '')})")
    return data["result"]


def hand_off(settings, text: str, image: str | pathlib.Path | None) -> str:
    """Send the card with the steps, then the post text. Returns the text message's id."""
    chat = settings.telegram_chat_id
    if image:
        with open(image, "rb") as handle:
            _call(settings, "sendPhoto", data={"chat_id": chat, "caption": STEPS},
                  files={"photo": ("linkedin-post.jpg", handle, "image/jpeg")})
    else:
        _call(settings, "sendMessage", data={"chat_id": chat, "text": STEPS, "disable_web_page_preview": True})
    message = _call(settings, "sendMessage", data={"chat_id": chat, "text": text[:4096],
                                                   "disable_web_page_preview": True})
    return str(message["message_id"])


def notify(settings, text: str) -> None:
    """A plain message to the owner, for things only they can fix."""
    _call(settings, "sendMessage", data={"chat_id": settings.telegram_chat_id, "text": text[:4096],
                                         "disable_web_page_preview": True})
