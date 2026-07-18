"""出品コンテンツ生成(タイトル・説明文)。

デフォルトはテンプレート生成(無料・決定的)。
config の listing.use_llm を true にし、ANTHROPIC_API_KEY と anthropic パッケージが
あれば Claude で説明文を生成する(失敗時はテンプレートへフォールバック)。
"""
from __future__ import annotations

import os

from .config import Config
from .models import Listing, SupplierProduct
from .pricing import PricingEngine

DESCRIPTION_TEMPLATE = """\
【商品説明】
{title}

・カテゴリ: {category}
・お届け目安: ご注文から約{shipping_days}日
・在庫: 残り{stock}点

【ご注文について】
ご注文確定後、提携倉庫より直接発送いたします。
発送までのリードタイムを商品ページ記載の日数どおりに設定しております。
在庫状況により、まれにお取り寄せにお時間をいただく場合がございます。

【{shop_name}のお約束】
・追跡番号付きで発送します
・不良品は到着後7日以内のご連絡で返品・交換に対応します
"""


def _template_copy(p: SupplierProduct, shop_name: str) -> tuple[str, str]:
    title = p.title[:60]
    description = DESCRIPTION_TEMPLATE.format(
        title=p.title,
        category=p.category or "その他",
        shipping_days=p.shipping_days,
        stock=p.stock,
        shop_name=shop_name,
    )
    return title, description


def _llm_copy(p: SupplierProduct, shop_name: str) -> tuple[str, str] | None:
    """Claude で販売用コピーを生成。使えない環境では None を返す。"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        print("  [info] anthropic パッケージ未導入のためテンプレート生成にフォールバック")
        return None
    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=1024,
            thinking={"type": "adaptive"},
            output_config={"effort": "low"},
            system=(
                "あなたはEC出品コピーライターです。誇大表現・効果効能の断定・"
                "景品表示法に抵触する表現を避け、簡潔で信頼感のある日本語で書いてください。"
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"次の商品情報から、1行目に60文字以内の商品タイトル、"
                    f"2行目以降に販売ページ用の説明文(300字程度)を書いてください。"
                    f"お届け目安は約{p.shipping_days}日、ショップ名は{shop_name}。\n\n"
                    f"商品名: {p.title}\nカテゴリ: {p.category}\n"
                ),
            }],
        )
        text = next(b.text for b in response.content if b.type == "text")
        lines = text.strip().splitlines()
        title = lines[0].strip()[:60]
        description = "\n".join(lines[1:]).strip()
        if title and description:
            return title, description
    except Exception as e:
        print(f"  [warn] LLM生成に失敗({e})。テンプレートにフォールバック")
    return None


class ListingGenerator:
    def __init__(self, cfg: Config, pricing: PricingEngine):
        self.use_llm = cfg["listing"]["use_llm"]
        self.shop_name = cfg["listing"]["shop_name"]
        self.pricing = pricing

    def build(self, p: SupplierProduct, score: float) -> Listing:
        copy_pair = _llm_copy(p, self.shop_name) if self.use_llm else None
        title, description = copy_pair or _template_copy(p, self.shop_name)
        price = self.pricing.initial_price(p.landed_cost)
        return Listing(
            sku=p.sku,
            title=title,
            description=description,
            price=price,
            cost=p.landed_cost,
            stock=p.stock,
            status="active",
            score=score,
            image_url=p.image_url,
            category=p.category,
            shipping_days=p.shipping_days,
        )
