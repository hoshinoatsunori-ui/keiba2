"""
check_detail.py - horse_detailの保存データを確認するスクリプト
使い方: python check_detail.py
"""
import sqlite3, json
from pathlib import Path

DB_PATH = Path(__file__).parent / "keiba.db"

with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    
    cnt = conn.execute("SELECT COUNT(*) FROM horse_detail").fetchone()[0]
    print(f"=== horse_detail: {cnt}件 ===")
    
    if cnt == 0:
        print("データがありません")
    else:
        r = conn.execute("SELECT horse_id, bamei, recent_races FROM horse_detail LIMIT 1").fetchone()
        rr = json.loads(r["recent_races"] or "[]")
        print(f"\n馬名: {r['bamei']}  horse_id: {r['horse_id']}")
        print(f"近走件数: {len(rr)}")
        if rr:
            print(f"\n1走目のキー: {list(rr[0].keys())}")
            print(f"\n1走目の内容:")
            for k, v in rr[0].items():
                print(f"  {k}: {repr(v)}")