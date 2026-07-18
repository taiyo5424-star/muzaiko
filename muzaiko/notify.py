"""日次レポートの Slack / Discord Webhook 通知。

環境変数(既定: MUZAIKO_WEBHOOK_URL)にWebhook URLを設定すると有効になる。
未設定なら何もしない(ドライラン運用を邪魔しない)。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .config import Config


def notify(cfg: Config, text: str) -> bool:
    url = os.environ.get(cfg["notify"]["webhook_env"], "")
    if not url:
        return False
    ntype = cfg["notify"]["type"]
    # Slack: {"text": ...} / Discord: {"content": ...}(2000字制限)
    if ntype == "discord":
        payload = {"content": text[:1900]}
    else:
        payload = {"text": text[:3500]}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        print(f"  [通知] {ntype} に送信しました")
        return True
    except (urllib.error.URLError, OSError) as e:
        print(f"  [warn] 通知送信に失敗: {e}")
        return False
