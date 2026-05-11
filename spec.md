# 競馬収支管理システム — 仕様書

## 概要

netkeiba.com の公開ページをスクレイピングして、複数の予想グループ（AI・自分）ごとに馬券の買い目・的中・収支を管理・比較する Flask 製 Web アプリ。

---

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| Web フレームワーク | Python 3.11+ / Flask |
| スクレイピング | requests + BeautifulSoup4 (lxml) |
| DB | SQLite 3（WAL モード） |
| フロントエンド | Vanilla JS（SPA 風）/ HTML / CSS |

依存パッケージ: `flask requests beautifulsoup4 lxml`

---

## 起動

```bash
python keiba.py
# http://localhost:5000 が自動で開く
```

---

## ファイル構成

```
keiba2/
├── keiba.py          # Flask アプリ本体・全 API ルート
├── scraper.py        # netkeiba スクレイパー
├── db.py             # SQLite CRUD 関数
├── templates/
│   └── index.html    # SPA フロントエンド（HTML + CSS + JS）
├── keiba.db          # SQLite DB（.gitignore 対象）
└── docs/
    ├── zenn/article.md
    └── qiita/article.md
```

---

## DB スキーマ

### races — レース一覧

| カラム | 型 | 説明 |
|-------|----|------|
| race_id | TEXT PK | netkeiba の 12 桁コード（YYYY競馬場開催回日レースNo） |
| kaisai_date | TEXT | 開催日（YYYY/MM/DD） |
| jo_name | TEXT | 競馬場名 |
| kaisai_kai | INTEGER | 開催回 |
| day_no | INTEGER | 開催日目 |
| race_no | INTEGER | レース番号 |
| race_name | TEXT | レース名 |
| race_data | TEXT | 距離・馬場等の文字列 |
| status | TEXT | 未取得 / 出走表取得済 / 結果取得済 |
| scraped_at | TEXT | 取得日時 |

### horses — 出走馬

| カラム | 型 | 説明 |
|-------|----|------|
| id | INTEGER PK | |
| race_id | TEXT FK | |
| wakuban | INTEGER | 枠番 |
| umaban | INTEGER | 馬番 |
| bamei | TEXT | 馬名 |
| barei | TEXT | 性齢（牡3等） |
| jockey | TEXT | 騎手 |
| kinryo | TEXT | 斤量 |
| trainer | TEXT | 調教師 |
| odds | TEXT | 単勝オッズ |
| horse_id | TEXT | netkeiba の馬 ID |

### horse_detail — 血統・近走

| カラム | 型 | 説明 |
|-------|----|------|
| horse_id | TEXT PK | |
| bamei | TEXT | |
| father / father_father / father_mother | TEXT | 父系統 |
| mother / mother_father / mother_mother | TEXT | 母系統 |
| recent_races | TEXT | 直近10走（JSON配列） |
| updated_at | TEXT | |

### forecast_groups — 予想グループ

| カラム | 型 | 説明 |
|-------|----|------|
| id | INTEGER PK | |
| name | TEXT | グループ名 |
| color | TEXT | 表示カラー（#rrggbb） |
| type | TEXT | `ai`（AI予想）/ `self`（自分の予想） |
| ai_model | TEXT | AIモデル名（例: claude-3-5-sonnet） |
| created_at | TEXT | |

### prediction_records — 予想記録

race_id × forecast_group_id の組み合わせで UNIQUE。

| カラム | 型 | 説明 |
|-------|----|------|
| id | INTEGER PK | |
| race_id | TEXT FK | |
| forecast_group_id | INTEGER FK | |
| prompt | TEXT | AI へのプロンプト（AI型） |
| ai_output | TEXT | AI の回答（AI型） |
| memo | TEXT | メモ（自分型） |
| created_at / updated_at | TEXT | |

### bets — 買い目

| カラム | 型 | 説明 |
|-------|----|------|
| id | INTEGER PK | |
| race_id | TEXT FK | |
| forecast_id | INTEGER FK | forecast_groups.id（NULL=グループなし） |
| ticket_type | TEXT | 単勝/複勝/枠連/馬連/ワイド/馬単/三連複/三連単 |
| combination | TEXT | 馬番の組み合わせ（例: `3-7-12`） |
| purchase | INTEGER | 購入金額（円） |
| result | TEXT | `◎`（的中）/ `✗`（外れ）/ 空文字（未判定） |
| payout | INTEGER | 払戻金額（円） |
| created_at | TEXT | |

### results — レース結果

| カラム | 型 | 説明 |
|-------|----|------|
| race_id | TEXT PK | |
| rank1 / rank2 / rank3 | TEXT | 1〜3着（馬番 馬名） |
| haraimodoshi | TEXT | 払戻テキスト（サマリ） |
| haraimodoshi_json | TEXT | 払戻詳細 JSON 配列 |
| updated_at | TEXT | |

---

## API 一覧

### レース管理

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/weekend_dates` | 今週末（土日）の日付を返す |
| POST | `/api/fetch_race_ids` | 指定日の race_id を取得して DB 登録 |
| GET | `/api/races` | 登録済みレース一覧（`?year=YYYY` でフィルタ） |

### 出走表

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/shutuba/<race_id>` | DB 保存済みの出走表を返す |
| POST | `/api/shutuba/<race_id>/fetch` | netkeiba から出走表を取得・保存 |
| POST | `/api/shutuba/fetch_all` | 未取得レースの出走表を一括取得 |
| POST | `/api/shutuba/<race_id>/fetch_details` | 全出走馬の血統・近走を一括取得 |
| GET | `/api/shutuba/<race_id>/horses_with_detail` | 出走馬＋血統を結合して返す |

### 買い目

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/bets` | 買い目一覧（`?race_id=` でフィルタ） |
| POST | `/api/bets` | 買い目を登録 |
| DELETE | `/api/bets/<id>` | 買い目を削除 |

### 結果

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/api/results/fetch_pending` | 結果未取得レースを一括処理・的中判定 |
| POST | `/api/results/refetch` | 取得済み含めて強制再取得 |
| GET | `/api/results/<race_id>` | 結果・払戻テーブルを返す |

### 収支集計

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/summary` | 収支集計（`?year=` `?forecast_id=` でフィルタ） |
| GET | `/api/summary/compare` | グループ別収支比較（`?year=` でフィルタ） |

### 予想グループ

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/forecast_groups` | グループ一覧 |
| POST | `/api/forecast_groups` | グループ作成 |
| DELETE | `/api/forecast_groups/<id>` | グループ削除（買い目の forecast_id は NULL に） |

### 予想記録

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/predictions` | 予想記録（`?race_id=` `?forecast_group_id=` でフィルタ） |
| POST | `/api/predictions` | 予想記録を upsert（race_id × group で一意） |
| DELETE | `/api/predictions/<id>` | 予想記録を削除 |

---

## フロントエンド ページ構成

### 📅 日程・race_id 取得
- 今週末の race_id を一括取得
- 任意日付（YYYYMMDD）を指定して取得
- 登録済みレース一覧（出走表・買い目ページへのショートカット付き）

### 📋 出走表
- race_id を入力して出走表を取得・表示
- 未取得の出走表を一括取得
- タブ切り替えで血統・近走を表示

### 🎫 買い目入力
1. レース選択
2. 予想グループ選択（グループなし可）
3. **予想を記録** カード（グループ選択時のみ表示）
   - AI型: プロンプト入力欄 ＋ AI回答入力欄
   - 自分型: メモ入力欄
4. 買い目（券種・馬番・購入金額）を追加
5. 購入リスト表示・削除

### 🏆 結果取得
- 買い目がある未処理レースを一括取得・的中判定
- 買い目一覧（グループ・的中・払戻・収支）

### 📊 収支集計
- 年・グループでフィルタ
- サマリカード（購入・払戻・収支・回収率・的中率）
- 月別推移テーブル
- 券種別内訳テーブル

### 🔀 予想比較
1. **グループ管理**: タイプ（AI/自分）・モデル名・カラーを設定して作成・削除
2. **収支比較テーブル**: グループを列として横並び比較、回収率で自動順位付け（🥇🥈🥉）・1位との差分行表示
3. **予想内容ビューア**: レースを選択して各グループのプロンプト・AI回答・メモを表示

---

## スクレイピング対象

| URL パターン | 用途 |
|------------|------|
| `race.netkeiba.com/top/race_list_sub.html?kaisai_date=` | race_id 一覧 |
| `race.netkeiba.com/race/shutuba.html?race_id=` | 出走表（基本情報） |
| `race.netkeiba.com/race/shutuba_past.html?race_id=` | 出走表＋血統・近走 |
| `race.netkeiba.com/race/result.html?race_id=` | レース結果・払戻 |

- 文字コード: EUC-JP（`apparent_encoding` が不正確なため強制設定）
- リクエスト間隔: 0.5秒スリープ
- ログイン不要の公開ページのみ対象

---

## race_id の構造

```
202605030812
↑↑↑↑ ↑↑ ↑↑ ↑↑ ↑↑
年    競馬場 開催回 日目  レースNo

競馬場コード: 01=札幌 02=函館 03=福島 04=新潟 05=東京
             06=中山 07=中京 08=京都 09=阪神 10=小倉
```

---

## 的中判定ロジック

組み合わせ文字列を正規化（数字のリストにソート）して比較。馬連・三連複など順不同の券種に対応。

```python
def _match_combination(harai_comb: str, kaime_comb: str) -> bool:
    def normalize(s):
        nums = re.split(r"[-→\s]+", str(s).strip())
        return sorted(int(n) for n in nums if n.isdigit())
    return normalize(harai_comb) == normalize(kaime_comb)
```

払戻金額 = `harai_payout × (purchase / 100)`

---

## DB マイグレーション方針

`init_db()` 実行時に `PRAGMA table_info` でカラム存在を確認し、不足分を `ALTER TABLE ADD COLUMN` で追加する。既存データへの影響なし。

```python
cols = [r[1] for r in conn.execute("PRAGMA table_info(bets)").fetchall()]
if "forecast_id" not in cols:
    conn.execute("ALTER TABLE bets ADD COLUMN forecast_id INTEGER DEFAULT NULL")
```
