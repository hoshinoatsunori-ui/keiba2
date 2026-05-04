"""
debug_horse.py - 馬詳細ページの全テーブル構造をダンプするデバッグスクリプト
使い方: python debug_horse.py HORSE_ID
例:     python debug_horse.py 2022101614
"""
import sys
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.9",
    "Referer": "https://race.netkeiba.com/",
}

def debug(horse_id):
    url = f"https://db.netkeiba.com/horse/{horse_id}"
    print(f"\n[URL] {url}")

    resp = requests.get(url, headers=HEADERS, timeout=20)
    print(f"[STATUS] {resp.status_code}")

    detected = (resp.apparent_encoding or "").lower()
    resp.encoding = "EUC-JP" if detected in ("ascii", "iso-8859-1", "") else detected
    print(f"[ENCODING] {resp.encoding}")

    soup = BeautifulSoup(resp.text, "lxml")

    # 馬名
    for sel in ["div.horse_title h1", "h1.horse_title", "h1", ".title_name"]:
        el = soup.select_one(sel)
        if el:
            print(f"[馬名] {el.get_text(strip=True)[:30]}  (selector: {sel})")
            break

    # ページ内の全テーブルをリスト
    print("\n=== ページ内の全テーブル ===")
    for i, tbl in enumerate(soup.find_all("table")):
        cls   = tbl.get("class", [])
        tid   = tbl.get("id", "")
        rows  = tbl.find_all("tr")
        cols  = len(rows[1].find_all("td")) if len(rows) > 1 else 0
        # 先頭行のテキストサンプル
        sample = ""
        if rows:
            sample = rows[0].get_text(" ", strip=True)[:50]
        print(f"  [{i}] class={cls}  id='{tid}'  rows={len(rows)}  cols={cols}")
        print(f"       先頭行: {sample}")

    # 全divのid/classを血統・近走に関係しそうなものだけ
    print("\n=== 血統・近走関連のdiv/section ===")
    keywords = ["blood", "pedigree", "race", "result", "history", "record", "recent", "Blood", "Race", "Result"]
    for el in soup.find_all(["div", "section", "article"]):
        cls = " ".join(el.get("class", []))
        eid = el.get("id", "")
        if any(k.lower() in cls.lower() or k.lower() in eid.lower() for k in keywords):
            print(f"  <{el.name}> id='{eid}'  class='{cls}'")

if __name__ == "__main__":
    hid = sys.argv[1] if len(sys.argv) > 1 else "2022101614"
    debug(hid)