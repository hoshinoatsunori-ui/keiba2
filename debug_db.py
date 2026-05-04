"""
debug_db.py - DBの状態確認スクリプト
使い方: python debug_db.py
"""
import sqlite3, json
from pathlib import Path

DB_PATH = Path(__file__).parent / "keiba.db"

with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row

    # racesテーブル
    races = conn.execute("SELECT race_id, race_name, status FROM races LIMIT 5").fetchall()
    print("=== races (先頭5件) ===")
    for r in races: print(f"  {r['race_id']}  {r['race_name']}  {r['status']}")

    # horsesのhorse_id
    print("\n=== horses の horse_id (先頭5件) ===")
    rows = conn.execute("SELECT race_id, umaban, bamei, horse_id FROM horses LIMIT 5").fetchall()
    for r in rows: print(f"  馬番={r['umaban']}  {r['bamei']}  horse_id='{r['horse_id']}'")

    total = conn.execute("SELECT COUNT(*) FROM horses").fetchone()[0]
    has_id = conn.execute("SELECT COUNT(*) FROM horses WHERE horse_id != ''").fetchone()[0]
    print(f"\n  horse_id取得状況: {has_id}/{total}頭")

    # horse_detailテーブル
    print("\n=== horse_detail (先頭5件) ===")
    details = conn.execute("SELECT horse_id, bamei, father, mother, mother_father, updated_at FROM horse_detail LIMIT 5").fetchall()
    if details:
        for d in details:
            print(f"  horse_id={d['horse_id']}  {d['bamei']}")
            print(f"    父={d['father']}  母={d['mother']}  母父={d['mother_father']}")
            print(f"    updated={d['updated_at']}")
    else:
        print("  ★ horse_detailテーブルが空です ★")
        print("  → 「🧬 血統・近走を取得」ボタンを押してください")

    # 結合確認
    print("\n=== horses LEFT JOIN horse_detail (先頭3件) ===")
    joined = conn.execute("""
        SELECT h.umaban, h.bamei, h.horse_id, hd.father, hd.mother
        FROM horses h LEFT JOIN horse_detail hd ON h.horse_id = hd.horse_id
        LIMIT 3
    """).fetchall()
    for r in joined:
        print(f"  馬番={r['umaban']}  {r['bamei']}  horse_id={r['horse_id']}")
        print(f"    father='{r['father']}'  mother='{r['mother']}'")
        joined_ok = bool(r['father'])
        print(f"    結合状態: {'✅ OK' if joined_ok else '❌ horse_detailが空またはhorse_idが不一致'}")