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
        "type": "local",                    # local(ドライラン) | shopify
        "shopify_domain": "",               # 例: mystore.myshopify.com
        "shopify_token_env": "SHOPIFY_ACCESS_TOKEN",
        "fee_rate": 0.10,                   # 販売手数料+決済手数料の想定合計率
    },
    "research": {
        "max_listings": 20,                 # 同時出品数の上限
        "max_cost": 8000,                   # 仕入原価の上限(円)
        "min_stock": 3,                     # 仕入先在庫の下限
        "max_shipping_days": 21,            # 出荷リードタイム上限
        "min_expected_margin": 500,         # 期待粗利の下限(円)
    },
    "pricing": {
        "target_margin_rate": 0.35,         # 目標粗利率(手数料控除後)
        "min_margin_rate": 0.12,            # これを下回ったら値上げ or 出品停止
        "min_margin_jpy": 300,              # 最低粗利額(円)
        "psychological_ending": 80,         # 価格末尾(例: 2,980円)
    },
    "listing": {
        "use_llm": False,                   # ANTHROPIC_API_KEY があれば説明文をLLM生成
        "shop_name": "muzaiko store",
    },
    "optimizer": {
        "enabled": True,
        "price_step": 0.07,                 # 値上げ実験の幅(7%)
        "min_sales_to_test": 3,             # 実験開始に必要な直近販売数
        "eval_window_days": 7,              # 実験の評価期間(日)
        "stale_days": 14,                   # 販売ゼロで入替対象になる日数
        "auto_delist_loss": True,           # 赤字SKUの自動停止
    },
    "notify": {
        "type": "slack",                    # slack | discord
        "webhook_env": "MUZAIKO_WEBHOOK_URL",
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
