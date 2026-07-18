"""集客コンテンツ生成: アクティブ出品からSNS投稿ドラフト(週間プラン)を自動生成。

Phase 0(広告費ゼロ)の集客はSNSオーガニックが主戦場。
週3本 × 3つの型(新着紹介 / 使用シーン / お得訴求)をローテーションし、
スコア上位の出品から順に題材にする。出力は out/sns_posts.md。
listing.use_llm が有効なら文面をClaudeで強化(失敗時はテンプレへフォールバック)。
"""
from __future__ import annotations

from datetime import date, timedelta

from .config import Config
from .models import Listing

HASHTAG_MAP = {
    "家電": ["#家電", "#便利グッズ"],
    "オーディオ": ["#ガジェット", "#イヤホン"],
    "スマホ": ["#スマホアクセサリー", "#ガジェット"],
    "キッチン": ["#キッチン用品", "#暮らしを楽しむ"],
    "ペット": ["#ペット用品", "#ペットのいる暮らし"],
    "スポーツ": ["#フィットネス", "#宅トレ"],
    "アウトドア": ["#キャンプ用品", "#アウトドア好きな人と繋がりたい"],
    "インテリア": ["#インテリア雑貨", "#おうち時間"],
    "撮影": ["#撮影機材", "#動画配信"],
    "健康": ["#健康グッズ", "#セルフケア"],
    "PC": ["#デスク環境", "#ガジェット"],
}
GENERIC_TAGS = ["#新商品", "#お買い物好きな人と繋がりたい"]


def _hashtags(listing: Listing) -> str:
    tags: list[str] = []
    for key, values in HASHTAG_MAP.items():
        if key in listing.category or key in listing.title:
            tags.extend(values)
    tags.extend(GENERIC_TAGS)
    return " ".join(dict.fromkeys(tags))[:120]


def _post_new_arrival(l: Listing, shop_name: str) -> str:
    return (f"【新入荷】{l.title}\n\n"
            f"{shop_name}に新しい商品が入荷しました✨\n"
            f"価格: {l.price:,.0f}円\n\n"
            f"プロフィールのリンクからチェックしてください🛒\n"
            f"{_hashtags(l)}")


def _post_use_case(l: Listing, shop_name: str) -> str:
    return (f"{l.title.split()[0] if l.title.split() else l.title}、"
            f"こんな場面で活躍します💡\n\n"
            f"「{l.title}」\n"
            f"毎日の暮らしがちょっと快適になるアイテムです。\n"
            f"実際の使い心地はストアの商品ページでチェック👀\n\n"
            f"{_hashtags(l)}")


def _post_value(l: Listing, shop_name: str) -> str:
    return (f"🔖 {l.title}\n\n"
            f"いま{shop_name}で{l.price:,.0f}円。\n"
            f"追跡番号付き発送・不良品は到着後7日以内の返品交換対応です。\n"
            f"気になっていた方はこの機会にどうぞ。\n\n"
            f"{_hashtags(l)}")


STYLES = [("新着紹介", _post_new_arrival), ("使用シーン", _post_use_case), ("お得訴求", _post_value)]
POST_WEEKDAYS = (0, 2, 5)  # 月・水・土


def generate_weekly_posts(cfg: Config, listings: dict[str, Listing],
                          start: date | None = None, weeks: int = 2) -> str:
    shop_name = cfg["listing"]["shop_name"]
    active = sorted(
        (l for l in listings.values() if l.status == "active"),
        key=lambda l: l.score, reverse=True,
    )
    if not active:
        return "アクティブな出品がありません。先に research → publish を実行してください。\n"

    start = start or date.today()
    # 次の投稿曜日まで進める
    while start.weekday() not in POST_WEEKDAYS:
        start += timedelta(days=1)

    lines = [
        "# SNS投稿プラン(自動生成)",
        "",
        f"生成日: {date.today().isoformat()} / 対象: アクティブ出品 {len(active)}件",
        "",
        "使い方: 各投稿をコピーして X / Instagram に予約投稿。画像は商品画像を添付。",
        "文面は自由に編集OK。反応が良かった型を増やすこと。",
        "",
    ]
    day = start
    idx = 0
    total = weeks * len(POST_WEEKDAYS)
    for i in range(total):
        listing = active[idx % len(active)]
        style_name, style_fn = STYLES[i % len(STYLES)]
        weekday_jp = "月火水木金土日"[day.weekday()]
        lines.append(f"## {day.isoformat()}({weekday_jp}){style_name}: {listing.sku}")
        lines.append("")
        lines.append("```")
        lines.append(style_fn(listing, shop_name))
        lines.append("```")
        lines.append("")
        idx += 1
        day += timedelta(days=1)
        while day.weekday() not in POST_WEEKDAYS:
            day += timedelta(days=1)
    return "\n".join(lines)
