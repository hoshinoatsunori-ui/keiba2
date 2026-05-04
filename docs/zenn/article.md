---
title: "Pythonで作る競馬収支管理システム — Flask + SQLite + netkeibaスクレイピング"
emoji: "🏇"
type: "tech"
topics: ["python", "flask", "sqlite", "beautifulsoup", "scraping"]
published: false
---

## はじめに

競馬を楽しんでいると「どのレースにいくら賭けて、的中したのか？　年間の収支は？」を把握したくなります。Excel で管理していたものの、結果入力が面倒で断念……という経験から、**netkeibaの公開ページを自動取得して収支を一元管理する Web アプリ**を作りました。

この記事では設計の考え方と実装のポイントを紹介します。

## 作ったもの

![スクリーンショット](../../assets/screenshot.png)

- **出走表・レース結果を自動取得**（netkeiba.com のログイン不要ページ）
- **買い目を登録**して的中を自動判定
- **収支集計**（年別・回収率）
- SQLite で永続化、Flask で SPA 風の Web UI

リポジトリ: https://github.com/hoshinoatsunori-ui/keiba2

## 技術スタック

| 役割 | ライブラリ |
|------|-----------|
| Web フレームワーク | Flask |
| スクレイピング | requests + BeautifulSoup4 (lxml) |
| DB | SQLite（WAL モード） |
| フロントエンド | Vanilla JS（SPA 風） |

依存パッケージは `pip install flask requests beautifulsoup4 lxml` だけです。

## DB 設計

```sql
-- レース一覧
CREATE TABLE races (
    race_id     TEXT PRIMARY KEY,  -- 12桁: YYYY競馬場開催日レース番号
    kaisai_date TEXT,
    jo_name     TEXT,
    race_name   TEXT,
    race_data   TEXT,
    status      TEXT DEFAULT '未取得'
);

-- 出走馬
CREATE TABLE horses (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id  TEXT NOT NULL,
    umaban   INTEGER,
    bamei    TEXT,
    jockey   TEXT,
    odds     TEXT,
    horse_id TEXT DEFAULT ''
);

-- 買い目
CREATE TABLE bets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id     TEXT NOT NULL,
    ticket_type TEXT,   -- 単勝/馬連/三連複...
    combination TEXT,   -- 例: "3-7-12"
    purchase    INTEGER DEFAULT 100,
    result      TEXT DEFAULT '',  -- ◎ or ✗
    payout      INTEGER DEFAULT 0
);

-- 血統・近走
CREATE TABLE horse_detail (
    horse_id     TEXT PRIMARY KEY,
    father       TEXT,
    mother       TEXT,
    mother_father TEXT,
    recent_races TEXT   -- JSON
);
```

race_id は netkeiba の 12 桁コードをそのまま使います。`YYYY競馬場コード（2桁）開催回（2桁）日目（2桁）レース番号（2桁）` という構造で、コードからメタ情報を復元できます。

```python
JO_CODE_MAP = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
    "05": "東京", "06": "中山", "07": "中京", "08": "京都",
    "09": "阪神", "10": "小倉",
}

def parse_race_id(race_id: str) -> dict:
    return {
        "year":       race_id[0:4],
        "jo_name":    JO_CODE_MAP.get(race_id[4:6], race_id[4:6]),
        "kaisai_kai": int(race_id[6:8]),
        "day_no":     int(race_id[8:10]),
        "race_no":    int(race_id[10:12]),
    }
```

## スクレイピングの実装ポイント

### 文字コードの罠

netkeiba は EUC-JP エンコードです。requests の自動検出が `ascii` や `iso-8859-1` と誤判定することがあるため、強制的に EUC-JP に固定しています。

```python
def _fetch(url: str) -> BeautifulSoup:
    resp = SESSION.get(url, timeout=20)
    resp.raise_for_status()
    detected = (resp.apparent_encoding or "").lower()
    resp.encoding = "EUC-JP" if detected in ("ascii", "iso-8859-1", "") else detected
    return BeautifulSoup(resp.text, "lxml")
```

### 払戻テーブルのパース

払戻データは「組み合わせ」と「金額」が別 td に入っており、しかもワイドなど複数組み合わせがある券種は `<ul>` が複数あります。

```python
combs = []
uls = result_td.find_all("ul")
if uls:
    # 馬連・ワイド・三連複etc: 1ul = 1組み合わせ
    for ul in uls:
        nums = [sp.get_text(strip=True) for sp in ul.select("li span") if sp.get_text(strip=True)]
        if nums:
            combs.append("-".join(nums))
else:
    # 単勝・複勝: div>span
    for div in result_td.find_all("div"):
        sp = div.find("span")
        if sp and sp.get_text(strip=True):
            combs.append(sp.get_text(strip=True))
```

### 的中判定

組み合わせ文字列を正規化して比較します。馬連は順不同なのでソートしてから一致確認します。

```python
def _match_combination(harai_comb: str, kaime_comb: str) -> bool:
    def normalize(s):
        nums = re.split(r"[-→\s]+", str(s).strip())
        try:
            return sorted(int(n) for n in nums if n.isdigit())
        except ValueError:
            return []
    return normalize(harai_comb) == normalize(kaime_comb)
```

## Flask API 設計

REST ライクなエンドポイントに整理し、フロントエンドは fetch API で呼び出すだけにしました。

```
GET  /api/weekend_dates              今週末の日付
POST /api/fetch_race_ids             指定日の race_id 一覧取得
GET  /api/races                      登録済みレース一覧
POST /api/shutuba/<race_id>/fetch    出走表取得
POST /api/shutuba/<race_id>/fetch_details  血統・近走取得
POST /api/bets                       買い目登録
POST /api/results/fetch_pending      未処理の結果を一括取得
GET  /api/summary                    収支集計
```

## 使い方

```bash
pip install flask requests beautifulsoup4 lxml
python keiba.py
# → ブラウザが自動で開く (http://localhost:5000)
```

1. サイドバーの「レース取得」で開催日（YYYYMMDD）を入力 → レース一覧が DB に登録される
2. レースを選んで「出走表取得」→「血統・近走を取得」
3. 馬券を決めたら買い目を登録
4. レース後「結果取得」で的中判定＆収支が更新される

## おわりに

個人的な収支管理ツールとして作りましたが、出走表や血統データを手軽に取得できる基盤ができたので、機械学習での予測モデルに拡張するのも面白そうです。

**注意**: スクレイピングはサーバーに負荷をかけます。リクエスト間隔を適切に設けた上で、個人利用の範囲でご利用ください。

---

ソースコード: https://github.com/hoshinoatsunori-ui/keiba2
