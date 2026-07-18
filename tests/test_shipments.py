"""出荷処理のテスト。"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from muzaiko.channels import LocalChannel
from muzaiko.config import Config
from muzaiko.models import Order
from muzaiko.shipments import process_shipments


class ShipmentsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        cfg = Config.load(self.tmp)
        self.channel = LocalChannel(cfg.output_dir, cfg.state_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_shipments_csv_marks_orders_shipped(self):
        orders = {
            "O-1": Order(order_id="O-1", sku="SKU-001", qty=1,
                         sale_price=2980, status="purchased"),
            "O-2": Order(order_id="O-2", sku="SKU-002", qty=1,
                         sale_price=1280, status="purchased"),
        }
        csv_path = self.tmp / "shipments_in.csv"
        csv_path.write_text(
            "order_id,tracking_number,carrier\n"
            "O-1,JP123456789,ヤマト運輸\n"
            "O-9,NOPE,佐川急便\n",   # 存在しない注文
            encoding="utf-8",
        )
        stats = process_shipments(csv_path, orders, self.channel)
        self.assertEqual(stats["shipped"], 1)
        self.assertEqual(stats["not_found"], 1)
        self.assertEqual(orders["O-1"].status, "shipped")
        self.assertEqual(orders["O-1"].tracking_number, "JP123456789")
        self.assertEqual(orders["O-2"].status, "purchased")


if __name__ == "__main__":
    unittest.main()
