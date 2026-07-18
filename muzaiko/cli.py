"""muzaiko CLI: 無在庫販売パイプラインの実行入口。

使い方:
    python -m muzaiko.cli research   # 仕入先フィードから出品候補を選定
    python -m muzaiko.cli publish    # 候補をチャネルに出品
    python -m muzaiko.cli sync       # 価格・在庫を仕入先に追従
    python -m muzaiko.cli orders     # 受注取込→発注(自動 or キュー出力)
    python -m muzaiko.cli report     # 収益レポート+改善アクション
    python -m muzaiko.cli run        # 上記を一括実行(定期実行用)
"""
from __future__ import annotations

import argparse
import sys

import csv
import shutil
from datetime import datetime
from pathlib import Path

from .analytics import report
from .channels import build_channel
from .config import Config
from .listing_gen import ListingGenerator
from .notify import notify
from .optimizer import Optimizer
from .orders import process_orders
from .pricing import PricingEngine
from .research import Researcher
from .shipments import process_shipments
from .storage import Store
from .suppliers import build_supplier
from .sync import sync_listings


def _ctx(root: str):
    cfg = Config.load(root)
    store = Store(cfg.state_dir)
    pricing = PricingEngine(cfg)
    return cfg, store, pricing


def _export_listings_csv(listings, path: Path) -> None:
    """アクティブ出品を一括登録用CSVに書き出す(BASE/STORESの管理画面や
    各種一括登録ツールへ貼り付けて使う。API未接続のPhase 0でも出品作業を短縮)。"""
    rows = [l for l in listings.values() if l.status == "active"]
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # Excelで文字化けしないBOM付き
        writer = csv.writer(f)
        writer.writerow(["sku", "title", "price", "stock", "category",
                        "image_url", "description"])
        for l in rows:
            writer.writerow([l.sku, l.title, int(l.price), l.stock, l.category,
                             l.image_url, l.description.replace("\n", " / ")])
    print(f"  [出力] 一括出品用CSV → {path}")


def cmd_init(root: str) -> None:
    """初期セットアップ: config.json を作成し、次にやることを案内する。"""
    cfg_path = Path(root) / "config.json"
    example = Path(root) / "config.example.json"
    if cfg_path.exists():
        print(f"config.json は既に存在します: {cfg_path}")
    elif example.exists():
        shutil.copy(example, cfg_path)
        print(f"✔ {cfg_path} を作成しました")
    else:
        print("config.example.json が見つかりません")
        return
    print("""
次にやること:
  1. 仕入先CSVを data/ に置き、config.json の supplier.feed_path を変更
     (国内卸のCSVは supplier.encoding を "cp932"、列名は supplier.column_map で対応付け)
  2. python -m muzaiko.cli run   ← まずはドライランで動作確認
  3. 販路が決まったら channel.type を "shopify" か "base" に変更
     - 詳細手順と手数料の実勢は README.md / STRATEGY.md を参照
  4. 特定商取引法ページは docs/TOKUSHOHO_TEMPLATE.md の穴埋めで作成
""")


def cmd_research(root: str) -> None:
    cfg, store, pricing = _ctx(root)
    supplier = build_supplier(cfg)
    print("▶ 仕入先フィードを取得中...")
    products = supplier.fetch_products()
    print(f"  {len(products)}件の商品を取得")
    researcher = Researcher(cfg, pricing)
    selected = researcher.select(products)
    gen = ListingGenerator(cfg, pricing)
    listings = store.load_listings()
    new = 0
    for p, score in selected:
        if p.sku in listings:
            continue
        listings[p.sku] = gen.build(p, score)
        listings[p.sku].status = "draft"
        new += 1
        print(f"  [候補] {p.sku} score={score} 想定価格={listings[p.sku].price:.0f}円 "
              f"想定粗利={pricing.margin(listings[p.sku].price, p.landed_cost):.0f}円")
    store.save_listings(listings)
    print(f"✔ 新規出品候補 {new}件(draft)。`publish` で出品します")


def cmd_publish(root: str) -> None:
    cfg, store, _ = _ctx(root)
    channel = build_channel(cfg)
    listings = store.load_listings()
    published = 0
    for l in listings.values():
        if l.status != "draft":
            continue
        l.channel_id = channel.publish(l)
        l.status = "active"
        l.created_at = datetime.now().isoformat(timespec="seconds")
        published += 1
        print(f"  [出品] {l.sku}: {l.title[:30]} @{l.price:.0f}円 (id={l.channel_id})")
    store.save_listings(listings)
    _export_listings_csv(listings, cfg.output_dir / "listings_export.csv")
    print(f"✔ {published}件を出品しました(チャネル: {cfg['channel']['type']})")


def cmd_sync(root: str) -> None:
    cfg, store, pricing = _ctx(root)
    supplier = build_supplier(cfg)
    channel = build_channel(cfg)
    listings = store.load_listings()
    if not listings:
        print("出品がありません。先に research → publish を実行してください")
        return
    print("▶ 仕入先在庫・価格と同期中...")
    products = supplier.fetch_products()
    stats = sync_listings(listings, products, pricing, channel)
    store.save_listings(listings)
    _export_listings_csv(listings, cfg.output_dir / "listings_export.csv")
    print(f"✔ 同期完了: 改定{stats['repriced']} 停止{stats['paused']} "
          f"再開{stats['reactivated']} 在庫更新{stats['stock_updated']}")


def cmd_orders(root: str) -> None:
    cfg, store, _ = _ctx(root)
    supplier = build_supplier(cfg)
    channel = build_channel(cfg)
    listings = store.load_listings()
    orders = store.load_orders()
    print("▶ 受注を処理中...")
    stats = process_orders(orders, listings, channel, supplier, cfg.output_dir)
    store.save_orders(orders)
    print(f"✔ 取込{stats['imported']} 自動発注{stats['auto_ordered']} "
          f"手動キュー{stats['queued']}")


def cmd_optimize(root: str) -> None:
    """収益最大化アクションの自動実行(価格実験・赤字停止・出品入替)。"""
    cfg, store, pricing = _ctx(root)
    channel = build_channel(cfg)
    listings = store.load_listings()
    orders = store.load_orders()
    print("▶ 自動最適化を実行中...")
    optimizer = Optimizer(cfg, pricing, store)
    stats = optimizer.run(listings, orders, channel)
    store.save_listings(listings)
    print(f"✔ 最適化: 実験開始{stats['exp_started']} 採用{stats['exp_kept']} "
          f"撤回{stats['exp_rolled_back']} 赤字停止{stats['loss_delisted']} "
          f"入替{stats['stale_delisted']}")


def cmd_shipments(root: str, csv_file: str) -> None:
    """追跡番号CSVを取り込み、発送済み登録+顧客通知。"""
    cfg, store, _ = _ctx(root)
    channel = build_channel(cfg)
    orders = store.load_orders()
    print(f"▶ 出荷CSVを処理中: {csv_file}")
    stats = process_shipments(Path(csv_file), orders, channel)
    store.save_orders(orders)
    print(f"✔ 発送登録{stats['shipped']} 不明{stats['not_found']} スキップ{stats['skipped']}")


def cmd_report(root: str) -> None:
    cfg, store, pricing = _ctx(root)
    text = report(store.load_listings(), store.load_orders(), pricing)
    print(text)
    (cfg.output_dir / "report.txt").write_text(text, encoding="utf-8")
    notify(cfg, text)


def cmd_run(root: str) -> None:
    """フルサイクル実行(cron / GitHub Actions 向け)。"""
    cmd_research(root)
    cmd_publish(root)
    cmd_sync(root)
    cmd_orders(root)
    cmd_optimize(root)
    cmd_report(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="muzaiko", description="無在庫販売自動化パイプライン")
    parser.add_argument("--root", default=".", help="プロジェクトルート(config.json の場所)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "research", "publish", "sync", "orders", "optimize", "report", "run"):
        sub.add_parser(name)
    ship = sub.add_parser("shipments")
    ship.add_argument("--file", default="data/shipments_in.csv",
                      help="追跡番号CSV(order_id,tracking_number,carrier)")
    args = parser.parse_args(argv)
    if args.command == "shipments":
        cmd_shipments(args.root, args.file)
        return 0
    {
        "init": cmd_init,
        "research": cmd_research,
        "publish": cmd_publish,
        "sync": cmd_sync,
        "orders": cmd_orders,
        "optimize": cmd_optimize,
        "report": cmd_report,
        "run": cmd_run,
    }[args.command](args.root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
