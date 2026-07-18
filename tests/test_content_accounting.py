"""コンテンツ生成・会計エクスポート・ダッシュボードのテスト。"""
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from muzaiko.accounting import export_ledger
from muzaiko.config import Config
from muzaiko.content import generate_weekly_posts
from muzaiko.dashboard import render_dashboard
from muzaiko.models import Listing, Order
from muzaiko.storage import Store


def _listing(sku, title, price, cost, score=50.0, category=""):
    return Listing(sku=sku, title=title, description="", price=price, cost=cost,
                   stock=10, status="active", score=score, category=category)


class ContentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = Config.load(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_weekly_posts_generated(self):
        listings = {
            "A": _listing("A", "ワイヤレスイヤホン Bluetooth5.3", 3080, 1750,
                          score=80, category="家電・オーディオ"),
            "B": _listing("B", "ヨガマット 10mm", 3180, 1850, score=60, category="スポーツ"),
        }
        text = generate_weekly_posts(self.cfg, listings, start=date(2026, 7, 20), weeks=2)
        self.assertEqual(text.count("## 2026-"), 6)   # 週3本×2週
        self.assertIn("#ガジェット", text)             # カテゴリ連動ハッシュタグ
        self.assertIn("新着紹介", text)
        self.assertIn("使用シーン", text)
        self.assertIn("お得訴求", text)
        # スコア上位(A)が最初の題材になる
        first_post = text.split("## ")[1]
        self.assertIn(": A", first_post)

    def test_empty_listings_message(self):
        text = generate_weekly_posts(self.cfg, {})
        self.assertIn("アクティブな出品がありません", text)


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_ledger_rows_and_monthly_summary(self):
        listings = {"A": _listing("A", "商品A", 3000, 1500)}
        orders = {
            "O-1": Order(order_id="O-1", sku="A", qty=2, sale_price=3000,
                         ordered_at="2026-07-01T10:00:00", fee=600, status="done"),
            "O-2": Order(order_id="O-2", sku="A", qty=1, sale_price=3000,
                         ordered_at="2026-08-02T10:00:00", fee=300, status="shipped"),
            "O-X": Order(order_id="O-X", sku="A", qty=1, sale_price=3000,
                         ordered_at="2026-08-03T10:00:00", fee=300, status="cancelled"),
        }
        path = self.tmp / "ledger.csv"
        n = export_ledger(orders, listings, path)
        self.assertEqual(n, 2)  # cancelledは除外
        text = path.read_text(encoding="utf-8-sig")
        self.assertIn("月次集計", text)
        self.assertIn("2026-07", text)
        self.assertIn("2026-08", text)
        # 7月分: 売上6000 手数料600 仕入3000 粗利2400
        self.assertIn("6000,600,3000,2400", text.replace('"', ""))


class DashboardTest(unittest.TestCase):
    def test_dashboard_renders_with_history(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            cfg = Config.load(tmp)
            store = Store(cfg.state_dir)
            store.save_json("kpi_history.json", [
                {"date": "2026-07-01", "active_listings": 5, "orders": 2,
                 "revenue": 6000, "fees": 420, "cogs": 3600, "profit": 1980},
                {"date": "2026-07-02", "active_listings": 5, "orders": 4,
                 "revenue": 12000, "fees": 840, "cogs": 7200, "profit": 3960},
            ])
            out = tmp / "dashboard.html"
            render_dashboard(store, out)
            html = out.read_text(encoding="utf-8")
            self.assertIn("12,000", html)          # KPIタイル
            self.assertIn("2026-07-02", html)      # テーブルビュー
            self.assertIn('"revenue": 12000', html.replace(": ", ": "))
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
