"""ドメインモデル定義。"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class SupplierProduct:
    """仕入先(サプライヤー)の商品1件。"""

    sku: str
    title: str
    cost: float                 # 仕入原価(円)
    stock: int                  # 仕入先在庫数
    shipping_cost: float = 0.0  # 発送コスト(円)
    shipping_days: int = 7      # 出荷までの日数
    weight_g: int = 0
    category: str = ""
    image_url: str = ""
    product_url: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def landed_cost(self) -> float:
        """商品原価+送料の合計。"""
        return self.cost + self.shipping_cost

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SupplierProduct":
        return cls(**d)


@dataclass
class Listing:
    """販売チャネル上の出品1件。"""

    sku: str
    title: str
    description: str
    price: float
    cost: float                  # landed cost snapshot
    stock: int
    status: str = "draft"        # draft | active | paused | delisted
    channel_id: str = ""         # チャネル側の商品ID
    score: float = 0.0           # リサーチ時のスコア
    image_url: str = ""
    category: str = ""
    created_at: str = ""         # 出品日時 ISO8601

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Listing":
        return cls(**d)


@dataclass
class Order:
    """受注1件。"""

    order_id: str
    sku: str
    qty: int
    sale_price: float            # 販売単価(円)
    ordered_at: str = ""         # ISO8601
    fee: float = 0.0             # 販売手数料(円)
    status: str = "new"          # new | to_purchase | purchased | shipped | done | cancelled
    supplier_order_id: str = ""
    customer_note: str = ""
    tracking_number: str = ""
    carrier: str = ""

    @property
    def revenue(self) -> float:
        return self.sale_price * self.qty

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Order":
        return cls(**d)
