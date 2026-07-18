"""仕入先アダプタのテスト(列マッピング・文字コード・数値表記の許容)。"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from muzaiko.suppliers import CsvSupplier


class CsvSupplierTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_japanese_wholesale_csv_with_column_map_and_cp932(self):
        """国内卸フォーマット(Shift_JIS・日本語列名・カンマ/円付き数値)を読める。"""
        feed = self.tmp / "oroshi.csv"
        content = (
            "商品コード,商品名,卸価格,在庫数,送料\n"
            "W-001,アルミ製スマホスタンド,\"1,480円\",25,300\n"
            "W-002,ステンレスボトル500ml,980,10,\n"
        )
        feed.write_bytes(content.encode("cp932"))
        supplier = CsvSupplier(feed, encoding="cp932", column_map={
            "sku": "商品コード",
            "title": "商品名",
            "cost": "卸価格",
            "stock": "在庫数",
            "shipping_cost": "送料",
        })
        products = supplier.fetch_products()
        self.assertEqual(len(products), 2)
        self.assertEqual(products[0].sku, "W-001")
        self.assertEqual(products[0].cost, 1480.0)
        self.assertEqual(products[0].shipping_cost, 300.0)
        self.assertEqual(products[1].stock, 10)
        self.assertEqual(products[1].shipping_days, 7)  # 未指定はデフォルト

    def test_missing_column_error_lists_actual_columns(self):
        feed = self.tmp / "bad.csv"
        feed.write_text("code,name\nX,Y\n", encoding="utf-8")
        supplier = CsvSupplier(feed)
        with self.assertRaises(ValueError) as ctx:
            supplier.fetch_products()
        self.assertIn("column_map", str(ctx.exception))
        self.assertIn("code", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
