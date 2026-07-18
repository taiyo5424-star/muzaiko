"""仕入先アダプタ。

- CsvSupplier: CSVフィード(卸業者からの商品リスト)を読む。今すぐ動く。
- AliExpressSupplier: API連携のスタブ。APIキー取得後に実装を差し込む。
"""
from __future__ import annotations

import csv
from pathlib import Path

from .config import Config
from .models import SupplierProduct


class SupplierBase:
    def fetch_products(self) -> list[SupplierProduct]:
        raise NotImplementedError

    def place_order(self, sku: str, qty: int, shipping_address: dict) -> str:
        """発注して仕入先注文IDを返す。自動発注非対応なら空文字を返す。"""
        raise NotImplementedError


class CsvSupplier(SupplierBase):
    """CSVフィード仕入先。列: sku,title,cost,stock,shipping_cost,shipping_days,weight_g,category,image_url,product_url"""

    REQUIRED = {"sku", "title", "cost", "stock"}

    def __init__(self, feed_path: Path):
        self.feed_path = feed_path

    def fetch_products(self) -> list[SupplierProduct]:
        products: list[SupplierProduct] = []
        with open(self.feed_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            missing = self.REQUIRED - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"フィードに必須列がありません: {missing}")
            for row in reader:
                try:
                    products.append(SupplierProduct(
                        sku=row["sku"].strip(),
                        title=row["title"].strip(),
                        cost=float(row["cost"]),
                        stock=int(row["stock"]),
                        shipping_cost=float(row.get("shipping_cost") or 0),
                        shipping_days=int(row.get("shipping_days") or 7),
                        weight_g=int(row.get("weight_g") or 0),
                        category=(row.get("category") or "").strip(),
                        image_url=(row.get("image_url") or "").strip(),
                        product_url=(row.get("product_url") or "").strip(),
                    ))
                except (ValueError, KeyError) as e:
                    print(f"  [skip] 行の解析に失敗 sku={row.get('sku')}: {e}")
        return products

    def place_order(self, sku: str, qty: int, shipping_address: dict) -> str:
        # CSV仕入先は自動発注不可。発注キューへの出力で人間が処理する。
        return ""


class AliExpressSupplier(SupplierBase):
    """AliExpress Open Platform 連携のスタブ。

    利用するには https://openservice.aliexpress.com でアプリ登録し、
    Dropshipping API (aliexpress.ds.*) のキーを取得して実装を追加する。
    """

    def __init__(self, app_key: str, app_secret: str):
        self.app_key = app_key
        self.app_secret = app_secret

    def fetch_products(self) -> list[SupplierProduct]:
        raise NotImplementedError(
            "AliExpress APIキーを設定し、aliexpress.ds.product.get の呼び出しを実装してください"
        )

    def place_order(self, sku: str, qty: int, shipping_address: dict) -> str:
        raise NotImplementedError(
            "aliexpress.ds.order.create の呼び出しを実装してください"
        )


def build_supplier(cfg: Config) -> SupplierBase:
    stype = cfg["supplier"]["type"]
    if stype == "csv":
        return CsvSupplier(cfg.root / cfg["supplier"]["feed_path"])
    if stype == "aliexpress":
        import os
        return AliExpressSupplier(
            os.environ.get("ALIEXPRESS_APP_KEY", ""),
            os.environ.get("ALIEXPRESS_APP_SECRET", ""),
        )
    raise ValueError(f"未対応の仕入先タイプ: {stype}")
