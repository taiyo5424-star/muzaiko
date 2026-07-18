# Ac Hampton「How I'd Make My First $10,000 Dropshipping in 2026 (Using Claude)」学習ノート

- 動画: https://youtu.be/blwESLCVh-A (Ac Hampton)
- 出典: 自動生成字幕の全文読解(認識誤りは文脈補正・推定併記)
- 注記: アフィリエイト導線多数(.storeドメイン、Shopify $1プラン、Team Drop、Ecom Boss、プロンプトパック)。実績($10M超等)は自己申告

## 4ステップ・ブループリント概要

「すべて失って明日ゼロから始めるなら」の設定で、手作業の10倍速く動くAIスタックを構築する。

## ステップ1: 「ビジネスの頭脳」= Claudeプロジェクト構築(約10分)

**商品でもストアでもなく、最初に作るのは運営の中枢。**

1. Claudeで新規プロジェクト作成。カスタム指示:
   > "You are the chief of operations for [自分の名前]'s drop shipping store launch."
2. プロジェクト内の新規チャットでオープニングプロンプト:
   > "You are now my chief of operations for launching a drop shipping store today. I need a team of specialists to help me move fast. Build me a team of five specialists who report directly to you, each with five plus years of experience: a product research specialist, brand strategist, copywriter, media buyer, and customer service specialist."
3. Claudeが5人の専門家ペルソナを生成(商品リサーチ / ブランド戦略 / コピー / メディアバイヤー / CS)
4. このチャットを「Chief of Operations」にリネームして土台にする

**運用ルール:**
- 作業ごとに**同一プロジェクト内で新規チャット**を開き、専門家を名前で呼ぶ(「Hey Maya, validate this product」「Hey Sam, build me a brand」「Hey Alex, write the product page copy」)
- 同一プロジェクトなので**コンテキストとメモリが全チャットに引き継がれ、毎回説明し直す必要がない**
- プロジェクトに自前資料を貼ると出力品質がさらに上がる
- 効果: 実雇用なら月数千ドルのチームを約10分で構築

## ステップ2: 商品検証(約5分/従来3時間)

**原則: 勘で選ばない。惚れ込まない。実需のある候補をAIに順位付けさせる。**

1. 候補6商品を自分で集める(画像・価格・バリエーション・トレンド状況メモ)
2. 1メッセージでまとめて投入し、プロンプト:
   > "Analyze six products. The best combo of validation, margin, and evergreen demand."
3. 出力: 3軸スコアカード(各10点)
   - **Validation**: 実証された需要・実際にお金が使われているか
   - **Margin**: 広告費を引いても利益が残るか
   - **Evergreen demand**: 通年需要か一過性か
   - +各商品の「なぜ勝てるか / なぜリスクか」+優先度ランキング+スキップ判定

**動画内の実例:**
- 勝者: ビキニライン用ペインフリー脱毛クリーム — **GMV $12M・TikTok関連動画16.8万本**(=広告の実証済み設計図がある)×敏感肌というアンダーサーブドニッチ
- スキップ: ホワイトニングマウスウォッシュ — 直感では選んでいたが「**在庫残790個**=広告スケールした瞬間に在庫切れ」で却下
- **教訓: 在庫ボトルネックの確認は必須**

## ステップ3: ストア構築(約30分/従来1週間)

- **独自ドメイン必須**(Shopify無料サブドメインのままローンチは初心者最大のミス。URLだけで離脱される)。「.store」推奨
- **ゼロからデザインしない。売れている競合ストアURLをClaudeに渡してクローン改良:**
  > "Use this example link as a guide to build me out a mockup store. Then convert it into Shopify code sections for each section in a row with your own improvements. Then give me a step-by-step guide on how to get this exact store into my own Shopify."
- Claudeの成果物: ①HTMLモックアップ(Artifactで確認) ②セクション別Shopify Liquidコード ③反映手順ガイド
- ページ構成: ヒーロー → 購入ボックス → ベネフィット → How it works(3ステップ) → 競合比較表 → レビュー → FAQ → **スティッキーAdd to Cartバー**
- Shopify側: Edit code → sectionsフォルダに同名セクション作成 → コード貼付を全セクションで繰り返す → Customizeで配置・色・画像調整
- **エラー対応ループ: エラー文をそのままClaudeに貼る → 修正版をもらう → 貼り直す**(数回の往復は正常)

## サプライヤー

- 1688/Taobao工場直仕入ツール(動画では「Team Drop」表記)で画像検索→ストア直インポート。専属エージェント付き
- **仕入基準: 原価→売価で最低2.5倍。** 競合売価$25なら送料込$10以下で仕入れる

## ステップ4: 広告クリエイティブ(5分未満/従来$300・2週間/本)

- **この段階のゲームは物量。** 月5本のテストでは勝ちクリエイティブは見つからない
- AI広告生成ツール(Ecom Boss)をClaudeの**カスタムコネクター+スキルファイル**で連携(設定は1回2分)
- プロジェクトに商品・競合・ブランドボイス・顧客像が蓄積済みなので、**説明なしでオンブランドの広告**が出る(汎用AIスロップにならない)
- 手順: 商品画像+URL → アングル・ターゲット・フックを指示 → フォト広告生成 → 「この画像から動画を作って」→ AI UGC風動画広告
- **本質: 制作スピード=テスト時間=優位性。** 商品の鮮度ウィンドウが閉じる前に多アングルをテストし勝者に予算集中

## 収益直結の要点(まとめ)

1. 順番: 頭脳(Claudeプロジェクト)→ 商品検証 → ストア → 広告
2. 1プロジェクト=1ビジネス、1チャット=1タスク
3. 商品は「検証×マージン×通年需要」の3軸で機械的に決定
4. 在庫ボトルネック確認は必須
5. コンテンツエコシステム(TikTok動画数)が大きい商品×アンダーサーブドニッチ
6. 独自ドメインは最優先・最高ROIの投資
7. ストアは競合クローン改良で30分
8. 仕入2.5倍ルール(売価の40%以下で仕入れ)
9. 広告はクリエイティブ物量で勝つ
10. 最後のピースは広告運用スキル(スケール/損切り判断)
