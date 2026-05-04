"""
patch_scraper.py - scraper.pyのData02処理を強制パッチするスクリプト
scraper.pyを直接書き換えます
使い方: python patch_scraper.py
"""
import re
from pathlib import Path

scraper_path = Path(__file__).parent / "scraper.py"

with open(scraper_path, "r", encoding="utf-8") as f:
    content = f.read()

# 現在のData02処理を確認
if 'from bs4 import NavigableString as _NS' in content:
    print("✅ scraper.pyは既に最新版です")
    print("   → __pycache__を削除してから再起動してください:")
    print("   rmdir /s /q __pycache__")
    print("   python reset_detail.py")
    print("   python keiba.py")
else:
    # 古いData02処理を新しいものに置換
    # 複数のパターンに対応
    patterns_to_replace = [
        # パターン1: get_text使用版
        (
            r'# Data02.*?race_name = "".*?if d02:.*?a_tag = d02\.find\("a"\).*?if a_tag:.*?race_name = a_tag\.get_text\(strip=True\).*?(?=# Data05)',
            None
        ),
    ]
    
    new_data02 = '''            # Data02: レース名
            # 構造: <div class="Data02"><a href="...">レース名<span class="Icon_GradeType">2勝</span></a></div>
            # <a>内の直接テキストノード（NavigableString）だけを取得してspanを除外する
            d02 = di.select_one(".Data02")
            race_name = ""
            if d02:
                from bs4 import NavigableString as _NS
                a_tag = d02.find("a")
                src = a_tag if a_tag else d02
                for node in src.children:
                    if isinstance(node, _NS):
                        t = str(node).strip()
                        if t:
                            race_name = t
                            break

            '''
    
    # 正規表現でData02ブロックを検出して置換
    pattern = re.compile(
        r'# Data02[^\n]*\n.*?race_name = ""\n.*?if d02:.*?(?=# Data05)',
        re.DOTALL
    )
    
    new_content, n = pattern.subn(new_data02, content)
    if n > 0:
        with open(scraper_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"✅ scraper.pyを修正しました ({n}箇所)")
    else:
        print("⚠️ パターンが見つかりません。手動で確認してください")
        # Data02周辺を表示
        idx = content.find("Data02")
        if idx > 0:
            print("\n現在のData02処理:")
            print(content[idx-20:idx+400])

print("\n次のコマンドを実行してください:")
print("  rmdir /s /q __pycache__")
print("  python reset_detail.py")
print("  python keiba.py")
