"""
fix_race_names.py - horse_detailのrace_nameから「2勝」「1勝」等を除去する
scraper.pyの更新なしにDBを直接修正します
使い方: python fix_race_names.py
"""
import sqlite3, json, re
from pathlib import Path

DB_PATH = Path(__file__).parent / "keiba.db"

# クラス名パターン（レース名に混入するもの）
CLASS_PATTERN = re.compile(r'[0-9][勝障]$|新馬$|未勝利$|オープン$|G[123]$|障害$')

with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT horse_id, bamei, recent_races FROM horse_detail").fetchall()
    
    print(f"処理対象: {len(rows)}頭")
    fixed_total = 0
    
    for r in rows:
        rr = json.loads(r["recent_races"] or "[]")
        changed = False
        
        for race in rr:
            name = race.get("race_name", "")
            # 末尾のクラス名を除去: "ベストウィ2勝" → "ベストウィ"
            clean = re.sub(r'\s*[0-9][勝障]\s*$|\s*新馬\s*$|\s*未勝利\s*$|\s*オープン\s*$|\s*G[123]\s*$', '', name).strip()
            if clean != name:
                race["race_name"] = clean
                changed = True
        
        if changed:
            conn.execute(
                "UPDATE horse_detail SET recent_races=? WHERE horse_id=?",
                (json.dumps(rr, ensure_ascii=False), r["horse_id"])
            )
            fixed_total += 1
            print(f"  修正: {r['bamei']}")
    
    print(f"\n修正完了: {fixed_total}頭")
    print("ブラウザをリロードしてください")
