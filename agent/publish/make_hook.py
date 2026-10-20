"""Posts the day's LinkedIn post to the Interview Sarthi page through a Make.com scenario.

Owner's decision, 28 Sep 2026: LinkedIn's page-posting API is only for registered companies, but Make's
own LinkedIn app is approved, so a Make scenario ("Custom webhook" then LinkedIn "Create an organization
image post") can post on the page for us. The run sends the text and the card image as one multipart
request to the scenario's webhook address (LINKEDIN_WEBHOOK_URL, a secret: anyone holding it can post).
"""

from __future__ import annotations

import pathlib


def send(url: str, text: str, image: str | pathlib.Path | None, alt: str = "") -> None:
    import requests

    data = {"text": text, "alt": alt[:300]}
    if image:
        with open(image, "rb") as handle:
            response = requests.post(url, data=data, timeout=60,
                                     files={"image": ("interview-sarthi-jobs.jpg", handle, "image/jpeg")})
    else:
        response = requests.post(url, data=data, timeout=60)
    if response.status_code != 200:
        # Never echo the URL: it is the secret.
        raise RuntimeError(f"Make webhook refused the post (HTTP {response.status_code}: {response.text[:200]})")
