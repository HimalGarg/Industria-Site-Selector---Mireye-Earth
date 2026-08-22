import sqlite3
import json

conn = sqlite3.connect(r"backend\site_ranker.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()

rows = c.execute("SELECT cart_item_id, session_id, address, source_url, listing_title, image_url, details, llm_structured, added_at FROM cart_items ORDER BY added_at DESC LIMIT 5").fetchall()

for i, row in enumerate(rows):
    print(f"=== TOP ITEM #{i+1} ===")
    print(f"Address: {row['address']}")
    print(f"Source: {row['source_url']}")
    print(f"Listing Title: {row['listing_title']}")
    print(f"Image URL: {row['image_url']}")
    print(f"Added At: {row['added_at']}")
    print("\n--- DETAILS JSON ---")
    details = json.loads(row['details']) if row['details'] else {}
    print(json.dumps(details, indent=2))
    print("\n--- LLM STRUCTURED JSON ---")
    llm = json.loads(row['llm_structured']) if row['llm_structured'] else {}
    print(json.dumps(llm, indent=2))
    print("=" * 60 + "\n")
