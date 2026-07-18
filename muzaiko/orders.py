"""受注処理: チャネルから受注を取り込み、仕入先への発注に変換する。

安全設計:
- 取込直後・自動発注1件成功ごとに save コールバックで永続化
  (途中クラッシュしても再実行時に二重発注しない)
- 仕入先APIの例外は1件単位で捕捉し、手動発注キューに落として処理を継続
- チャネル側でキャンセルされた注文を発注前に検知して cancelled にする
- 受注時点の仕入原価を Order に記録(後の原価変動が過去の損益を書き換えない)
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable

from .channels import ChannelBase
from .models import Listing, Order
from .suppliers import SupplierBase


def process_orders(
    orders: dict[str, Order],
    listings: dict[str, Listing],
    channel: ChannelBase,
    supplier: SupplierBase,
    output_dir: Path,
    save: Callable[[], None] | None = None,
) -> dict[str, int]:
    stats = {"imported": 0, "auto_ordered": 0, "queued": 0,
             "unmatched": 0, "cancelled": 0, "errors": 0}

    def _save() -> None:
        if save:
            save()

    # 0. チャネル側キャンセルの反映(発注前に必ず行う)
    try:
        cancelled_ids = channel.fetch_cancelled_ids()
    except Exception as e:
        print(f"  [warn] キャンセル確認に失敗(継続): {e}")
        cancelled_ids = []
    for o in orders.values():
        if o.status not in ("new", "to_purchase"):
            continue
        if any(o.order_id == cid or o.order_id.startswith(f"{cid}-")
               for cid in cancelled_ids):
            o.status = "cancelled"
            stats["cancelled"] += 1
            print(f"  [キャンセル] {o.order_id}: チャネル側で取消済み")

    # 1. 新規受注の取込
    for o in channel.fetch_orders():
        if o.order_id in orders:
            continue
        listing = listings.get(o.sku)
        if listing is None:
            print(f"  [警告] 受注 {o.order_id}: 未知のSKU {o.sku}(損益集計から除外されます)")
            stats["unmatched"] += 1
        else:
            o.cost_at_order = listing.cost
        orders[o.order_id] = o
        stats["imported"] += 1
        print(f"  [受注] {o.order_id}: {o.sku} x{o.qty} @{o.sale_price:.0f}円")
    _save()               # 取込を即永続化(発注前にクラッシュしても受注は残る)
    channel.ack_orders()  # 永続化に成功してから取込元を消費

    # 2. 発注処理
    queue_rows = []

    def _queue(o: Order) -> None:
        o.status = "to_purchase"
        listing = listings.get(o.sku)
        queue_rows.append({
            "order_id": o.order_id,
            "sku": o.sku,
            "qty": o.qty,
            "sale_price": f"{o.sale_price:.0f}",
            "est_cost": f"{o.cost_at_order:.0f}" if o.cost_at_order else
                        (f"{listing.cost:.0f}" if listing else ""),
            "supplier_url": "",
            "ordered_at": o.ordered_at,
        })
        stats["queued"] += 1

    for o in orders.values():
        if o.status != "new":
            continue
        try:
            supplier_order_id = supplier.place_order(o.sku, o.qty, o.shipping_address)
        except NotImplementedError:
            supplier_order_id = ""
        except Exception as e:
            print(f"  [warn] {o.order_id}: 自動発注に失敗、手動キューへ回します: {e}")
            stats["errors"] += 1
            _queue(o)
            _save()
            continue
        if supplier_order_id:
            o.supplier_order_id = supplier_order_id
            o.status = "purchased"
            stats["auto_ordered"] += 1
            _save()   # 1件成功ごとに永続化(二重発注防止)
        else:
            _queue(o)
    _save()

    # 3. 手動発注キューをCSV出力
    if queue_rows:
        queue_file = output_dir / "purchase_queue.csv"
        with open(queue_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(queue_rows[0].keys()))
            writer.writeheader()
            writer.writerows(queue_rows)
        print(f"  [発注キュー] {len(queue_rows)}件を {queue_file} に出力(要手動発注)")

    return stats
