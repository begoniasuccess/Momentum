import sys, os
sys.path.append(os.path.dirname(__file__))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from common import utils, db
from module import finMind
import re
import copy
from datetime import datetime
import pytz

TZ = pytz.timezone("Asia/Taipei")

def to_day_ts(ts_series: pd.Series) -> pd.Series:
    """將 timestamp（秒）轉成台北時區「當日 00:00」的 epoch 秒"""
    dt = pd.to_datetime(ts_series, unit="s", utc=True, errors="coerce").dt.tz_convert(TZ)
    day0 = dt.dt.normalize()  # 歸零到當天 00:00
    return (day0.view("int64") // 10**9).astype("Int64")

def build_trading_index() -> dict[int, int]:
    """建立交易日曆索引：day_ts → 交易日序號"""
    df_calendar = finMind.getTwStockTradingDates()
    df_calendar["date"] = pd.to_datetime(df_calendar["date"]).dt.tz_localize(TZ).dt.normalize()
    df_calendar["day_ts"] = (df_calendar["date"].view("int64") // 10**9).astype("int64")
    uniq = pd.Index(df_calendar["day_ts"].unique()).sort_values()
    return {int(ts): i for i, ts in enumerate(uniq)}


def update_punish_notice_dt():
    """
    自動計算 twse/tpex 處置股距離最後注意公告的交易日差 (T–N)
    並更新至 notice_dt 欄位
    """

    punish_apiNames = ["上市公布處置有價證券", "上櫃處置有價證券資訊"]

    # 取得交易日曆索引（timestamp 版）
    trading_idx = build_trading_index()

    for punish_apiName in punish_apiNames:
        punish_apiInfo = utils.get_api_info(punish_apiName)
        punish_table = punish_apiInfo["storage_table"].iloc[0]
        punish_time_col = punish_apiInfo["time_col"].iloc[0]
        type = punish_apiInfo["type"].iloc[0].lower()

        print(f"\n🔹 處理資料表：{punish_table}")

        # 搜尋 notice 對應表
        if type == "twse":
            notice_apiName = "上市公布注意有價證券資訊"
        else:
            notice_apiName = "上櫃公布注意有價證券資訊"

        notice_apiInfo = utils.get_api_info(notice_apiName)
        notice_table = notice_apiInfo["storage_table"].iloc[0]
        notice_time_col = notice_apiInfo["time_col"].iloc[0]

        punish_ts_col = punish_time_col + "_ts"
        notice_ts_col = notice_time_col + "_ts"

        # === 讀取處置與注意資料 ===
        df_punish = db.query_to_df(
            f"SELECT id, 證券代號, last_notice, {punish_ts_col} AS punish_ts FROM {punish_table}"
        )
        df_notice = db.query_to_df(
            f"SELECT id, {notice_ts_col} AS notice_ts FROM {notice_table}"
        )

        # 建立 notice_id → notice_ts 對照表
        notice_map = dict(zip(df_notice["id"], df_notice["notice_ts"]))
        df_punish["notice_ts"] = df_punish["last_notice"].map(notice_map)

        # 正規化到「當日 00:00」
        df_punish["punish_day_ts"] = to_day_ts(df_punish["punish_ts"])
        df_punish["notice_day_ts"] = to_day_ts(df_punish["notice_ts"])

        # === 計算交易日差 ===
        def calc_t_minus(row):
            try:
                p = int(row["punish_day_ts"])
                n = int(row["notice_day_ts"])
                ip = trading_idx.get(p)
                in_ = trading_idx.get(n)
                if ip is None or in_ is None:
                    return None
                diff = ip - in_
                return f"T-{diff}" if diff >= 0 else None
            except Exception:
                return None

        df_punish["notice_dt"] = df_punish.apply(calc_t_minus, axis=1)

        # === 批次更新資料庫 ===
        updates = [
            (r["notice_dt"], int(r["id"]))
            for _, r in df_punish.iterrows()
            if pd.notna(r["notice_dt"])
        ]
        if updates:
            sql = f"UPDATE {punish_table} SET notice_dt = ? WHERE id = ?"
            affected = db.execute_sql(sql, updates)
            print(f"✅ 已更新 {affected} 筆 notice_dt")
        else:
            print("⚠️ 無可更新資料")

    print("\n🎯 全部處置表更新完成！")
    
def divideAttentionLawSrc():
    apiNames = ["上市公布注意有價證券資訊", "上櫃公布注意有價證券資訊"]
    
    for apiName in apiNames:
        apiInfo = utils.get_api_info(apiName)
        table = apiInfo["storage_table"].iloc[0]
        type = apiInfo["type"].iloc[0].lower()
        time_col = apiInfo["time_col"].iloc[0]
        
        sql = f"SELECT * FROM {table}"
        sql += f" WHERE law_src IS NOT NULL AND law_src <> ''"
        sql += f" AND id NOT IN (SELECT DISTINCT(target_id) FROM addition_info WHERE target_table = '{table}')"
        sql += f" ORDER BY id"
        df = db.query_to_df(sql)
        if df.empty:
            continue
        
        ele_base = AddInfo()
        ele_base.tag = "stock_notice_law_src"
        ele_base.target_table = table       
        ele_base.col_name = "law_src" 
        ele_base.val_type = "str"
        
        total_insert = 0
        reportCnt = 100        
        for idx, row in enumerate(df.itertuples(index=True, name="notice"), 1):
            if idx % reportCnt == 1:
                print(f"***開始處理第 {idx} 筆資料...")
                
            # 分析law_src
            law_srcs = row.law_src.split(",")
            # print(law_srcs) 
            
            add_vals = []
            sort = 0
            for law_src in law_srcs:
                sort = sort + 1
                ele = copy.deepcopy(ele_base)
                ele.target_id = row.id
                ele.col_val = law_src
                ele.memo = sort
                add_vals.append(ele)
            
            insert_cnt = insert_addition_info(add_vals)
            total_insert += insert_cnt
            # sys.exit()
            
        print("total_insert", total_insert)
    return

### 寫入 Relation
def writein_relation():
    """
    將處置公告(punish)和注意公告(notice)建立關聯
    修正版：
    - 不限制距離天數，保留所有可能對應 notice
    - 不刪除舊資料，允許多批 notice 對應同一 punish
    - 支援 TWSE / TPEX
    """
    table = "relation_punish_notice"
    insert_cols = ["type", "punish_id", "notice_id"]

    apiNames = ["上市公布處置有價證券", "上櫃處置有價證券資訊"]

    for apiName in apiNames:
        print("**開始處理：", apiName)

        punish_apiInfo = utils.get_api_info(apiName)
        punish_table = punish_apiInfo["storage_table"].iloc[0]
        type = punish_apiInfo["type"].iloc[0].lower()
        punish_time_col = punish_apiInfo["time_col"].iloc[0]

        # 查找尚未關聯的處置公告
        sql = f"""
        SELECT *
        FROM {punish_table}
        WHERE last_notice IS NULL OR notice_cnt IS NULL
        ORDER BY {punish_time_col}_ts DESC
        """
        df_punishes = db.query_to_df(sql)
        if df_punishes.empty:
            continue

        total_insert = 0
        total_update = 0
        reportCnt = 100

        for idx, row_punish in enumerate(df_punishes.itertuples(index=True, name="punish"), 1):
            if idx % reportCnt == 1:
                print(f"***開始處理第 {idx} 筆資料...")

            # 依交易所選擇對應 notice API
            match type:
                case "twse":
                    notice_apiName = "上市公布注意有價證券資訊"
                case "tpex":
                    notice_apiName = "上櫃公布注意有價證券資訊"
                case _:
                    print(f"***未知交易所類型：{type}")
                    continue

            notice_apiInfo = utils.get_api_info(notice_apiName)
            notice_table = notice_apiInfo["storage_table"].iloc[0]
            notice_time_col = notice_apiInfo["time_col"].iloc[0]

            punish_date_ts = getattr(row_punish, punish_time_col + "_ts")

            # 🔹 撈取所有該證券的 notice，無時間限制
            sql = f"""
            SELECT *
            FROM {notice_table}
            WHERE 證券代號 = (
                SELECT 證券代號
                FROM {punish_table}
                WHERE id+0 = {row_punish.id}
            )
            ORDER BY {notice_time_col}_ts DESC
            """
            df_notices = db.query_to_df(sql)

            if df_notices.empty:
                print("*** 找不到注意股資料", sql)
                continue

            insert_vals = []

            for row_notice in df_notices.itertuples(index=True, name="notice"):
                notice_date_ts = getattr(row_notice, notice_time_col + "_ts")

                # 如果需要，可以加額外過濾條件，例如：
                # notice_date_ts <= punish_date_ts
                # 現在保留所有 notice
                insert_vals.append([type, row_punish.id, row_notice.id])

            if len(insert_vals) == 0:
                continue

            # 🔹 批次寫入 relation table
            sql_insert = f"""
            INSERT OR REPLACE INTO {table}
                ({",".join(insert_cols)})
            VALUES ({", ".join(["?"] * len(insert_cols))})
            """
            insert_cnt = db.execute_sql(sql_insert, insert_vals)
            total_insert += insert_cnt

            # 🔹 更新 punish table，last_notice 使用最接近處置公告的 notice
            sorted_insert = sorted(insert_vals, key=lambda x: getattr(df_notices[df_notices.id == x[2]].iloc[0], notice_time_col + "_ts"), reverse=True)
            fst_notice_id = sorted_insert[0][2]

            sql_update = f"""
            UPDATE {punish_table}
            SET last_notice = {fst_notice_id},
                notice_cnt = {len(insert_vals)}
            WHERE id+0 = {row_punish.id}
            """
            update_cnt = db.execute_sql(sql_update)
            total_update += update_cnt

        print(f"total_update={total_update}, total_insert={total_insert}")

    print("✅ 全部處理完成")
    return

def writein_relation2():
    table = "relation_punish_notice"
    insert_cols = ["type", "punish_id", "notice_id"]

    apiNames = ["上市公布處置有價證券", "上櫃處置有價證券資訊"]

    for apiName in apiNames:
        print("**開始處理：", apiName)

        punish_apiInfo = utils.get_api_info(apiName)
        punish_table = punish_apiInfo["storage_table"].iloc[0]
        type = punish_apiInfo["type"].iloc[0].lower()
        punish_time_col = punish_apiInfo["time_col"].iloc[0]

        # 找出尚未關聯注意股的處置公告
        sql = f"""
        SELECT COUNT(*) AS cnt
        FROM {punish_table}
        WHERE last_notice IS NULL OR notice_cnt IS NULL
        """
        totalCnt = db.query_single_value(sql)
        print("totalCnt =", int(totalCnt))

        if totalCnt < 1:
            continue

        sql = f"""
        SELECT *
        FROM {punish_table}
        WHERE last_notice IS NULL OR notice_cnt IS NULL
        ORDER BY {punish_time_col}_ts DESC
        """
        df_punishes = db.query_to_df(sql)
        if df_punishes.empty:
            continue

        total_insert = 0
        total_update = 0
        reportCnt = 100

        for idx, row_punish in enumerate(df_punishes.itertuples(index=True, name="punish"), 1):
            if idx % reportCnt == 1:
                print(f"***開始處理第 {idx} 筆資料...")

            # 依交易所切換對應注意 API
            match type:
                case "twse":
                    notice_apiName = "上市公布注意有價證券資訊"
                case "tpex":
                    notice_apiName = "上櫃公布注意有價證券資訊"
                case _:
                    print(f"***未知交易所類型：{type}")
                    continue

            notice_apiInfo = utils.get_api_info(notice_apiName)
            notice_table = notice_apiInfo["storage_table"].iloc[0]
            notice_time_col = notice_apiInfo["time_col"].iloc[0]

            punish_date_ts = getattr(row_punish, punish_time_col + "_ts")

            # 🔹 限制在處置公告前 14 天內的注意資料
            sql = f"""
            SELECT *
            FROM {notice_table}
            WHERE 證券代號 = (
                SELECT 證券代號
                FROM {punish_table}
                WHERE id+0 = {row_punish.id}
            )
              AND {notice_time_col}_ts BETWEEN ({punish_date_ts} - 86400*14) AND {punish_date_ts}
            ORDER BY {notice_time_col}_ts DESC
            """
            df_notices = db.query_to_df(sql)

            if df_notices.empty:
                print("*** 找不到注意股資料", sql)
                continue

            insert_vals = []
            previous_notice_date_ts = None

            for row_notice in df_notices.itertuples(index=True, name="notice"):
                notice_date_ts = getattr(row_notice, notice_time_col + "_ts")

                # 距離處置超過 7 天就跳過（但不中斷）
                if (punish_date_ts - notice_date_ts) > 86400 * 7:
                    continue

                # 若與上一筆注意公告間隔太久，也跳過
                if previous_notice_date_ts and (previous_notice_date_ts - notice_date_ts) > 86400 * 5:
                    continue

                insert_vals.append([type, row_punish.id, row_notice.id])
                previous_notice_date_ts = notice_date_ts

            if len(insert_vals) == 0:
                continue

            # 🔹 清空舊關聯再重建，避免舊資料殘留
            db.execute_sql(f"DELETE FROM {table} WHERE punish_id = {row_punish.id}")

            # 🔹 寫入關聯表
            sql_insert = f"""
            INSERT OR REPLACE INTO {table}
                ({",".join(insert_cols)})
            VALUES ({", ".join(["?"] * len(insert_cols))})
            """
            insert_cnt = db.execute_sql(sql_insert, insert_vals)
            total_insert += insert_cnt

            # 🔹 更新 punish table 的 last_notice 與 notice_cnt
            fst_notice_id = insert_vals[-1][2]  # 最接近處置日的那筆
            sql_update = f"""
            UPDATE {punish_table}
            SET last_notice = {fst_notice_id},
                notice_cnt = {len(insert_vals)}
            WHERE id+0 = {row_punish.id}
            """
            update_cnt = db.execute_sql(sql_update)
            total_update += update_cnt

        print(f"total_update={total_update}, total_insert={total_insert}")

    print("✅ 全部處理完成")
    return

def writein_relation_old():
    table = "relation_punish_notice"
    insert_cols = [
        "type", 
        "punish_id",
        "notice_id"
    ]
    
    apiNames = ["上市公布處置有價證券", "上櫃處置有價證券資訊"]
    for apiName in apiNames:
        print("**開始處理：", apiName)
        punish_apiInfo = utils.get_api_info(apiName)
        punish_table = punish_apiInfo["storage_table"].iloc[0]
        type = punish_apiInfo["type"].iloc[0].lower()
        punish_time_col = punish_apiInfo["time_col"].iloc[0]
        
        sql = f"SELECT COUNT(*) AS cnt FROM {punish_table}"
        sql += f" WHERE last_notice IS NULL OR notice_cnt IS NULL"
        
        totalCnt = db.query_single_value(sql)
        print("totalCnt=", int(totalCnt))
        
        if totalCnt < 1:
            continue        
        
        sql = f"SELECT * FROM {punish_table}"
        sql += f" WHERE last_notice IS NULL OR notice_cnt IS NULL"
        sql += f" ORDER BY {punish_time_col}_ts DESC"
        df_punishes = db.query_to_df(sql)
        # print("sql=", sql)
        # print(df_punishes.head(1))
        if df_punishes.empty:
            continue
        
        ## 遍歷資料
        idx = 0
        total_insert = 0
        total_update = 0
        reportCnt = 100
        for row_punish in df_punishes.itertuples(index=True, name="punish"): 
            idx += 1  
            if (idx % reportCnt == 1):
                print(f"***開始處理第{idx}筆資料...")
                
            notice_apiName = ""
            match type:
                case "twse":
                    notice_apiName = "上市公布注意有價證券資訊"
                case "tpex":
                    notice_apiName = "上櫃公布注意有價證券資訊"
            notice_apiInfo = utils.get_api_info(notice_apiName)
            notice_table = notice_apiInfo["storage_table"].iloc[0]
            notice_time_col = notice_apiInfo["time_col"].iloc[0]
            
            ### 搜尋可能關聯的注意股名單
            sql = f"SELECT * FROM {notice_table}"
            sql += f" WHERE 證券代號 = (SELECT 證券代號 FROM {punish_table} WHERE id+0 = {row_punish.id})"
            sql += f" AND {notice_time_col}_ts <= (SELECT {punish_time_col}_ts FROM {punish_table} WHERE id+0 = {row_punish.id})"
            sql += f" ORDER BY {notice_time_col}_ts DESC"
            
            df_notices = db.query_to_df(sql)
            # print("sql=", sql)
            # print(df_target.head(1))
            
            if df_notices.empty:
                print("*** 找不到注意股資料", sql)
                continue
        
            punish_date_ts = getattr(row_punish, punish_time_col + "_ts")
            insert_vals = []
            previous_notice_date_ts = None
            notice_idx = 0
            fst_notice_id = None            
            for row_notice in df_notices.itertuples(index=True, name="notice"): 
                notice_idx += 1
                notice_date_ts = getattr(row_notice, notice_time_col + "_ts")
                if notice_idx == 1:                        
                    if (punish_date_ts - notice_date_ts) > 86400*3 :
                        break # 跳出此批注意股
                    fst_notice_id = row_notice.id                    
                else:
                    if (previous_notice_date_ts - notice_date_ts) > 86400*4 :
                        break # 跳出此批注意股
                previous_notice_date_ts = notice_date_ts
                
                try:                            
                    insert_vals.append([
                        type,
                        row_punish.id,
                        row_notice.id
                    ])
                except:
                    print("***Data write in error：", row_notice)
                    continue
                
            if len(insert_vals) == 0:
                continue        
            
            ### 插入relation table
            sql = f"""
            INSERT OR REPLACE INTO {table} 
                ({",".join(insert_cols)})
            VALUES 
                ({", ".join(["?"] * len(insert_cols))})
            """
            insert_cnt =  db.execute_sql(sql, insert_vals)
            if (insert_cnt > 0):
                total_insert += insert_cnt
            else:
                print("***Relation table 寫入失敗", sql)
            
            ### 更新punish table
            sql = f"""
            UPDATE {punish_table} 
                SET last_notice = {fst_notice_id}, notice_cnt = {len(insert_vals)}
            WHERE id+0 = {row_punish.id}
            """
            update_cnt =  db.execute_sql(sql)
            if (update_cnt > 0):
                total_update += update_cnt
            else:
                print("***Punish table 更新失敗", sql, row_punish)
        
        print("total_update", total_update)
        print("total_insert", total_insert)
    return 

def ana_punish_content(type, row):
    result = None
    match type.lower():
        case 'twse':
            text = row.處置內容
            # １處置原因：該有價證券之交易，連續三個營業日達本公司「公布注意交易資訊」標準。
            match_reason = re.search(r'１處置原因：(.+?)２處置期間：', text, re.S)
            # ２處置期間：自民國一百十四年九月二十三日起至一百十四年十月八日﹝十個營業日，如遇：ａ有價證券最後交易日在處置期間，僅處置至最後交易日，ｂ有價證券停止買賣、全日暫停交易則順延執行，ｃ開休市日變動則調整處置迄日〕。
            match_period = re.search(r'２處置期間：(.+?)３處置措施：', text, re.S)
            match_measures = re.search(r'３處置措施：(.*)', text, re.S)

            reason = match_reason.group(1).strip() if match_reason else None
            period = match_period.group(1).strip() if match_period else None
            measures = match_measures.group(1).strip() if match_measures else None

            # ３處置措施：
            # ａ以人工管制之撮合終端機執行撮合作業（約每五分鐘撮合一次）。
            # ｂ投資人每日委託買賣該有價證券數量單筆達十交易單位或多筆累積達三十交易單位以上時，應就其當日已委託之買賣，向該投資人收取全部之買進價金或賣出證券。
            #ｃ信用交易部分，應收足融資自備款或融券保證金。有關信用交易了結部分，則依相關規定辦理。
            measure_a = re.search(r'ａ(.*?)(?=ｂ|$)', measures, re.S)
            measure_b = re.search(r'ｂ(.*?)(?=ｃ|$)', measures, re.S)
            measure_c = re.search(r'ｃ(.*)', measures, re.S)
            
            result = {
                "處置原因": [reason, 'str'],    
                "處置期間": [period, 'str'],
                "處置措施_a": [measure_a.group(1).strip() if measure_a else None, 'str'],
                "處置措施_b": [measure_b.group(1).strip() if measure_b else None, 'str'],
                "處置措施_c": [measure_c.group(1).strip() if measure_c else None, 'str'],
            }
            
        case 'tpex':
            text = row.處置內容
            
            # OK
            def extract_recent_days(text: str):
                """擷取『最近XX個營業日內曾發布處置』"""
                m = re.search(r"最近(\d+)個營業日內曾發布處置", text)
                if not m:
                    return None
                return {'發布處置_最近n日內': [int(m.group(1)), 'int']}

            # OK
            def extract_attention_trigger(text: str):
                """
                解析完整句型：
                『因連續x個營業日達本中心作業要點第y條第z項第k款經本中心公布注意交易資訊』
                回傳 dict：
                    {
                    "注意公告_連續觸發_天數": x,
                    "注意公告_連續觸發_條項款": "000y000z000k"
                    }
                若找不到完整句型則回傳 None
                """
                pattern = (
                    r"連續(\d+)個營業日達本中心作業要點"
                    r"第([一二三四五六七八九十百千零0-9０-９]+)條"
                    r"第([一二三四五六七八九十百千零0-9０-９]+)項"
                    r"第([一二三四五六七八九十百千零0-9０-９]+)款"
                    r"經本中心公布注意交易資訊"
                )

                m = re.search(pattern, text)
                if not m:
                    return None  # 沒有完整結構就跳過

                n_days = int(m.group(1))
                t = utils.chinese_to_int(m.group(2))
                i = utils.chinese_to_int(m.group(3))
                k = utils.chinese_to_int(m.group(4))
                clause_code = f"{t:04d}{i:04d}{k:04d}"

                return {
                    "注意公告_連續觸發_天數": [n_days, 'int'],
                    "注意公告_連續觸發_條項款": [clause_code, 'str'],
                }

            # OK
            def extract_interval(text: str):
                """擷取『約每n分鐘撮合一次』"""
                m = re.search(r"約每([一二三四五六七八九十百千零0-9０-９]+)分鐘撮合一次", text)
                if not m:
                    return None
                return {
                    "撮合頻率_n分一次": [int(m.group(1)), 'int']
                }
            
            # OK
            def parse_recent_days_notice(text: str):
                """
                解析「最近X個營業日內有Y個營業日經本中心公布注意交易資訊」
                回傳 {
                    "注意公告_近日多次_n個營業日": X,Y,
                    "注意公告_近日多次_次數":                    
                    }
                """
                pattern = r"最近(\d+)個營業日內有(\d+)個營業日經本中心公布注意交易資訊"
                m = re.search(pattern, text)
                if not m:
                    return None
                return {
                    "注意公告_近日多次_n個營業日": [int(m.group(1)), 'int'],
                    "注意公告_近日多次_次數": [int(m.group(2)), 'int']
                }
            
            # OK
            def parse_consecutive_days_notice(text: str):
                """
                解析「連續X個營業日經本中心公布注意交易資訊」
                回傳 {'注意公告_連續觸發_天數': X}
                """
                pattern = r"連續(\d+)個營業日經本中心公布注意交易資訊"
                m = re.search(pattern, text)
                if not m:
                    return None
                return {"注意公告_連續觸發_天數": [int(m.group(1)), 'int']}
            
            def parse_recent_rule_trigger(text: str):
                """
                解析：
                「最近X個營業日曾達本中心作業要點第x條第y項第z款經本中心公布注意交易資訊」

                回傳：
                {
                "注意公告_近日曾達_n個營業日": X,
                "注意公告_近日曾達_條項款": "<條(4位)><項(4位)><款(4位)>"
                }
                若找不到完整句型回傳 None。
                """
                pattern = (
                    r"最近(\d+)個營業日曾達本中心作業要點"
                    r"第([一二三四五六七八九十百千零0-9０-９]+)條"
                    r"第([一二三四五六七八九十百千零0-9０-９]+)項"
                    r"第([一二三四五六七八九十百千零0-9０-９]+)款"
                    r"經本中心公[布告]注意交易資訊"
                )

                m = re.search(pattern, text)
                if not m:
                    return None

                obs_days = int(m.group(1))

                ch_t = m.group(2)
                ch_i = m.group(3)
                ch_k = m.group(4)

                t = utils.chinese_to_int(ch_t)
                i = utils.chinese_to_int(ch_i)
                k = utils.chinese_to_int(ch_k)

                if t is None or i is None or k is None:
                    return None

                clause_code = f"{t:04d}{i:04d}{k:04d}"

                return {
                    "注意公告_近日曾達_n個營業日": [obs_days, 'int'],
                    "注意公告_近日曾達_條項款": [clause_code, 'str']
                }
            
            fun_list = [extract_recent_days, extract_attention_trigger, extract_interval, parse_recent_days_notice, parse_consecutive_days_notice, parse_recent_rule_trigger]
            
            result = {}
            for fun in fun_list:
                feature = fun(text)
                if feature is None:
                    continue
                result.update(feature)
    
    return result

### 對處置股的資料進行各種處理
def handle_punish():    
    # apiNames = ["上市公布處置有價證券", "上櫃處置有價證券資訊"]
    apiNames = ["上櫃處置有價證券資訊"]
    
    tag = "stock_punish"
    for apiName in apiNames:
        print("**開始處理：", apiName)
        apiInfo = utils.get_api_info(apiName)
        table = apiInfo["storage_table"].iloc[0]
        type = apiInfo["type"].iloc[0].lower()
        time_col = apiInfo["time_col"].iloc[0]
        
        sql = f"SELECT COUNT(*) AS cnt FROM {table}"
        sql += f" WHERE law_src IS NULL or TRIM(law_src) = ''"
        if type == 'tpex':
            # 可轉債股票不是特定關係戶買不到，這邊略過
            sql += " AND 處置內容 NOT LIKE '%公司債%'"       
        
        totalCnt = db.query_single_value(sql)
        print("totalCnt=", int(totalCnt))
        
        if totalCnt < 1:
            continue
        
            
        sql = f"SELECT * FROM {table}"
        sql += f" WHERE law_src IS NULL or TRIM(law_src) = ''"
        if type == 'tpex':
            # 可轉債股票不是特定關係戶買不到，這邊略過
            sql += " AND 處置內容 NOT LIKE '%公司債%'"       
        sql += f" ORDER BY {time_col}_ts DESC"
        df_target = db.query_to_df(sql)
        # print("sql=", sql)
        # print(df_target.head(1))
        if df_target.empty:
            continue
        
        total_insert = 0
        total_update = 0
        
        ## 遍歷資料
        idx = 0
        reportCnt = 100
        
        for row in df_target.itertuples(index=True, name="MyRow"): 
            idx += 1  
            if (idx % reportCnt == 1):
                print(f"***開始處理第{idx}筆資料...")

            ele_base = AddInfo()
            ele_base.tag = tag
            ele_base.target_table = table
            ele_base.target_id = row.id
            
            ### 處理處置內容
            punish_content_obj = ana_punish_content(type, row)
            add_vals = []
            # print("punish_content_obj", punish_content_obj)
            stock_name = row.證券名稱
            if type == 'tpex':
                stock_name = re.sub(r"\(.*\)$", "", stock_name)
            for col_name, col_val in punish_content_obj.items():
                if col_val[0] is None:
                    continue
                ele = copy.deepcopy(ele_base)
                ele.col_name = col_name.strip()
                ele.col_val = col_val[0]
                ele.val_type = col_val[1].strip()                    
                ele.memo = f"[{row.證券代號}_{stock_name}]{getattr(row, time_col)}"
                add_vals.append(ele)
            
            insert_cnt = insert_addition_info(add_vals)
            total_insert += insert_cnt
            
        print("total_insert", total_insert)
        print("total_update", total_update)
    return


def handle_twse_punish_from_addInfo():
    print()
    
    

class AddInfo:
    def __init__(self):
        self.id = None
        ###
        self.tag = None
        self.target_table = None
        self.target_id = None
        self.col_name = None
        self.col_val = None
        self.val_type = None
        self.memo = None
        
    def output_list(self) -> list:
        data_list = [
            self.tag,
            self.target_table,
            self.target_id,
            self.col_name,
            self.col_val,
            self.val_type,
            self.memo
        ]
        if self.id is not None:
            data_list.insert(0, self.id)
        return data_list

def insert_addition_info(datas: list) -> int:
    table = "addition_info"
    insert_cols = [
        "tag",
        "target_table",
        "target_id",
        "col_name",
        "col_val",
        "val_type",
        "memo"
    ]

    # 統一轉成 list[tuple]
    insert_vals = []
    for oneData in datas:
        if isinstance(oneData, AddInfo):
            insert_vals.append(oneData.output_list())
        elif isinstance(oneData, (list, tuple)):
            insert_vals.append(tuple(oneData))
        else:
            raise TypeError(f"Unsupported data type: {type(oneData)}")
    if not insert_vals:
        return 0

    sql = f"INSERT OR IGNORE INTO {table}"
    sql += f"({",".join(insert_cols)})"
    sql += f" VALUES "
    sql += f"({", ".join(["?"] * len(insert_cols))})"

    insert_cnt = db.execute_sql(sql, insert_vals)
    # if insert_cnt == 0:
    #     print("***AddtionInfo table 未寫入資料", sql)
    if insert_cnt < 0:
        print("***AddtionInfo table 寫入失敗", sql)

    return insert_cnt

### 把注意股的"觸發法條(law_src)"擷取出來
def handle_notice():    
    apiNames = ["上市公布注意有價證券資訊", "上櫃公布注意有價證券資訊"]
    
    for apiName in apiNames:
        print("**開始處理：", apiName)
        apiInfo = utils.get_api_info(apiName)
        table = apiInfo["storage_table"].iloc[0]
        type = apiInfo["type"].iloc[0].lower()
        time_col = apiInfo["time_col"].iloc[0]
        
        sql = f"SELECT COUNT(*) AS cnt FROM {table}"
        sql += f" WHERE law_src IS NULL or TRIM(law_src) = ''"
        
        totalCnt = db.query_single_value(sql)
        print("totalCnt=", int(totalCnt))
        
        if totalCnt < 1:
            continue
        
        total_update = 0
        
        
        sql = f"SELECT * FROM {table}"
        sql += f" WHERE law_src IS NULL or TRIM(law_src) = ''"
        if type == 'tpex':
            # 可轉債股票不是特定關係戶買不到，這邊略過
            sql += " AND 處置內容 NOT LIKE '%公司債%'"        
        sql += f" ORDER BY {time_col}_ts DESC"
        df_target = db.query_to_df(sql)
        # print("sql=", sql)
        # print(df_target.head(1))
        if df_target.empty:
            continue
        
        ## 遍歷資料
        idx = 0
        reportCnt = 100
        for row in df_target.itertuples(index=True, name="MyRow"): 
            idx += 1  
            if (idx % reportCnt == 1):
                print(f"***開始處理第{idx}筆資料...")
            ### 寫入law_src欄位                
            regex = r"﹝(.*?)﹞"
            match type:
                case "twse":
                    regex = r"﹝(.*?)﹞"
                case "tpex":
                    regex = r"[（(](第.*?)[）)]" 
                    
            matches = re.findall(regex, row.注意交易資訊)
            if matches is None:
                print("**未寫入：", row.id, row.證券代號, row.證券名稱)
                continue
            
            updateVal = ""
            for m in matches:
                # print(m)               
                if updateVal != "":
                    updateVal += "," 
                    
                updateVal += "".join(m)  
            
            if updateVal.strip() == "":
                print("**未寫入：", row.id, row.證券代號, row.證券名稱)
                continue
            
            sql = f"""
                UPDATE {table} 
                    SET law_src = '{updateVal}'
                    WHERE id+0 = {row.id}                 
                """                            
            exeResult = db.execute_sql(sql)
            # print(row.id, row.證券代號, row.證券名稱)
            # print("exeResult=", exeResult, "sql=", sql)
            total_update += exeResult
            
        print("total_update", total_update)
    return




# if __name__ == "__main__": 