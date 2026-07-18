"""自動最適化エンジン: 収益最大化アクションを提案で終わらせず自動実行する。

1. 価格実験: 売れ筋SKUの価格を自動で引き上げ、評価期間後に
   売上レート(販売速度×価格)がベースラインを維持していれば新価格を採用、
   悪化していれば旧価格へ自動ロールバック。
2. 赤字SKUの自動停止。
3. 一定期間売れない出品(stale)の自動入替(delist → 次回リサーチで新商品が入る)。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .channels import ChannelBase
from .config import Config
from .models import Listing, Order
from .pricing import PricingEngine
from .storage import Store

EXPERIMENTS_FILE = "price_experiments.json"


def _parse_dt(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def _sales_qty(orders: dict[str, Order], sku: str, start: datetime, end: datetime) -> int:
    qty = 0
    for o in orders.values():
        if o.sku != sku or o.status == "cancelled":
            continue
        dt = _parse_dt(o.ordered_at)
        if dt and start <= dt < end:
            qty += o.qty
    return qty


class Optimizer:
    def __init__(self, cfg: Config, pricing: PricingEngine, store: Store):
        o = cfg["optimizer"]
        self.enabled = o["enabled"]
        self.price_step = o["price_step"]
        self.min_sales_to_test = o["min_sales_to_test"]
        self.eval_window_days = o["eval_window_days"]
        self.stale_days = o["stale_days"]
        self.auto_delist_loss = o["auto_delist_loss"]
        self.pricing = pricing
        self.store = store

    def run(
        self,
        listings: dict[str, Listing],
        orders: dict[str, Order],
        channel: ChannelBase,
        now: datetime | None = None,
    ) -> dict[str, int]:
        stats = {"exp_started": 0, "exp_kept": 0, "exp_rolled_back": 0,
                 "loss_delisted": 0, "stale_delisted": 0}
        if not self.enabled:
            return stats
        now = now or datetime.now()
        window = timedelta(days=self.eval_window_days)
        experiments: dict[str, dict] = self.store.load_json(EXPERIMENTS_FILE, {})

        # --- 1. 進行中の価格実験を評価 ---
        for sku, exp in experiments.items():
            if exp.get("status") != "running" or sku not in listings:
                continue
            # 停止中(在庫切れ等)の期間は販売ゼロが価格のせいに見えてしまうため、
            # activeに戻るまで評価を保留する(実験はrunningのまま)
            if listings[sku].status != "active":
                continue
            started = _parse_dt(exp["started_at"])
            if not started or now - started < window:
                continue
            test_qty = _sales_qty(orders, sku, started, now)
            test_days = max((now - started).total_seconds() / 86400, 0.1)
            test_rev_rate = (test_qty / test_days) * exp["new_price"]
            baseline_rev_rate = exp["baseline_velocity"] * exp["old_price"]
            listing = listings[sku]
            if test_rev_rate >= baseline_rev_rate * 0.95:
                exp["status"] = "kept"
                stats["exp_kept"] += 1
                print(f"  [実験採用] {sku}: {exp['old_price']}円→{exp['new_price']}円 "
                      f"(売上レート {baseline_rev_rate:.0f}→{test_rev_rate:.0f}円/日)")
            else:
                listing.price = exp["old_price"]
                # 実験期間中に原価が上がっていた場合、旧価格が下限粗利を割ることが
                # あるため、復元後に最低ラインへクランプする
                clamped, _ = self.pricing.reprice(listing, listing.cost)
                listing.price = max(exp["old_price"], clamped)
                channel.update(listing)
                exp["status"] = "rolled_back"
                stats["exp_rolled_back"] += 1
                print(f"  [実験撤回] {sku}: {exp['new_price']}円→{listing.price:.0f}円に戻す "
                      f"(売上レート {baseline_rev_rate:.0f}→{test_rev_rate:.0f}円/日)")
            exp["evaluated_at"] = now.isoformat(timespec="seconds")

        # --- 2. 新しい価格実験を開始 ---
        for sku, listing in listings.items():
            if listing.status != "active":
                continue
            exp = experiments.get(sku)
            if exp and exp.get("status") == "running":
                continue
            # クールダウン: 前回実験の評価から評価期間が経つまで再実験しない
            if exp:
                evaluated = _parse_dt(exp.get("evaluated_at", ""))
                if evaluated and now - evaluated < window:
                    continue
            # 直近評価期間の販売数がしきい値以上なら値上げ実験
            recent_qty = _sales_qty(orders, sku, now - window, now)
            if recent_qty < self.min_sales_to_test:
                continue
            old_price = int(listing.price)
            new_price = self.pricing._round_psych(old_price * (1 + self.price_step))
            if new_price <= old_price:
                continue
            listing.price = new_price
            channel.update(listing)
            experiments[sku] = {
                "sku": sku,
                "old_price": old_price,
                "new_price": new_price,
                "baseline_velocity": recent_qty / self.eval_window_days,
                "started_at": now.isoformat(timespec="seconds"),
                "status": "running",
            }
            stats["exp_started"] += 1
            print(f"  [実験開始] {sku}: {old_price}円→{new_price}円 "
                  f"(直近{self.eval_window_days}日で{recent_qty}個販売)")

        # --- 3. 赤字SKUの自動停止(受注時原価スナップショットで判定) ---
        if self.auto_delist_loss:
            for sku, listing in listings.items():
                if listing.status != "active":
                    continue
                profit = 0.0
                qty = 0
                for o in orders.values():
                    if o.sku != sku or o.status == "cancelled":
                        continue
                    cost = o.cost_at_order if o.cost_at_order > 0 else listing.cost
                    profit += o.revenue - o.fee - cost * o.qty
                    qty += o.qty
                if qty >= 2 and profit < 0:
                    listing.status = "delisted"
                    channel.update(listing)
                    stats["loss_delisted"] += 1
                    print(f"  [赤字停止] {sku}: 累計利益 {profit:,.0f}円")

        # --- 4. stale出品の自動入替 ---
        for sku, listing in listings.items():
            if listing.status != "active":
                continue
            created = _parse_dt(listing.created_at)
            if not created or now - created < timedelta(days=self.stale_days):
                continue
            if _sales_qty(orders, sku, created, now) == 0:
                listing.status = "delisted"
                channel.update(listing)
                stats["stale_delisted"] += 1
                print(f"  [入替] {sku}: {self.stale_days}日間販売ゼロのため出品枠を解放")

        self.store.save_json(EXPERIMENTS_FILE, experiments)
        return stats
