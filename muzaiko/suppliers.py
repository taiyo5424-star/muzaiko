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
    """CSVフィード仕入先。

    標準列: sku,title,cost,stock,shipping_cost,shipping_days,weight_g,category,image_url,product_url
    国内卸(TopSeller/NETSEA等)の独自フォーマットは config.supplier.column_map で
    「標準列名 → フィードの列名」を対応付ければコード変更なしで読める。
    文字コードは config.supplier.encoding(Shift_JIS系は "cp932")。
    """

    REQUIRED = ("sku", "title", "cost", "stock")

    def __init__(self, feed_path: Path, encoding: str = "utf-8-sig",
                 column_map: dict[str, str] | None = None):
        self.feed_path = feed_path
        self.encoding = encoding
        self.column_map = column_map or {}

    def _get(self, row: dict, field: str) -> str:
        return (row.get(self.column_map.get(field, field)) or "").strip()

    @staticmethod
    def _num(value: str) -> float:
        """'1,980円' のような表記も数値化する。"""
        cleaned = value.replace(",", "").replace("円", "").strip()
        return float(cleaned) if cleaned else 0.0

    def fetch_products(self) -> list[SupplierProduct]:
        products: list[SupplierProduct] = []
        with open(self.feed_path, encoding=self.encoding, newline="") as f:
            reader = csv.DictReader(f)
            fields = set(reader.fieldnames or [])
            missing = [c for c in self.REQUIRED
                       if self.column_map.get(c, c) not in fields]
            if missing:
                raise ValueError(
                    f"フィードに必須列がありません: {missing} "
                    f"(column_map で列名を対応付けてください。実際の列: {sorted(fields)})"
                )
            for row in reader:
                try:
                    products.append(SupplierProduct(
                        sku=self._get(row, "sku"),
                        title=self._get(row, "title"),
                        cost=self._num(self._get(row, "cost")),
                        stock=int(self._num(self._get(row, "stock"))),
                        shipping_cost=self._num(self._get(row, "shipping_cost")),
                        shipping_days=int(self._num(self._get(row, "shipping_days")) or 7),
                        weight_g=int(self._num(self._get(row, "weight_g"))),
                        category=self._get(row, "category"),
                        image_url=self._get(row, "image_url"),
                        product_url=self._get(row, "product_url"),
                    ))
                except ValueError as e:
                    print(f"  [skip] 行の解析に失敗 sku={self._get(row, 'sku')}: {e}")
        return products

    def place_order(self, sku: str, qty: int, shipping_address: dict) -> str:
        # CSV仕入先は自動発注不可。発注キューへの出力で人間が処理する。
        return ""


class AliExpressSupplier(SupplierBase):
    """AliExpress Dropshipping API 仕入先。

    data/aliexpress_products.txt の商品IDリストから価格・在庫を取得し、
    受注時は aliexpress.ds.order.create で自動発注する。
    ※ 実キー取得後、必ず1商品でテストしてから本運用に入ること。
    """

    def __init__(self, product_ids_path: Path, shipping_address: dict | None = None):
        import os
        from .aliexpress import AliExpressClient
        self.client = AliExpressClient(
            os.environ.get("ALIEXPRESS_APP_KEY", ""),
            os.environ.get("ALIEXPRESS_APP_SECRET", ""),
            os.environ.get("ALIEXPRESS_ACCESS_TOKEN", ""),
        )
        self.product_ids_path = product_ids_path
        self.shipping_address = shipping_address or {}
        self._sku_map: dict[str, tuple[str, str]] = {}  # sku -> (product_id, sku_attr)

    def fetch_products(self) -> list[SupplierProduct]:
        from .aliexpress import load_product_ids
        products: list[SupplierProduct] = []
        for pid in load_product_ids(self.product_ids_path):
            try:
                result = self.client.product_get(pid)
            except Exception as e:
                print(f"  [warn] AliExpress商品 {pid} の取得に失敗: {e}")
                continue
            body = (result.get("aliexpress_ds_product_get_response", {})
                    .get("result", {}))
            info = body.get("ae_item_base_info_dto", {})
            for sku in (body.get("ae_item_sku_info_dtos", {})
                        .get("ae_item_sku_info_d_t_o", [])):
                sku_id = f"AE-{pid}-{sku.get('sku_id', '0')}"
                self._sku_map[sku_id] = (pid, sku.get("sku_attr", ""))
                products.append(SupplierProduct(
                    sku=sku_id,
                    title=info.get("subject", f"AliExpress {pid}"),
                    cost=float(sku.get("offer_sale_price", sku.get("sku_price", 0))),
                    stock=int(sku.get("sku_available_stock", 0)),
                    shipping_days=15,
                    category=info.get("category_id", ""),
                    product_url=f"https://www.aliexpress.com/item/{pid}.html",
                ))
        return products

    def place_order(self, sku: str, qty: int, shipping_address: dict) -> str:
        mapped = self._sku_map.get(sku)
        if mapped is None and sku.startswith("AE-"):
            parts = sku.split("-", 2)
            mapped = (parts[1], "") if len(parts) >= 2 else None
        if mapped is None:
            return ""
        address = shipping_address or self.shipping_address
        if not address:
            return ""  # 配送先未設定なら手動キューに回す
        pid, sku_attr = mapped
        return self.client.order_create(pid, sku_attr, qty, address)


def build_supplier(cfg: Config) -> SupplierBase:
    stype = cfg["supplier"]["type"]
    if stype == "csv":
        return CsvSupplier(
            cfg.root / cfg["supplier"]["feed_path"],
            encoding=cfg["supplier"].get("encoding", "utf-8-sig"),
            column_map=cfg["supplier"].get("column_map", {}),
        )
    if stype == "aliexpress":
        return AliExpressSupplier(cfg.root / "data" / "aliexpress_products.txt")
    raise ValueError(f"未対応の仕入先タイプ: {stype}")
