"""販売チャネルアダプタ。

- LocalChannel: ドライラン。出品は out/ にJSONとして書き出し、受注は state/incoming_orders.json から取り込む。
- ShopifyChannel: Shopify Admin REST API。SHOPIFY_ACCESS_TOKEN 設定で実出品・実受注取得。
- BaseECChannel: BASE API。無料プランで使えるPhase 0推奨チャネル(要OAuthアプリ登録)。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
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

    def fetch_cancelled_ids(self) -> list[str]:
        """チャネル側でキャンセルされた注文ID(注文単位)を返す(対応チャネルのみ)。"""
        return []

    def ack_orders(self) -> None:
        """取込済み受注の永続化完了後に呼ばれる。取込元の消費など(対応チャネルのみ)。"""
        return None

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
        # ファイルの削除は ack_orders(永続化成功後)まで遅延する。
        # 途中でクラッシュしても受注が失われない。重複はorder_idで排除される。
        return [Order.from_dict(d) for d in raw]

    def ack_orders(self) -> None:
        f = self.state_dir / "incoming_orders.json"
        if f.exists():
            f.unlink()


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
        # 1. 出品状態(active/draft)。在庫0の売り越し防止はこの status 切替が担う
        #    (在庫数そのものの同期は InventoryLevel API が必要なため未対応)
        status = "active" if listing.status == "active" else "draft"
        self._request("PUT", f"/products/{listing.channel_id}.json", {
            "product": {"id": int(listing.channel_id), "status": status},
        })
        # 2. 価格は既存バリアントを id 指定で更新する
        #    (id なしの variants を product PUT に含めると新規バリアント扱いになる)
        prod = self._request("GET", f"/products/{listing.channel_id}.json")
        variants = prod.get("product", {}).get("variants", [])
        target = next((v for v in variants if v.get("sku") == listing.sku),
                      variants[0] if variants else None)
        if target and str(target.get("price")) != str(int(listing.price)):
            self._request("PUT", f"/variants/{target['id']}.json", {
                "variant": {"id": target["id"], "price": str(int(listing.price))},
            })

    def _paged_orders(self, params: str) -> list[dict]:
        """since_id ベースのページネーションで全件取得。"""
        results: list[dict] = []
        since_id = 0
        while True:
            page = self._request(
                "GET", f"/orders.json?{params}&limit=250&since_id={since_id}"
            ).get("orders", [])
            results.extend(page)
            if len(page) < 250:
                return results
            since_id = max(int(o["id"]) for o in page)

    def fetch_orders(self) -> list[Order]:
        orders: list[Order] = []
        for o in self._paged_orders("status=open&financial_status=paid"):
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
                    shipping_address=o.get("shipping_address") or {},
                ))
        return orders

    def fetch_cancelled_ids(self) -> list[str]:
        return [str(o["id"]) for o in self._paged_orders("status=cancelled&fields=id")]


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


class BaseECChannel(ChannelBase):
    """BASE(thebase.com)API アダプタ。

    必要な環境変数:
      BASE_CLIENT_ID / BASE_CLIENT_SECRET / BASE_REFRESH_TOKEN
    BASE Developers(developers.thebase.in)でアプリ登録し、
    read_items / write_items / read_orders スコープで認可して取得する。
    アクセストークンは短命のため refresh_token グラントで毎回取得する。
    ※ API仕様は実アカウントで1商品テストしてから本運用に入ること。
    """

    API = "https://api.thebase.in"

    def __init__(self, fee_rate: float):
        self.client_id = os.environ.get("BASE_CLIENT_ID", "")
        self.client_secret = os.environ.get("BASE_CLIENT_SECRET", "")
        self.refresh_token = os.environ.get("BASE_REFRESH_TOKEN", "")
        if not (self.client_id and self.client_secret and self.refresh_token):
            raise ValueError(
                "BASE利用には環境変数 BASE_CLIENT_ID / BASE_CLIENT_SECRET / "
                "BASE_REFRESH_TOKEN が必要です(developers.thebase.in でアプリ登録)"
            )
        self.fee_rate = fee_rate
        self._access_token = ""

    def _token(self) -> str:
        if self._access_token:
            return self._access_token
        data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
        }).encode()
        req = urllib.request.Request(f"{self.API}/1/oauth/token", data=data, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            self._access_token = json.loads(resp.read().decode())["access_token"]
        return self._access_token

    def _request(self, method: str, path: str, form: dict | None = None) -> dict:
        req = urllib.request.Request(
            f"{self.API}{path}",
            method=method,
            headers={"Authorization": f"Bearer {self._token()}"},
            data=urllib.parse.urlencode(form).encode() if form is not None else None,
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"BASE API error {e.code}: {e.read().decode()[:500]}") from e

    def publish(self, listing: Listing) -> str:
        result = self._request("POST", "/1/items/add", {
            "title": listing.title,
            "detail": listing.description,
            "price": int(listing.price),
            "stock": listing.stock,
            "visible": 1,
            "identifier": listing.sku,
        })
        return str(result["item"]["item_id"])

    def update(self, listing: Listing) -> None:
        if not listing.channel_id or listing.channel_id.startswith("local-"):
            return
        self._request("POST", "/1/items/edit", {
            "item_id": listing.channel_id,
            "price": int(listing.price),
            "stock": listing.stock if listing.status == "active" else 0,
            "visible": 1 if listing.status == "active" else 0,
        })

    @staticmethod
    def _ordered_at(value) -> str:
        """BASEの ordered はUnixタイムスタンプ。ISO8601に変換する。"""
        try:
            from datetime import datetime
            return datetime.fromtimestamp(int(value)).isoformat(timespec="seconds")
        except (ValueError, TypeError, OSError):
            return str(value or "")

    def fetch_orders(self) -> list[Order]:
        orders: list[Order] = []
        offset = 0
        while True:
            result = self._request("GET", f"/1/orders?limit=100&offset={offset}")
            page = result.get("orders", [])
            for o in page:
                key = o.get("unique_key", "")
                if not key:
                    continue
                detail = self._request("GET", f"/1/orders/detail/{key}")
                for item in detail.get("order", {}).get("order_items", []):
                    price = float(item.get("price", 0))
                    qty = int(item.get("amount", 1))
                    orders.append(Order(
                        order_id=f"{key}-{item.get('order_item_id', '')}",
                        sku=str(item.get("identifier") or item.get("item_id") or ""),
                        qty=qty,
                        sale_price=price,
                        ordered_at=self._ordered_at(o.get("ordered")),
                        fee=round(price * qty * self.fee_rate, 1),
                    ))
            if len(page) < 100:
                return orders
            offset += 100


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
    if ctype == "base":
        return BaseECChannel(cfg["channel"]["fee_rate"])
    if ctype == "ebay":
        from .ebay import EbayChannel
        return EbayChannel(cfg["channel"]["fee_rate"], cfg["channel"].get("ebay", {}))
    raise ValueError(f"未対応のチャネルタイプ: {ctype}")
