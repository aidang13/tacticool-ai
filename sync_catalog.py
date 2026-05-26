"""
sync_catalog.py — Pull all products from WooCommerce and save to products.json

Usage:
    python sync_catalog.py

Requires environment variables (set in Railway or .env):
    WOO_URL            e.g. https://tacticoolgun.com
    WOO_CONSUMER_KEY   from WooCommerce > Settings > Advanced > REST API
    WOO_CONSUMER_SECRET
"""

import requests
import json
import os
import sys

WOO_URL = os.environ.get("WOO_URL", "https://tacticoolgun.com")
WOO_KEY = os.environ.get("WOO_CONSUMER_KEY", "")
WOO_SECRET = os.environ.get("WOO_CONSUMER_SECRET", "")


def fetch_all_products():
    products = []
    page = 1
    print(f"Fetching products from {WOO_URL}...")

    while True:
        try:
            r = requests.get(
                f"{WOO_URL}/wp-json/wc/v3/products",
                params={"per_page": 100, "page": page, "status": "publish", "stock_status": "instock"},
                auth=(WOO_KEY, WOO_SECRET),
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"Error on page {page}: {e}")
            break

        if not data:
            break

        # Keep only the fields we need for the AI
        for p in data:
            products.append({
                "id": p.get("id"),
                "name": p.get("name", ""),
                "permalink": p.get("permalink", ""),
                "price": p.get("price", ""),
                "regular_price": p.get("regular_price", ""),
                "sale_price": p.get("sale_price", ""),
                "stock_status": p.get("stock_status", ""),
                "short_description": p.get("short_description", ""),
                "description": p.get("description", "")[:500],
                "categories": p.get("categories", []),
                "tags": p.get("tags", []),
                "attributes": p.get("attributes", []),
                "sku": p.get("sku", ""),
            })

        print(f"  Page {page}: {len(data)} products (total so far: {len(products)})")

        if len(data) < 100:
            break
        page += 1

    return products


def main():
    if not WOO_KEY or not WOO_SECRET:
        print("ERROR: WOO_CONSUMER_KEY and WOO_CONSUMER_SECRET must be set")
        sys.exit(1)

    products = fetch_all_products()
    output_path = os.path.join(os.path.dirname(__file__), "products.json")

    with open(output_path, "w") as f:
        json.dump(products, f, indent=2)

    print(f"\nDone! Saved {len(products)} products to {output_path}")


if __name__ == "__main__":
    main()
