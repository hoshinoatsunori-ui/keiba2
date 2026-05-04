# 競馬収支管理システム

netkeiba.com の公開ページをスクレイピングして、馬券の買い目・的中・収支を一元管理する Flask 製 Web アプリです。

## 機能

| 機能 | 概要 |
|------|------|
| レース取得 | 指定日の開催一覧・race_id を取得して DB に登録 |
| 出走表取得 | 馬番・馬名・騎手・斤量・オッズを取得 |
| 血統・近走取得 | 父・母・母父・近5走成績を一括取得 |
| 買い目登録 | 券種・組み合わせ・購入金額を記録 |
| 結果取得 | 着順・払戻を取得し買い目の的中を自動判定 |
| 収支集計 | 年別・レース別の投資額・回収額・回収率を表示 |

## 技術スタック

- **バックエンド**: Python 3.11+ / Flask
- **スクレイピング**: requests / BeautifulSoup4 (lxml)
- **DB**: SQLite（WAL モード）
- **フロントエンド**: Vanilla JS + HTML/CSS（SPA 風）

## セットアップ

```bash
# 依存パッケージのインストール
pip install flask requests beautifulsoup4 lxml

# 起動（ブラウザが自動で開きます）
python keiba.py
```

アクセス先: http://localhost:5000

## ファイル構成

```
keiba2/
├── keiba.py          # Flask アプリ本体・API ルート
├── scraper.py        # netkeiba スクレイパー
├── db.py             # SQLite 操作
├── templates/
│   └── index.html    # SPA フロントエンド
└── docs/
    ├── zenn/         # Zenn 投稿原稿
    └── qiita/        # Qiita 投稿原稿
```

## スクレイピングについて

- 対象: netkeiba.com の**ログイン不要**な公開ページのみ
- リクエスト間隔: 0.5 秒のスリープを挟んでいます
- robots.txt および利用規約の範囲内での個人利用を前提としています

## ライセンス

MIT
