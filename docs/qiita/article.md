# Pythonで競馬収支管理システムを作った — Flask + SQLite + netkeibaスクレイピング

## 概要

netkeiba.com の公開ページをスクレイピングして、馬券の買い目・的中・収支を管理する Flask 製 Web アプリです。

**できること:**
- 指定日のレース一覧・出走表を自動取得
- 血統（父・母・母父）と近5走成績を一括取得
- 買い目（券種・組み合わせ・購入金額）の登録
- レース結果の自動取得と的中判定
- 年別・レース別の収支集計

リポジトリ: https://github.com/hoshinoatsunori-ui/keiba2

## 動機

Excel で馬券の記録をつけていたものの、結果の手入力が面倒で続かなかった。「netkeiba のデータを自動取得して収支管理できるツールがあれば……」という動機で作成。

## 技術構成

| 役割 | 技術 |
|------|------|
| Web フレームワーク | Flask |
| スクレイピング | requests + BeautifulSoup4 (lxml) |
| DB | SQLite（WAL モード） |
| フロントエンド | Vanilla JS（SPA 風、外部依存なし） |

```bash
pip install flask requests beautifulsoup4 lxml
python keiba.py
# http://localhost:5000 が自動で開く
```

## DB スキーマ

```sql
-- レース（race_id は netkeiba の 12 桁コードをそのまま利用）
CREATE TABLE races (
    race_id     TEXT PRIMARY KEY,
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
    ticket_type TEXT,
    combination TEXT,
    purchase    INTEGER DEFAULT 100,
    result      TEXT DEFAULT '',
    payout      INTEGER DEFAULT 0
);

-- 血統・近走
CREATE TABLE horse_detail (
    horse_id      TEXT PRIMARY KEY,
    father        TEXT,
    mother        TEXT,
    mother_father TEXT,
    recent_races  TEXT  -- JSON
);
```

race_id の構造は `YYYY競馬場コード（2桁）開催回（2桁）日目（2桁）レース番号（2桁）` で、コードから競馬場名なども復元できます。

```python
JO_CODE_MAP = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
    "05": "東京", "06": "中山", "07": "中京", "08": "京都",
    "09": "阪神", "10": "小倉",
}
```

## スクレイピングの実装

### EUC-JP の文字コード問題

netkeiba は EUC-JP エンコードですが、requests の `apparent_encoding` が `ascii` や `iso-8859-1` と誤判定することがあります。検出結果が信頼できない場合は EUC-JP を強制します。

```python
def _fetch(url: str) -> BeautifulSoup:
    resp = SESSION.get(url, timeout=20)
    resp.raise_for_status()
    detected = (resp.apparent_encoding or "").lower()
    resp.encoding = "EUC-JP" if detected in ("ascii", "iso-8859-1", "") else detected
    return BeautifulSoup(resp.text, "lxml")
```

### 払戻テーブルのパース

券種ごとに `<tr>` のクラス名が異なり、ワイドなど複数組み合わせは `<ul>` が複数並ぶ構造です。

```python
TICKET_CLASS_MAP = {
    "Tansho": "単勝", "Fukusho": "複勝", "Wakuren": "枠連",
    "Umaren": "馬連", "Wide": "ワイド", "Umatan": "馬単",
    "Fuku3":  "三連複", "Tan3": "三連単",
}

combs = []
uls = result_td.find_all("ul")
if uls:
    # 馬連・ワイド・三連複etc: 1ul = 1組み合わせ
    for ul in uls:
        nums = [sp.get_text(strip=True)
                for sp in ul.select("li span") if sp.get_text(strip=True)]
        if nums:
            combs.append("-".join(nums))
else:
    # 単勝・複勝: div>span 構造
    for div in result_td.find_all("div"):
        sp = div.find("span")
        if sp and (t := sp.get_text(strip=True)):
            combs.append(t)
```

### 的中判定ロジック

馬連・三連複などは順不同なので、数字をソートしてから比較します。

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

### 血統・近走の取得（shutuba_past.html）

`shutuba_past.html` には出走表と血統・近走が同時に含まれています。1リクエストで全馬分を取得できます。

```python
def fetch_race_horse_details(race_id: str) -> list[dict]:
    url = f"https://race.netkeiba.com/race/shutuba_past.html?race_id={race_id}"
    soup = _fetch(url)

    results = []
    for tr in soup.select("tr.HorseList"):
        hi_td = tr.select_one("td.Horse_Info")
        father = hi_td.select_one(".Horse01").get_text(strip=True)
        bamei  = hi_td.select_one(".Horse02").get_text(strip=True)
        mother = hi_td.select_one(".Horse03").get_text(strip=True)
        # ...近走は td.Past > div.Data_Item から取得
```

## Flask API

```
GET  /api/weekend_dates               今週末の日付
POST /api/fetch_race_ids              指定日の race_id 一覧取得・DB登録
GET  /api/races                       登録済みレース一覧
POST /api/shutuba/<race_id>/fetch     出走表取得
POST /api/shutuba/<race_id>/fetch_details  血統・近走取得
POST /api/bets                        買い目登録
DELETE /api/bets/<id>                 買い目削除
POST /api/results/fetch_pending       未処理の結果を一括取得
GET  /api/summary                     収支集計
```

フロントエンドは Vanilla JS の `fetch()` で API を叩く SPA 構成です。外部 JS ライブラリは一切使っていないのでシンプルです。

## 使い方

1. 「レース取得」でレース日（YYYYMMDD 形式）を入力 → DB に登録
2. レース一覧からレースを選択 → 「出走表取得」「血統・近走を取得」
3. 馬券を決めたら券種・組み合わせ・購入金額を登録
4. レース後「結果取得」をクリック → 的中◎/✗が自動で付く
5. 「収支集計」ページで投資額・回収額・回収率を確認

## まとめ

スクレイピング（EUC-JP 対応・HTML 構造の丁寧な解析）+ Flask REST API + SQLite という構成で、依存ライブラリを最小限に抑えたシンプルな実装になりました。

今後の拡張候補としては機械学習モデルとの連携（取得した血統・近走データを特徴量に）を考えています。

**注意**: スクレイピングはサーバーへの負荷に配慮し、個人利用の範囲で使用してください。リクエスト間隔のスリープを必ず入れましょう。

---

ソースコード: https://github.com/hoshinoatsunori-ui/keiba2
