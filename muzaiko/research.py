"""商品リサーチ: 仕入先フィードから出品候補を選定・スコアリングする。"""
from __future__ import annotations

from .config import Config
from .models import SupplierProduct
from .pricing import PricingEngine


class Researcher:
    def __init__(self, cfg: Config, pricing: PricingEngine):
        r = cfg["research"]
        self.max_listings = r["max_listings"]
        self.max_cost = r["max_cost"]
        self.min_stock = r["min_stock"]
        self.max_shipping_days = r["max_shipping_days"]
        self.min_expected_margin = r["min_expected_margin"]
        self.trend_keywords = r["trend_keywords"]
        self.pricing = pricing

    def _passes_filters(self, p: SupplierProduct) -> tuple[bool, str]:
        if p.cost > self.max_cost:
            return False, f"原価{p.cost:.0f}円が上限超"
        if p.stock < self.min_stock:
            return False, f"在庫{p.stock}が下限未満"
        if p.shipping_days > self.max_shipping_days:
            return False, f"リードタイム{p.shipping_days}日が上限超"
        expected_price = self.pricing.initial_price(p.landed_cost)
        margin = self.pricing.margin(expected_price, p.landed_cost)
        if margin < self.min_expected_margin:
            return False, f"期待粗利{margin:.0f}円が下限未満"
        return True, ""

    def trend_hits(self, p: SupplierProduct) -> list[str]:
        """タイトル/カテゴリに一致したトレンドキーワードを返す。"""
        text = f"{p.title} {p.category}"
        return [kw for kw in self.trend_keywords if kw and kw in text]

    def score(self, p: SupplierProduct) -> float:
        """0-100点。粗利額を主軸に、在庫の厚さ・配送速度・トレンド適合で加点。

        トレンド加点は越境ECの売れ筋(トレカ/ホビー/アニメの推し活・
        コレクター消費)に合致する商品を優先するためのもの。
        """
        price = self.pricing.initial_price(p.landed_cost)
        margin = self.pricing.margin(price, p.landed_cost)
        margin_score = min(margin / 2000, 1.0) * 50          # 粗利2,000円で満点
        stock_score = min(p.stock / 50, 1.0) * 15            # 在庫50で満点
        speed_score = max(0.0, 1 - p.shipping_days / self.max_shipping_days) * 15
        trend_score = min(len(self.trend_hits(p)) / 2, 1.0) * 20  # 2キーワード一致で満点
        return round(margin_score + stock_score + speed_score + trend_score, 1)

    def select(self, products: list[SupplierProduct]) -> list[tuple[SupplierProduct, float]]:
        """フィルタ→スコア降順で上位を返す。"""
        candidates: list[tuple[SupplierProduct, float]] = []
        for p in products:
            ok, reason = self._passes_filters(p)
            if not ok:
                print(f"  [除外] {p.sku} {p.title[:20]}: {reason}")
                continue
            candidates.append((p, self.score(p)))
        candidates.sort(key=lambda t: t[1], reverse=True)
        return candidates[: self.max_listings]
