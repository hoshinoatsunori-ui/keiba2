"""
migrate_detail.py - horse_detailの近走データを新フォーマットに変換
keiba.dbを保持したまま、古いフォーマット（dist_time_baba/detail）を
新フォーマット（distance/time/baba/num_horses/umaban/ninki/jockey/kinryo）に変換する

使い方: python migrate_detail.py
"""
import sqlite3, json, re
from pathlib import Path

DB_PATH = Path(__file__).parent / "keiba.db"

def parse_past(lines):
    """Past tdの行リストを新フォーマットのdictに変換"""
    if len(lines) < 2:
        return None

    dp = lines[0].split()
    race_date = dp[0] if dp else ""
    place     = dp[1] if len(dp) > 1 else ""
    chakun    = lines[1] if len(lines) > 1 else ""
    race_name = lines[2] if len(lines) > 2 else ""

    # クラス名が単独行に入る場合（"2勝","1勝"等）はスキップ
    dist_idx = 3
    if len(lines) > 3 and re.match(r"^[0-9][勝障]$|^新馬$|^未勝利$|^オープン$|^G[123]$", lines[3]):
        dist_idx = 4

    dtb    = lines[dist_idx]     if len(lines) > dist_idx     else ""
    detail = lines[dist_idx + 1] if len(lines) > dist_idx + 1 else ""
    ca     = lines[dist_idx + 2] if len(lines) > dist_idx + 2 else ""
    chakusa= lines[dist_idx + 3] if len(lines) > dist_idx + 3 else ""

    # 距離・タイム・馬場
    dm = re.match(r"([芝ダ障][^\s]*)\s+([0-9:.]+)\s*(.*)", dtb)
    if dm:
        distance = dm.group(1)
        time_val = dm.group(2)
        baba     = dm.group(3).strip()
    else:
        distance = dtb; time_val = ""; baba = ""

    # 頭数・馬番・人気・騎手・斤量
    nhm = re.search(r"(\d+)頭", detail)
    um  = re.search(r"(\d+)番", detail)
    nkm = re.search(r"(\d+)人", detail)
    km  = re.search(r"(\d+\.\d+)\s*$", detail)
    num_horses  = nhm.group(1) if nhm else ""
    past_umaban = um.group(1)  if um  else ""
    ninki       = nkm.group(1) if nkm else ""
    kinryo_v    = km.group(1)  if km  else ""
    jt = re.sub(r"\d+頭|\d+番|\d+人|\d+\.\d+", "", detail).strip()
    jockey_v = " ".join(jt.split())

    # 上がり
    am = re.search(r"\(([\d.]+)\)", ca)
    agari = am.group(1) if am else ""

    return {
        "date":       race_date,
        "place":      place,
        "chakun":     chakun,
        "race_name":  race_name,
        "num_horses": num_horses,
        "umaban":     past_umaban,
        "ninki":      ninki,
        "jockey":     jockey_v,
        "kinryo":     kinryo_v,
        "distance":   distance,
        "time":       time_val,
        "baba":       baba,
        "agari":      agari,
        "chakusa":    chakusa,
    }

with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT horse_id, recent_races FROM horse_detail").fetchall()
    print(f"変換対象: {len(rows)}件")
    
    converted = 0
    for r in rows:
        rr = json.loads(r["recent_races"] or "[]")
        if not rr:
            continue
        
        # 既に新フォーマットかチェック
        if "distance" in rr[0] and "num_horses" in rr[0]:
            # 新フォーマット済み（ただしnum_horsesが空の場合は再変換）
            if rr[0].get("num_horses") != "" or rr[0].get("distance") != "":
                print(f"  スキップ(新形式): {r['horse_id']}")
                continue
        
        # 古いフォーマット（dist_time_baba/detail）の場合は変換
        new_rr = []
        for race in rr:
            if "dist_time_baba" in race:
                # 古いフォーマット → 行に分解して再パース
                # dist_time_baba, detail から復元
                dtb    = race.get("dist_time_baba", "")
                detail = race.get("detail", "")
                ca_str = ""
                chakusa= race.get("chakusa", "")
                
                # 疑似的に行リストを作成
                lines = [
                    race.get("date","") + " " + race.get("place",""),
                    race.get("chakun",""),
                    race.get("race_name",""),
                    dtb,
                    detail,
                    ca_str,
                    chakusa,
                ]
                parsed = parse_past(lines)
                if parsed:
                    new_rr.append(parsed)
            elif "distance" in race:
                # 新フォーマットだがnum_horsesが取れていない → 再パース不可、そのまま保持
                new_rr.append(race)
            else:
                new_rr.append(race)
        
        conn.execute(
            "UPDATE horse_detail SET recent_races=? WHERE horse_id=?",
            (json.dumps(new_rr, ensure_ascii=False), r["horse_id"])
        )
        converted += 1
        print(f"  変換: {r['horse_id']}")
    
    print(f"\n変換完了: {converted}件")
    print("アプリを再起動して確認してください")
