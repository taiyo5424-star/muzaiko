# AIプロンプト集(動画から抽出・実戦用)

8本の動画で実際に使われていたプロンプトを、そのまま使える形で整理。出典は各knowledgeファイル参照。

## 1. 運営の中枢: Claudeプロジェクト設定(Ac Hampton式)

**プロジェクトのカスタム指示:**
```
You are the chief of operations for [自分の名前]'s drop shipping store launch.
```

**オープニングプロンプト(専門家チーム構築):**
```
You are now my chief of operations for launching a drop shipping store today.
I need a team of specialists to help me move fast.
Build me a team of five specialists who report directly to you,
each with five plus years of experience:
a product research specialist, brand strategist, copywriter,
media buyer, and customer service specialist.
```

**運用ルール:**
- 1プロジェクト=1ビジネス、1チャット=1タスク。専門家を名前で呼ぶ(「Hey [名前], validate this product」)
- プロジェクトに商品・競合・ブランドボイス・顧客像・自社ポリシーを先に蓄積する(後工程の広告品質が段違いになる)
- 日本語運用の場合は同構造の日本語版でよい

## 2. 商品検証スコアリング(Ac Hampton式)

候補商品(画像・価格・バリエーション・トレンドメモ)を1メッセージにまとめて:
```
Analyze [N] products. Which has the best combo of
validation, margin, and evergreen demand?
Score each 1-10 on the three axes, explain why it wins / why it's risky,
give a final priority ranking, and tell me which to test first,
second, and which to skip entirely.
```
- 3軸: **Validation(実証された需要)/ Margin(広告費を引いて残るか)/ Evergreen demand(通年需要)**
- 追加チェック: **在庫ボトルネック**(スケールした瞬間に在庫切れにならないか)

## 3. 売れ行き事前検証(TETSUYA式)

```
以下の商品がドロップシッピングで売れる可能性を分析してください。
- 商品名: [名前]
- 商品リンク: [URL]
- 商品説明: [説明]
- 市場データ: 月間売上[X]、成長率[Y]%、販売件数[Z]、平均価格[P]、クリエイターCVR[C]%
判定基準: 市場規模 / 成長率 / 動画クリエイティブとの親和性 / 競合状況 / 価格・粗利余地
```

## 4. ブランド名・コンセプト生成(TETSUYA式)

```
この[ジャンル]の商品を取り扱うブランド名を10個考えてください。
条件: 一言で終わる・覚えやすい・日本人が発音しやすい
```
```
このブランドのコンセプト候補: ①[案A] ②[案B]
人が購入したくなるコンセプトを心理学的に考えて、どちらが良いか理由付きで選んでください。
また、そのコンセプトでTikTok広告の冒頭フック(共感シーン)がどう撮れるかも提案してください。
```
- **選定基準: 「広告動画の冒頭フックが撮れるか」でコンセプトを決める**

## 5. 競合ページ構造の学習→自分の商品ページ構築(Shenton式)

競合ページのスクショ(33%ズームアウトで全体をカバーする約5枚)を添付して:
```
Here's a screenshot of a high-converting Shopify product page.
Study the layout, hero structure, benefit presentation,
social proof placement, and overall visual hierarchy.
Build me a new product page for the product I'm selling: [商品名].
Follow the same structural principles: strong hero, clear benefit breakdown,
social proof section, and a clean call to action.
Use my product's actual details though, not theirs.
Brand name: [ブランド名] / Brand color: [色]
```
**逆質問への回答基準:** 画像→プレースホルダー / 機能→競合と同じセットでブランディングだけ変更 / レビュー→プレースホルダー

**注意: 構造はコピー、著作物(コピー原文・画像・ブランド)はコピーしない。**

## 6. 競合ストアのShopifyクローン改良(Ac Hampton式)

```
Use this example link as a guide to build me out a mockup store: [競合URL]
Then convert it into Shopify code sections for each section in a row,
with your own improvements.
Then give me a step-by-step guide on how to get this exact store
into my own Shopify.
```
- エラーが出たら**エラー文をそのまま貼って修正版をもらうループ**を回す(数回の往復は正常)

## 7. AI画像生成(Shenton式)

```
Create a high-quality 4K photorealistic product image.
Type: [Lifestyle image / product shot / review avatar / how-to-use step]
[Claudeが生成した画像指示文をそのまま貼る]
Customer avatar: [顧客アバター詳細]
Square 1:1 ratio.
```
- **必ず実際の商品画像を添付**(忘れると別商品が生成される)
- テキスト誤挿入は「No text, please」で修正
- 数回のリビジョン前提。顧客アバターはターゲット属性と一致させる(CVR直結)

## 8. 画像差し替え→ページ完成(Shenton式)

```
Here are all [N] missing product placeholder images,
in the exact order they appear going down the landing page.
Replace the blank placeholders with these and complete the page.
```

## 9. 競合レビューからの不満抽出(differentiation用)

```
以下は競合商品のレビュー[N]件です。
1. 共通する不満・クレーム
2. 未充足のニーズ・欲しいと言われている機能
3. 上記を解決する差別化ポイント・訴求アングル
を抽出して、広告フックの候補として使える形で出してください。
[レビューを貼り付け]
```
