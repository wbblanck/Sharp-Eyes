"""Post stdin to Will's Discord channel: `echo text | python3 discord_post.py`."""

import json
import sys
import urllib.request
from pathlib import Path

webhook = (Path(__file__).parent / ".discord-webhook").read_text().strip()
text = sys.stdin.read().strip()
for i in range(0, len(text), 1900):  # Discord caps a message at 2,000 characters
    req = urllib.request.Request(
        webhook,
        data=json.dumps({"content": text[i : i + 1900]}).encode(),
        headers={"User-Agent": "sharp-eyes", "Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=30)
