"""
debug_shutuba.py - 出走表のhorse_idリンク構造を確認するスクリプト
使い方: python debug_shutuba.py RACE_ID
例:     python debug_shutuba.py 202604010101
"""
import sys
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.9",
}

def debug(race_id):
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    print(f"\n[URL] {url}")

    resp = requests.get(url, headers=HEADERS, timeout=20)
    print(f"[STATUS] {resp.status_code}")

    detected = (resp.apparent_encoding or "").lower()
    resp.encoding = "EUC-JP" if detected in ("ascii", "iso-8859-1", "") else detected
    print(f"[ENCODING] {resp.encoding}")

    soup = BeautifulSoup(resp.text, "lxml")

    rows = soup.select("tr[id^='tr_']")
    print(f"\n[出走馬数] {len(rows)}頭")

    for tr in rows[:3]:  # 先頭3頭を確認
        umaban = tr["id"].replace("tr_", "")
        horse_td = tr.select_one("td.HorseInfo")
        if not horse_td:
            print(f"  馬番{umaban}: HorseInfo td が見つかりません")
            continue

        # 全リンクを表示
        all_links = [(a.get("href",""), a.get_text(strip=True)[:20]) for a in horse_td.find_all("a")]
        print(f"\n  馬番{umaban} の全リンク:")
        for href, text in all_links:
            print(f"    href='{href}'  text='{text}'")

        # horse_idをすべてのパターンで試す
        for href, _ in all_links:
            for pat in [r"horse[/=_]?(\d{6,12})", r"/horse/(\w+)", r"horse_id=(\w+)"]:
                m = re.search(pat, href)
                if m:
                    print(f"    → horse_id候補: '{m.group(1)}' (pattern: {pat})")

        # data属性も確認
        for el in horse_td.find_all(attrs=True):
            for attr, val in el.attrs.items():
                if "horse" in attr.lower() or "id" in attr.lower():
                    print(f"    data属性: {attr}='{val}'")

if __name__ == "__main__":
    rid = sys.argv[1] if len(sys.argv) > 1 else "202604010101"
    debug(rid)