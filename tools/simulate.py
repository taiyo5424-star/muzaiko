"""30日間の運用シミュレーション。

価格弾力性のある需要モデルで受注を生成しながら、
research → publish → (毎日) sync → orders → optimize → KPI記録
のループを回し、価格実験・自動入替が実際に機能する様子を確認する。

実行:  python tools/simulate.py [日数]
出力:  out/dashboard.html(シミュレーション結果のダッシュボード)、収益レポート
"""
from __future__ import annotations

import random
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from muzaiko.analytics import report
from muzaiko.channels import LocalChannel
from muzaiko.config import Config
from muzaiko.dashboard import render_dashboard
from muzaiko.listing_gen import ListingGenerator
from muzaiko.models import Order
from muzaiko.optimizer import Optimizer
from muzaiko.pricing import PricingEngine
from muzaiko.research import Researcher
from muzaiko.storage import Store
from muzaiko.suppliers import CsvSupplier
from muzaiko.sync import sync_listings

ELASTICITY = 3.0     # 価格弾力性(値上げに対する需要減の強さ)
BASE_DEMAND = 0.55   # スコア100の商品の1日あたり期待販売数


def simulate(days: int = 30, seed: int = 42) -> None:
    random.seed(seed)
    tmp = Path(tempfile.mkdtemp(prefix="muzaiko-sim-"))
    try:
        (tmp / "data").mkdir()
        shutil.copy(REPO_ROOT / "data" / "sample_supplier.csv", tmp / "data")
        cfg = Config.load(tmp)
        store = Store(cfg.state_dir)
        pricing = PricingEngine(cfg)
        channel = LocalChannel(cfg.output_dir, cfg.state_dir)
        supplier = CsvSupplier(tmp / "data" / "sample_supplier.csv")
        start = datetime(2026, 7, 1, 9, 0, 0)

        # Day 0: リサーチ→出品
        products = supplier.fetch_products()
        selected = Researcher(cfg, pricing).select(products)
        gen = ListingGenerator(cfg, pricing)
        listings = {}
        initial_prices = {}
        for p, score in selected:
            l = gen.build(p, score)
            l.created_at = start.isoformat(timespec="seconds")
            l.channel_id = channel.publish(l)
            listings[p.sku] = l
            initial_prices[p.sku] = l.price
        print(f"Day 0: {len(listings)}件を出品\n")

        orders: dict[str, Order] = {}
        optimizer = Optimizer(cfg, pricing, store)
        oid = 0

        for day in range(1, days + 1):
            now = start + timedelta(days=day)
            # --- 需要生成(価格弾力性モデル) ---
            for sku, l in listings.items():
                if l.status != "active":
                    continue
                lam = (BASE_DEMAND * (l.score / 100)
                       * (initial_prices[sku] / l.price) ** ELASTICITY)
                qty = int(lam) + (1 if random.random() < lam - int(lam) else 0)
                for _ in range(qty):
                    oid += 1
                    orders[f"S-{oid}"] = Order(
                        order_id=f"S-{oid}", sku=sku, qty=1, sale_price=l.price,
                        ordered_at=(now - timedelta(hours=random.randint(1, 20))
                                    ).isoformat(timespec="seconds"),
                        fee=round(l.price * cfg["channel"]["fee_rate"], 1),
                        status="done",
                    )
            # --- 日次パイプライン ---
            sync_listings(listings, products, pricing, channel)
            stats = optimizer.run(listings, orders, channel, now=now)
            if any(stats.values()):
                print(f"Day {day}: {stats}")
            # --- KPI記録 ---
            sold = list(orders.values())
            revenue = sum(o.revenue for o in sold)
            fees = sum(o.fee for o in sold)
            cogs = sum(listings[o.sku].cost * o.qty for o in sold if o.sku in listings)
            history = store.load_json("kpi_history.json", [])
            history.append({
                "date": now.date().isoformat(),
                "active_listings": sum(1 for l in listings.values() if l.status == "active"),
                "orders": len(sold),
                "revenue": round(revenue),
                "fees": round(fees),
                "cogs": round(cogs),
                "profit": round(revenue - fees - cogs),
            })
            store.save_json("kpi_history.json", history)

        store.save_listings(listings)
        store.save_orders(orders)
        print()
        print(report(listings, orders, pricing))
        out = REPO_ROOT / "out"
        out.mkdir(exist_ok=True)
        render_dashboard(store, out / "dashboard.html")
        print(f"\nシミュレーション完了({days}日間・受注{len(orders)}件)")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    simulate(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
