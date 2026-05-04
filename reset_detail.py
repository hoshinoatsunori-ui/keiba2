"""
reset_detail.py - horse_detailテーブルのみリセットするスクリプト
races・horses・betsは保持したまま血統・近走だけ再取得できるようにする
使い方: python reset_detail.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "keiba.db"

with sqlite3.connect(DB_PATH) as conn:
    count = conn.execute("SELECT COUNT(*) FROM horse_detail").fetchone()[0]
    conn.execute("DELETE FROM horse_detail")
    print(f"horse_detailを{count}件削除しました")
    print("アプリを再起動して「🧬 血統・近走を取得」を再実行してください")
