import re
import time
import requests
import pandas as pd
from datetime import datetime
from typing import Optional, Tuple, List
from common import db, utils  # 你原本的 DB 模組

# ============================================================
# 3) TPEX attention (上櫃公布注意有價證券)
# ============================================================

def get_notice(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    對應：
      POST https://www.tpex.org.tw/www/zh-tw/bulletin/attention
      payload: startDate=YYYY/MM/DD&endDate=YYYY/MM/DD&...&response=json

    入庫表：tpex_bulletin_attention
    快取：date_span(target_table='tpex_bulletin_attention', idx_key='date')
    """
    target_table = "tpex_bulletin_attention"
    req_s = pd.Timestamp(start_date).normalize()
    req_e = pd.Timestamp(end_date).normalize()
    if req_s > req_e:
        raise ValueError("start_date 不可大於 end_date")

    mem_s, mem_e = utils._get_span(target_table)
    fetch_ranges, new_s, new_e = utils._calc_fetch_ranges(req_s, req_e, mem_s, mem_e)

    url = "https://www.tpex.org.tw/www/zh-tw/bulletin/attention"

    delete_sql = f"DELETE FROM {target_table} WHERE 公告日期 >= ? AND 公告日期 <= ?"

    insert_sql = f"""
    INSERT INTO {target_table}
      (證券代號, 證券名稱, 累計, 注意交易資訊, 公告日期, 收盤價, 本益比, link, created_at, 公告日期_ts)
    VALUES (?,?,?,?,?,?,?,?,?,?)
    """

    for fs, fe in fetch_ranges:
        if fs > fe:
            continue

        payload = {
            "startDate": fs.strftime("%Y/%m/%d"),
            "endDate": fe.strftime("%Y/%m/%d"),
            "code": "",
            "cate": "",
            "type": "all",
            "order": "date",
            "id": "",
            "response": "json",
        }

        r = requests.post(url, data=payload, timeout=30)
        r.raise_for_status()
        js = r.json()

        tables = js.get("tables") or []
        if not tables:
            continue

        data = tables[0].get("data") or []
        if not data:
            continue

        rows = []
        for item in data:
            # fields:
            # ["編號","證券代號","證券名稱","累計","注意交易資訊","公告日期","收盤價","本益比","link"]
            sid = str(item[1]).strip()
            name = str(item[2]).strip()
            acc = utils._clean_int(item[3])
            info = str(item[4]).strip()
            pub_roc = str(item[5]).strip()  # 115/01/15
            pub_ad = utils._roc_to_ad_yyyy_mm_dd(pub_roc)
            close_p = utils._clean_float(item[6])
            pe = utils._clean_float(item[7])
            link = str(item[8]).strip() if item[8] is not None else None

            if not pub_ad:
                continue

            rows.append((
                sid, name, acc, info, pub_ad, close_p, pe, link,
                pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                utils._to_unix_ts(pub_ad),
            ))

        if rows:
            db.execute_sql(delete_sql, (utils._dstr(fs), utils._dstr(fe)))
            db.execute_sql(insert_sql, rows)

    utils._update_span(target_table, new_s, new_e)

    df = db.query_to_df(
        f"""
        SELECT id, 證券代號, 證券名稱, 累計, 注意交易資訊, 公告日期, 收盤價, 本益比, link, created_at, 公告日期_ts
        FROM {target_table}
        WHERE 公告日期 >= ? AND 公告日期 <= ?
        ORDER BY 公告日期, 證券代號
        """,
        (utils._dstr(req_s), utils._dstr(req_e)),
    )
    return df if df is not None else pd.DataFrame()


# ============================================================
# 4) TPEX disposal (上櫃公布處置有價證券資訊)
# ============================================================
def get_punish(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    對應：
      POST https://www.tpex.org.tw/www/zh-tw/bulletin/disposal
      payload: startDate=YYYY/MM/DD&endDate=YYYY/MM/DD&...&response=json

    入庫表：tpex_bulletin_disposal（UNIQUE(證券代號, 公布日期)）
    快取：date_span(target_table='tpex_bulletin_disposal', idx_key='date')
    """
    import pandas as pd
    import requests

    target_table = "tpex_bulletin_disposal"
    req_s = pd.Timestamp(start_date).normalize()
    req_e = pd.Timestamp(end_date).normalize()
    if req_s > req_e:
        raise ValueError("start_date 不可大於 end_date")

    mem_s, mem_e = utils._get_span(target_table)
    fetch_ranges, new_s, new_e = utils._calc_fetch_ranges(req_s, req_e, mem_s, mem_e)

    print("======== [DEBUG get_punish TPEX] ========")
    print("[DEBUG] target_table:", target_table)
    print("[DEBUG] req range:", utils._dstr(req_s), "~", utils._dstr(req_e))
    print("[DEBUG] mem span :", mem_s, "~", mem_e)
    print("[DEBUG] fetch_ranges:",
          [(utils._dstr(s), utils._dstr(e)) for s, e in fetch_ranges])

    url = "https://www.tpex.org.tw/www/zh-tw/bulletin/disposal"

    # INSERT 欄位共 19 欄，其中 created_at 用 CURRENT_TIMESTAMP
    insert_cols = [
        "公布日期", "證券代號", "證券名稱", "累計", "處置起訖時間", "處置原因", "處置內容",
        "收盤價", "本益比", "memo",
        "created_at", "公布日期_ts",
        "law_src", "last_notice", "notice_cnt", "notice_dt",
        "處置起始日", "處置結束日", "處置總天數"
    ]
    insert_col_count = len(insert_cols)          # 19
    expected_row_len = insert_col_count - 1      # 18（不含 created_at）

    upsert_sql = f"""
    INSERT INTO {target_table}
      (公布日期, 證券代號, 證券名稱, 累計, 處置起訖時間, 處置原因, 處置內容, 收盤價, 本益比, memo,
       created_at, 公布日期_ts,
       law_src, last_notice, notice_cnt, notice_dt,
       處置起始日, 處置結束日, 處置總天數)
    VALUES (?,?,?,?,?,?,?,?,?,?, CURRENT_TIMESTAMP, ?,
            ?,?,?,?,
            ?,?,?)
    ON CONFLICT(證券代號, 公布日期) DO UPDATE SET
      證券名稱 = excluded.證券名稱,
      累計 = excluded.累計,
      處置起訖時間 = excluded.處置起訖時間,
      處置原因 = excluded.處置原因,
      處置內容 = excluded.處置內容,
      收盤價 = excluded.收盤價,
      本益比 = excluded.本益比,
      memo = excluded.memo,
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

    qmarks = upsert_sql.count("?")
    print("[DEBUG] INSERT cols count:", insert_col_count, "(includes created_at)")
    print("[DEBUG] expected_row_len:", expected_row_len)
    print("[DEBUG] SQL qmarks:", qmarks)

    if qmarks != expected_row_len:
        raise ValueError(
            f"[FATAL] SQL ? 數量({qmarks}) != row 期望長度({expected_row_len})"
        )

    total_rows = 0
    total_ranges = 0

    for fs, fe in fetch_ranges:
        if fs > fe:
            continue

        print("\n------ [DEBUG] fetch range ------")
        print("[DEBUG] fs ~ fe:", utils._dstr(fs), "~", utils._dstr(fe))

        payload = {
            "startDate": fs.strftime("%Y/%m/%d"),
            "endDate": fe.strftime("%Y/%m/%d"),
            "code": "",
            "cate": "",
            "type": "all",
            "reason": "-1",
            "measure": "-1",
            "order": "date",
            "id": "",
            "response": "json",
        }

        r = requests.post(url, data=payload, timeout=30)
        r.raise_for_status()
        js = r.json()

        tables = js.get("tables") or []
        print("[DEBUG] tables len:", len(tables))
        if not tables:
            continue

        data = tables[0].get("data") or []
        print("[DEBUG] data len:", len(data))
        if not data:
            continue

        rows = []
        for i, item in enumerate(data):
            try:
                # ["編號","公布日期","證券代號","證券名稱","累計","處置起訖時間",
                #  "處置原因","處置內容","收盤價","本益比"," "]
                pub_roc = str(item[1]).strip()
                pub_ad = utils._roc_to_ad_yyyy_mm_dd(pub_roc)
                sid = str(item[2]).strip()

                raw_name = str(item[3]).strip()
                name = raw_name.split("(")[0].strip()

                acc = utils._clean_int(item[4])
                period = str(item[5]).strip()
                reason = str(item[6]).strip()
                content = str(item[7]).strip()
                close_p = utils._clean_float(item[8])
                pe = utils._clean_float(item[9])
                memo = item[10]
                memo_str = str(memo) if memo is not None else None

                if not pub_ad:
                    print(f"[DEBUG] skip row#{i}: invalid pub_ad ({pub_roc})")
                    continue

                s_ad, e_ad, total_days = utils._parse_range_roc(period)

                law_src = None
                last_notice = None
                notice_cnt = None
                notice_dt = None

                row = (
                    pub_ad, sid, name, acc, period, reason, content,
                    close_p, pe, memo_str,
                    utils._to_unix_ts(pub_ad),
                    law_src, last_notice, notice_cnt, notice_dt,
                    s_ad, e_ad, total_days
                )

                if len(row) != expected_row_len:
                    print("❌ [DEBUG] row length mismatch")
                    print("[DEBUG] expected:", expected_row_len, "got:", len(row))
                    print("[DEBUG] row:", row)
                    print("[DEBUG] raw item:", item)
                    raise ValueError("Row length mismatch")

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
            db.execute_sql(upsert_sql, rows)
            total_rows += len(rows)
            total_ranges += 1

    utils._update_span(target_table, new_s, new_e)
    print("[DEBUG] update_span:", utils._dstr(new_s), "~", utils._dstr(new_e))
    print("[DEBUG] inserted ranges:", total_ranges)
    print("[DEBUG] inserted rows:", total_rows)
    print("======== [DEBUG get_punish TPEX END] ========")

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
