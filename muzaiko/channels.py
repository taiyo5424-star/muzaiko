"""販売チャネルアダプタ。

- LocalChannel: ドライラン。出品は out/ にHTML/JSONとして書き出し、受注は state/incoming_orders.json から取り込む。
- ShopifyChannel: Shopify Admin REST API。SHOPIFY_ACCESS_TOKEN 設定で実出品・実受注取得。
- ShopeeExportChannel: Shopee(東南アジア)輸出向け。セラーセンターの一括アップロード用CSVを生成する。
  Shopeeの無在庫はプレオーダー(発送期限を最大10日に延長)を設定するのが正規ルート。
  発送期限(DTS)超過や在庫切れキャンセルはペナルティ対象のため、sync との併用が前提。
"""
from __future__ import annotations

import csv
import json
import urllib.error
import urllib.request
from pathlib import Path

from .config import Config
from .models import Listing, Order

API_VERSION = "2024-07"

# Shopeeの通常発送期限(営業日)。これを超えるリードタイムはプレオーダー設定にする。
SHOPEE_STANDARD_DTS_DAYS = 2


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


class ShopeeExportChannel(ChannelBase):
    """Shopee輸出用チャネル。

    Shopee Open Platform APIは法人審査+パートナー契約が必要なため、
    個人セラーでもすぐ使える「セラーセンター一括アップロードCSV」を生成する。
    out/shopee/mass_upload.csv をセラーセンターの一括出品ツールに読み込ませる運用。
    価格は fx_rate で現地通貨に換算して出力する。
    """

    def __init__(self, output_dir: Path, state_dir: Path,
                 currency: str, fx_rate: float, max_days_to_ship: int):
        self.dir = output_dir / "shopee"
        self.listings_dir = self.dir / "listings"
        self.listings_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir = state_dir
        self.currency = currency
        self.fx_rate = fx_rate
        self.max_days_to_ship = max_days_to_ship

    def _row(self, listing: Listing) -> dict:
        lead = listing.shipping_days or SHOPEE_STANDARD_DTS_DAYS
        days_to_ship = min(lead, self.max_days_to_ship)
        if lead > self.max_days_to_ship:
            print(f"  [警告] {listing.sku}: リードタイム{lead}日はShopeeプレオーダー上限"
                  f"({self.max_days_to_ship}日)超。DTS違反ペナルティのリスクがあります")
        return {
            "sku": listing.sku,
            "product_name": listing.title,
            "description": listing.description,
            f"price_{self.currency.lower()}": round(listing.price * self.fx_rate, 2),
            "stock": listing.stock if listing.status == "active" else 0,
            "category": listing.category,
            "image_url": listing.image_url,
            "days_to_ship": days_to_ship,
            "pre_order": "yes" if lead > SHOPEE_STANDARD_DTS_DAYS else "no",
        }

    def _rebuild_csv(self) -> None:
        rows = []
        for f in sorted(self.listings_dir.glob("*.json")):
            rows.append(json.loads(f.read_text(encoding="utf-8")))
        if not rows:
            return
        with open(self.dir / "mass_upload.csv", "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def publish(self, listing: Listing) -> str:
        row = self._row(listing)
        (self.listings_dir / f"{listing.sku}.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
        self._rebuild_csv()
        return f"shopee-{listing.sku}"

    def update(self, listing: Listing) -> None:
        self.publish(listing)

    def fetch_orders(self) -> list[Order]:
        # セラーセンターからエクスポートした受注を state/incoming_orders.json に置く運用
        f = self.state_dir / "incoming_orders.json"
        if not f.exists():
            return []
        raw = json.loads(f.read_text(encoding="utf-8"))
        orders = [Order.from_dict(d) for d in raw]
        f.unlink()
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
    if ctype == "shopee_export":
        return ShopeeExportChannel(
            cfg.output_dir,
            cfg.state_dir,
            cfg["channel"]["currency"],
            cfg["channel"]["fx_rate"],
            cfg["channel"]["max_days_to_ship"],
        )
    raise ValueError(f"未対応のチャネルタイプ: {ctype}")
