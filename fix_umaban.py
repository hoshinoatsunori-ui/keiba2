"""
fix_umaban.py - horsesテーブルのumabanとwakubanを正しい値に修正する

問題: tr_N のNを馬番として使っていたため、実際の馬番と異なる値が入っている
解決: netkeibaから再取得して正しい馬番・枠番・斤量・オッズで上書きする

使い方: python fix_umaban.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import db
import scraper
import time

with db.get_conn() as conn:
    races = conn.execute(
        "SELECT DISTINCT race_id FROM horses ORDER BY race_id"
    ).fetchall()

print(f"修正対象: {len(races)}レース")
print("netkeibaから再取得します...\n")

for row in races:
    race_id = row[0]
    try:
        data = scraper.fetch_shutuba(race_id)
        horses = data["horses"]
        db.save_horses(race_id, horses)

        # レース名も更新
        ri = data["race_info"]
        if ri["race_name"]:
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE races SET race_name=?, race_data=?, status='出走表取得済' WHERE race_id=?",
                    (ri["race_name"], ri["race_data"], race_id)
                )

        # 結果確認
        sample = horses[:2]
        print(f"  {race_id} {ri['race_name']}: {len(horses)}頭")
        for h in sample:
            print(f"    {h['wakuban']}枠 {h['umaban']}番 {h['bamei']} 斤量={h['kinryo']} オッズ={h['odds']}")

        time.sleep(0.5)
    except Exception as e:
        print(f"  {race_id}: エラー - {e}")

print("\n修正完了。アプリをリロードしてください。")
