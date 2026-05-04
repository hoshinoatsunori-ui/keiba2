"""
db.py - SQLiteデータベース操作
テーブル:
  races     - レース一覧（race_id, 開催情報, ステータス）
  horses    - 出走表（race_id別の出走馬）
  bets      - 買い目（購入馬券）
  results   - レース結果・払戻
"""

import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "keiba.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS races (
            race_id     TEXT PRIMARY KEY,
            kaisai_date TEXT,
            jo_name     TEXT,
            kaisai_kai  INTEGER,
            day_no      INTEGER,
            race_no     INTEGER,
            race_name   TEXT,
            race_data   TEXT,
            status      TEXT DEFAULT '未取得',
            scraped_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS horses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id     TEXT NOT NULL,
            wakuban     INTEGER,
            umaban      INTEGER,
            bamei       TEXT,
            barei       TEXT,
            jockey      TEXT,
            kinryo      TEXT,
            trainer     TEXT,
            odds        TEXT,
            horse_id    TEXT DEFAULT '',
            FOREIGN KEY (race_id) REFERENCES races(race_id)
        );

        CREATE TABLE IF NOT EXISTS bets (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id      TEXT NOT NULL,
            ticket_type  TEXT,
            combination  TEXT,
            purchase     INTEGER DEFAULT 100,
            result       TEXT DEFAULT '',
            payout       INTEGER DEFAULT 0,
            created_at   TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (race_id) REFERENCES races(race_id)
        );

        CREATE TABLE IF NOT EXISTS horse_detail (
            horse_id      TEXT PRIMARY KEY,
            bamei         TEXT,
            father        TEXT,
            father_father TEXT,
            father_mother TEXT,
            mother        TEXT,
            mother_father TEXT,
            mother_mother TEXT,
            recent_races  TEXT,  -- JSON文字列
            updated_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS results (
            race_id           TEXT PRIMARY KEY,
            rank1             TEXT,
            rank2             TEXT,
            rank3             TEXT,
            haraimodoshi      TEXT,
            haraimodoshi_json TEXT DEFAULT '[]',
            updated_at        TEXT,
            FOREIGN KEY (race_id) REFERENCES races(race_id)
        );
        """)


# ── races ──────────────────────────────────────────────────────────────────

def upsert_race(race_id: str, kaisai_date: str, jo_name: str,
                kaisai_kai: int, day_no: int, race_no: int,
                race_name: str = "", race_data: str = "",
                status: str = "未取得") -> bool:
    """レースを登録（既存なら更新）。True=新規追加, False=既存"""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT race_id FROM races WHERE race_id=?", (race_id,)
        ).fetchone()
        if existing:
            if race_name:
                conn.execute(
                    """UPDATE races SET race_name=?, race_data=?, status=?,
                       scraped_at=? WHERE race_id=?""",
                    (race_name, race_data, status,
                     datetime.now().strftime("%Y/%m/%d %H:%M"), race_id)
                )
            return False
        conn.execute(
            """INSERT INTO races
               (race_id, kaisai_date, jo_name, kaisai_kai, day_no, race_no,
                race_name, race_data, status)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (race_id, kaisai_date, jo_name, kaisai_kai, day_no, race_no,
             race_name, race_data, status)
        )
        return True


def get_races(year: int = None) -> list[dict]:
    with get_conn() as conn:
        if year:
            rows = conn.execute(
                "SELECT * FROM races WHERE race_id LIKE ? ORDER BY race_id",
                (f"{year}%",)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM races ORDER BY race_id"
            ).fetchall()
        return [dict(r) for r in rows]


def get_race(race_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM races WHERE race_id=?", (race_id,)
        ).fetchone()
        return dict(row) if row else None


# ── horses ─────────────────────────────────────────────────────────────────

def save_horses(race_id: str, horses: list[dict]):
    with get_conn() as conn:
        conn.execute("DELETE FROM horses WHERE race_id=?", (race_id,))
        conn.executemany(
            """INSERT INTO horses
               (race_id, wakuban, umaban, bamei, barei, jockey, kinryo, trainer, odds, horse_id)
               VALUES (:race_id,:wakuban,:umaban,:bamei,:barei,:jockey,:kinryo,:trainer,:odds,:horse_id)""",
            [{"race_id": race_id, "horse_id": h.get("horse_id",""), **{k:v for k,v in h.items() if k!="horse_id"}} for h in horses]
        )


def get_horses(race_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM horses WHERE race_id=? ORDER BY umaban",
            (race_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# ── bets ───────────────────────────────────────────────────────────────────

def save_bet(race_id: str, ticket_type: str, combination: str,
             purchase: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO bets (race_id, ticket_type, combination, purchase)
               VALUES (?,?,?,?)""",
            (race_id, ticket_type, combination, purchase)
        )
        return cur.lastrowid


def delete_bet(bet_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM bets WHERE id=?", (bet_id,))


def get_bets(race_id: str = None) -> list[dict]:
    with get_conn() as conn:
        if race_id:
            rows = conn.execute(
                "SELECT * FROM bets WHERE race_id=? ORDER BY id",
                (race_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT b.*, r.race_name, r.kaisai_date
                   FROM bets b LEFT JOIN races r ON b.race_id=r.race_id
                   ORDER BY b.race_id, b.id"""
            ).fetchall()
        return [dict(r) for r in rows]


def update_bet_result(bet_id: int, result: str, payout: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE bets SET result=?, payout=? WHERE id=?",
            (result, payout, bet_id)
        )


# ── results ────────────────────────────────────────────────────────────────

def save_result(race_id: str, rank1: str, rank2: str, rank3: str,
                haraimodoshi: str, harai_list: list = None):
    import json as _json
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO results
               (race_id, rank1, rank2, rank3, haraimodoshi, haraimodoshi_json, updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (race_id, rank1, rank2, rank3, haraimodoshi,
             _json.dumps(harai_list or [], ensure_ascii=False),
             datetime.now().strftime("%Y/%m/%d %H:%M"))
        )
        conn.execute(
            "UPDATE races SET status='結果取得済' WHERE race_id=?",
            (race_id,)
        )


def get_result(race_id: str) -> dict | None:
    import json as _json
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM results WHERE race_id=?", (race_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["harai_list"] = _json.loads(d.get("haraimodoshi_json") or "[]")
        except Exception:
            d["harai_list"] = []
        return d


# ── 収支集計 ────────────────────────────────────────────────────────────────

def get_summary(year: int = None) -> dict:
    with get_conn() as conn:
        base = "FROM bets b LEFT JOIN races r ON b.race_id=r.race_id"
        where = f"WHERE b.race_id LIKE '{year}%'" if year else ""

        row = conn.execute(
            f"SELECT SUM(purchase) total_bet, SUM(payout) total_payout, "
            f"COUNT(*) total_count, SUM(CASE WHEN result='◎' THEN 1 ELSE 0 END) hit_count "
            f"{base} {where}"
        ).fetchone()

        monthly = conn.execute(
            f"SELECT substr(r.kaisai_date,1,7) month, "
            f"SUM(b.purchase) bet, SUM(b.payout) payout "
            f"{base} {where} GROUP BY substr(r.kaisai_date,1,7) ORDER BY 1"
        ).fetchall()

        by_ticket = conn.execute(
            f"SELECT b.ticket_type, SUM(b.purchase) bet, SUM(b.payout) payout, "
            f"COUNT(*) total, SUM(CASE WHEN b.result='◎' THEN 1 ELSE 0 END) hit "
            f"{base} {where} GROUP BY b.ticket_type ORDER BY bet DESC"
        ).fetchall()

        total_bet    = row["total_bet"]    or 0
        total_payout = row["total_payout"] or 0
        total_count  = row["total_count"]  or 0
        hit_count    = row["hit_count"]    or 0

        return {
            "total_bet":     total_bet,
            "total_payout":  total_payout,
            "balance":       total_payout - total_bet,
            "recovery_rate": round(total_payout / total_bet * 100, 1) if total_bet else 0,
            "total_count":   total_count,
            "hit_count":     hit_count,
            "hit_rate":      round(hit_count / total_count * 100, 1) if total_count else 0,
            "monthly":       [dict(r) for r in monthly],
            "by_ticket":     [dict(r) for r in by_ticket],
        }


# ── horse_detail ────────────────────────────────────────────────────────────

import json as _json


def save_horse_detail(horse_id: str, bamei: str, blood: dict, recent_races: list):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO horse_detail
               (horse_id, bamei, father, father_father, father_mother,
                mother, mother_father, mother_mother, recent_races, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                horse_id, bamei,
                blood.get("father",""), blood.get("father_father",""), blood.get("father_mother",""),
                blood.get("mother",""), blood.get("mother_father",""), blood.get("mother_mother",""),
                _json.dumps(recent_races, ensure_ascii=False),
                datetime.now().strftime("%Y/%m/%d %H:%M"),
            )
        )


def get_horse_detail(horse_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM horse_detail WHERE horse_id=?", (horse_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["recent_races"] = _json.loads(d.get("recent_races") or "[]")
        except Exception:
            d["recent_races"] = []
        return d


def get_horses_with_detail(race_id: str) -> list[dict]:
    """出走馬一覧＋血統情報を結合して返す"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT h.*, hd.father, hd.father_father, hd.father_mother,
                      hd.mother, hd.mother_father, hd.mother_mother,
                      hd.recent_races, hd.updated_at as detail_updated
               FROM horses h
               LEFT JOIN horse_detail hd ON h.horse_id = hd.horse_id
               WHERE h.race_id=?
               ORDER BY h.umaban""",
            (race_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["recent_races"] = _json.loads(d.get("recent_races") or "[]")
            except Exception:
                d["recent_races"] = []
            result.append(d)
        return result
