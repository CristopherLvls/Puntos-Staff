#!/usr/bin/env python3
"""Lista colecciones y muestra muestras de la BD SirgioBOT (solo lectura)."""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

URI = os.getenv("MONGODB_READONLY_URI")
DB_NAME = os.getenv("MONGODB_READONLY_DB", "sirgiobot")


def main():
    if not URI:
        print("Configura MONGODB_READONLY_URI en .env")
        sys.exit(1)

    client = MongoClient(URI, serverSelectionTimeoutMS=15000)
    db = client[DB_NAME]
    print(f"Base de datos: {DB_NAME}\nColecciones:")
    for name in sorted(db.list_collection_names()):
        count = db[name].estimated_document_count()
        print(f"  - {name} (~{count} docs)")
        sample = db[name].find_one()
        if sample:
            sample.pop("_id", None)
            print(f"    Muestra: {json.dumps(sample, default=str, ensure_ascii=False)[:500]}")
        print()


if __name__ == "__main__":
    main()
