"""自動最適化エンジンのテスト。"""
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from muzaiko.channels import LocalChannel
from muzaiko.config import Config
from muzaiko.models import Listing, Order
from muzaiko.optimizer import EXPERIMENTS_FILE, Optimizer
from muzaiko.pricing import PricingEngine
from muzaiko.storage import Store


def _listing(sku: str, price: int, cost: float, created_at: str = "") -> Listing:
    return Listing(sku=sku, title=sku, description="", price=price, cost=cost,
                   stock=10, status="active", created_at=created_at)


def _order(oid: str, sku: str, qty: int, price: float, days_ago: float, now: datetime) -> Order:
    return Order(order_id=oid, sku=sku, qty=qty, sale_price=price,
                 ordered_at=(now - timedelta(days=days_ago)).isoformat(timespec="seconds"),
                 fee=price * qty * 0.10)


class OptimizerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = Config.load(self.tmp)
        self.store = Store(self.cfg.state_dir)
        self.pricing = PricingEngine(self.cfg)
        self.channel = LocalChannel(self.cfg.output_dir, self.cfg.state_dir)
        self.opt = Optimizer(self.cfg, self.pricing, self.store)
        self.now = datetime(2026, 7, 18, 12, 0, 0)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_experiment_starts_on_seller(self):
        listings = {"A": _listing("A", 2980, 1500, self.now.isoformat())}
        orders = {f"o{i}": _order(f"o{i}", "A", 1, 2980, i, self.now) for i in range(4)}
        stats = self.opt.run(listings, orders, self.channel, now=self.now)
        self.assertEqual(stats["exp_started"], 1)
        self.assertGreater(listings["A"].price, 2980)
        self.assertEqual(int(listings["A"].price) % 100,
                         self.cfg["pricing"]["psychological_ending"])

    def test_experiment_rollback_when_sales_drop(self):
        listings = {"A": _listing("A", 3180, 1500, self.now.isoformat())}
        self.store.save_json(EXPERIMENTS_FILE, {"A": {
            "sku": "A", "old_price": 2980, "new_price": 3180,
            "baseline_velocity": 1.0,  # 実験前は1個/日
            "started_at": (self.now - timedelta(days=8)).isoformat(timespec="seconds"),
            "status": "running",
        }})
        # 実験期間中の販売ゼロ → ロールバック
        stats = self.opt.run(listings, {}, self.channel, now=self.now)
        self.assertEqual(stats["exp_rolled_back"], 1)
        self.assertEqual(listings["A"].price, 2980)

    def test_experiment_kept_when_sales_hold(self):
        listings = {"A": _listing("A", 3180, 1500, self.now.isoformat())}
        self.store.save_json(EXPERIMENTS_FILE, {"A": {
            "sku": "A", "old_price": 2980, "new_price": 3180,
            "baseline_velocity": 0.5,
            "started_at": (self.now - timedelta(days=8)).isoformat(timespec="seconds"),
            "status": "running",
        }})
        # 実験中も同等ペースで売れている → 新価格を採用
        orders = {f"o{i}": _order(f"o{i}", "A", 1, 3180, i * 2 - 1, self.now)
                  for i in range(1, 5)}  # 1,3,5,7日前の4件
        stats = self.opt.run(listings, orders, self.channel, now=self.now)
        self.assertEqual(stats["exp_kept"], 1)
        self.assertEqual(listings["A"].price, 3180)

    def test_stale_listing_delisted(self):
        old = (self.now - timedelta(days=20)).isoformat(timespec="seconds")
        listings = {"B": _listing("B", 1980, 900, old)}
        stats = self.opt.run(listings, {}, self.channel, now=self.now)
        self.assertEqual(stats["stale_delisted"], 1)
        self.assertEqual(listings["B"].status, "delisted")

    def test_loss_maker_delisted(self):
        listings = {"C": _listing("C", 1000, 1500, self.now.isoformat())}
        orders = {f"o{i}": _order(f"o{i}", "C", 1, 1000, i, self.now) for i in range(2)}
        stats = self.opt.run(listings, orders, self.channel, now=self.now)
        self.assertEqual(stats["loss_delisted"], 1)
        self.assertEqual(listings["C"].status, "delisted")


if __name__ == "__main__":
    unittest.main()
