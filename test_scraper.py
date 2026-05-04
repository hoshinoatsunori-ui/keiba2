"""
test_scraper.py - scraper.pyが正しいバージョンか確認するスクリプト
使い方: python test_scraper.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# __pycache__を使わず直接importするためreloadを使う
import importlib
import scraper
importlib.reload(scraper)

print("=== scraper.pyのバージョン確認 ===")

# 馬番取得が正しいか確認
src = open(Path(__file__).parent / "scraper.py", encoding="utf-8").read()
if "td[class*=Umaban]" in src:
    print("✅ 馬番取得: 正しい (td[class*=Umaban])")
else:
    print("❌ 馬番取得: 古いコードが残っています")
    print("   → rmdir /s /q __pycache__ を実行してください")

if 'all_tds[5].get_text' in src:
    print("✅ 斤量取得: 正しい (all_tds[5])")
else:
    print("❌ 斤量取得: 古いコードが残っています")

if 'all_tds[9].get_text' in src or "all_tds[9]" in src:
    print("✅ オッズ取得: 正しい (all_tds[9])")
else:
    print("❌ オッズ取得: 古いコードが残っています")

print("\n=== 実際の関数チェック ===")
import inspect
src_fn = inspect.getsource(scraper.fetch_shutuba)
print("fetch_shutuba内のumaban取得方法:")
for line in src_fn.split('\n'):
    if 'umaban' in line and ('tr[' in line or 'Umaban' in line or 'replace' in line):
        print(f"  {line.strip()}")