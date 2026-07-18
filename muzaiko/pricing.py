"""価格エンジン: 初期価格の算出とリプライシング(収益最大化)。"""
from __future__ import annotations

import math

from .config import Config
from .models import Listing


class PricingEngine:
    def __init__(self, cfg: Config):
        p = cfg["pricing"]
        self.target_margin = p["target_margin_rate"]
        self.min_margin_rate = p["min_margin_rate"]
        self.min_margin_jpy = p["min_margin_jpy"]
        self.ending = p["psychological_ending"]
        # DDP(関税セラー負担)向けの上乗せは手数料と同じ扱いで価格に織り込む
        self.fee_rate = cfg["channel"]["fee_rate"] + p["tariff_buffer_rate"]

    def _round_psych(self, price: float) -> int:
        """980円/2,980円のような心理的価格に切り上げ丸め。"""
        base = math.ceil(price / 100) * 100
        return int(base - (100 - self.ending)) if base - (100 - self.ending) >= price else int(base + self.ending)

    def initial_price(self, landed_cost: float) -> int:
        """手数料控除後に目標粗利率を確保する価格。
        price * (1 - fee) - cost = price * (1 - fee) * target_margin を解く。
        """
        price = landed_cost / ((1 - self.fee_rate) * (1 - self.target_margin))
        price = max(price, (landed_cost + self.min_margin_jpy) / (1 - self.fee_rate))
        return self._round_psych(price)

    def margin(self, price: float, landed_cost: float) -> float:
        """手数料控除後の粗利額(円)。"""
        return price * (1 - self.fee_rate) - landed_cost

    def margin_rate(self, price: float, landed_cost: float) -> float:
        net = price * (1 - self.fee_rate)
        return (net - landed_cost) / net if net > 0 else -1.0

    def reprice(self, listing: Listing, new_cost: float) -> tuple[int, str]:
        """仕入原価変動に追従して価格を見直す。(新価格, 理由) を返す。"""
        current_rate = self.margin_rate(listing.price, new_cost)
        if current_rate < self.min_margin_rate or self.margin(listing.price, new_cost) < self.min_margin_jpy:
            new_price = self.initial_price(new_cost)
            return new_price, f"粗利率{current_rate:.1%}が下限割れのため再計算"
        return int(listing.price), "維持"
