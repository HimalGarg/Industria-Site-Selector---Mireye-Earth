import sqlite3
import json

conn = sqlite3.connect(r"backend\site_ranker.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Find duplicate listing URLs
urls = c.execute("SELECT source_url, COUNT(*) as cnt FROM cart_items WHERE source_url LIKE '%crexi%' GROUP BY source_url HAVING cnt > 1").fetchall()

print("Duplicates found:")
for u in urls:
    print(f"URL: {u['source_url']} ({u['cnt']} captures)")

# Let's inspect the Wendy's listing captures across time
rows = c.execute("SELECT cart_item_id, address, source_url, listing_title, image_url, details, llm_structured, added_at FROM cart_items WHERE source_url LIKE '%2601532%' ORDER BY added_at DESC").fetchall()

print(f"\nComparing {len(rows)} captures of Wendy's (Harrisburg, PA):\n")

for i, r in enumerate(rows):
    print(f"--- Capture #{i+1} at {r['added_at']} ---")
    details = json.loads(r['details']) if r['details'] else {}
    print(f"Details Keys ({len(details)}):", sorted(list(details.keys())))
    print("Price in details:", details.get('price'))
    print("Image URL:", r['image_url'])
    print("Title:", r['listing_title'])
    print()
