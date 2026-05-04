"""
keiba.py - 競馬収支管理システム（Flask）
起動: python keiba.py
URL:  http://localhost:5000
"""

import re
import time
import webbrowser
import threading
from datetime import datetime
from flask import Flask, jsonify, render_template, request

import db
import scraper

app = Flask(__name__)
db.init_db()


# ── ページ ───
@app.route("/favicon.ico")
def favicon():
    return "", 204  # No Content（ログに出さない）


@app.route("/")
def index():
    return render_template("index.html")


# ── API: レース日程 ───────────────────────────────────────────────────────────

@app.route("/api/weekend_dates")
def api_weekend_dates():
    """今週末の日付を返す"""
    return jsonify({"dates": scraper.get_this_weekend_dates()})


@app.route("/api/fetch_race_ids", methods=["POST"])
def api_fetch_race_ids():
    """指定日のrace_idを取得してDBに登録"""
    data = request.json or {}
    kaisai_date = data.get("kaisai_date", "")
    if not re.match(r"^\d{8}$", kaisai_date):
        return jsonify({"success": False, "message": "YYYYMMDD形式で入力してください"}), 400

    try:
        jo_list = scraper.fetch_race_ids_by_date(kaisai_date)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

    added = skipped = 0
    for jo in jo_list:
        for race_id in jo["ids"]:
            meta = scraper.parse_race_id(race_id)
            date_fmt = f"{meta['year']}/{kaisai_date[4:6]}/{kaisai_date[6:8]}"
            is_new = db.upsert_race(
                race_id=race_id,
                kaisai_date=date_fmt,
                jo_name=meta["jo_name"],
                kaisai_kai=meta["kaisai_kai"],
                day_no=meta["day_no"],
                race_no=meta["race_no"],
            )
            if is_new:
                added += 1
            else:
                skipped += 1

    return jsonify({
        "success": True,
        "added": added,
        "skipped": skipped,
        "jo_list": jo_list,
        "message": f"{kaisai_date[:4]}/{kaisai_date[4:6]}/{kaisai_date[6:]} の race_id を {added} 件登録（スキップ: {skipped} 件）",
    })


# ── API: レース一覧 ───────────────────────────────────────────────────────────

@app.route("/api/races")
def api_races():
    year = request.args.get("year")
    races = db.get_races(int(year) if year else None)
    return jsonify(races)


# ── API: 出走表 ───────────────────────────────────────────────────────────────

@app.route("/api/shutuba/<race_id>")
def api_get_shutuba(race_id: str):
    """DBに保存済みの出走表を返す"""
    race  = db.get_race(race_id)
    horses = db.get_horses(race_id)
    return jsonify({"race": race, "horses": horses})


@app.route("/api/shutuba/<race_id>/fetch", methods=["POST"])
def api_fetch_shutuba(race_id: str):
    """netkeibaから出走表を取得してDBに保存"""
    if not re.match(r"^\d{12}$", race_id):
        return jsonify({"success": False, "message": "race_idは12桁の数字です"}), 400

    try:
        data = scraper.fetch_shutuba(race_id)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

    ri = data["race_info"]
    meta = scraper.parse_race_id(race_id)

    db.upsert_race(
        race_id=race_id,
        kaisai_date="",
        jo_name=meta["jo_name"],
        kaisai_kai=meta["kaisai_kai"],
        day_no=meta["day_no"],
        race_no=meta["race_no"],
        race_name=ri["race_name"],
        race_data=ri["race_data"],
        status="出走表取得済",
    )
    db.save_horses(race_id, data["horses"])

    return jsonify({
        "success":    True,
        "race_info":  ri,
        "horses":     data["horses"],
        "message":    f"{ri['race_name']} の出走表を取得しました（{len(data['horses'])}頭）",
    })


@app.route("/api/shutuba/fetch_all", methods=["POST"])
def api_fetch_all_shutuba():
    """レース一覧の未取得race_idの出走表を一括取得"""
    races = [r for r in db.get_races() if r["status"] == "未取得"]
    created = errors = 0
    for race in races:
        try:
            data = scraper.fetch_shutuba(race["race_id"])
            ri   = data["race_info"]
            db.upsert_race(
                race_id=race["race_id"],
                kaisai_date=race["kaisai_date"],
                jo_name=race["jo_name"],
                kaisai_kai=race["kaisai_kai"],
                day_no=race["day_no"],
                race_no=race["race_no"],
                race_name=ri["race_name"],
                race_data=ri["race_data"],
                status="出走表取得済",
            )
            db.save_horses(race["race_id"], data["horses"])
            created += 1
            time.sleep(0.5)
        except Exception:
            errors += 1

    return jsonify({
        "success": True,
        "created": created,
        "errors":  errors,
        "message": f"{created}件の出走表を取得しました（エラー: {errors}件）",
    })


# ── API: 買い目 ───────────────────────────────────────────────────────────────

@app.route("/api/bets", methods=["GET"])
def api_get_bets():
    race_id = request.args.get("race_id")
    return jsonify(db.get_bets(race_id))


@app.route("/api/bets", methods=["POST"])
def api_save_bet():
    d = request.json or {}
    bet_id = db.save_bet(
        race_id     = d.get("race_id", ""),
        ticket_type = d.get("ticket_type", ""),
        combination = d.get("combination", ""),
        purchase    = int(d.get("purchase", 100)),
    )
    return jsonify({"success": True, "bet_id": bet_id})


@app.route("/api/bets/<int:bet_id>", methods=["DELETE"])
def api_delete_bet(bet_id: int):
    db.delete_bet(bet_id)
    return jsonify({"success": True})


# ── API: レース結果 ───────────────────────────────────────────────────────────

@app.route("/api/results/fetch_pending", methods=["POST"])
def api_fetch_pending_results():
    """買い目があって結果未取得のレースを一括処理"""
    bets = db.get_bets()
    pending_ids = list({
        b["race_id"] for b in bets if b["result"] == ""
    })

    fetched = errors = 0
    for race_id in pending_ids:
        try:
            data = scraper.fetch_result(race_id)
            res  = data["result"]
            harai = data["haraimodoshi"]

            top3   = res[:3]
            rank1  = f"{top3[0]['umaban']} {top3[0]['bamei']}" if len(top3) > 0 else ""
            rank2  = f"{top3[1]['umaban']} {top3[1]['bamei']}" if len(top3) > 1 else ""
            rank3  = f"{top3[2]['umaban']} {top3[2]['bamei']}" if len(top3) > 2 else ""
            harai_str = " / ".join(
                f"{h['ticket_type']} {h['combination']} ¥{h['payout']:,}"
                for h in harai
            )
            db.save_result(race_id, rank1, rank2, rank3, harai_str, harai)

            # 買い目の的中判定
            race_bets = db.get_bets(race_id)
            for bet in race_bets:
                hit = False
                payout = 0
                for h in harai:
                    if _normalize_ticket(h["ticket_type"]) != _normalize_ticket(bet["ticket_type"]):
                        continue
                    if _match_combination(h["combination"], bet["combination"]):
                        hit = True
                        payout = int(h["payout"] * (bet["purchase"] / 100))
                db.update_bet_result(bet["id"], "◎" if hit else "✗", payout)

            fetched += 1
            time.sleep(0.5)
        except Exception as e:
            import traceback
            app.logger.error(f"result fetch error {race_id}: {e}\n{traceback.format_exc()}")
            errors += 1

    return jsonify({
        "success": True,
        "fetched": fetched,
        "errors":  errors,
        "message": f"{fetched}件の結果を取得しました（エラー: {errors}件）",
    })


def _normalize_ticket(t: str) -> str:
    return t.replace(" ", "").replace("　", "").lower()


def _match_combination(harai_comb: str, kaime_comb: str) -> bool:
    def normalize(s):
        nums = re.split(r"[-→\s]+", str(s).strip())
        try:
            return sorted(int(n) for n in nums if n.isdigit())
        except ValueError:
            return []
    return normalize(harai_comb) == normalize(kaime_comb)


# ── API: 馬詳細（血統・近走）────────────────────────────────────────────────

@app.route("/api/horse/<horse_id>")
def api_get_horse(horse_id: str):
    """DBに保存済みの馬詳細を返す"""
    detail = db.get_horse_detail(horse_id)
    return jsonify(detail)


@app.route("/api/horse/<horse_id>/fetch", methods=["POST"])
def api_fetch_horse(horse_id: str):
    """個別馬の取得は fetch_details（レース単位）を使うため非対応"""
    return jsonify({
        "success": False,
        "message": "個別取得は非対応です。出走表画面の「🧬 血統・近走を取得」ボタンを使ってください。"
    }), 400


@app.route("/api/shutuba/<race_id>/fetch_details", methods=["POST"])
def api_fetch_race_details(race_id: str):
    """
    shutuba_past.html から全出走馬の血統・近走を一括取得して保存する。
    db.netkeiba.com は使用しない（ログイン不要の shutuba_past.html から取得）。
    """
    horses = db.get_horses(race_id)
    if not horses:
        return jsonify({"success": False, "message": "先に出走表を取得してください"}), 400

    try:
        details = scraper.fetch_race_horse_details(race_id)
    except Exception as e:
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": f"取得エラー: {e}"}), 500

    app.logger.info(f"fetch_race_horse_details: {len(details)}頭取得")

    if not details:
        return jsonify({"success": False, "message": "血統・近走データが取得できませんでした（0件）"}), 500

    saved = 0
    no_id = 0
    for d in details:
        hid = d.get("horse_id", "")
        if not hid:
            no_id += 1
            app.logger.warning(f"horse_id空: {d.get('bamei','?')} (umaban={d.get('umaban')})")
            continue
        db.save_horse_detail(
            horse_id=hid,
            bamei=d.get("bamei", ""),
            blood={
                "father":        d.get("father", ""),
                "father_father": "",
                "father_mother": "",
                "mother":        d.get("mother", ""),
                "mother_father": d.get("mother_father", ""),
                "mother_mother": "",
            },
            recent_races=d.get("recent_races", []),
        )
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE horses SET horse_id=? WHERE race_id=? AND umaban=?",
                (hid, race_id, d["umaban"])
            )
        saved += 1
        app.logger.info(f"  saved: {d.get('bamei')} horse_id={hid} father={d.get('father','?')}")

    msg = f"{saved}頭の血統・近走を取得しました"
    if no_id: msg += f"（horse_id未取得: {no_id}頭）"
    return jsonify({
        "success": True,
        "done":    saved,
        "no_id":   no_id,
        "errors":  [],
        "message": msg,
    })


@app.route("/api/shutuba/<race_id>/horses_with_detail")
def api_horses_with_detail(race_id: str):
    """出走馬＋血統情報を結合して返す"""
    horses = db.get_horses_with_detail(race_id)
    return jsonify(horses)


# ── API: デバッグ ──────────────────────────────────────────────────────────

@app.route("/api/debug/horses/<race_id>")
def api_debug_horses(race_id: str):
    """horse_idの取得状態を確認するデバッグ用エンドポイント"""
    horses = db.get_horses(race_id)
    return jsonify([{
        "umaban": h["umaban"], "bamei": h["bamei"],
        "horse_id": h.get("horse_id",""), "has_id": bool(h.get("horse_id",""))
    } for h in horses])


# ── API: レース結果詳細 ───────────────────────────────────────────────────

@app.route("/api/results/refetch", methods=["POST"])
def api_refetch_results():
    """結果取得済みも含めて強制再取得する"""
    data = request.json or {}
    race_ids = data.get("race_ids", [])  # 空なら買い目のある全レース

    if not race_ids:
        bets = db.get_bets()
        race_ids = list({b["race_id"] for b in bets if b["result"] in ("◎","✗")})

    fetched = errors = 0
    for race_id in race_ids:
        try:
            data_r = scraper.fetch_result(race_id)
            res    = data_r["result"]
            harai  = data_r["haraimodoshi"]
            top3   = res[:3]
            rank1  = f"{top3[0]['umaban']} {top3[0]['bamei']}" if len(top3) > 0 else ""
            rank2  = f"{top3[1]['umaban']} {top3[1]['bamei']}" if len(top3) > 1 else ""
            rank3  = f"{top3[2]['umaban']} {top3[2]['bamei']}" if len(top3) > 2 else ""
            harai_str = " / ".join(
                f"{h['ticket_type']} {h['combination']} ¥{h['payout']:,}" for h in harai
            )
            db.save_result(race_id, rank1, rank2, rank3, harai_str, harai)

            # 買い目の的中を再判定
            race_bets = db.get_bets(race_id)
            for bet in race_bets:
                hit = False; payout = 0
                for h in harai:
                    if _normalize_ticket(h["ticket_type"]) != _normalize_ticket(bet["ticket_type"]):
                        continue
                    if _match_combination(h["combination"], bet["combination"]):
                        hit = True
                        payout = int(h["payout"] * (bet["purchase"] / 100))
                db.update_bet_result(bet["id"], "◎" if hit else "✗", payout)
            fetched += 1
            time.sleep(0.5)
        except Exception as e:
            errors += 1
            app.logger.error(f"refetch error {race_id}: {e}")

    return jsonify({
        "success": True,
        "fetched": fetched,
        "errors":  errors,
        "message": f"{fetched}件を再取得しました（エラー: {errors}件）",
    })


# ── API: レース結果詳細 ────────────────────────────────────────────────────

@app.route("/api/results/<race_id>")
def api_get_result(race_id: str):
    """指定レースの結果・払戻テーブルを返す"""
    result = db.get_result(race_id)
    return jsonify(result)


# ── API: 収支集計 ─────────────────────────────────────────────────────────────

@app.route("/api/summary")
def api_summary():
    year = request.args.get("year")
    return jsonify(db.get_summary(int(year) if year else None))


# ── 起動 ──────────────────────────────────────────────────────────────────────

def open_browser():
    time.sleep(1.0)
    webbrowser.open("http://localhost:5000")


if __name__ == "__main__":
    print("=" * 50)
    print("  🏇 競馬収支管理システム 起動中...")
    print("  URL: http://localhost:5000")
    print("  終了: Ctrl+C")
    print("=" * 50)
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
