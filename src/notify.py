"""
Pushes the digest to a phone via ntfy.sh — free, no account, no API key.
Anyone who knows the exact topic name can read it, so treat the topic
name itself like a lightweight secret (long and random, not your name).
"""

from __future__ import annotations

import requests


def send_ntfy(topic: str, title: str, body: str, *, priority: str = "default", tags: str = "school") -> None:
    if not topic:
        raise ValueError("NTFY_TOPIC is required to send a notification")

    resp = requests.post(
        f"https://ntfy.sh/{topic}",
        data=body.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": priority,
            "Tags": tags,
        },
        timeout=15,
    )
    resp.raise_for_status()
