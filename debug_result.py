"""
debug_result.py - 結果取得のデバッグと手動的中判定（DBカラム問題対応版）
使い方: python debug_result.py
"""
import sys, json, re, sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import importlib
import scraper
importlib.reload(scraper)
import db

RACE_ID = "202604010101"

print("=== 1. scraper.pyバージョン確認 ===")
import inspect
src = inspect.getsource(scraper.fetch_result)
print("Payout_Detail_Table:", src.count("Payout_Detail_Table"), "箇所")
print("select:", "soup.select" in src)

print("\n=== 2. 結果を取得 ===")
try:
    data = scraper.fetch_result(RACE_ID)
    result = data["result"]
    harai  = data["haraimodoshi"]
    print(f"着順: {len(result)}頭")
    for r in result[:5]:
        print(f"  {r['chakun']}着 {r['umaban']}番 {r['bamei']}")
    print(f"\n払戻: {len(harai)}件")
    for h in harai:
        print(f"  {h['ticket_type']} {h['combination']} ¥{h['payout']:,}")
except Exception as e:
    import traceback
    print(f"エラー: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n=== 3. 買い目との照合 ===")
bets = db.get_bets(RACE_ID)
print(f"買い目: {len(bets)}件")
for bet in bets:
    print(f"  {bet['ticket_type']} {bet['combination']} ¥{bet['purchase']}")
    for h in harai:
        if h["ticket_type"] != bet["ticket_type"]:
            continue
        def norm(s):
            nums = re.split(r"[-→\s]+", str(s).strip())
            return sorted(int(n) for n in nums if n.isdigit())
        if norm(h["combination"]) == norm(bet["combination"]):
            payout = int(h["payout"] * bet["purchase"] / 100)
            print(f"    → ◎ 的中！払戻 ¥{payout:,}")

print("\n=== 4. DBに保存（直接SQL） ===")
top3  = result[:3]
rank1 = f"{top3[0]['umaban']} {top3[0]['bamei']}" if len(top3)>0 else ""
rank2 = f"{top3[1]['umaban']} {top3[1]['bamei']}" if len(top3)>1 else ""
rank3 = f"{top3[2]['umaban']} {top3[2]['bamei']}" if len(top3)>2 else ""
harai_str = " / ".join(f"{h['ticket_type']} {h['combination']} ¥{h['payout']:,}" for h in harai)
harai_json = json.dumps(harai, ensure_ascii=False)
from datetime import datetime
now = datetime.now().strftime("%Y/%m/%d %H:%M")

with db.get_conn() as conn:
    # haraimodoshi_jsonカラムがなければ追加
    cols = [r[1] for r in conn.execute("PRAGMA table_info(results)").fetchall()]
    if "haraimodoshi_json" not in cols:
        conn.execute("ALTER TABLE results ADD COLUMN haraimodoshi_json TEXT DEFAULT '[]'")
        print("  haraimodoshi_jsonカラムを追加しました")

    conn.execute(
        """INSERT OR REPLACE INTO results
           (race_id, rank1, rank2, rank3, haraimodoshi, haraimodoshi_json, updated_at)
           VALUES (?,?,?,?,?,?,?)""",
        (RACE_ID, rank1, rank2, rank3, harai_str, harai_json, now)
    )
    conn.execute("UPDATE races SET status='結果取得済' WHERE race_id=?", (RACE_ID,))

for bet in bets:
    hit = False; payout = 0
    for h in harai:
        if h["ticket_type"] != bet["ticket_type"]: continue
        def norm(s):
            nums = re.split(r"[-→\s]+", str(s).strip())
            return sorted(int(n) for n in nums if n.isdigit())
        if norm(h["combination"]) == norm(bet["combination"]):
            hit = True
            payout = int(h["payout"] * bet["purchase"] / 100)
    db.update_bet_result(bet["id"], "◎" if hit else "✗", payout)
    print(f"  {bet['ticket_type']} {bet['combination']}: {'◎' if hit else '✗'} 払戻¥{payout:,}")

print("\n完了。ブラウザをリロードしてください。")