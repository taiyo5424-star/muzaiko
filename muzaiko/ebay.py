"""eBay輸出チャネル(Phase 2)— Sell API アダプタ。

必要なもの:
  1. developer.ebay.com でアプリ登録(Production キー)
  2. ユーザー認可フローで refresh_token を取得
     (スコープ: sell.inventory, sell.fulfillment)
  3. 環境変数 EBAY_CLIENT_ID / EBAY_CLIENT_SECRET / EBAY_REFRESH_TOKEN
  4. config.json:
     "channel": {
       "type": "ebay",
       "fee_rate": 0.18,                # FVF+海外決済+為替の実効値(STRATEGY.md)
       "ebay": {
         "marketplace_id": "EBAY_US",
         "exchange_rate_jpy_usd": 155,  # 円建て価格をUSDに換算するレート
         "fulfillment_policy_id": "",   # Seller Hubで作成したポリシーID(3つ必須)
         "payment_policy_id": "",
         "return_policy_id": "",
         "merchant_location_key": "default"
       }
     }

※ 実キー取得後、Sandbox → 1商品の実出品テストを経てから本運用に入ること。
   出品は Inventory API の inventory_item → offer → publish の3段階。
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .models import Listing, Order

API = "https://api.ebay.com"
TOKEN_URL = f"{API}/identity/v1/oauth2/token"
SCOPES = ("https://api.ebay.com/oauth/api_scope/sell.inventory "
          "https://api.ebay.com/oauth/api_scope/sell.fulfillment")


class EbayChannel:
    """eBay Sell API アダプタ(ChannelBase互換)。内部価格はJPY、出品時にUSD換算。"""

    def __init__(self, fee_rate: float, options: dict):
        self.client_id = os.environ.get("EBAY_CLIENT_ID", "")
        self.client_secret = os.environ.get("EBAY_CLIENT_SECRET", "")
        self.refresh_token = os.environ.get("EBAY_REFRESH_TOKEN", "")
        if not (self.client_id and self.client_secret and self.refresh_token):
            raise ValueError(
                "eBay利用には環境変数 EBAY_CLIENT_ID / EBAY_CLIENT_SECRET / "
                "EBAY_REFRESH_TOKEN が必要です(developer.ebay.com でアプリ登録)"
            )
        self.fee_rate = fee_rate
        self.marketplace = options.get("marketplace_id", "EBAY_US")
        self.rate = float(options.get("exchange_rate_jpy_usd", 155))
        self.policies = {
            "fulfillmentPolicyId": options.get("fulfillment_policy_id", ""),
            "paymentPolicyId": options.get("payment_policy_id", ""),
            "returnPolicyId": options.get("return_policy_id", ""),
        }
        self.location_key = options.get("merchant_location_key", "default")
        self._access_token = ""
        self._offer_ids: dict[str, str] = {}  # sku -> offer_id

    # --- auth ---
    def _token(self) -> str:
        if self._access_token:
            return self._access_token
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "scope": SCOPES,
        }).encode()
        req = urllib.request.Request(TOKEN_URL, data=data, method="POST", headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            self._access_token = json.loads(resp.read().decode())["access_token"]
        return self._access_token

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        req = urllib.request.Request(
            f"{API}{path}",
            method=method,
            headers={
                "Authorization": f"Bearer {self._token()}",
                "Content-Type": "application/json",
                "Content-Language": "en-US",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
            },
            data=json.dumps(payload).encode() if payload is not None else None,
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"eBay API error {e.code}: {e.read().decode()[:500]}") from e

    def _usd(self, jpy: float) -> str:
        return f"{jpy / self.rate:.2f}"

    # --- ChannelBase interface ---
    def publish(self, listing: Listing) -> str:
        # 1. inventory item(商品マスタ+在庫)
        self._request("PUT", f"/sell/inventory/v1/inventory_item/{listing.sku}", {
            "product": {
                "title": listing.title[:80],
                "description": listing.description,
                "imageUrls": [listing.image_url] if listing.image_url else [],
            },
            "condition": "NEW",
            "availability": {"shipToLocationAvailability": {"quantity": listing.stock}},
        })
        # 2. offer(価格・ポリシー)
        offer_payload = {
            "sku": listing.sku,
            "marketplaceId": self.marketplace,
            "format": "FIXED_PRICE",
            "availableQuantity": listing.stock,
            "pricingSummary": {"price": {"value": self._usd(listing.price),
                                         "currency": "USD"}},
            "listingPolicies": {k: v for k, v in self.policies.items() if v},
            "merchantLocationKey": self.location_key,
        }
        result = self._request("POST", "/sell/inventory/v1/offer", offer_payload)
        offer_id = str(result.get("offerId", ""))
        self._offer_ids[listing.sku] = offer_id
        # 3. publish
        pub = self._request("POST", f"/sell/inventory/v1/offer/{offer_id}/publish", {})
        return str(pub.get("listingId", offer_id))

    def update(self, listing: Listing) -> None:
        qty = listing.stock if listing.status == "active" else 0
        self._request("PUT", f"/sell/inventory/v1/inventory_item/{listing.sku}", {
            "product": {"title": listing.title[:80]},
            "condition": "NEW",
            "availability": {"shipToLocationAvailability": {"quantity": qty}},
        })
        offer_id = self._offer_ids.get(listing.sku)
        if offer_id:
            self._request("PUT", f"/sell/inventory/v1/offer/{offer_id}", {
                "sku": listing.sku,
                "marketplaceId": self.marketplace,
                "format": "FIXED_PRICE",
                "availableQuantity": qty,
                "pricingSummary": {"price": {"value": self._usd(listing.price),
                                             "currency": "USD"}},
                "listingPolicies": {k: v for k, v in self.policies.items() if v},
                "merchantLocationKey": self.location_key,
            })

    def fetch_orders(self) -> list[Order]:
        result = self._request(
            "GET", "/sell/fulfillment/v1/order?filter=orderfulfillmentstatus:"
                   "%7BNOT_STARTED%7CIN_PROGRESS%7D&limit=50")
        orders: list[Order] = []
        for o in result.get("orders", []):
            for li in o.get("lineItems", []):
                usd = float(li.get("total", {}).get("value", 0))
                jpy = usd * self.rate
                orders.append(Order(
                    order_id=f'{o.get("orderId", "")}-{li.get("lineItemId", "")}',
                    sku=li.get("sku", ""),
                    qty=int(li.get("quantity", 1)),
                    sale_price=round(jpy / max(int(li.get("quantity", 1)), 1), 1),
                    ordered_at=o.get("creationDate", ""),
                    fee=round(jpy * self.fee_rate, 1),
                ))
        return orders

    def mark_shipped(self, order: Order) -> None:
        ebay_order_id = order.order_id.rsplit("-", 1)[0]
        line_item_id = order.order_id.rsplit("-", 1)[-1]
        try:
            self._request(
                "POST",
                f"/sell/fulfillment/v1/order/{ebay_order_id}/shipping_fulfillment",
                {
                    "lineItems": [{"lineItemId": line_item_id, "quantity": order.qty}],
                    "shippingCarrierCode": order.carrier or "JapanPost",
                    "trackingNumber": order.tracking_number,
                },
            )
        except RuntimeError as e:
            print(f"  [warn] {order.order_id}: eBay発送登録に失敗 {e}")
