"""パイプライン全体のスモークテスト(標準ライブラリ unittest)。"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from muzaiko.cli import cmd_orders, cmd_publish, cmd_report, cmd_research, cmd_sync
from muzaiko.config import Config
from muzaiko.pricing import PricingEngine
from muzaiko.storage import Store


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "data").mkdir()
        shutil.copy(REPO_ROOT / "data" / "sample_supplier.csv", self.tmp / "data")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_pricing_guarantees_min_margin(self):
        cfg = Config.load(self.tmp)
        pricing = PricingEngine(cfg)
        for cost in (300, 1000, 5000):
            price = pricing.initial_price(cost)
            self.assertGreaterEqual(pricing.margin(price, cost), cfg["pricing"]["min_margin_jpy"])
            self.assertEqual(price % 100, cfg["pricing"]["psychological_ending"])

    def test_full_cycle(self):
        root = str(self.tmp)
        cmd_research(root)
        cmd_publish(root)

        cfg = Config.load(self.tmp)
        store = Store(cfg.state_dir)
        listings = store.load_listings()
        self.assertGreater(len(listings), 0)
        # 高額部品(原価上限超)と在庫僅少品は除外されている
        self.assertNotIn("SKU-011", listings)
        self.assertNotIn("SKU-012", listings)
        self.assertTrue(all(l.status == "active" for l in listings.values()))

        # 受注を注入して orders → report まで
        sku = next(iter(listings))
        incoming = [{
            "order_id": "T-1", "sku": sku, "qty": 2,
            "sale_price": listings[sku].price, "ordered_at": "2026-07-18T00:00:00",
            "fee": round(listings[sku].price * 2 * 0.10, 1),
        }]
        (cfg.state_dir / "incoming_orders.json").write_text(
            json.dumps(incoming), encoding="utf-8")
        cmd_orders(root)
        orders = store.load_orders()
        self.assertEqual(orders["T-1"].status, "to_purchase")
        self.assertTrue((cfg.output_dir / "purchase_queue.csv").exists())

        cmd_sync(root)
        cmd_report(root)
        self.assertTrue((cfg.output_dir / "report.txt").exists())


if __name__ == "__main__":
    unittest.main()
