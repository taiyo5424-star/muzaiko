"""受注処理の安全性テスト(レビュー指摘の回帰防止)。

- 自動発注の途中失敗でクラッシュ・二重発注しない
- チャネル側キャンセルの検知
- 原価スナップショットにより過去の損益が原価変動で書き換わらない
- 原価不明の受注が粗利集計から除外される
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from muzaiko.analytics import order_cogs, report
from muzaiko.channels import ChannelBase
from muzaiko.config import Config
from muzaiko.models import Listing, Order
from muzaiko.orders import process_orders
from muzaiko.pricing import PricingEngine
from muzaiko.suppliers import SupplierBase


class StubChannel(ChannelBase):
    def __init__(self, orders=None, cancelled=None):
        self._orders = orders or []
        self._cancelled = cancelled or []
        self.acked = False

    def publish(self, listing):
        return f"stub-{listing.sku}"

    def update(self, listing):
        pass

    def fetch_orders(self):
        return self._orders

    def fetch_cancelled_ids(self):
        return self._cancelled

    def ack_orders(self):
        self.acked = True


class FlakySupplier(SupplierBase):
    """1件目は成功、2件目はAPIエラー、3件目は成功する仕入先。"""

    def __init__(self):
        self.calls = 0

    def fetch_products(self):
        return []

    def place_order(self, sku, qty, shipping_address):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("API 500")
        return f"SUP-{self.calls}"


def _listing(sku, price=3000, cost=1500):
    return Listing(sku=sku, title=sku, description="", price=price, cost=cost,
                   stock=10, status="active")


def _order(oid, sku, price=3000, status="new"):
    return Order(order_id=oid, sku=sku, qty=1, sale_price=price,
                 ordered_at="2026-07-18T10:00:00", fee=300, status=status)


class OrdersSafetyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_supplier_error_does_not_crash_or_lose_orders(self):
        listings = {"A": _listing("A"), "B": _listing("B"), "C": _listing("C")}
        channel = StubChannel(orders=[_order("O-1", "A"), _order("O-2", "B"),
                                      _order("O-3", "C")])
        orders = {}
        saves = []
        stats = process_orders(orders, listings, channel, FlakySupplier(),
                               self.tmp, save=lambda: saves.append(len(orders)))
        self.assertEqual(stats["auto_ordered"], 2)
        self.assertEqual(stats["errors"], 1)
        self.assertEqual(stats["queued"], 1)
        # 失敗した1件は手動キューへ、成功2件は purchased
        statuses = sorted(o.status for o in orders.values())
        self.assertEqual(statuses, ["purchased", "purchased", "to_purchase"])
        # 取込直後+成功/失敗ごとに保存されている(クラッシュ時の二重発注防止)
        self.assertGreaterEqual(len(saves), 4)
        self.assertTrue(channel.acked)

    def test_cancelled_orders_are_not_purchased(self):
        listings = {"A": _listing("A")}
        orders = {"999-1": _order("999-1", "A")}  # 前回取込済み・未発注
        channel = StubChannel(orders=[], cancelled=["999"])
        supplier = FlakySupplier()
        stats = process_orders(orders, listings, channel, supplier, self.tmp)
        self.assertEqual(stats["cancelled"], 1)
        self.assertEqual(orders["999-1"].status, "cancelled")
        self.assertEqual(supplier.calls, 0)  # 発注APIは呼ばれない

    def test_cost_snapshot_freezes_history(self):
        listings = {"A": _listing("A", cost=1000)}
        channel = StubChannel(orders=[_order("O-1", "A")])
        process_orders({}, listings, channel, FlakySupplier(), self.tmp)
        orders = {}
        channel2 = StubChannel(orders=[_order("O-1", "A")])
        process_orders(orders, listings, channel2, FlakySupplier(), self.tmp)
        self.assertEqual(orders["O-1"].cost_at_order, 1000)
        # 仕入原価が上がっても過去の受注原価は変わらない
        listings["A"].cost = 1600
        self.assertEqual(order_cogs(orders["O-1"], listings), 1000)

    def test_unknown_sku_excluded_from_profit(self):
        cfg = Config.load(self.tmp)
        pricing = PricingEngine(cfg)
        listings = {"A": _listing("A", cost=1500)}
        orders = {
            "O-1": _order("O-1", "A", status="done"),
            "O-X": _order("O-X", "GHOST", price=99999, status="done"),  # 未知SKU
        }
        orders["O-1"].cost_at_order = 1500
        text = report(listings, orders, pricing)
        self.assertIn("原価不明 1件", text)
        # 未知SKUの99999円が粗利に混入していない(既知分: 3000-300-1500=1200)
        self.assertIn("1,200 円", text)


if __name__ == "__main__":
    unittest.main()
