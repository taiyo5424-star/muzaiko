"""収益分析と収益最大化のためのアクション提案。"""
from __future__ import annotations

from collections import defaultdict

from .models import Listing, Order
from .pricing import PricingEngine


def order_cogs(o: Order, listings: dict[str, Listing]) -> float | None:
    """受注の仕入原価。受注時スナップショットを優先し、
    不明(未知SKUかつスナップショットなし)なら None を返す。
    None の受注を粗利に混ぜると原価0円扱いで利益が過大計上されるため、
    呼び出し側は集計から除外すること。"""
    if o.cost_at_order > 0:
        return o.cost_at_order * o.qty
    listing = listings.get(o.sku)
    return listing.cost * o.qty if listing else None


def report(
    listings: dict[str, Listing],
    orders: dict[str, Order],
    pricing: PricingEngine,
) -> str:
    lines: list[str] = []
    active = [l for l in listings.values() if l.status == "active"]
    lines.append("=" * 60)
    lines.append("収益レポート")
    lines.append("=" * 60)
    lines.append(f"出品数: {len(listings)}(アクティブ {len(active)})")

    # --- 売上集計(原価不明の受注は粗利集計から除外して過大計上を防ぐ) ---
    all_sold = [o for o in orders.values() if o.status != "cancelled"]
    sold = []
    unknown_cost = []
    for o in all_sold:
        (unknown_cost if order_cogs(o, listings) is None else sold).append(o)
    revenue = sum(o.revenue for o in sold)
    fees = sum(o.fee for o in sold)
    cogs = 0.0
    sku_sales: dict[str, dict] = defaultdict(lambda: {"qty": 0, "revenue": 0.0, "profit": 0.0})
    for o in sold:
        cost = order_cogs(o, listings) or 0.0
        cogs += cost
        profit = o.revenue - o.fee - cost
        s = sku_sales[o.sku]
        s["qty"] += o.qty
        s["revenue"] += o.revenue
        s["profit"] += profit

    profit_total = revenue - fees - cogs
    lines.append(f"受注件数: {len(all_sold)}"
                 + (f"(うち原価不明 {len(unknown_cost)}件は粗利集計から除外)"
                    if unknown_cost else ""))
    lines.append(f"売上高:   {revenue:>12,.0f} 円")
    lines.append(f"手数料:   {fees:>12,.0f} 円")
    lines.append(f"仕入原価: {cogs:>12,.0f} 円")
    lines.append(f"粗利益:   {profit_total:>12,.0f} 円"
                 + (f"(粗利率 {profit_total / revenue:.1%})" if revenue else ""))

    # --- SKU別トップ ---
    if sku_sales:
        lines.append("")
        lines.append("SKU別実績(利益順):")
        ranked = sorted(sku_sales.items(), key=lambda kv: kv[1]["profit"], reverse=True)
        for sku, s in ranked[:10]:
            title = (listings[sku].title[:24] if sku in listings else "?")
            lines.append(f"  {sku:<12} {title:<26} 数量{s['qty']:>3} 利益 {s['profit']:>9,.0f}円")

    # --- 収益最大化アクション ---
    lines.append("")
    lines.append("推奨アクション:")
    actions = 0
    for sku, s in sku_sales.items():
        listing = listings.get(sku)
        if not listing:
            continue
        # 売れ筋 → 値上げテスト
        if s["qty"] >= 3 and listing.status == "active":
            lines.append(f"  [値上げ検討] {sku}: 販売{s['qty']}件。価格+5〜10%のテストを推奨")
            actions += 1
        # 赤字SKU → 停止
        if s["profit"] < 0:
            lines.append(f"  [停止検討] {sku}: 累計利益 {s['profit']:,.0f}円(赤字)")
            actions += 1
    for l in active:
        rate = pricing.margin_rate(l.price, l.cost)
        if rate < pricing.min_margin_rate:
            lines.append(f"  [値上げ必須] {l.sku}: 現在粗利率 {rate:.1%} が下限 {pricing.min_margin_rate:.0%} 未満")
            actions += 1
    stale = [l for l in active if l.sku not in sku_sales]
    if len(stale) > 5:
        lines.append(f"  [入替検討] 販売実績のない出品が{len(stale)}件。次回リサーチで入替を推奨")
        actions += 1
    if actions == 0:
        lines.append("  (現時点で推奨アクションはありません)")

    lines.append("=" * 60)
    return "\n".join(lines)
