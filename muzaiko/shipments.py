"""出荷処理: 追跡番号CSVを取り込み、注文を発送済みにしてチャネルへ登録する。

CSV列: order_id,tracking_number,carrier
仕入先(または転送業者)から届く追跡番号一覧を貼り付けるだけで、
Shopifyの発送登録と顧客への発送通知まで自動化される。
"""
from __future__ import annotations

import csv
from pathlib import Path

from .channels import ChannelBase
from .models import Order


def process_shipments(
    csv_path: Path,
    orders: dict[str, Order],
    channel: ChannelBase,
) -> dict[str, int]:
    stats = {"shipped": 0, "not_found": 0, "skipped": 0}
    if not csv_path.exists():
        print(f"  出荷CSVが見つかりません: {csv_path}")
        return stats
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            order_id = (row.get("order_id") or "").strip()
            tracking = (row.get("tracking_number") or "").strip()
            if not order_id or not tracking:
                stats["skipped"] += 1
                continue
            o = orders.get(order_id)
            if o is None:
                print(f"  [警告] 未知の注文ID: {order_id}")
                stats["not_found"] += 1
                continue
            if o.status == "shipped":
                stats["skipped"] += 1
                continue
            o.tracking_number = tracking
            o.carrier = (row.get("carrier") or "").strip()
            o.status = "shipped"
            channel.mark_shipped(o)
            stats["shipped"] += 1
            print(f"  [発送] {order_id}: {o.carrier} {tracking}")
    return stats
