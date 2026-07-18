"""JSONファイルベースの状態ストア(listings / orders)。"""
from __future__ import annotations

import json
from pathlib import Path

from .models import Listing, Order


class Store:
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.listings_file = state_dir / "listings.json"
        self.orders_file = state_dir / "orders.json"

    # --- listings ---
    def load_listings(self) -> dict[str, Listing]:
        if not self.listings_file.exists():
            return {}
        raw = json.loads(self.listings_file.read_text(encoding="utf-8"))
        return {d["sku"]: Listing.from_dict(d) for d in raw}

    def save_listings(self, listings: dict[str, Listing]) -> None:
        data = [l.to_dict() for l in listings.values()]
        self.listings_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # --- generic json (実験記録などの補助状態) ---
    def load_json(self, name: str, default):
        f = self.state_dir / name
        if not f.exists():
            return default
        return json.loads(f.read_text(encoding="utf-8"))

    def save_json(self, name: str, data) -> None:
        (self.state_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # --- orders ---
    def load_orders(self) -> dict[str, Order]:
        if not self.orders_file.exists():
            return {}
        raw = json.loads(self.orders_file.read_text(encoding="utf-8"))
        return {d["order_id"]: Order.from_dict(d) for d in raw}

    def save_orders(self, orders: dict[str, Order]) -> None:
        data = [o.to_dict() for o in orders.values()]
        self.orders_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
