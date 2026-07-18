# muzaiko — 無在庫販売(ドロップシッピング)自動化パイプライン

仕入先フィードの取得から、出品作成・価格/在庫同期・受注の発注転送・収益分析までを
1コマンドで回す自動化システムです。Python 3.11+ の標準ライブラリのみで動作します。

```
仕入先フィード ──▶ リサーチ ──▶ 出品生成 ──▶ 販売チャネル
   (CSV/API)     (選定・採点)  (コピー+価格)   (Shopify等)
        ▲                                        │
        │            価格・在庫同期(毎日) ◀──────┤
        │                                        ▼
   発注(自動/キュー) ◀───── 受注取込 ◀───── 顧客の注文
                                │
                                ▼
                     収益レポート+改善アクション
```

---

## ⚠️ はじめに必ず読むこと(法律・規約)

無在庫販売そのものは日本で違法ではありませんが、**やり方を間違えると規約違反・法令違反**になります。

| 販売先 | 無在庫販売の可否(2026-07-18 検証) |
|---|---|
| 自社EC(Shopify / BASE / STORES) | ✅ 可(本システムの推奨構成) |
| Yahoo!ショッピング | ❌ **約款で明示禁止**(在庫未確保出品・他ECからの直送を禁止。出店停止の執行事例あり) |
| Amazon | △ ポリシーG201808410準拠時のみ公式容認(seller of record要件等。違反で出品権限取消) |
| メルカリ / ラクマ / PayPayフリマ | ❌ 規約で明確に禁止 |
| eBay(輸出) | ✅ 可(卸からの直送のみ。小売他社からの直送は禁止。実効手数料 約17〜20%) |

> 販路・仕入先の最新の事実関係と推奨戦略は **[STRATEGY.md](STRATEGY.md)** を参照
> (多源泉検証済みリサーチに基づく。固定費0円で始める Phase 0 構成を推奨)。

守るべきこと:
- **特定商取引法**: 販売者名・住所・連絡先・引渡時期などの表記が必須(Shopifyならページを作成)
- **景品表示法**: 誇大表現・二重価格表示の禁止(本システムのテンプレは考慮済み)
- **納期の正直な表示**: 仕入先リードタイムをそのまま表示する設計にしています
- 古物商許可(中古品を扱う場合)、輸入時は関税・PSE/食品衛生法等の規制品に注意

## 何が自動で、何が人間の仕事か

| 工程 | 自動化 |
|---|---|
| 商品リサーチ・選定・採点 | ✅ 全自動(`research`) |
| タイトル・説明文・価格の生成 | ✅ 全自動(`publish`、LLM生成もオプションで可) |
| 価格改定・在庫同期・売り越し防止 | ✅ 全自動(`sync`、毎日実行推奨) |
| 受注の取込 | ✅ 全自動(`orders`) |
| 仕入先への発注 | △ AliExpress APIなら自動発注。それ以外は発注キューCSVを出力し人間が発注 |
| **収益最適化(値上げ実験・赤字停止・出品入替)** | ✅ 全自動(`optimize`) |
| 発送登録・追跡番号・顧客への発送通知 | ✅ 半自動(`shipments`: 追跡番号CSVを置くだけ) |
| 収益分析・改善提案・Slack/Discord通知 | ✅ 全自動(`report`、KPIダッシュボードも自動更新) |
| SNS集客用の投稿文作成 | ✅ 全自動(`content`: 週3本×2週間分のドラフト生成) |
| 記帳・確定申告用の仕訳出力 | ✅ 全自動(`ledger`) |
| **アカウント開設・決済設定・法的表記・顧客対応** | ❌ 人間(あなた)の仕事(定型文は [docs/CUSTOMER_SERVICE_TEMPLATES.md](docs/CUSTOMER_SERVICE_TEMPLATES.md)) |

> 収益は保証されません。無在庫販売は「薄利×回転×継続改善」のビジネスです。
> 本システムはその改善ループを自動で回すための道具です。

---

## クイックスタート(3分・課金なしのドライラン)

```bash
cd muzaiko
python -m muzaiko.cli init       # config.json を作成し、次にやることを表示

python -m muzaiko.cli research   # サンプル仕入先フィードから候補選定
python -m muzaiko.cli publish    # out/listings/ に出品データを生成
python -m muzaiko.cli sync       # 価格・在庫同期
python -m muzaiko.cli report     # レポート出力

# テスト受注を流してみる
cat > state/incoming_orders.json <<'EOF'
[{"order_id":"TEST-1","sku":"SKU-007","qty":2,"sale_price":3680,"fee":736,"ordered_at":"2026-07-18T09:00:00"}]
EOF
python -m muzaiko.cli orders     # out/purchase_queue.csv に発注キューが出る
python -m muzaiko.cli report

# まとめて実行
python -m muzaiko.cli run

# その他のコマンド
python -m muzaiko.cli content    # SNS投稿ドラフト(out/sns_posts.md)
python -m muzaiko.cli ledger     # 仕訳CSV(out/ledger.csv)
python tools/simulate.py 30      # 30日運用シミュレーション(デモ・検証用)
```

`report` 実行後は `out/dashboard.html` をブラウザで開くとKPIタイルと
売上・粗利の推移グラフが見られます(データは日次で自動蓄積)。

テスト実行: `python -m unittest discover tests`

---

## 本番運用への道筋

### STEP 1 — 店舗と仕入先を用意する(人間の作業)

**固定費0円で始める場合(推奨・詳細はSTRATEGY.md)**
1. **TopSeller** おためしプラン(永年無料・5商品)に登録し、商品CSVを `data/` に配置
   - 国内卸のCSVはShift_JISが多い → `supplier.encoding: "cp932"`
   - 列名が違っても `supplier.column_map` で対応付け(例: `{"sku": "商品コード", "cost": "卸価格"}`)
2. **BASE** スタンダードプラン(月額0円)で開店し、特定商取引法ページを作成
   (テンプレ: [docs/TOKUSHOHO_TEMPLATE.md](docs/TOKUSHOHO_TEMPLATE.md))
3. 出品は2通り:
   - **手動**: `publish` が出力する `out/listings_export.csv` を管理画面から一括登録
   - **API**: BASE Developersでアプリ登録し `BASE_CLIENT_ID` / `BASE_CLIENT_SECRET` /
     `BASE_REFRESH_TOKEN` を設定 → `channel.type: "base"` で出品・受注取込まで自動
4. `channel.fee_rate` は `0.07`(BASEの手数料実勢)

**本格運用(月商10万円〜)**
1. **Shopify** Basic(年払い ¥3,650/月)で開店
   - 管理画面 → アプリ開発 → カスタムアプリで **Admin API アクセストークン** を発行
     (権限: `write_products`, `read_orders`)
   - `fee_rate` は `0.04` 程度に(決済手数料 3.25〜3.55%)
2. 仕入先を **NETSEA**(「販売後注文可」ラベル商材=ドロップシッピング公式対応)に拡大
   - 検索フィルタ「消費者へ直送=対応可」で絞り込み、CSVを `data/` へ
   - 海外仕入は AliExpress Dropshipping API(`muzaiko/aliexpress.py`、キー取得後に要テスト)

### STEP 2 — 設定を切り替える

```json
// config.json
{
  "supplier": { "type": "csv", "feed_path": "data/your_feed.csv" },
  "channel": {
    "type": "shopify",
    "shopify_domain": "yourstore.myshopify.com",
    "fee_rate": 0.07
  }
}
```

```bash
export SHOPIFY_ACCESS_TOKEN="shpat_xxxx"
python -m muzaiko.cli run
```

### STEP 3 — 毎日自動で回す

`.github/workflows/daily-run.yml` を同梱しています。

1. リポジトリ Variables に `MUZAIKO_ENABLED=true`
2. Secrets に `SHOPIFY_ACCESS_TOKEN`
3. 毎朝 JST 6:00 に research→publish→sync→orders→report が実行され、
   レポートと発注キューが Actions のартファクトに出力されます

(サーバー運用なら cron で `python -m muzaiko.cli run` を1日1〜2回)

---

## 収益最大化の仕組み

- **価格エンジン** (`pricing.py`): 手数料控除後に目標粗利率(既定35%)を確保する価格を自動算出。
  末尾◯80円の心理的価格。原価が上がって粗利率が下限(12%)を割ると自動値上げ。
- **自動価格実験** (`optimizer.py`): 直近7日で3個以上売れたSKUは自動で+7%の値上げ実験を開始。
  7日後に売上レート(販売速度×価格)を評価し、維持できていれば新価格を採用、
  落ちていれば旧価格に自動ロールバック。採用後はクールダウンを挟んで段階的に上限を探る。
- **自動入替** (`optimizer.py`): 赤字SKUは自動停止。14日間売れない出品は自動で枠を解放し、
  次回リサーチで新商品と入れ替わる。
- **売り越し防止** (`sync.py`): 仕入先在庫切れを検知した瞬間に出品を自動停止。在庫復活で自動再開。
- **リサーチスコア** (`research.py`): 粗利額60点+在庫の厚さ20点+配送速度20点で採点し上位のみ出品。
- **日次通知** (`notify.py`): 環境変数 `MUZAIKO_WEBHOOK_URL` にSlack/DiscordのWebhook URLを
  設定すると、毎日のレポートが自動送信される。

つまり `run` を毎日回すだけで「売れる商品に絞り、売れる限界まで値段を上げ、
死に筋を捨てて新商品を試す」ループが自動で回り続けます。

## 出荷オペレーション

仕入先(または発送代行)から届く追跡番号の一覧をCSVで置いて1コマンド:

```csv
# data/shipments_in.csv
order_id,tracking_number,carrier
123456789-111,JP123456789,ヤマト運輸
```

```bash
python -m muzaiko.cli shipments --file data/shipments_in.csv
```

Shopify運用時は Fulfillment API で発送登録+顧客への発送通知メールまで自動実行されます。

## AliExpress 自動発注(任意)

1. https://openservice.aliexpress.com でアプリ登録(Drop Shipping カテゴリ)し、
   `ALIEXPRESS_APP_KEY` / `ALIEXPRESS_APP_SECRET` / `ALIEXPRESS_ACCESS_TOKEN` を設定
2. `data/aliexpress_products.txt` に扱いたい商品ID(1行1ID)を記載
3. `config.json` で `"supplier": {"type": "aliexpress"}`

これで `research` が価格・在庫をAPIから取得し、`orders` が自動発注まで行います。
※ 署名実装は公開仕様準拠ですが、**実キー取得後に必ず1商品でテスト**してください。

## 設定リファレンス(config.json)

| キー | 意味 | 既定値 |
|---|---|---|
| `research.max_listings` | 同時出品数の上限 | 20 |
| `research.max_cost` | 仕入原価の上限(円) | 8000 |
| `research.min_expected_margin` | 出品条件となる期待粗利(円) | 500 |
| `pricing.target_margin_rate` | 目標粗利率(手数料控除後) | 0.35 |
| `pricing.min_margin_rate` | 値上げ発動ラインの粗利率 | 0.12 |
| `channel.fee_rate` | 販売+決済手数料の合計率 | 0.10 |
| `listing.use_llm` | Claude による説明文生成(要 `ANTHROPIC_API_KEY` と `pip install anthropic`) | false |
| `optimizer.price_step` | 値上げ実験の幅 | 0.07 |
| `optimizer.min_sales_to_test` | 実験開始に必要な直近販売数 | 3 |
| `optimizer.eval_window_days` | 実験の評価期間(日) | 7 |
| `optimizer.stale_days` | 販売ゼロで入替対象になる日数 | 14 |
| `notify.type` | 通知先(slack / discord) | slack |

## ディレクトリ構成

```
muzaiko/
├── muzaiko/           # パッケージ本体
│   ├── cli.py         # コマンド入口
│   ├── suppliers.py   # 仕入先アダプタ(CSV: 列マッピング/cp932対応、AliExpress)
│   ├── channels.py    # 販売チャネル(local / Shopify / BASE)
│   ├── research.py    # 商品選定・スコアリング
│   ├── listing_gen.py # 出品コピー生成(テンプレ / LLM)
│   ├── pricing.py     # 価格エンジン
│   ├── sync.py        # 在庫・価格同期
│   ├── orders.py      # 受注→発注変換
│   ├── optimizer.py   # 自動最適化(価格実験・赤字停止・入替)
│   ├── shipments.py   # 追跡番号取込・発送登録
│   ├── aliexpress.py  # AliExpress Dropshipping APIクライアント
│   ├── ebay.py        # eBay輸出チャネル(Sell API、JPY→USD換算)
│   ├── content.py     # SNS投稿ドラフト生成(集客)
│   ├── accounting.py  # 仕訳CSVエクスポート(確定申告用)
│   ├── dashboard.py   # KPIダッシュボード(HTML)
│   ├── notify.py      # Slack/Discord通知
│   └── analytics.py   # 収益レポート
├── data/              # 仕入先フィード置き場
├── docs/              # 特商法テンプレ・運用ランブック
├── state/             # 出品・受注の状態(JSON、自動生成)
├── out/               # レポート・発注キュー・一括出品CSV(自動生成)
└── tests/             # テスト
```

日々の運用手順(毎日5分・週1で30分)は [docs/OPERATIONS.md](docs/OPERATIONS.md) を参照。

## ロードマップ(拡張ポイント)

- [x] AliExpress Dropshipping API 実装(自動発注)
- [x] 追跡番号の自動登録と顧客通知(`shipments`)
- [x] Slack/Discord への日次レポート通知(`notify.py`)
- [x] 自動価格実験によるリプライシング(`optimizer.py`)
- [x] BASE チャネルアダプタ+一括出品CSVエクスポート
- [x] 国内卸CSVの列マッピング・Shift_JIS対応(NETSEA/TopSellerのCSVをそのまま利用可)
- [x] eBay輸出チャネルアダプタ(`muzaiko/ebay.py`、Sell API。要キー・要Sandboxテスト)
- [x] SNS集客コンテンツ生成 / 仕訳CSV / KPIダッシュボード / 30日シミュレータ
- [ ] 競合価格スクレイピングによる動的リプライシング
- [ ] 楽天市場チャネルアダプタ(Yahoo!は規約禁止のため対象外)
