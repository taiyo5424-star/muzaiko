"""会計帳簿エクスポート: 受注データから確定申告・記帳用の仕訳CSVを生成。

出力(out/ledger.csv、Excel対応BOM付き):
  日付, 注文ID, SKU, 摘要, 売上高, 支払手数料, 仕入高, 粗利, ステータス
末尾に月次集計。freee/マネーフォワード等へのインポートの下敷きに使える。
※ 税務判断は税理士・税務署に確認すること。青色申告なら開業届+青色申請を忘れずに。
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from .analytics import order_cogs
from .models import Listing, Order


def export_ledger(
    orders: dict[str, Order],
    listings: dict[str, Listing],
    path: Path,
) -> int:
    rows = []
    monthly: dict[str, dict[str, float]] = defaultdict(
        lambda: {"revenue": 0.0, "fee": 0.0, "cogs": 0.0}
    )
    for o in sorted(orders.values(), key=lambda x: x.ordered_at):
        if o.status == "cancelled":
            continue
        listing = listings.get(o.sku)
        cogs = order_cogs(o, listings)
        day = (o.ordered_at or "")[:10]
        month = day[:7]
        if cogs is None:
            # 原価不明: 仕入高・粗利を空欄にして「要確認」を明示(0円計上しない)
            rows.append([day, o.order_id, o.sku,
                         (listing.title[:30] if listing else o.sku),
                         f"{o.revenue:.0f}", f"{o.fee:.0f}", "", "",
                         f"{o.status}(原価要確認)"])
            continue
        profit = o.revenue - o.fee - cogs
        rows.append([
            day, o.order_id, o.sku,
            (listing.title[:30] if listing else o.sku),
            f"{o.revenue:.0f}", f"{o.fee:.0f}", f"{cogs:.0f}", f"{profit:.0f}",
            o.status,
        ])
        if month:
            m = monthly[month]
            m["revenue"] += o.revenue
            m["fee"] += o.fee
            m["cogs"] += cogs

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["日付", "注文ID", "SKU", "摘要", "売上高",
                        "支払手数料", "仕入高", "粗利", "ステータス"])
        writer.writerows(rows)
        writer.writerow([])
        writer.writerow(["月次集計", "", "", "", "売上高", "支払手数料", "仕入高", "粗利", ""])
        for month in sorted(monthly):
            m = monthly[month]
            profit = m["revenue"] - m["fee"] - m["cogs"]
            writer.writerow([month, "", "", "",
                             f"{m['revenue']:.0f}", f"{m['fee']:.0f}",
                             f"{m['cogs']:.0f}", f"{profit:.0f}", ""])
    return len(rows)
