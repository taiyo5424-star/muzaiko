"""受注処理: チャネルから受注を取り込み、仕入先への発注に変換する。"""
from __future__ import annotations

import csv
from pathlib import Path

from .channels import ChannelBase
from .models import Listing, Order
from .suppliers import SupplierBase


def process_orders(
    orders: dict[str, Order],
    listings: dict[str, Listing],
    channel: ChannelBase,
    supplier: SupplierBase,
    output_dir: Path,
) -> dict[str, int]:
    """新規受注の取込 → 自動発注 or 発注キュー出力。統計を返す。"""
    stats = {"imported": 0, "auto_ordered": 0, "queued": 0, "unmatched": 0}

    # 1. 新規受注の取込
    for o in channel.fetch_orders():
        if o.order_id in orders:
            continue
        if o.sku not in listings:
            print(f"  [警告] 受注 {o.order_id}: 未知のSKU {o.sku}")
            stats["unmatched"] += 1
        orders[o.order_id] = o
        stats["imported"] += 1
        print(f"  [受注] {o.order_id}: {o.sku} x{o.qty} @{o.sale_price:.0f}円")

    # 2. 発注処理
    queue_rows = []
    for o in orders.values():
        if o.status != "new":
            continue
        try:
            supplier_order_id = supplier.place_order(o.sku, o.qty, {})
        except NotImplementedError:
            supplier_order_id = ""
        if supplier_order_id:
            o.supplier_order_id = supplier_order_id
            o.status = "purchased"
            stats["auto_ordered"] += 1
        else:
            o.status = "to_purchase"
            listing = listings.get(o.sku)
            queue_rows.append({
                "order_id": o.order_id,
                "sku": o.sku,
                "qty": o.qty,
                "sale_price": f"{o.sale_price:.0f}",
                "est_cost": f"{listing.cost:.0f}" if listing else "",
                "supplier_url": "",
                "ordered_at": o.ordered_at,
            })
            stats["queued"] += 1

    # 3. 手動発注キューをCSV出力
    if queue_rows:
        queue_file = output_dir / "purchase_queue.csv"
        with open(queue_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(queue_rows[0].keys()))
            writer.writeheader()
            writer.writerows(queue_rows)
        print(f"  [発注キュー] {len(queue_rows)}件を {queue_file} に出力(要手動発注)")

    return stats
