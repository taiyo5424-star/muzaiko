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

from .analytics import report
from .channels import build_channel
from .config import Config
from .listing_gen import ListingGenerator
from .orders import process_orders
from .pricing import PricingEngine
from .research import Researcher
from .storage import Store
from .suppliers import build_supplier
from .sync import sync_listings


def _ctx(root: str):
    cfg = Config.load(root)
    store = Store(cfg.state_dir)
    pricing = PricingEngine(cfg)
    return cfg, store, pricing


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
        published += 1
        print(f"  [出品] {l.sku}: {l.title[:30]} @{l.price:.0f}円 (id={l.channel_id})")
    store.save_listings(listings)
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


def cmd_report(root: str) -> None:
    cfg, store, pricing = _ctx(root)
    text = report(store.load_listings(), store.load_orders(), pricing)
    print(text)
    (cfg.output_dir / "report.txt").write_text(text, encoding="utf-8")


def cmd_run(root: str) -> None:
    """フルサイクル実行(cron / GitHub Actions 向け)。"""
    cmd_research(root)
    cmd_publish(root)
    cmd_sync(root)
    cmd_orders(root)
    cmd_report(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="muzaiko", description="無在庫販売自動化パイプライン")
    parser.add_argument("--root", default=".", help="プロジェクトルート(config.json の場所)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("research", "publish", "sync", "orders", "report", "run"):
        sub.add_parser(name)
    args = parser.parse_args(argv)
    {
        "research": cmd_research,
        "publish": cmd_publish,
        "sync": cmd_sync,
        "orders": cmd_orders,
        "report": cmd_report,
        "run": cmd_run,
    }[args.command](args.root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
