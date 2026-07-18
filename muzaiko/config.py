"""設定管理。config.json + 環境変数で上書き。標準ライブラリのみ使用。"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "supplier": {
        "type": "csv",                      # csv | aliexpress(要API)
        "feed_path": "data/sample_supplier.csv",
    },
    "channel": {
        "type": "local",                    # local(ドライラン) | shopify | shopee_export
        "shopify_domain": "",               # 例: mystore.myshopify.com
        "shopify_token_env": "SHOPIFY_ACCESS_TOKEN",
        "fee_rate": 0.10,                   # 販売手数料+決済手数料の想定合計率
        "currency": "JPY",                  # 出品価格の通貨(輸出チャネルで変更)
        "fx_rate": 1.0,                     # 1円あたりの現地通貨レート(例: SGDなら0.0087)
        "max_days_to_ship": 10,             # 発送期限の上限(Shopeeプレオーダーは最大10日)
    },
    "research": {
        "max_listings": 20,                 # 同時出品数の上限
        "max_cost": 8000,                   # 仕入原価の上限(円)
        "min_stock": 3,                     # 仕入先在庫の下限
        "max_shipping_days": 21,            # 出荷リードタイム上限
        "min_expected_margin": 500,         # 期待粗利の下限(円)
        # 越境ECで需要が伸びているカテゴリ(推し活・コレクター消費)を加点する
        # キーワード。タイトル/カテゴリに部分一致でトレンド加点(BEENOS 2025年版
        # 越境ECランキング: 1位トレカ 2位ホビー 3位アニメグッズ)。
        "trend_keywords": [
            "トレカ", "トレーディングカード", "カードゲーム",
            "ホビー", "フィギュア", "ぬいぐるみ", "マスコット", "キーホルダー",
            "アニメ", "キャラクター", "プラモデル", "限定",
            "ポケモン", "ちいかわ", "サンリオ", "シルバニア",
        ],
    },
    "pricing": {
        "target_margin_rate": 0.35,         # 目標粗利率(手数料控除後)
        "min_margin_rate": 0.12,            # これを下回ったら値上げ or 出品停止
        "min_margin_jpy": 300,              # 最低粗利額(円)
        "psychological_ending": 80,         # 価格末尾(例: 2,980円)
        # 米国向け等、関税をセラー負担(DDP)で売る場合の上乗せ率。
        # デミニミス撤廃+一律関税の環境では米国向けは0.10前後を推奨。
        "tariff_buffer_rate": 0.0,
    },
    "listing": {
        "use_llm": False,                   # ANTHROPIC_API_KEY があれば説明文をLLM生成
        "shop_name": "muzaiko store",
    },
    "state_dir": "state",
    "output_dir": "out",
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    def __init__(self, data: dict[str, Any], root: Path):
        self.data = data
        self.root = root

    @classmethod
    def load(cls, root: str | Path = ".", path: str = "config.json") -> "Config":
        root = Path(root).resolve()
        cfg_file = root / path
        data = DEFAULTS
        if cfg_file.exists():
            with open(cfg_file, encoding="utf-8") as f:
                data = _deep_merge(DEFAULTS, json.load(f))
        return cls(data, root)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    @property
    def state_dir(self) -> Path:
        p = self.root / self.data["state_dir"]
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def output_dir(self) -> Path:
        p = self.root / self.data["output_dir"]
        p.mkdir(parents=True, exist_ok=True)
        return p

    def shopify_token(self) -> str:
        return os.environ.get(self.data["channel"]["shopify_token_env"], "")
