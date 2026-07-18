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

    def test_trend_keyword_boosts_score(self):
        """推し活・コレクター系キーワードに一致する商品はスコアが上がる。"""
        from muzaiko.models import SupplierProduct
        from muzaiko.research import Researcher

        cfg = Config.load(self.tmp)
        researcher = Researcher(cfg, PricingEngine(cfg))
        base = dict(cost=1000, stock=50, shipping_cost=300, shipping_days=7)
        plain = SupplierProduct(sku="P-1", title="ステンレスタンブラー 500ml", **base)
        trend = SupplierProduct(sku="P-2", title="シルバニアファミリー 限定 ぬいぐるみ",
                                category="ホビー", **base)
        self.assertGreater(researcher.score(trend), researcher.score(plain))
        self.assertGreaterEqual(len(researcher.trend_hits(trend)), 2)
        self.assertEqual(researcher.trend_hits(plain), [])

    def test_tariff_buffer_raises_price_for_ddp(self):
        """関税バッファ(DDP)を設定すると価格に織り込まれる。"""
        cfg_plain = Config.load(self.tmp)
        (self.tmp / "config.json").write_text(
            json.dumps({"pricing": {"tariff_buffer_rate": 0.10}}), encoding="utf-8")
        cfg_ddp = Config.load(self.tmp)
        p_plain = PricingEngine(cfg_plain)
        p_ddp = PricingEngine(cfg_ddp)
        for cost in (1000, 5000):
            self.assertGreater(p_ddp.initial_price(cost), p_plain.initial_price(cost))

    def test_shopee_export_channel_writes_mass_upload_csv(self):
        """shopee_export チャネルは現地通貨換算済みの一括アップロードCSVを出力する。"""
        (self.tmp / "config.json").write_text(json.dumps({
            "channel": {"type": "shopee_export", "currency": "SGD", "fx_rate": 0.0087},
        }), encoding="utf-8")
        root = str(self.tmp)
        cmd_research(root)
        cmd_publish(root)

        cfg = Config.load(self.tmp)
        csv_path = cfg.output_dir / "shopee" / "mass_upload.csv"
        self.assertTrue(csv_path.exists())
        import csv as csv_mod
        with open(csv_path, encoding="utf-8-sig") as f:
            rows = list(csv_mod.DictReader(f))
        self.assertGreater(len(rows), 0)
        store = Store(cfg.state_dir)
        listings = store.load_listings()
        for row in rows:
            listing = listings[row["sku"]]
            self.assertAlmostEqual(
                float(row["price_sgd"]), round(listing.price * 0.0087, 2))
            self.assertLessEqual(int(row["days_to_ship"]), 10)
            if listing.shipping_days > 2:
                self.assertEqual(row["pre_order"], "yes")


if __name__ == "__main__":
    unittest.main()
