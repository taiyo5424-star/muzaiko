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

| 販売先 | 無在庫販売の可否 |
|---|---|
| 自社EC(Shopify / BASE / STORES) | ✅ 可(本システムの推奨構成) |
| Shopee(東南アジア輸出) | ✅ 可(プレオーダー機能=発送期限最大10日で正規運用。DTS遵守必須) |
| Yahoo!ショッピング | △ 条件付き(納期遵守が必須) |
| Amazon | △ ドロップシッピングポリシー準拠時のみ(自分が販売者として表示される事等) |
| メルカリ / ラクマ / PayPayフリマ | ❌ 規約で明確に禁止 |
| eBay(輸出) | ✅ 可(卸からの直送のみ。小売他社からの直送は禁止。米国向けはDDP=関税込み価格が前提) |

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
| 仕入先への発注 | △ API対応仕入先なら自動。それ以外は発注キューCSVを出力し人間が発注 |
| 収益分析・改善提案 | ✅ 全自動(`report`) |
| **アカウント開設・決済設定・法的表記・顧客対応** | ❌ 人間(あなた)の仕事 |

> 収益は保証されません。無在庫販売は「薄利×回転×継続改善」のビジネスです。
> 本システムはその改善ループを自動で回すための道具です。

---

## クイックスタート(3分・課金なしのドライラン)

```bash
cd muzaiko
cp config.example.json config.json   # 省略可(デフォルト設定で動く)

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
```

テスト実行: `python -m unittest discover tests`

---

## 本番運用への道筋

### STEP 1 — 店舗と仕入先を用意する(人間の作業)

1. **Shopify** で開店(月額 $5〜 のBasicプランで可)
   - 特定商取引法ページ・返品ポリシーを作成
   - 管理画面 → アプリ開発 → カスタムアプリで **Admin API アクセストークン** を発行
     (権限: `write_products`, `read_orders`)
2. **仕入先** を確保
   - 国内卸: NETSEA / TopSeller など → 商品CSVをダウンロードして `data/` に配置
   - 海外: AliExpress Dropshipping API(`muzaiko/suppliers.py` のスタブに実装を追加)

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
  米国向け等は `tariff_buffer_rate` で関税分(DDP)も価格に織り込める。
- **売り越し防止** (`sync.py`): 仕入先在庫切れを検知した瞬間に出品を自動停止。在庫復活で自動再開。
- **リサーチスコア** (`research.py`): 粗利額50点+在庫の厚さ15点+配送速度15点+
  トレンド適合20点(トレカ/ホビー/アニメ等の推し活・コレクターカテゴリ)で採点し上位のみ出品。
- **Shopee輸出対応** (`channels.py` の `shopee_export`): セラーセンター一括アップロード用CSVを
  現地通貨換算で自動生成。リードタイムからプレオーダーを自動判定し、発送期限10日超は警告。
- **改善アクション** (`analytics.py`): レポートが毎回、
  「売れ筋の値上げテスト」「赤字SKUの停止」「動かない出品の入替」を具体的に提案。

> 📈 **2026年7月時点の市場環境に基づく戦略(なぜ輸出×Shopee×推し活カテゴリなのか)は
> [docs/strategy-2026-07.md](docs/strategy-2026-07.md) を参照。**根拠ソース付き。

**運用のコツ**: 週1回、レポートの推奨アクションに従って `config.json` の
`target_margin_rate` や仕入先フィードを調整 → 出品を入れ替える。このループの継続が利益の源泉です。

## 設定リファレンス(config.json)

| キー | 意味 | 既定値 |
|---|---|---|
| `research.max_listings` | 同時出品数の上限 | 20 |
| `research.max_cost` | 仕入原価の上限(円) | 8000 |
| `research.min_expected_margin` | 出品条件となる期待粗利(円) | 500 |
| `research.trend_keywords` | トレンド加点するキーワード(推し活・コレクター系) | トレカ/ホビー/アニメ等 |
| `pricing.target_margin_rate` | 目標粗利率(手数料控除後) | 0.35 |
| `pricing.min_margin_rate` | 値上げ発動ラインの粗利率 | 0.12 |
| `pricing.tariff_buffer_rate` | DDP(関税セラー負担)の上乗せ率。米国向けは0.10推奨 | 0.0 |
| `channel.fee_rate` | 販売+決済手数料の合計率 | 0.10 |
| `channel.currency` / `channel.fx_rate` | 輸出時の通貨と換算レート(1円あたり) | JPY / 1.0 |
| `channel.max_days_to_ship` | 発送期限の上限(Shopeeプレオーダーは最大10日) | 10 |
| `listing.use_llm` | Claude による説明文生成(要 `ANTHROPIC_API_KEY` と `pip install anthropic`) | false |

## ディレクトリ構成

```
muzaiko/
├── muzaiko/           # パッケージ本体
│   ├── cli.py         # コマンド入口
│   ├── suppliers.py   # 仕入先アダプタ(CSV / AliExpressスタブ)
│   ├── channels.py    # 販売チャネル(local / Shopify)
│   ├── research.py    # 商品選定・スコアリング
│   ├── listing_gen.py # 出品コピー生成(テンプレ / LLM)
│   ├── pricing.py     # 価格エンジン
│   ├── sync.py        # 在庫・価格同期
│   ├── orders.py      # 受注→発注変換
│   └── analytics.py   # 収益レポート
├── data/              # 仕入先フィード置き場
├── state/             # 出品・受注の状態(JSON、自動生成)
├── out/               # レポート・発注キュー・ドライラン出品(自動生成)
└── tests/             # スモークテスト
```

## ロードマップ(拡張ポイント)

- [x] Shopee輸出チャネル(一括アップロードCSV生成・プレオーダー対応)
- [x] トレンドカテゴリ加点(推し活・コレクター消費)
- [x] DDP関税バッファ・多通貨価格
- [ ] Shopee Open Platform API 直結(法人審査後の自動出品・受注取得)
- [ ] AliExpress Dropshipping API 実装(自動発注の完成)
- [ ] NETSEA など国内卸のフィード自動取得
- [ ] 競合価格スクレイピングによる動的リプライシング
- [ ] 楽天市場 / Yahoo!ショッピング / eBay チャネルアダプタ
- [ ] 追跡番号の自動登録と顧客通知
- [ ] LINE/Slack への日次レポート通知
