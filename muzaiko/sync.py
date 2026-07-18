"""在庫・価格同期: 仕入先の最新状態に出品を追従させる。無在庫販売の生命線。"""
from __future__ import annotations

from .channels import ChannelBase
from .models import Listing, SupplierProduct
from .pricing import PricingEngine


def sync_listings(
    listings: dict[str, Listing],
    products: list[SupplierProduct],
    pricing: PricingEngine,
    channel: ChannelBase,
) -> dict[str, int]:
    """仕入先フィードと出品を突き合わせて更新。統計を返す。"""
    by_sku = {p.sku: p for p in products}
    stats = {"repriced": 0, "paused": 0, "reactivated": 0, "stock_updated": 0}

    for sku, listing in listings.items():
        if listing.status == "delisted":
            continue
        p = by_sku.get(sku)

        # 仕入先から消えた or 在庫切れ → 出品停止(売り越し防止)
        if p is None or p.stock <= 0:
            if listing.status == "active":
                listing.status = "paused"
                listing.stock = 0
                channel.update(listing)
                stats["paused"] += 1
                print(f"  [停止] {sku}: 仕入先在庫切れ")
            elif listing.status == "draft":
                # 未出品candidateも在庫を0にして、publishでの売り越し出品を防ぐ
                listing.stock = 0
            continue

        # 在庫復活
        if listing.status == "paused" and p.stock > 0:
            listing.status = "active"
            stats["reactivated"] += 1
            print(f"  [再開] {sku}: 在庫復活({p.stock})")

        # 在庫数の追従
        if listing.stock != p.stock:
            listing.stock = p.stock
            stats["stock_updated"] += 1

        # 原価変動に応じたリプライシング
        new_price, reason = pricing.reprice(listing, p.landed_cost)
        if new_price != int(listing.price):
            print(f"  [改定] {sku}: {listing.price:.0f}円 → {new_price}円({reason})")
            listing.price = new_price
            stats["repriced"] += 1
        listing.cost = p.landed_cost

        channel.update(listing)

    return stats
