# 運用ランブック

日常運用は「毎日5分・週1で30分」を想定。自動化されている部分は触らない。

## 毎日(自動 — GitHub Actions / cron)

`python -m muzaiko.cli run` が以下を無人実行:

| 工程 | 内容 |
|---|---|
| research | 仕入先フィードから新候補を選定(出品枠が空いていれば) |
| publish | 候補を出品(local時は out/listings_export.csv に一括登録用CSV) |
| sync | 価格・在庫を仕入先に追従。**在庫切れは即・出品停止**(売り越し防止) |
| orders | 受注取込 → 自動発注 or out/purchase_queue.csv に発注キュー |
| optimize | 値上げ実験の開始/評価、赤字SKU停止、14日売れない出品の入替 |
| report | 収益レポート出力 + Webhook通知(設定時) |

## 毎日(人間 — 5分)

1. 通知 or `out/report.txt` を一読
2. `out/purchase_queue.csv` があれば仕入先で発注(自動発注仕入先なら不要)
3. 追跡番号が届いたらCSVに貼って:
   ```bash
   python -m muzaiko.cli shipments --file data/shipments_in.csv
   ```
4. 顧客からの問い合わせに返信(ここはあなたの信用の源泉。自動化しない)

## 週1(人間 — 30分)

1. レポートの「推奨アクション」を確認(optimizerが自動処理済みのものは
   ログに出ている。残っているのは判断が必要なものだけ)
2. 入替で空いた出品枠に対して、仕入先の新着CSVを取り直して `run`
3. 価格実験の結果(state/price_experiments.json)を眺めて、
   採用が続くカテゴリ=需要が強い → 同カテゴリの商品を仕入先で探して追加
4. SNS投稿の予約(週3本目安)

## 月1(人間)

- 販路の手数料・規約の変更確認(STRATEGY.md の数値は2026-07-18時点)
- 売上規模の確認:
  - 月商10万円超 → Shopify移行を検討(手数料7%→4%、STRATEGY.md参照)
  - 利益が出始めたら開業届・帳簿(会計ソフト連携)を整える
- `config.json` のチューニング:
  - 売れているのに粗利が薄い → `target_margin_rate` を上げて次回出品から反映
  - 出品が埋まらない → `research.min_expected_margin` を下げる(慎重に)

## トラブルシューティング

| 症状 | 対処 |
|---|---|
| 受注したのに仕入先在庫がない | `sync` の実行頻度を上げる(1日2回に)。それでも起きたら即返金+謝罪が最善 |
| CSVが文字化けする | `supplier.encoding` を `"cp932"` に |
| 列名が合わずresearchが失敗 | エラーに実際の列名一覧が出る。`supplier.column_map` で対応付け |
| Shopify/BASEのAPIエラー | トークン期限・スコープを確認。エラー本文の先頭500字がログに出る |
| 価格実験が始まらない | 直近7日で3個以上売れたSKUが対象(config の optimizer.min_sales_to_test) |
