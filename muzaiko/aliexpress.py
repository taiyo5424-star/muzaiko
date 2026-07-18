"""AliExpress Open Platform (Dropshipping API) クライアント。

必要なもの:
  1. https://openservice.aliexpress.com でアプリ登録(Drop Shipping カテゴリ)
  2. 環境変数 ALIEXPRESS_APP_KEY / ALIEXPRESS_APP_SECRET / ALIEXPRESS_ACCESS_TOKEN
  3. data/aliexpress_products.txt に扱いたい商品ID(1行1ID)

署名方式は公開仕様(sign_method=sha256, HMAC-SHA256, パラメータをキー順連結)で
実装している。※実キー取得後に必ず1商品でテストしてから本運用に入ること。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

GATEWAY = "https://api-sg.aliexpress.com/sync"


class AliExpressClient:
    def __init__(self, app_key: str, app_secret: str, access_token: str = ""):
        if not app_key or not app_secret:
            raise ValueError("ALIEXPRESS_APP_KEY / ALIEXPRESS_APP_SECRET を設定してください")
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = access_token

    def _sign(self, params: dict[str, str]) -> str:
        base = "".join(f"{k}{params[k]}" for k in sorted(params))
        return hmac.new(
            self.app_secret.encode(), base.encode(), hashlib.sha256
        ).hexdigest().upper()

    def call(self, method: str, biz_params: dict | None = None) -> dict:
        params: dict[str, str] = {
            "app_key": self.app_key,
            "method": method,
            "timestamp": str(int(time.time() * 1000)),
            "sign_method": "sha256",
            "v": "2.0",
            "format": "json",
        }
        if self.access_token:
            params["session"] = self.access_token
        for k, v in (biz_params or {}).items():
            params[k] = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        params["sign"] = self._sign(params)
        req = urllib.request.Request(
            GATEWAY,
            data=urllib.parse.urlencode(params).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
        if "error_response" in result:
            raise RuntimeError(f"AliExpress APIエラー: {result['error_response']}")
        return result

    # --- Dropshipping API ---
    def product_get(self, product_id: str, ship_to: str = "JP") -> dict:
        """商品情報(価格・在庫)を取得。"""
        return self.call("aliexpress.ds.product.get", {
            "product_id": product_id,
            "ship_to_country": ship_to,
            "target_currency": "JPY",
            "target_language": "ja",
        })

    def order_create(self, product_id: str, sku_attr: str, qty: int,
                     address: dict) -> str:
        """発注してAliExpress注文IDを返す。

        address 例:
          {"full_name": "山田太郎", "country": "JP", "province": "Tokyo",
           "city": "Shibuya", "address": "1-2-3", "zip": "150-0001",
           "phone_country": "+81", "mobile_no": "9012345678"}
        """
        result = self.call("aliexpress.ds.order.create", {
            "param_place_order_request4_open_api_d_t_o": {
                "logistics_address": address,
                "product_items": [{
                    "product_id": product_id,
                    "sku_attr": sku_attr,
                    "product_count": qty,
                }],
            }
        })
        body = result.get("aliexpress_ds_order_create_response", {}).get("result", {})
        ids = body.get("order_list", {}).get("number", [])
        return str(ids[0]) if ids else ""

    def tracking_get(self, order_id: str) -> dict:
        """発送状況・追跡番号を取得。"""
        return self.call("aliexpress.ds.order.tracking.get", {
            "ae_order_id": order_id,
        })


def load_product_ids(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line.strip() for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
