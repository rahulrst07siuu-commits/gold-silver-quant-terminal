import os
import sys

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

import database.db_manager as db

proj = r"D:\Downloads\Gold_Silver_Quant_Project"
gold_csv = os.path.join(proj, "data", "GOLD_HOURLY_INR_CLEAN.csv")
silver_csv = os.path.join(proj, "data", "SILVER_HOURLY_INR_CLEAN.csv")

print("Initializing SQLite database structure...")
db.init_db()

print("Seeding database with verified historical records...")
db.seed_from_clean_csv(gold_csv, silver_csv)

gold_latest = db.get_latest_quote("gold")
silver_latest = db.get_latest_quote("silver")

print(f"Database ready at: {db.DB_FILE}")
print(f"Gold latest: {gold_latest.get('timestamp')} @ ₹{gold_latest.get('close')}")
print(f"Silver latest: {silver_latest.get('timestamp')} @ ₹{silver_latest.get('close')}")
