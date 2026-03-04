import requests
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os
import re
import time
import requests
from typing import Optional, Tuple, List
from common import db, utils  # 你原本的 DB 模組

twseUrl = "https://www.twse.com.tw/rwd/zh"

# ======== 1. 個股成交日資訊 ========
def get_stock_day(stock_no: str, date: datetime | None = None) -> pd.DataFrame:
    date_str = utils._date_to_str(date)
    apiEndpoint = "afterTrading/STOCK_DAY"
    apiParams = f"date={date_str}&stockNo={stock_no}&response=json"
    apiUrl = f"{twseUrl}/{apiEndpoint}?{apiParams}"

    res = requests.get(apiUrl)
    data = res.json()

    df = pd.DataFrame(data.get("data", []), columns=data.get("fields", []))
    utils._save_to_csv(df, apiEndpoint, f"{stock_no}_{date_str}")
    return df

# ======== 2. 個股收盤價 ========
def get_stock_day_avg(stock_no: str, date: datetime | None = None) -> pd.DataFrame:
    date_str = utils._date_to_str(date)
    apiEndpoint = "afterTrading/STOCK_DAY_AVG"
    apiParams = f"date={date_str}&stockNo={stock_no}&response=json"
    apiUrl = f"{twseUrl}/{apiEndpoint}?{apiParams}"

    res = requests.get(apiUrl)
    data = res.json()

    df = pd.DataFrame(data.get("data", []), columns=data.get("fields", []))
    utils._save_to_csv(df, apiEndpoint, f"{stock_no}_{date_str}")
    return df

# ======== 3. 三大法人 ========
def get_institutional_investors(date: datetime | None = None) -> pd.DataFrame:
    date_str = utils._date_to_str(date)
    apiEndpoint = "fund/BFI82U"
    apiParams = f"type=day&dayDate={date_str}&weekDate={date_str}&monthDate={date_str}&response=json"
    apiUrl = f"{twseUrl}/{apiEndpoint}?{apiParams}"

    res = requests.get(apiUrl)
    data = res.json()

    df = pd.DataFrame(data.get("data", []), columns=data.get("fields", []))
    utils._save_to_csv(df, apiEndpoint, f"{date_str}")
    return df

# ======== 4. 融資融券餘額 ========
def get_margin_trading(date: datetime | None = None) -> pd.DataFrame:
    date_str = utils._date_to_str(date)
    apiEndpoint = "marginTrading/MI_MARGN"
    apiParams = f"date={date_str}&selectType=MS&response=json"
    apiUrl = f"{twseUrl}/{apiEndpoint}?{apiParams}"

    res = requests.get(apiUrl)
    data = res.json()

    # tables[0] 才有資料
    tables = data.get("tables", [])
    if not tables or "fields" not in tables[0] or "data" not in tables[0]:
        raise ValueError(f"❌ API 回傳格式異常: {data}")

    fields = tables[0]["fields"]
    rows = tables[0]["data"]

    df = pd.DataFrame(rows, columns=fields)

    utils._save_to_csv(df, apiEndpoint, f"{date_str}")
    return df

# ======== 5. 注意股公告 ========
def get_notice2(start_date: datetime | None = None, end_date: datetime | None = None) -> pd.DataFrame:
    start_str = utils._date_to_str(start_date)
    end_str = utils._date_to_str(end_date)
    apiEndpoint = "announcement/notice"
    apiParams = f"querytype=1&stockNo=&selectType=&startDate={start_str}&endDate={end_str}&sortKind=STKNO&response=json"
    apiUrl = f"{twseUrl}/{apiEndpoint}?{apiParams}"

    res = requests.get(apiUrl)
    data = res.json()

    df = pd.DataFrame(data.get("data", []), columns=data.get("fields", []))
    utils._save_to_csv(df, apiEndpoint, f"{start_str}_{end_str}")
    return df


# ============================================================
# 1) TWSE notice (上市公布注意有價證券)
# ============================================================

def get_notice(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    對應：
      GET https://www.twse.com.tw/rwd/zh/announcement/notice?querytype=1&...&startDate=YYYYMMDD&endDate=YYYYMMDD&response=json

    入庫表：twse_announcement_notice
    快取：date_span(target_table='twse_announcement_notice', idx_key='date')
    """
    target_table = "twse_announcement_notice"
    req_s = pd.Timestamp(start_date).normalize()
    req_e = pd.Timestamp(end_date).normalize()
    if req_s > req_e:
        raise ValueError("start_date 不可大於 end_date")

    mem_s, mem_e = utils._get_span(target_table)
    fetch_ranges, new_s, new_e = utils._calc_fetch_ranges(req_s, req_e, mem_s, mem_e)

    base_url = "https://www.twse.com.tw/rwd/zh/announcement/notice"

    # notice 表沒有 UNIQUE(證券代號, 日期) → 用「日期範圍先刪再灌」避免重複
    delete_sql = f"DELETE FROM {target_table} WHERE 日期 >= ? AND 日期 <= ?"

    insert_sql = f"""
    INSERT INTO {target_table}
      (證券代號, 證券名稱, 累計次數, 注意交易資訊, 日期, 收盤價, 本益比, created_at, 日期_ts)
    VALUES (?,?,?,?,?,?,?,?,?)
    """

    for fs, fe in fetch_ranges:
        if fs > fe:
            continue

        params = {
            "querytype": "1",
            "stockNo": "",
            "selectType": "",
            "startDate": fs.strftime("%Y%m%d"),
            "endDate": fe.strftime("%Y%m%d"),
            "sortKind": "DATE",
            "response": "json",
        }

        r = requests.get(base_url, params=params, timeout=30)
        r.raise_for_status()
        js = r.json()

        data = js.get("data") or []
        if not data:
            # 仍更新 span（代表這段已確認沒資料）
            continue

        rows = []
        for item in data:
            # fields: ["編號","證券代號","證券名稱","累計次數","注意交易資訊","日期","收盤價","本益比"]
            sid = str(item[1]).strip()
            name = str(item[2]).strip()
            cnt = utils._clean_int(item[3])
            info = str(item[4]).strip()
            roc_dt = str(item[5]).strip()
            ad_dt = utils._roc_to_ad_yyyy_mm_dd(roc_dt)  # notice 的日期是民國點分隔
            close_p = utils._clean_float(item[6])
            pe = utils._clean_float(item[7])

            if not ad_dt:
                continue

            rows.append((
                sid, name, cnt, info, ad_dt, close_p, pe,
                pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                utils._to_unix_ts(ad_dt),
            ))

        if rows:
            # 先刪掉該 range（以避免重複）
            db.execute_sql(delete_sql, (utils._dstr(fs), utils._dstr(fe)))
            db.execute_sql(insert_sql, rows)

    utils._update_span(target_table, new_s, new_e)

    # DB 回傳
    df = db.query_to_df(
        f"""
        SELECT id, 證券代號, 證券名稱, 累計次數, 注意交易資訊, 日期, 收盤價, 本益比, created_at, 日期_ts
        FROM {target_table}
        WHERE 日期 >= ? AND 日期 <= ?
        ORDER BY 日期, 證券代號
        """,
        (utils._dstr(req_s), utils._dstr(req_e)),
    )
    return df if df is not None else pd.DataFrame()


# ============================================================
# 2) TWSE punish (上市公布處置有價證券資訊)
# ============================================================
def get_punish(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    對應：
      GET https://www.twse.com.tw/rwd/zh/announcement/punish?response=json

    入庫表：twse_announcement_punish（UNIQUE(證券代號, 公布日期)）
    快取：date_span(target_table='twse_announcement_punish', idx_key='date')
    """
    import pandas as pd
    import requests
    from datetime import datetime

    target_table = "twse_announcement_punish"
    req_s = pd.Timestamp(start_date).normalize()
    req_e = pd.Timestamp(end_date).normalize()
    if req_s > req_e:
        raise ValueError("start_date 不可大於 end_date")

    mem_s, mem_e = utils._get_span(target_table)
    fetch_ranges, new_s, new_e = utils._calc_fetch_ranges(req_s, req_e, mem_s, mem_e)

    base_url = "https://www.twse.com.tw/rwd/zh/announcement/punish"

    # === INSERT 欄位（18 欄，其中 created_at 用 CURRENT_TIMESTAMP，不需要 row 值） ===
    insert_cols = [
        "公布日期", "證券代號", "證券名稱", "累計", "處置條件", "處置起迄時間", "處置措施", "處置內容", "備註",
        "created_at", "公布日期_ts",
        "law_src", "last_notice", "notice_cnt", "notice_dt",
        "處置起始日", "處置結束日", "處置總天數"
    ]
    insert_col_count = len(insert_cols)  # 18

    # row 會提供的值（不含 created_at）=> 17
    expected_row_len = insert_col_count - 1  # 17

    # === SQL：VALUES 的 ? 要等於 17（created_at 用 CURRENT_TIMESTAMP）===
    # 9個? + CURRENT_TIMESTAMP + 1個? + 4個? + 3個? = 17
    upsert_sql = f"""
    INSERT INTO {target_table}
      (公布日期, 證券代號, 證券名稱, 累計, 處置條件, 處置起迄時間, 處置措施, 處置內容, 備註,
       created_at, 公布日期_ts,
       law_src, last_notice, notice_cnt, notice_dt,
       處置起始日, 處置結束日, 處置總天數)
    VALUES (?,?,?,?,?,?,?,?,?,
            CURRENT_TIMESTAMP, ?,
            ?,?,?,?,
            ?,?,?)
    ON CONFLICT(證券代號, 公布日期) DO UPDATE SET
      證券名稱 = excluded.證券名稱,
      累計 = excluded.累計,
      處置條件 = excluded.處置條件,
      處置起迄時間 = excluded.處置起迄時間,
      處置措施 = excluded.處置措施,
      處置內容 = excluded.處置內容,
      備註 = excluded.備註,
      公布日期_ts = excluded.公布日期_ts,
      law_src = excluded.law_src,
      last_notice = excluded.last_notice,
      notice_cnt = excluded.notice_cnt,
      notice_dt = excluded.notice_dt,
      處置起始日 = excluded.處置起始日,
      處置結束日 = excluded.處置結束日,
      處置總天數 = excluded.處置總天數,
      created_at = CURRENT_TIMESTAMP
    """

    def _count_qmarks(sql: str) -> int:
        return sql.count("?")

    qmarks = _count_qmarks(upsert_sql)

    # 這裡印出最關鍵對齊資訊
    print("======== [DEBUG get_punish] ========")
    print("[DEBUG] target_table:", target_table)
    print("[DEBUG] req range:", utils._dstr(req_s), "~", utils._dstr(req_e))
    print("[DEBUG] mem span :", mem_s, "~", mem_e)
    print("[DEBUG] fetch_ranges:", [(utils._dstr(s), utils._dstr(e)) for s, e in fetch_ranges])
    print("[DEBUG] INSERT cols count:", insert_col_count, " (includes created_at)")
    print("[DEBUG] expected_row_len (exclude created_at):", expected_row_len)
    print("[DEBUG] SQL qmarks:", qmarks, "=> should equal expected_row_len")
    if qmarks != expected_row_len:
        raise ValueError(f"[FATAL] SQL ? 數量({qmarks}) != row 期望長度({expected_row_len})，請先修 SQL。")

    total_inserted_ranges = 0

    for fs, fe in fetch_ranges:
        if fs > fe:
            continue

        print("\n------ [DEBUG] fetch range ------")
        print("[DEBUG] fs ~ fe:", utils._dstr(fs), "~", utils._dstr(fe))

        params = {
            "response": "json",
            "startDate": fs.strftime("%Y%m%d"),
            "endDate": fe.strftime("%Y%m%d"),
        }

        r = requests.get(base_url, params=params, timeout=30)
        r.raise_for_status()
        js = r.json()

        stat = js.get("stat")
        title = js.get("title")
        fields = js.get("fields")
        data = js.get("data") or []

        print("[DEBUG] stat:", stat)
        if title:
            print("[DEBUG] title:", title)
        if fields:
            print("[DEBUG] fields:", fields)
        print("[DEBUG] data len:", len(data))

        if not data:
            continue

        rows = []
        for i, item in enumerate(data):
            try:
                # fields:
                # ["編號","公布日期","證券代號","證券名稱","累計","處置條件","處置起迄時間","處置措施","處置內容","備註"]
                pub_roc = str(item[1]).strip()
                pub_ad = utils._roc_to_ad_yyyy_mm_dd(pub_roc)
                sid = str(item[2]).strip()
                name = str(item[3]).strip()
                acc = utils._clean_int(item[4])
                cond = str(item[5]).strip()
                period = str(item[6]).strip()
                measure = str(item[7]).strip()
                content = str(item[8]).strip()
                memo = item[9]  # 可能是 html string
                memo_str = str(memo) if memo is not None else None

                if not pub_ad:
                    print(f"[DEBUG] skip row#{i}: pub_ad empty; pub_roc={pub_roc!r}, item={item}")
                    continue

                # 解析處置起迄時間（可能回傳 None）
                s_ad, e_ad, total_days = utils._parse_range_roc(period)

                # enrich 欄位先保留 None
                law_src = None
                last_notice = None
                notice_cnt = None
                notice_dt = None

                row = (
                    pub_ad, sid, name, acc, cond, period, measure, content, memo_str,
                    utils._to_unix_ts(pub_ad),
                    law_src, last_notice, notice_cnt, notice_dt,
                    s_ad, e_ad, total_days
                )

                if len(row) != expected_row_len:
                    print("❌ [DEBUG] row length mismatch")
                    print("[DEBUG] expected_row_len:", expected_row_len)
                    print("[DEBUG] got len(row):", len(row))
                    print("[DEBUG] row content:", row)
                    print("[DEBUG] raw item:", item)
                    raise ValueError("Row length mismatch")

                # 印第一筆樣本
                if i == 0:
                    print("[DEBUG] sample row len:", len(row))
                    print("[DEBUG] sample row:", row)

                rows.append(row)

            except Exception as ex:
                print("❌ [DEBUG] exception while parsing item")
                print("[DEBUG] item index:", i)
                print("[DEBUG] item:", item)
                print("[DEBUG] ex:", repr(ex))
                raise

        if rows:
            print("[DEBUG] inserting rows:", len(rows))
            # 額外再驗一次每筆長度
            bad = [j for j, rr in enumerate(rows) if len(rr) != expected_row_len]
            if bad:
                print("❌ [DEBUG] found bad rows idx:", bad[:20])
                print("[DEBUG] first bad row:", rows[bad[0]])
                raise ValueError("Found bad rows length before DB insert")

            db.execute_sql(upsert_sql, rows)
            total_inserted_ranges += 1

    utils._update_span(target_table, new_s, new_e)
    print("\n[DEBUG] update_span:", utils._dstr(new_s), "~", utils._dstr(new_e))
    print("[DEBUG] inserted_ranges:", total_inserted_ranges)
    print("======== [DEBUG get_punish END] ========")

    df = db.query_to_df(
        f"""
        SELECT *
        FROM {target_table}
        WHERE 公布日期 >= ? AND 公布日期 <= ?
        ORDER BY 公布日期, 證券代號
        """,
        (utils._dstr(req_s), utils._dstr(req_e)),
    )
    return df if df is not None else pd.DataFrame()

# ======== 範例測試 ========
if __name__ == "__main__":
    test = datetime.today()
    test = test - relativedelta(months=1)

    # 測試下載各項資料
    get_stock_day("2330", test)
    get_stock_day_avg("0050", test)
    get_institutional_investors(test)
    get_margin_trading(test)
    get_notice2(datetime(2025, 10, 1), datetime(2025, 10, 4))
