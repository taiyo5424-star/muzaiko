# Alexander Shenton「How To Start AI Dropshipping in 2026 (Full Guide)」学習ノート

- 動画: https://youtu.be/T6wIiFHSxJ4 (Alexander Shenton)
- 出典: 自動生成字幕の全文読解(認識誤りは文脈補正済み)
- 注記: 3PLサービスのスポンサー的紹介を含む。実態は「売れている競合の商品ページをClaudeで再構築して同じ商品を売る」実演チュートリアル

## 全体ワークフロー(実演された手順)

1. **売れている商品・ストアの発見**: 一商品ストア(腰痛サポートベルト)を発見し、ZIK Analyticsで売上を数値検証
2. **競合LPの構造分析**: ヒーロー/画像/社会的証明/比較表/オファー/FAQ/レビューを分解
3. **仕入(3PL)**: サプライヤーのエージェントに商品画像を送り見積もり
4. **Claudeで商品ページ再構築**: 競合ページのスクショ約5枚(ブラウザ33%ズームアウトで撮影)を渡し、構造を学習させて自分の商品用に構築
5. **修正イテレーション**: 問題点をフィードバックしリアルタイム修正(上部CTA・スティッキーカートボタン追加)
6. **AI画像生成**: プレースホルダー11枚をChatGPT画像生成で作成
7. **画像差し替え→完成**: 全体で**30分未満**
8. **広告立ち上げ**(実演なし):「ページを複製しても売上は複製されない」— マーケ計画・広告クリエイティブ・運用は別途必要

## 実際に使われたプロンプト

**ページ構築(定番プロンプト):**
> "Here's a screenshot of a high-converting Shopify product page. Study the layout, hero structure, benefit presentation, social proof placement, overall visual hierarchy. Build me a new product page for the new product that I'm selling: [商品名]. Follow the same structural principles: strong hero, clear benefit breakdown, social proof section, and a clean call to action. Use my product's actual details though, not theirs."
> + ブランド名・ブランドカラーを追記

**Claudeの逆質問への回答基準:**
- 画像は? → プレースホルダーで(後からAIで生成)
- 機能・差別化は? → **競合と同じ機能セット、ブランディングだけ変更**(競合が「何が売れるか」を検証済みだから)
- レビューは? → プレースホルダーで

**画像差し替え:**
> "Here are all 11 of the missing product placeholder images in the exact order of how they appear going down the landing page. Please replace the placeholders with these and complete the page."

**画像生成(ChatGPT):**
> "Create a high-quality 4K photorealistic product image. [種別: Lifestyle image等] + [Claudeが生成した画像指示文] + [顧客アバター詳細] + square 1:1 ratio"

- **必ず実際の商品画像を最初から添付する**(忘れると別商品が生成される)
- テキスト誤挿入には「No text, please」で修正
- **一発で完璧は稀。数回のリビジョン前提**

## ケーススタディ数値(腰痛サポートベルト)

| 項目 | 数値 |
|---|---|
| 競合の販売価格 | $99 |
| 競合の直近30日売上 | $82,000超(日次$2,000〜3,000で安定・増加傾向) |
| AliExpress価格 | 約$20 |
| 3PL経由仕入 | **送料込$15未満** |
| 配送 | 中国→米国3〜7日(多くは4日) |
| 画像11枚の生成時間 | 20〜30分 |
| ページ完成 | 30分未満 |

**商品判定基準: ①一貫した日次売上 ②増加傾向 ③ツールで数値裏取り**

## 高CVRページの構成要素(競合分解から)

- ヒーロー(カート追加まで価格を見せない設計)
- 大量の高品質画像(大半はAI生成でもよくブランディングされたもの)
- 社会的証明: 医師レビュー、メディア掲載ロゴ
- ブロック分割の説明: 比較表 / 使い方(3ステップ) / 内容物 / 顧客メリット
- **50%オフ**オファー
- 顧客アバター(誰向けか・効いた実例)の提示
- **スタック型ボーナス: 無料ebook(AIで数分で作成)+1年保証**
- FAQ、アコーディオン形式の「選ばれる理由」、最下部にレビュー群

## 収益直結の戦術

1. **ゼロから作らず「実証済み」をコピーする**(本動画の核心)
2. **構造はコピー、著作物はコピーしない**: コピー原文・画像・ブランドは複製せず、レイアウト・構造だけ学習させて自分の商品で再構築(法的・倫理的な線引き)
3. **1年保証はほぼノーリスクの強オファー**: 行使されることが少なく、上乗せ分がそのまま利益になる
4. **無料ebookバンドル**で知覚価値アップ
5. **上部CTA+スクロール追従スティッキーカートボタン**で導線最短化
6. **顧客アバター一致の画像**(腰痛持ちのブルーカラー中年男性)+別デモグラフィック用画像(女性)も追加
7. **カスタムブランディング**(ロゴ・サンキューカード・梱包)でリピートへ
8. **アップセル設計**: リピート性の低い商品にはローション・ガイド等を追加し同じ顧客に再販売
9. AI生成ページの残課題(不格好なボタン、同じ顔のアバター、動かないレビューセクション等)は**必ず手直しする**
10. 現実的な目標: 競合と同等ページを作っても狙えるのは「競合の売上の何分の一か」
