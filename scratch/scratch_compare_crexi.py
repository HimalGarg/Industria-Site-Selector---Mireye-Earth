import sqlite3
import json

conn = sqlite3.connect(r"backend\site_ranker.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()

rows = c.execute("SELECT cart_item_id, session_id, address, source_url, listing_title, image_url, details, llm_structured, added_at FROM cart_items WHERE source_url LIKE '%crexi.com%' ORDER BY added_at DESC").fetchall()

print(f"Total Crexi items in DB: {len(rows)}\n")

for i, row in enumerate(rows):
    print(f"=== CREXI ITEM #{i+1} ===")
    print(f"Address: {row['address']}")
    print(f"Source: {row['source_url']}")
    print(f"Title: {row['listing_title']}")
    print(f"Image: {row['image_url']}")
    print(f"Added At: {row['added_at']}")
    details = json.loads(row['details']) if row['details'] else {}
    print(f"Details Keys ({len(details)}): {list(details.keys())}")
    llm = json.loads(row['llm_structured']) if row['llm_structured'] else {}
    print(f"LLM Keys: {list(llm.keys())}")
    print("-" * 50 + "\n")
