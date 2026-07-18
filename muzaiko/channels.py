"""販売チャネルアダプタ。

- LocalChannel: ドライラン。出品は out/ にHTML/JSONとして書き出し、受注は state/incoming_orders.json から取り込む。
- ShopifyChannel: Shopify Admin REST API。SHOPIFY_ACCESS_TOKEN 設定で実出品・実受注取得。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from .config import Config
from .models import Listing, Order

API_VERSION = "2024-07"


class ChannelBase:
    def publish(self, listing: Listing) -> str:
        """出品してチャネル側IDを返す。"""
        raise NotImplementedError

    def update(self, listing: Listing) -> None:
        """価格・在庫・状態を更新する。"""
        raise NotImplementedError

    def fetch_orders(self) -> list[Order]:
        """未取込の受注を返す。"""
        raise NotImplementedError

    def mark_shipped(self, order: Order) -> None:
        """チャネル側に発送済み+追跡番号を登録する(対応チャネルのみ)。"""
        return None


class LocalChannel(ChannelBase):
    """ドライラン用チャネル。出品内容をファイルに書き出して確認できる。"""

    def __init__(self, output_dir: Path, state_dir: Path):
        self.output_dir = output_dir
        self.state_dir = state_dir
        (self.output_dir / "listings").mkdir(parents=True, exist_ok=True)

    def publish(self, listing: Listing) -> str:
        path = self.output_dir / "listings" / f"{listing.sku}.json"
        path.write_text(
            json.dumps(listing.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return f"local-{listing.sku}"

    def update(self, listing: Listing) -> None:
        self.publish(listing)

    def fetch_orders(self) -> list[Order]:
        # デモ/手動運用: state/incoming_orders.json に受注を置くと取り込まれる
        f = self.state_dir / "incoming_orders.json"
        if not f.exists():
            return []
        raw = json.loads(f.read_text(encoding="utf-8"))
        orders = [Order.from_dict(d) for d in raw]
        f.unlink()  # 取り込んだら消費
        return orders


class ShopifyChannel(ChannelBase):
    """Shopify Admin REST API アダプタ(標準ライブラリのみで実装)。"""

    def __init__(self, domain: str, token: str, fee_rate: float):
        if not domain or not token:
            raise ValueError(
                "Shopify利用には config.json の channel.shopify_domain と "
                "環境変数 SHOPIFY_ACCESS_TOKEN が必要です"
            )
        self.base = f"https://{domain}/admin/api/{API_VERSION}"
        self.token = token
        self.fee_rate = fee_rate

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        req = urllib.request.Request(
            f"{self.base}{path}",
            method=method,
            headers={
                "X-Shopify-Access-Token": self.token,
                "Content-Type": "application/json",
            },
            data=json.dumps(payload).encode() if payload is not None else None,
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Shopify API error {e.code}: {e.read().decode()[:500]}") from e

    def publish(self, listing: Listing) -> str:
        payload = {
            "product": {
                "title": listing.title,
                "body_html": listing.description.replace("\n", "<br>"),
                "status": "active",
                "tags": listing.category,
                "variants": [{
                    "sku": listing.sku,
                    "price": str(int(listing.price)),
                    "inventory_management": "shopify",
                    "inventory_quantity": listing.stock,
                }],
                "images": [{"src": listing.image_url}] if listing.image_url else [],
            }
        }
        result = self._request("POST", "/products.json", payload)
        return str(result["product"]["id"])

    def update(self, listing: Listing) -> None:
        if not listing.channel_id or listing.channel_id.startswith("local-"):
            return
        status = "active" if listing.status == "active" else "draft"
        payload = {
            "product": {
                "id": int(listing.channel_id),
                "status": status,
                "variants": [{"sku": listing.sku, "price": str(int(listing.price))}],
            }
        }
        self._request("PUT", f"/products/{listing.channel_id}.json", payload)

    def fetch_orders(self) -> list[Order]:
        result = self._request("GET", "/orders.json?status=open&financial_status=paid")
        orders: list[Order] = []
        for o in result.get("orders", []):
            for item in o.get("line_items", []):
                if not item.get("sku"):
                    continue
                price = float(item["price"])
                orders.append(Order(
                    order_id=f'{o["id"]}-{item["id"]}',
                    sku=item["sku"],
                    qty=int(item["quantity"]),
                    sale_price=price,
                    ordered_at=o.get("created_at", ""),
                    fee=round(price * int(item["quantity"]) * self.fee_rate, 1),
                ))
        return orders


    def mark_shipped(self, order: Order) -> None:
        """Shopify Fulfillment Orders API で発送登録+顧客通知。"""
        shopify_order_id = order.order_id.split("-")[0]
        try:
            fo = self._request("GET", f"/orders/{shopify_order_id}/fulfillment_orders.json")
            open_fos = [x for x in fo.get("fulfillment_orders", [])
                        if x.get("status") in ("open", "in_progress")]
            if not open_fos:
                print(f"  [warn] {order.order_id}: 発送可能なfulfillment_orderがありません")
                return
            payload = {
                "fulfillment": {
                    "line_items_by_fulfillment_order": [
                        {"fulfillment_order_id": open_fos[0]["id"]}
                    ],
                    "tracking_info": {
                        "number": order.tracking_number,
                        "company": order.carrier or "Other",
                    },
                    "notify_customer": True,
                }
            }
            self._request("POST", "/fulfillments.json", payload)
        except RuntimeError as e:
            print(f"  [warn] {order.order_id}: 発送登録に失敗 {e}")


def build_channel(cfg: Config) -> ChannelBase:
    ctype = cfg["channel"]["type"]
    if ctype == "local":
        return LocalChannel(cfg.output_dir, cfg.state_dir)
    if ctype == "shopify":
        return ShopifyChannel(
            cfg["channel"]["shopify_domain"],
            cfg.shopify_token(),
            cfg["channel"]["fee_rate"],
        )
    raise ValueError(f"未対応のチャネルタイプ: {ctype}")
