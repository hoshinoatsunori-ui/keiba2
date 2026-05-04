"""
scraper.py - netkeibaスクレイピング
対象: ログイン不要の公開ページのみ

ブラウザ実測による正確なクラス名:

【shutuba.html】 出走表（基本情報）
  文字コード: EUC-JP
  tr#tr_N の N = 馬番
  td.Waku         = 枠番
  td.HorseInfo    = 馬情報
  span.HorseName  = 馬名
  a[href*=horse]  = horse_id
  td.Barei        = 性齢
  td.Txt_C        = 斤量（Waku/Umaban/Barei/Popular以外の最初）
  td.Jockey       = 騎手
  td.Trainer      = 調教師
  td.Txt_R.Popular= オッズ

【shutuba_past.html】 出走表＋近5走＋血統
  td.Horse_Info (not td.HorseInfo):
    div.Horse01 = 父
    div.Horse02 = 馬名
    div.Horse03 = 母
    div.Horse04 = 母父（カッコ付き）
  td.Past = 近走1走分（複数存在）
    テキスト構造: "日付 開催 | 着順 | レース名 | 距離 タイム 馬場 | 頭数 馬番 人気 騎手 斤量 | コーナー (上り) 馬体重 | 着差"
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
    "Referer": "https://race.netkeiba.com/",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

BASE_SHUTUBA   = "https://race.netkeiba.com/race/shutuba.html?race_id="
BASE_RESULT    = "https://race.netkeiba.com/race/result.html?race_id="
BASE_RACE_LIST = "https://race.netkeiba.com/top/race_list_sub.html?kaisai_date="
BASE_PAST      = "https://race.netkeiba.com/race/shutuba_past.html?race_id="



def _fetch(url: str) -> BeautifulSoup:
    """URLを取得してBeautifulSoupを返す（EUC-JP強制）"""
    resp = SESSION.get(url, timeout=20)
    resp.raise_for_status()
    detected = (resp.apparent_encoding or "").lower()
    resp.encoding = "EUC-JP" if detected in ("ascii", "iso-8859-1", "") else detected
    return BeautifulSoup(resp.text, "lxml")


# ── race_id一覧取得 ─────────────────────────────────────────────────────────

def fetch_race_ids_by_date(kaisai_date: str) -> list[dict]:
    """指定日（YYYYMMDD）の全race_idを競馬場別に返す"""
    url = f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={kaisai_date}"
    soup = _fetch(url)
    result = []
    for dt in soup.select("dt.RaceList_DataHeader"):
        jo_text = dt.get_text(" ", strip=True)
        jo_name = " ".join(jo_text.split()[:3])
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        ids, seen = [], set()
        for a in dd.select("a[href*='race_id=']"):
            m = re.search(r"race_id=(\d{12})", a["href"])
            if m and m.group(1) not in seen:
                ids.append(m.group(1))
                seen.add(m.group(1))
        if ids:
            result.append({"jo": jo_name, "ids": ids})
    return result


def get_this_weekend_dates() -> list[str]:
    today = date.today()
    dow = today.weekday()
    if dow == 5:
        sat = today
    elif dow == 6:
        sat = today - timedelta(days=1)
    else:
        sat = today + timedelta(days=(5 - dow))
    return [sat.strftime("%Y%m%d"), (sat + timedelta(days=1)).strftime("%Y%m%d")]


# ── 出走表取得（基本情報のみ）───────────────────────────────────────────────

def fetch_shutuba(race_id: str) -> dict:
    """
    shutuba.html から出走表を取得（基本情報 + horse_id）
    """
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    soup = _fetch(url)

    # レース情報
    name_tag = soup.select_one(".RaceName")
    race_name = re.sub(r"\s+", " ", name_tag.get_text(" ", strip=True)).strip() if name_tag else ""
    d01 = soup.select_one(".RaceData01")
    d02 = soup.select_one(".RaceData02")
    race_data = re.sub(r"\s+", " ", " ".join([
        d01.get_text(" ", strip=True) if d01 else "",
        d02.get_text(" ", strip=True) if d02 else "",
    ])).strip()

    race_info = {"race_id": race_id, "race_name": race_name, "race_data": race_data}

    # 馬一覧
    horses = []
    for tr in soup.select("tr[id^='tr_']"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 8:
            continue

        # 馬番: td[class*=Umaban] のテキスト（tr_N のNは内部IDで馬番ではない）
        umaban_td = tr.select_one("td[class*=Umaban]")
        try:
            umaban = int(umaban_td.get_text(strip=True)) if umaban_td else 0
        except ValueError:
            continue
        if umaban == 0:
            continue

        # 枠番: td[class*=Waku] のテキスト、枠番色はクラス名 WakuN のN
        waku_td = tr.select_one("td[class*=Waku]")
        try:
            wakuban = int(waku_td.get_text(strip=True)) if waku_td else 0
        except ValueError:
            wakuban = 0

        # 馬名 + horse_id
        horse_info_td = tr.select_one("td.HorseInfo")
        bamei, horse_id = "", ""
        if horse_info_td:
            hn = horse_info_td.select_one("span.HorseName")
            bamei = hn.get_text(strip=True) if hn else ""
            for a in horse_info_td.find_all("a"):
                href = a.get("href", "")
                m = re.search(r"horse[/=_]?(\d{6,12})", href)
                if m:
                    horse_id = m.group(1)
                    break
            if not bamei:
                for a in horse_info_td.find_all("a"):
                    t = a.get_text(strip=True)
                    if t:
                        bamei = t
                        break
        if not bamei:
            continue

        # 性齢
        barei_td = tr.select_one("td.Barei")
        barei = barei_td.get_text(strip=True) if barei_td else ""

        # td一覧を取得してインデックスで正確に取得
        # 構造: [0]枠番 [1]馬番 [2]印 [3]馬情報 [4]性齢 [5]斤量 [6]騎手 [7]調教師 [8]馬体重 [9]オッズ [10]人気
        all_tds = tr.find_all("td", recursive=False)

        # 斤量: index=5
        kinryo = all_tds[5].get_text(strip=True) if len(all_tds) > 5 else ""

        # 騎手: index=6（aタグがあればそのテキスト）
        jockey = ""
        if len(all_tds) > 6:
            jockey_td = all_tds[6]
            a = jockey_td.find("a")
            jockey = a.get_text(strip=True) if a else jockey_td.get_text(strip=True)

        # 調教師: index=7
        trainer = re.sub(r"\s+", " ", all_tds[7].get_text(" ", strip=True)).strip() if len(all_tds) > 7 else ""

        # オッズ: index=9（Txt_R Popular）
        odds = ""
        if len(all_tds) > 9:
            odds_txt = all_tds[9].get_text(strip=True)
            if re.match(r"[\d.]+", odds_txt):
                odds = odds_txt

        horses.append({
            "wakuban":  wakuban,
            "umaban":   umaban,
            "horse_id": horse_id,
            "bamei":    bamei,
            "barei":    barei,
            "jockey":   jockey,
            "kinryo":   kinryo,
            "trainer":  trainer,
            "odds":     odds,
        })

    if horses and not any(h["wakuban"] > 0 for h in horses):
        horses = _calc_wakuban(horses)

    return {"race_info": race_info, "horses": horses}


def _calc_wakuban(horses: list[dict]) -> list[dict]:
    horses = sorted(horses, key=lambda h: h["umaban"])
    n = len(horses)
    base, rem = n // 8, n % 8
    sizes = [base + (1 if w >= (8 - rem) else 0) for w in range(8)]
    idx = 0
    for w, size in enumerate(sizes):
        for _ in range(size):
            if idx < len(horses):
                horses[idx]["wakuban"] = w + 1
                idx += 1
    return horses


# ── 血統・近走取得（shutuba_past.html から）────────────────────────────────

def fetch_horse_detail(horse_id: str) -> dict:
    """
    horse_id に対応する race_id が必要なため、この関数は使わない。
    代わりに fetch_race_horse_details(race_id) を使う。
    互換性のために残す。
    """
    raise NotImplementedError("horse_idから直接は取得できません。fetch_race_horse_details(race_id)を使ってください。")


def fetch_race_horse_details(race_id: str) -> list[dict]:
    """
    shutuba_past.html から全出走馬の血統・近走を一括取得する。

    ブラウザ実測済みの構造:
      td.Horse_Info (not td.HorseInfo):
        div.Horse01 = 父
        div.Horse02 = 馬名
        div.Horse03 = 母
        div.Horse04 = 母父（例: "(Oasis Dream)"）
      td.Past = 近走1走分（複数）
        改行区切りのテキスト:
          行0: "2026.02.21 東京"
          行1: "3"  (着順)
          行2: "3歳未勝利"
          行3: "ダ1400 1:26.8 良"
          行4: "16頭 4番 10人 吉村誠之 55.0"
          行5: "2-2 (38.4) 484(+4)"
          行6: "スーパーガール(0.4)"  (着差)

    Returns:
        [{
          "umaban": int,
          "horse_id": str,
          "bamei": str,
          "father": str,   # 父
          "mother": str,   # 母
          "mother_father": str,  # 母父
          "recent_races": [{"date","place","chakun","race_name","dist_time_baba","detail","chakusa"}, ...]
        }, ...]
    """
    url = f"https://race.netkeiba.com/race/shutuba_past.html?race_id={race_id}"
    soup = _fetch(url)

    results = []
    for tr in soup.select("tr.HorseList"):
        # 馬番: td[class*=Umaban] のテキスト（tr_N のNは内部IDで馬番ではない）
        umaban_td = tr.select_one("td[class*=Umaban]")
        try:
            umaban = int(umaban_td.get_text(strip=True)) if umaban_td else 0
        except ValueError:
            continue
        if umaban == 0:
            continue

        # horse_id: Horse_Info td内のリンク
        hi_td = tr.select_one("td.Horse_Info")
        horse_id = ""
        bamei = ""
        father = mother = mother_father = ""

        if hi_td:
            # horse_id
            for a in hi_td.find_all("a"):
                m = re.search(r"horse[/=_]?(\d{6,12})", a.get("href", ""))
                if m:
                    horse_id = m.group(1)
                    break

            # 血統
            h01 = hi_td.select_one(".Horse01")
            h02 = hi_td.select_one(".Horse02")
            h03 = hi_td.select_one(".Horse03")
            h04 = hi_td.select_one(".Horse04")

            father        = h01.get_text(strip=True) if h01 else ""
            bamei         = h02.get_text(strip=True) if h02 else ""
            mother        = h03.get_text(strip=True) if h03 else ""
            mother_father = re.sub(r"[()]", "", h04.get_text(strip=True)).strip() if h04 else ""

        # 近走: td.Past 内の div.Data_Item > div.DataXX クラスで取得
        # ブラウザ実測済みの構造:
        #   div.Data01 > span[0]=日付+開催, span.Num=着順
        #   div.Data02 = レース名
        #   div.Data05 = 距離・タイム・馬場  例: "芝1200(外) 1:08.8 良"
        #   div.Data03 = 頭数・馬番・人気・騎手・斤量
        #   div.Data06 = コーナー・上がり3F・馬体重
        #   div.Data07 = 着差
        recent_races = []
        for past_td in tr.select("td.Past"):
            di = past_td.select_one("div.Data_Item")
            if not di:
                continue

            # Data01: 日付+開催 / 着順
            d01 = di.select_one(".Data01")
            race_date, place, chakun = "", "", ""
            if d01:
                spans = d01.find_all("span")
                if spans:
                    dp = spans[0].get_text(strip=True).split()
                    race_date = dp[0] if dp else ""
                    place     = dp[1] if len(dp) > 1 else ""
                num_span = d01.select_one("span.Num")
                chakun = num_span.get_text(strip=True) if num_span else ""

            # Data02: レース名
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

            # Data05: 距離・タイム・馬場
            d05 = di.select_one(".Data05")
            dtb = d05.get_text(strip=True) if d05 else ""
            dm = re.match(r"([芝ダ障][^\s]*)\s+([0-9:.]+)\s*(.*)", dtb)
            if dm:
                distance = dm.group(1)
                time_val = dm.group(2)
                baba     = dm.group(3).strip()
            else:
                distance = dtb; time_val = ""; baba = ""

            # Data03: 頭数・馬番・人気・騎手・斤量
            d03 = di.select_one(".Data03")
            detail = d03.get_text(strip=True) if d03 else ""
            nhm = re.search(r"(\d+)頭", detail)
            um  = re.search(r"(\d+)番", detail)
            nkm = re.search(r"(\d+)人", detail)
            km  = re.search(r"(\d+\.\d+)\s*$", detail)
            num_horses  = nhm.group(1) if nhm else ""
            past_umaban = um.group(1)  if um  else ""
            ninki       = nkm.group(1) if nkm else ""
            kinryo_val  = km.group(1)  if km  else ""
            jt = re.sub(r"\d+頭|\d+番|\d+人|\d+\.\d+", "", detail).strip()
            jockey_val = " ".join(jt.split())

            # Data06: コーナー・上がり3F・馬体重
            d06 = di.select_one(".Data06")
            ca  = d06.get_text(strip=True) if d06 else ""
            am  = re.search(r"\(([\d.]+)\)", ca)
            agari = am.group(1) if am else ""

            # Data07: 着差
            d07 = di.select_one(".Data07")
            chakusa = d07.get_text(strip=True) if d07 else ""

            recent_races.append({
                "date":       race_date,
                "place":      place,
                "chakun":     chakun,
                "race_name":  race_name,
                "num_horses": num_horses,
                "umaban":     past_umaban,
                "ninki":      ninki,
                "jockey":     jockey_val,
                "kinryo":     kinryo_val,
                "distance":   distance,
                "time":       time_val,
                "baba":       baba,
                "agari":      agari,
                "chakusa":    chakusa,
            })

        results.append({
            "umaban":       umaban,
            "horse_id":     horse_id,
            "bamei":        bamei,
            "father":       father,
            "mother":       mother,
            "mother_father": mother_father,
            "recent_races": recent_races,
        })

    return results


def fetch_horse_id_from_shutuba(race_id: str) -> dict[str, str]:
    """出走表から {umaban: horse_id} を返す（補完用）"""
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    soup = _fetch(url)
    result = {}
    result = {}
    for tr in soup.select("tr[id^='tr_']"):
        # 馬番: td[class*=Umaban] のテキスト
        umaban_td = tr.select_one("td[class*=Umaban]")
        try:
            umaban = int(umaban_td.get_text(strip=True)) if umaban_td else 0
        except ValueError:
            continue
        if umaban == 0:
            continue
        horse_info_td = tr.select_one("td.HorseInfo")
        if not horse_info_td:
            continue
        for a in horse_info_td.find_all("a"):
            m = re.search(r"horse[/=_]?(\d{6,12})", a.get("href", ""))
            if m:
                result[umaban] = m.group(1)
                break
    return result


# ── レース結果取得 ──────────────────────────────────────────────────────────

def fetch_result(race_id: str) -> dict:
    """
    レース結果・払戻を取得

    result.html の実際のHTML構造（ブラウザ実測）:
      着順: tr.HorseList / tr.FirstDisplay.HorseList
        td.Result_Num = 着順  tds[2]=馬番  tds[3]=馬名

      払戻: table.Payout_Detail_Table が2つ
        trクラス = 券種（Tansho/Fukusho/Wakuren/Umaren/Wide/Umatan/Fuku3/Tan3）
        td.Result:
          組み合わせは ul>li>span または div>span で各数字が個別タグに入っている
          複数組み合わせ（ワイド等）は ul が複数
        td.Payout:
          払戻金額は span 内に <br> 区切りで複数
    """
    TICKET_CLASS_MAP = {
        "Tansho":  "単勝",
        "Fukusho": "複勝",
        "Wakuren": "枠連",
        "Umaren":  "馬連",
        "Wide":    "ワイド",
        "Umatan":  "馬単",
        "Fuku3":   "三連複",
        "Tan3":    "三連単",
    }

    url  = BASE_RESULT + race_id
    soup = _fetch(url)

    # ---- 着順 ---------------------------------------------------------------
    result_rows = []
    for tr in soup.select("tr.HorseList, tr.FirstDisplay.HorseList"):
        tds    = tr.find_all("td")
        chakun = tr.select_one("td.Result_Num")
        if not chakun:
            continue
        umaban = tds[2].get_text(strip=True) if len(tds) > 2 else ""
        bamei  = tds[3].get_text(strip=True) if len(tds) > 3 else ""
        result_rows.append({
            "chakun": chakun.get_text(strip=True),
            "umaban": umaban,
            "bamei":  bamei,
        })

    # ---- 払戻 ---------------------------------------------------------------
    harai_list = []
    for pay_table in soup.select(".Payout_Detail_Table"):
        for tr in pay_table.find_all("tr"):
            tr_classes = tr.get("class", [])
            ticket_type = ""
            for cls in tr_classes:
                if cls in TICKET_CLASS_MAP:
                    ticket_type = TICKET_CLASS_MAP[cls]
                    break
            if not ticket_type:
                continue

            result_td = tr.select_one("td.Result")
            payout_td = tr.select_one("td.Payout")
            if not result_td or not payout_td:
                continue

            # 組み合わせ抽出: ul>li>span または div>span の数字をグループ化
            combs = []
            uls = result_td.find_all("ul")
            if uls:
                # 枠連/馬連/ワイド/馬単/三連複/三連単: ulがグループ（1組み合わせ=1ul）
                for ul in uls:
                    nums = [sp.get_text(strip=True) for sp in ul.select("li span") if sp.get_text(strip=True)]
                    if nums:
                        combs.append("-".join(nums))
            else:
                # 単勝/複勝: div>spanで各数字が個別
                divs = result_td.find_all("div")
                nums = []
                for div in divs:
                    sp = div.find("span")
                    if sp:
                        t = sp.get_text(strip=True)
                        if t:
                            nums.append(t)
                # 複勝は複数番号を個別組み合わせとして扱う
                for n in nums:
                    combs.append(n)

            # 払戻金額抽出: span内の<br>区切りテキスト
            payouts = []
            pay_span = payout_td.find("span")
            if pay_span:
                # <br>を改行に変換してget_text
                for br in pay_span.find_all("br"):
                    br.replace_with("\n")
                pay_text = pay_span.get_text()
                for line in pay_text.split("\n"):
                    line = line.strip()
                    if line:
                        payout = int(re.sub(r"[^\d]", "", line) or "0")
                        payouts.append(payout)

            # 組み合わせと払戻を対応付け
            for i, comb in enumerate(combs):
                payout = payouts[i] if i < len(payouts) else (payouts[0] if payouts else 0)
                harai_list.append({
                    "ticket_type": ticket_type,
                    "combination": comb,
                    "payout":      payout,
                })

    return {"result": result_rows, "haraimodoshi": harai_list}


# ── race_idメタ情報 ─────────────────────────────────────────────────────────

JO_CODE_MAP = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
    "05": "東京", "06": "中山", "07": "中京", "08": "京都",
    "09": "阪神", "10": "小倉",
}

def parse_race_id(race_id: str) -> dict:
    return {
        "year":       race_id[0:4],
        "jo_code":    race_id[4:6],
        "jo_name":    JO_CODE_MAP.get(race_id[4:6], race_id[4:6]),
        "kaisai_kai": int(race_id[6:8]),
        "day_no":     int(race_id[8:10]),
        "race_no":    int(race_id[10:12]),
    }