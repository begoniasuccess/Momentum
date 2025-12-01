import sys, os
sys.path.append(os.path.dirname(__file__))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from common import utils, db
from module import finMind
import re
from datetime import datetime, date
import pytz
import re
from typing import List, Optional, Iterable
from datetime import datetime
import time
import numpy as np
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    log_loss,
)
from lightgbm import LGBMClassifier

TZ = pytz.timezone("Asia/Taipei")

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

def fix_tpex_law_src(batch_size: int = 1000):
    """
    🚑 自動修復 tpex_bulletin_attention 的 law_src 欄位
    - 根據「注意交易資訊」內容重新解析出「第X款」
    - 若不同於舊值則覆蓋更新
    """
    table = "tpex_bulletin_attention"
    offset = 0
    total_fixed = 0

    pattern = re.compile(r"第[一二三四五六七八九十]+款")

    while True:
        sql = f"""
        SELECT id, 注意交易資訊, law_src
        FROM {table}
        ORDER BY id ASC
        LIMIT {batch_size} OFFSET {offset}
        """
        df = db.query_to_df(sql)
        if df.empty:
            print("✅ 已無更多資料，停止檢查")
            break

        updates = []
        for _, row in df.iterrows():
            info = str(row["注意交易資訊"]) if row["注意交易資訊"] else ""
            matches = pattern.findall(info)
            if not matches:
                continue

            new_law_src = ",".join(sorted(set(matches)))  # 去重+排序
            old_law_src = str(row["law_src"]) if row["law_src"] else ""

            if new_law_src != old_law_src:
                updates.append((new_law_src, row["id"]))

        if updates:
            db.execute_sql(f"UPDATE {table} SET law_src = ? WHERE id = ?", updates)
            total_fixed += len(updates)
            print(f"🩹 批次修正 {len(updates)} 筆（OFFSET={offset}）")

        offset += len(df)

    print(f"🎯 修正完成，共更新 {total_fixed} 筆")

import re
from typing import List, Optional
from datetime import datetime

BR_SPLIT = re.compile(r"<br\s*/?>", re.IGNORECASE)
LAW_PAT = re.compile(r"第[一二三四五六七八九十]+款")

def _split_paras(text: str) -> List[str]:
    if not text:
        return []
    parts = [p.strip() for p in BR_SPLIT.split(text)]
    return [p for p in parts if p != ""]  # 保留非空段

def _extract_first_law_or_empty(segment: str) -> str:
    m = LAW_PAT.search(segment or "")
    return m.group(0) if m else ""

def _get_ai_law_seq_by_memo(target_id: int) -> List[str]:
    sql = """
        SELECT col_val
        FROM addition_info
        WHERE tag='stock_notice_law_src'
          AND target_table='tpex_bulletin_attention'
          AND col_name='law_src'
          AND target_id+0=?
        ORDER BY CAST(memo AS INTEGER)
    """
    df = db.query_to_df(sql, (target_id,))
    return df["col_val"].astype(str).tolist() if not df.empty else []

def _delete_ai_law_rows(target_ids: List[int]) -> int:
    if not target_ids:
        return 0
    params = [(tid,) for tid in target_ids]
    sql = """
        DELETE FROM addition_info
        WHERE tag='stock_notice_law_src'
          AND target_table='tpex_bulletin_attention'
          AND col_name='law_src'
          AND target_id+0=?
    """
    return db.execute_sql(sql, params)

def _build_ai_law_rows(target_id: int, law_seq_per_para: List[str]) -> List[tuple]:
    rows = []
    for i, law in enumerate(law_seq_per_para, start=1):
        rows.append((
            "stock_notice_law_src",        # tag
            "tpex_bulletin_attention",     # target_table
            str(target_id),                # target_id（沿用字串）
            "law_src",                     # col_name
            law,                           # col_val（可能為 ""）
            "str",                         # val_type
            str(i),                        # memo（逐段對齊）
        ))
    return rows

def fix_tpex_law_src_and_rebuild_ai_strict(
    batch_size: int = 1000,
    ids: Optional[List[int]] = None,
    rewrite_table_law_src: bool = True,
    dry_run: bool = False,
    verbose: bool = True,
):
    """
    嚴格版：
    - 以 <br> 分段，逐段擷取第一個「第X款」，允許重複、保留順序。
    - 表欄位 law_src = 非空段的條款以逗號串接（保留重複與順序）。
    - addition_info 的 law_src 每段寫一筆（段內無條款則寫空字串）以確保 memo 與段落一一對齊。
    """
    t0 = datetime.now()
    scanned = 0
    upd_table = 0
    del_ai = 0
    ins_ai = 0

    # 取來源
    if ids:
        placeholders = ",".join(["?"] * len(ids))
        src = db.query_to_df(f"""
            SELECT id, 注意交易資訊, law_src
            FROM tpex_bulletin_attention
            WHERE id+0 IN ({placeholders})
            ORDER BY id+0 ASC
        """, tuple(ids))
        batches = [src]
    else:
        batches = []
        offset = 0
        while True:
            df = db.query_to_df(f"""
                SELECT id, 注意交易資訊, law_src
                FROM tpex_bulletin_attention
                ORDER BY id+0 ASC
                LIMIT {batch_size} OFFSET {offset}
            """)
            if df.empty:
                break
            batches.append(df)
            offset += len(df)

    for bidx, df in enumerate(batches, start=1):
        if df.empty: 
            continue
        scanned += len(df)

        table_update_params = []
        delete_ids = []
        ai_insert_rows = []

        for _, row in df.iterrows():
            tid = int(row["id"])
            info = str(row["注意交易資訊"]) if row["注意交易資訊"] else ""

            # 逐段解析
            paras = _split_paras(info)  # 段落列表（已去除空段）
            # 每段抓第一個條款（允許為空字串）
            laws_per_para = [_extract_first_law_or_empty(seg) for seg in paras]

            # 表用值：只串接非空的條款，保留重複與順序
            table_law_str = ",".join([x for x in laws_per_para if x])

            # 需要更新表？
            need_upd_table = rewrite_table_law_src and ((row["law_src"] or "") != table_law_str)

            # 需要重建 AI？
            current_ai = _get_ai_law_seq_by_memo(tid)
            need_rebuild_ai = (current_ai != laws_per_para)

            if not (need_upd_table or need_rebuild_ai):
                continue

            if need_upd_table:
                table_update_params.append((table_law_str, tid))

            if need_rebuild_ai:
                delete_ids.append(tid)
                ai_insert_rows.extend(_build_ai_law_rows(tid, laws_per_para))

        if verbose:
            print(f"📦 批次 {bidx}: 掃描 {len(df)} 筆，"
                  f"待更新表內 law_src={len(table_update_params)}，"
                  f"待重建 AI 明細（逐段）={len(delete_ids)} 筆")

        if not dry_run:
            if table_update_params:
                cnt = db.execute_sql(
                    "UPDATE tpex_bulletin_attention SET law_src = ? WHERE id+0 = ?",
                    table_update_params
                )
                if cnt > 0: upd_table += cnt

            if delete_ids:
                cnt_del = _delete_ai_law_rows(delete_ids)
                if cnt_del > 0: del_ai += cnt_del

            if ai_insert_rows:
                cnt_ins = insert_addition_info(ai_insert_rows)
                if cnt_ins > 0: ins_ai += cnt_ins

    stats = {
        "scanned": scanned,
        "table_law_src_updated": upd_table,
        "ai_law_rows_deleted": del_ai,
        "ai_law_rows_inserted": ins_ai,
        "elapsed_sec": (datetime.now() - t0).total_seconds(),
        "dry_run": dry_run
    }
    if verbose:
        print("🎯 完成：", stats)
    return stats

def extract_features(row):
    law = row["law_src"]
    text = row["注意交易資訊"] or ""
    table = row["target_table"]  # 👈 新增這行
    feats = []

    # ---------- 第一款 ----------
    if law == "第一款":
        m = re.search(r"(漲|跌)幅達?([0-9.]+)%", text)
        if m:
            direction = 1 if m.group(1) == "漲" else -1
            key = "acc_return_pct"
            feats.append((key, float(m.group(2)) * direction, get_threshold(law, key, table)))  # ✅ 修正
        m = re.search(r"價差達新臺幣([0-9.]+)元", text)
        if m:
            key = "price_diff"
            feats.append((key, float(m.group(1)), get_threshold(law, key, table)))  # ✅ 修正

    # ---------- 第十款 ----------
    elif law == "第十款":
        vals = re.findall(r"([0-9.]+)%", text)
        if len(vals) >= 1:
            key = "turnover_6d"
            feats.append((key, float(vals[0]), get_threshold(law, key, table)))  # ✅ 修正
        if len(vals) >= 2:
            key = "turnover_today"
            feats.append((key, float(vals[1]), get_threshold(law, key, table)))  # ✅ 修正

    # ---------- 第十三款 ----------
    elif law == "第十三款":
        vals = re.findall(r"([0-9.]+)%", text)
        if len(vals) >= 1:
            key = "daytrade_ratio_6d"
            feats.append((key, float(vals[0]), get_threshold(law, key, table)))  # ✅ 修正
        if len(vals) >= 2:
            key = "daytrade_ratio_1d"
            feats.append((key, float(vals[1]), get_threshold(law, key, table)))  # ✅ 修正

    return feats

def get_market_from_table(table_name: str) -> str:
    """由表名判斷市場別 ('twse' or 'tpex')"""
    if table_name.startswith("twse_"):
        return "twse"
    elif table_name.startswith("tpex_"):
        return "tpex"
    else:
        return "unknown"

def get_threshold(law, feature_key, table_name):
    """從 law_threshold_map 查詢指定市場+條款的閾值"""
    market = get_market_from_table(table_name)
    sql = """
    SELECT threshold_value FROM law_threshold_map
    WHERE market = ? AND law_src = ? AND feature_key = ?
    """
    val = db.query_single_value(sql, (market, law, feature_key))
    return float(val) if val is not None else None

def extract_law_src_feature(batch_size=1000):
    """
    從 v_notice_law_src 提取條款特徵 → law_feature_base
    支援：
      - 批次寫入（防記憶體爆炸）
      - 進度顯示
      - 中斷續跑
    """

    # ===============================
    #  1️⃣ 建立輸出表（含 threshold_value 欄位）
    # ===============================
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS law_feature_base (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ai_key TEXT NOT NULL,
        target_table TEXT NOT NULL,
        target_id INTEGER NOT NULL,
        law_src TEXT NOT NULL,
        feature_key TEXT NOT NULL,
        feature_value REAL,
        threshold_value REAL,
        raw_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    db.execute_sql(create_table_sql)

    # ===============================
    #  2️⃣ 找出已處理過的 ai_key（續跑機制）
    # ===============================
    exist_sql = "SELECT DISTINCT ai_key FROM law_feature_base"
    exist_df = db.query_to_df(exist_sql)
    done_keys = set(exist_df["ai_key"].tolist()) if not exist_df.empty else set()
    print(f"🧩 已完成 {len(done_keys):,} 筆，將跳過這些。")

    # ===============================
    #  3️⃣ 讀取待處理資料
    # ===============================
    sql = """
    SELECT ai_key, target_table, target_id, law_src, 注意交易資訊
    FROM v_notice_law_src
    WHERE 注意交易資訊 IS NOT NULL AND TRIM(注意交易資訊) != ''
    """
    df = db.query_to_df(sql)
    df = df[~df["ai_key"].isin(done_keys)].reset_index(drop=True)
    total = len(df)
    print(f"📊 本次需處理 {total:,} 筆")

    if total == 0:
        print("✅ 無需處理，全部已完成")
        return

    # ===============================
    #  4️⃣ 初始化 SQL
    # ===============================
    insert_sql = """
    INSERT INTO law_feature_base (
        ai_key, target_table, target_id, law_src,
        feature_key, feature_value, threshold_value, raw_text
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    batch_params = []
    inserted = 0
    t0 = time.time()

    # ===============================
    #  5️⃣ 主迴圈
    # ===============================
    for idx, row in df.iterrows():
        feats = extract_features(row)
        if not feats:
            continue

        for fk, fv, thr in feats:
            batch_params.append((
                row["ai_key"],
                row["target_table"],
                row["target_id"],
                row["law_src"],
                fk,
                fv,
                thr,
                row["注意交易資訊"],
            ))

        # 批次寫入 + 印出進度
        if len(batch_params) >= batch_size:
            db.execute_sql(insert_sql, batch_params)
            inserted += len(batch_params)
            batch_params.clear()
            elapsed = time.time() - t0
            print(f"📦 已處理 {idx+1:,}/{total:,} 筆，累計寫入 {inserted:,} 筆，用時 {elapsed:.1f}s")

    # ===============================
    #  6️⃣ 寫入剩餘
    # ===============================
    if batch_params:
        db.execute_sql(insert_sql, batch_params)
        inserted += len(batch_params)

    elapsed = time.time() - t0
    print(f"✅ 全部完成，共寫入 {inserted:,} 筆，總耗時 {elapsed:.1f}s")

def find_trading_date_index(target_date, trading_dates):
    match = trading_dates.index[trading_dates["date"] == target_date]
    return match[0] if len(match) > 0 else None

### 
# 	A."law1_consecutive_days"	INTEGER,
#	B."law1to8_count_10t"	INTEGER,
#	C."law1to8_count_30t"	INTEGER,
#	D."law1to8_consecutive_days"	INTEGER,
#	E."disposal_period"	INTEGER,
#	F."disposal_times_30t"	INTEGER,
###

def calc_consecutive_days(target_laws: list[str], target_column: str):
    """
    依 target_laws 計算連續交易日，寫回 target_column 欄位。

    target_laws:
        ex: ["第一款"]
        ex: ["第一款","第二款",...,"第八款"]

    target_column:
        ex: "law1_consecutive_days"
        ex: "law1to8_consecutive_days"
    """

    # 🧹 1. 先清空欄位
    db.execute_sql(f"UPDATE notice_behavior_feature SET {target_column} = NULL")

    # 🪓 2. 非 target_laws 的資料統一設成 0
    not_like_condition = " AND ".join([f"law_src NOT LIKE '%{law}%'" for law in target_laws])

    db.execute_sql(f"""
        UPDATE notice_behavior_feature
            SET {target_column} = 0
        WHERE law_src IS NULL
            OR ({not_like_condition})
    """)

    # 📝 3. 抓出所有符合 target_laws 的資料（按股票＋時間排序）
    like_condition = " OR ".join([f"law_src LIKE '%{law}%'" for law in target_laws])

    sql = f"""
        SELECT 
            strftime('%Y-%m-%d', N.notice_dt_ts, 'unixepoch', 'localtime') AS notice_date,
            N.id, N.stock_no
        FROM notice_behavior_feature N
        WHERE {like_condition}
        ORDER BY stock_no, notice_dt_ts ASC
    """
    print("calc_consecutive_days query sql = ")
    print(sql)
    df = db.query_to_df(sql)

    # 📅 4. 準備交易日 map
    trading_dates = finMind.getTwStockTradingDates()
    trading_dates["date"] = pd.to_datetime(trading_dates["date"])
    trading_dates = trading_dates.sort_values("date")
    trading_dates["date"] = trading_dates["date"].dt.strftime("%Y-%m-%d")
    trading_dates = trading_dates.reset_index(drop=True)

    date_to_idx = {d: i for i, d in enumerate(trading_dates["date"])}

    def td_idx(d):
        return date_to_idx.get(d, None)

    # 🔁 5. 逐筆計算連續交易日
    current_stock = None
    prev_idx = None
    consec = 0
    total = len(df)

    for i, (_, row) in enumerate(df.iterrows(), start=1):

        if i % 1000 == 0:
            print(f"[{target_column}] {i}/{total}...")

        stock = row["stock_no"]
        id_ = row["id"]
        notice_date = row["notice_date"]
        idx_curr = td_idx(notice_date)

        if stock != current_stock:
            # 換股票 → 重置
            consec = 1
            current_stock = stock
        else:
            # 同股票 → 判斷交易日是否連續
            if prev_idx is None or idx_curr is None:
                consec = 1
            elif idx_curr - prev_idx == 1:
                consec += 1
            else:
                consec = 1

        prev_idx = idx_curr

        # ⬇ UPDATE 寫回欄位（此股票此紀錄的連續天數）
        db.execute_sql(f"""
            UPDATE notice_behavior_feature
                SET {target_column} = {consec}
            WHERE id = {id_}
        """)

    print(f"✔ {target_column} 計算完成")

# A."law1_consecutive_days"
def calc_law1_consecutive_days():
    calc_consecutive_days(["第一款"], "law1_consecutive_days")

# D."law1to8_consecutive_days"
def calc_law1to8_consecutive_days():
    calc_consecutive_days(
        ["第一款", "第二款", "第三款", "第四款", "第五款", "第六款", "第七款", "第八款"],
        "law1to8_consecutive_days"
    )

def calc_law1to8_count_window(window_size: int, target_column: str):

    # 1. 清空欄位
    db.execute_sql(f"UPDATE notice_behavior_feature SET {target_column} = NULL")

    # 2. 抓全部 N 資料（含非 1～8 款，後面計算時才排除）
    sql = """
        SELECT
            id,
            stock_no,
            strftime('%Y-%m-%d', notice_dt_ts, 'unixepoch', 'localtime') AS notice_date,
            law_src
        FROM notice_behavior_feature
        ORDER BY stock_no, notice_dt_ts ASC
    """
    df = db.query_to_df(sql)

    # 3. 準備交易日表（含 index）
    trading_dates = finMind.getTwStockTradingDates()
    trading_dates["date"] = pd.to_datetime(trading_dates["date"])
    trading_dates = trading_dates.sort_values("date")
    trading_dates["date"] = trading_dates["date"].dt.strftime("%Y-%m-%d")
    trading_dates = trading_dates.reset_index(drop=True)

    date_to_idx = {d: i for i, d in enumerate(trading_dates["date"])}

    def td_idx(d):      # 交易日期轉 index
        return date_to_idx.get(d, None)

    # 4. 先做出每筆資料是否屬於「第一～八款」布林欄位
    def is_law1to8(val):
        if val is None:
            return False
        return any(kw in val for kw in [
            "第一款","第二款","第三款","第四款",
            "第五款","第六款","第七款","第八款"
        ])

    df["is_law1to8"] = df["law_src"].apply(is_law1to8)

    # 5. 為每支股票做 rolling window（以交易日計算）
    stock_groups = df.groupby("stock_no")

    total = len(df)
    processed = 0

    for stock_no, g in stock_groups:

        # g: 單一股票的所有公告（按時間排序）
        dates = g["notice_date"].tolist()
        ids = g["id"].tolist()
        is_law = g["is_law1to8"].tolist()

        # 交易日 index
        idx_list = [td_idx(d) for d in dates]

        for i in range(len(dates)):
            processed += 1
            if processed % 2000 == 0:
                print(f"[{target_column}] {processed}/{total}")

            id_ = ids[i]
            curr_idx = idx_list[i]

            if curr_idx is None:
                # 日期不在交易日表（幾乎不會）
                db.execute_sql(f"""
                    UPDATE notice_behavior_feature
                        SET {target_column} = 0
                    WHERE id = {id_}
                """)
                continue

            # 計算回溯 window_size 個交易日的範圍
            min_idx = curr_idx - (window_size - 1)

            # 在 g 內所有公告逐筆檢查是否落在交易日範圍
            count = 0
            for j in range(len(dates)):
                idx_j = idx_list[j]
                if idx_j is None:
                    continue
                if idx_j >= min_idx and idx_j <= curr_idx and is_law[j]:
                    count += 1

            # update
            db.execute_sql(f"""
                UPDATE notice_behavior_feature
                    SET {target_column} = {count}
                WHERE id = {id_}
            """)

    print(f"✔ {target_column} 計算完成")

def calc_law1to8_count_10t():
    calc_law1to8_count_window(10, "law1to8_count_10t")


def calc_law1to8_count_30t():
    calc_law1to8_count_window(30, "law1to8_count_30t")

###############################################
# 民國年日期處理 & 處置期間解析
###############################################



def roc_to_ad(roc_date: str) -> str:
    """
    民國年轉西元年：'114/09/22' → '2025-09-22'
    """
    y, m, d = roc_date.split("/")
    y = int(y) + 1911
    return f"{y:04d}-{int(m):02d}-{int(d):02d}"


def parse_period(raw_period: str):
    """
    處置起迄時間格式解析 (自動處理 ～ or ~)
    """
    if raw_period is None:
        return None, None
    s = raw_period.replace("～", "~").replace(" ", "")
    start, end = s.split("~")
    return roc_to_ad(start), roc_to_ad(end)



###############################################
# 計算交易日天數版本（正確取代總日曆天數）
###############################################

def calc_business_days(start: str, end: str, trading_calendar: pd.DataFrame) -> int:
    """
    依台股交易日表計算處置期間的「營業日天數」
    """
    start = pd.to_datetime(start)
    end = pd.to_datetime(end)

    mask = (trading_calendar["date"] >= start) & (trading_calendar["date"] <= end)
    return trading_calendar.loc[mask].shape[0]



###############################################
# TWSE 更新：處置起始日 / 結束日 / 處置總天數（以營業日）
###############################################

def update_twse_disposal_periods():
    # 取得交易日列表 DF：date為 datetime64
    trading_dates = finMind.getTwStockTradingDates()
    trading_dates["date"] = pd.to_datetime(trading_dates["date"])

    sql = """
        SELECT id, "處置起迄時間" AS period
        FROM twse_announcement_punish
    """
    df = db.query_to_df(sql)

    for _, row in df.iterrows():
        id_ = row["id"]
        raw = row["period"]

        start, end = parse_period(raw)
        if not start:
            continue

        # ⚠ 重點：用交易日計算
        total_days = calc_business_days(start, end, trading_dates)

        db.execute_sql(f"""
            UPDATE twse_announcement_punish
            SET 處置起始日 = '{start}',
                處置結束日 = '{end}',
                處置總天數 = {total_days}
            WHERE id = {id_}
        """)

    print("✔ TWSE 處置期間（營業日版本）已更新")



###############################################
# TPEX 更新：處置起始日 / 結束日 / 處置總天數（以營業日）
###############################################

def update_tpex_disposal_periods():

    trading_dates = finMind.getTwStockTradingDates()
    trading_dates["date"] = pd.to_datetime(trading_dates["date"])

    sql = """
        SELECT id, "處置起訖時間" AS period
        FROM tpex_bulletin_disposal
    """
    df = db.query_to_df(sql)

    for _, row in df.iterrows():
        id_ = row["id"]
        raw = row["period"]

        start, end = parse_period(raw)
        if not start:
            continue

        total_days = calc_business_days(start, end, trading_dates)

        db.execute_sql(f"""
            UPDATE tpex_bulletin_disposal
            SET 處置起始日 = '{start}',
                處置結束日 = '{end}',
                處置總天數 = {total_days}
            WHERE id = {id_}
        """)

    print("✔ TPEX 處置期間（營業日版本）已更新")



###############################################
# 主函數：一次更新 TWSE + TPEX
###############################################

def update_all_disposal_periods():
    update_twse_disposal_periods()
    update_tpex_disposal_periods()
    print("🎉 TWSE + TPEX：處置期間（起始 / 結束 / 營業日總天數）已全部更新完畢！")

##############################################################
# STEP 1：建立統一的 disposal_events（整併 TWSE + TPEX）
##############################################################

def load_disposal_events():
    sql1 = """
        SELECT 
            "證券代號" AS stock_no,
            處置起始日 AS start_date,
            處置結束日 AS end_date,
            處置總天數 AS total_days
        FROM twse_announcement_punish
        WHERE 處置起始日 IS NOT NULL
    """
    df1 = db.query_to_df(sql1)

    sql2 = """
        SELECT 
            "證券代號" AS stock_no,
            處置起始日 AS start_date,
            處置結束日 AS end_date,
            處置總天數 AS total_days
        FROM tpex_bulletin_disposal
        WHERE 處置起始日 IS NOT NULL
    """
    df2 = db.query_to_df(sql2)

    df = pd.concat([df1, df2], ignore_index=True)

    df["start_date"] = pd.to_datetime(df["start_date"])
    df["end_date"] = pd.to_datetime(df["end_date"])
    df["total_days"] = df["total_days"].astype(int)

    return df



##############################################################
# STEP 2：填入 G: disposal_period_day_index, E: disposal_period
##############################################################

def calc_disposal_period_and_index():
    print("⏳ 計算 disposal_period / disposal_period_day_index ...")

    events = load_disposal_events()

    # 清空欄位
    db.execute_sql("UPDATE notice_behavior_feature SET disposal_period_day_index = 0")
    db.execute_sql("UPDATE notice_behavior_feature SET disposal_period = 0")

    # 取得所有公告（每天最多一筆）
    sql = """
        SELECT 
            id,
            stock_no,
            strftime('%Y-%m-%d', notice_dt_ts, 'unixepoch', 'localtime') AS notice_date
        FROM notice_behavior_feature
        ORDER BY stock_no, notice_dt_ts
    """
    df = db.query_to_df(sql)
    df["notice_date"] = pd.to_datetime(df["notice_date"])

    # 依股票分組
    for stock_no, g in df.groupby("stock_no"):
        ev = events[events["stock_no"] == stock_no]
        if ev.empty:
            continue

        for _, row in g.iterrows():
            id_ = row["id"]
            notice_date = row["notice_date"]

            # 找出公告是否落在某段處置期
            hit = ev[(ev["start_date"] <= notice_date) & (notice_date <= ev["end_date"])]

            if hit.empty:
                continue

            hit = hit.iloc[0]
            st, total = hit["start_date"], hit["total_days"]

            day_idx = (notice_date - st).days + 1

            db.execute_sql(f"""
                UPDATE notice_behavior_feature
                    SET disposal_period_day_index = {day_idx},
                        disposal_period = {total}
                WHERE id = {id_}
            """)

    print("✔ disposal_period / disposal_period_day_index  已計算完畢")



##############################################################
# STEP 3：F: disposal_times_30t（最近 30 個交易日內，被處置的次數）
##############################################################

def calc_disposal_times_30t():
    print("⏳ 計算 disposal_times_30t ...")

    # 先清空
    db.execute_sql("UPDATE notice_behavior_feature SET disposal_times_30t = 0")

    # 取得交易日曆
    trading_dates = finMind.getTwStockTradingDates()
    trading_dates["date"] = pd.to_datetime(trading_dates["date"])
    trading_dates = trading_dates.sort_values("date").reset_index(drop=True)
    date_to_idx = {d: i for i, d in enumerate(trading_dates["date"])}

    # 建立公告資料
    sql = """
        SELECT 
            id,
            stock_no,
            disposal_period_day_index,  -- >0 表示處置期內的公告
            strftime('%Y-%m-%d', notice_dt_ts, 'unixepoch', 'localtime') AS notice_date
        FROM notice_behavior_feature
        ORDER BY stock_no, notice_dt_ts
    """
    df = db.query_to_df(sql)
    df["notice_date"] = pd.to_datetime(df["notice_date"])
    df["td_idx"] = df["notice_date"].map(date_to_idx)

    # 依股票處理
    for stock_no, g in df.groupby("stock_no"):
        g = g.reset_index(drop=True)

        # 找出哪些公告是處置期紀錄（只算起始日，不算每一天）
        # 方法：disposal_period_day_index == 1 才算一個處置事件
        disposal_events = g[g["disposal_period_day_index"] == 1]

        for i, row in g.iterrows():
            id_ = row["id"]
            curr_idx = row["td_idx"]

            if curr_idx is None:
                continue

            # 最近 30 個交易日的範圍
            min_idx = curr_idx - 29

            # 在此窗口內，處置次數 = 所有「當天為處置第一天」的記錄
            count = disposal_events[
                (disposal_events["td_idx"] >= min_idx) &
                (disposal_events["td_idx"] <= curr_idx)
            ].shape[0]

            db.execute_sql(f"""
                UPDATE notice_behavior_feature
                    SET disposal_times_30t = {count}
                WHERE id = {id_}
            """)

    print("✔ disposal_times_30t 已計算完畢")

def update_rule_one_day_away_flags():
    # 先把欄位全部清空為 NULL（保持語意乾淨）
    db.execute_sql("""
        UPDATE notice_behavior_feature SET
            rule1_one_day_away = NULL,
            rule2_one_day_away = NULL,
            rule3_one_day_away = NULL,
            rule4_one_day_away = NULL,
            any_rule_one_day_away = NULL
    """)

    # Rule 1：第一款連續三天 → 臨界 = 2
    db.execute_sql("""
        UPDATE notice_behavior_feature
        SET rule1_one_day_away = 1
        WHERE disposal_period_day_index = 0
          AND law1_consecutive_days = 2
    """)

    # Rule 2：一～八款連續五天 → 臨界 = 4
    db.execute_sql("""
        UPDATE notice_behavior_feature
        SET rule2_one_day_away = 1
        WHERE disposal_period_day_index = 0
          AND law1to8_consecutive_days = 4
    """)

    # Rule 3：最近 10t 有 6 天 → 臨界 = 5
    db.execute_sql("""
        UPDATE notice_behavior_feature
        SET rule3_one_day_away = 1
        WHERE disposal_period_day_index = 0
          AND law1to8_count_10t = 5
    """)

    # Rule 4：最近 30t 有 12 天 → 臨界 = 11
    db.execute_sql("""
        UPDATE notice_behavior_feature
        SET rule4_one_day_away = 1
        WHERE disposal_period_day_index = 0
          AND law1to8_count_30t = 11
    """)

    # any_rule_one_day_away（只要任一條規則成立）
    db.execute_sql("""
        UPDATE notice_behavior_feature
        SET any_rule_one_day_away = 
            CASE
                WHEN rule1_one_day_away = 1
                  OR rule2_one_day_away = 1
                  OR rule3_one_day_away = 1
                  OR rule4_one_day_away = 1
                THEN 1
                ELSE 0
            END
    """)

    print("✔ rule1~rule4 + any_rule_one_day_away 已全部更新完畢。")

def update_will_be_disposed_tomorrow():
    print("=== 開始計算 will_be_disposed_tomorrow ===")
    sql = """
    UPDATE notice_behavior_feature
        SET will_be_disposed_tomorrow = 1
        WHERE coming_punish_interval_days = 0
    """
    
    db.execute_sql(sql)

    print("🎉 will_be_disposed_tomorrow 更新完成")


def update_rule_one_day_away_count():
    print("=== 開始計算 rule_one_day_away_count ===")
    sql = """
        UPDATE notice_behavior_feature
        SET rule_one_day_away_count = 
            IFNULL(rule1_one_day_away, 0)
            + IFNULL(rule2_one_day_away, 0)
            + IFNULL(rule3_one_day_away, 0)
            + IFNULL(rule4_one_day_away, 0)
    """    
    db.execute_sql(sql)

    print("🎉 rule_one_day_away_count 更新完成")

def train_and_update_pred_prob_disposal_lgbm():
    # --------------------------------------------------
    # 1. 讀取訓練資料：只用「臨界狀態 & 有真實標籤」的資料
    # --------------------------------------------------
    print("=== 讀取訓練資料（any_rule_one_day_away = 1 & 有 label） ===")

    train_df = db.query_to_df("""
        SELECT 
            id,
            rule1_one_day_away,
            rule2_one_day_away,
            rule3_one_day_away,
            rule4_one_day_away,
            rule_one_day_away_count,
            law1_consecutive_days,
            law1to8_consecutive_days,
            law1to8_count_10t,
            law1to8_count_30t,
            disposal_times_30t,
            any_rule_one_day_away,
            will_be_disposed_tomorrow
        FROM notice_behavior_feature
        WHERE any_rule_one_day_away = 1
          AND disposal_period_day_index = 0
          AND will_be_disposed_tomorrow IS NOT NULL
    """)

    if train_df.empty or train_df["will_be_disposed_tomorrow"].sum() == 0:
        print("❌ 訓練資料不足（沒有任何正樣本或資料為空），無法訓練模型")
        return

    print(f"訓練樣本數：{len(train_df)}，正樣本：{int(train_df['will_be_disposed_tomorrow'].sum())}")

    # --------------------------------------------------
    # 2. 準備特徵 & 標籤
    # --------------------------------------------------
    feature_cols = [
        "rule1_one_day_away",
        "rule2_one_day_away",
        "rule3_one_day_away",
        "rule4_one_day_away",
        "rule_one_day_away_count",
        "law1_consecutive_days",
        "law1to8_consecutive_days",
        "law1to8_count_10t",
        "law1to8_count_30t",
        "disposal_times_30t",
    ]

    X = train_df[feature_cols].fillna(0)
    y = train_df["will_be_disposed_tomorrow"].astype(int)

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    # --------------------------------------------------
    # 3. 建立 LightGBM + GridSearch
    # --------------------------------------------------
    print("=== 使用 LightGBM + GridSearchCV 訓練模型 ===")

    lgbm = LGBMClassifier(
        objective="binary",
        random_state=42,
        n_jobs=-1,
    )

    param_grid = {
        "n_estimators": [200, 400],
        "learning_rate": [0.05, 0.1],
        "num_leaves": [31, 63],
        "max_depth": [-1, 5, 7],
        "subsample": [0.8, 1.0],
        "colsample_bytree": [0.8, 1.0],
    }

    grid = GridSearchCV(
        lgbm,
        param_grid,
        scoring="roc_auc",
        cv=5,
        n_jobs=-1,
        verbose=0,
    )

    grid.fit(X_train, y_train)

    best_model = grid.best_estimator_

    print("\n=== ★ LightGBM 最佳參數 ===")
    print(grid.best_params_)

    # --------------------------------------------------
    # 4. 驗證集上做模型報告
    # --------------------------------------------------
    print("\n=== ★ 模型分析報告（Validation set） ===")

    val_prob = best_model.predict_proba(X_val)[:, 1]
    val_pred = (val_prob >= 0.5).astype(int)

    print("\n--- Classification Report ---")
    print(classification_report(y_val, val_pred))

    print("\n--- Confusion Matrix ---")
    print(confusion_matrix(y_val, val_pred))

    auc = roc_auc_score(y_val, val_prob)
    ll = log_loss(y_val, val_prob)
    print(f"\nROC AUC: {auc:.4f}")
    print(f"Log Loss: {ll:.4f}")

    # Feature importance
    print("\n--- Feature Importance (LightGBM) ---")
    importances = best_model.feature_importances_
    for name, imp in sorted(zip(feature_cols, importances), key=lambda x: -x[1]):
        print(f"{name:30s} -> {imp}")

    # --------------------------------------------------
    # 5. 對「要預測的資料」產生 pred_prob_disposal
    #    只預測：any_rule_one_day_away = 1 & 非處置期間
    # --------------------------------------------------
    print("\n=== 讀取預測資料（any_rule_one_day_away = 1 & 未處置） ===")

    pred_df = db.query_to_df("""
        SELECT 
            id,
            rule1_one_day_away,
            rule2_one_day_away,
            rule3_one_day_away,
            rule4_one_day_away,
            rule_one_day_away_count,
            law1_consecutive_days,
            law1to8_consecutive_days,
            law1to8_count_10t,
            law1to8_count_30t,
            disposal_times_30t
        FROM notice_behavior_feature
        WHERE any_rule_one_day_away = 1
          AND disposal_period_day_index = 0
    """)

    if pred_df.empty:
        print("⚠ 沒有 any_rule_one_day_away = 1 的資料需要預測")
        return

    X_pred = pred_df[feature_cols].fillna(0)
    pred_probs = best_model.predict_proba(X_pred)[:, 1]
    pred_df["pred_prob_disposal"] = pred_probs

    # --------------------------------------------------
    # 6. 寫回 DB（只更新這些臨界樣本）
    # --------------------------------------------------
    print("\n=== 寫回 DB（更新 pred_prob_disposal，含進度） ===")
    total = len(pred_df)

    for i, (_, row) in enumerate(pred_df.iterrows(), start=1):
        if i % 500 == 0 or i == total:
            print(f"→ 更新進度：{i}/{total}")

        db.execute_sql(f"""
            UPDATE notice_behavior_feature
            SET pred_prob_disposal = {row['pred_prob_disposal']}
            WHERE id = {row['id']}
        """)

    print("\n🎉 LightGBM 版 pred_prob_disposal 已全部更新完成（僅 any_rule_one_day_away=1 的資料）")

def find_best_threshold_for_precision(target_precision=0.80):

    df = db.query_to_df("""
        SELECT pred_prob_disposal, will_be_disposed_tomorrow
        FROM notice_behavior_feature
        WHERE pred_prob_disposal IS NOT NULL
          AND will_be_disposed_tomorrow IS NOT NULL
          AND disposal_period_day_index = 0
    """)

    y_true = df["will_be_disposed_tomorrow"].values.astype(int)
    y_prob = df["pred_prob_disposal"].values
    
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_prob)

    # 找到 precision >= target_precision 的最小 threshold
    candidates = [(p, r, t) for p, r, t in zip(precisions, recalls, np.append(thresholds,1))
                  if p >= target_precision]

    if not candidates:
        print("沒有任何 threshold 能達到指定 precision")
        return None

    # precision 最接近 target precision 的 threshold
    best = min(candidates, key=lambda x: abs(x[0] - target_precision))

    print("\n=== ★ 最佳 threshold 結果 ===")
    print(f"目標 Precision       : {target_precision}")
    print(f"達成 Precision       : {best[0]:.4f}")
    print(f"對應 Recall         : {best[1]:.4f}")
    print(f"建議使用 Threshold  : {best[2]:.4f}")

    return best[2]


def statistics_disposal_probabilities():

    print("=== 統計資料來源：any_rule_one_day_away = 1 的樣本 ===")

    # ---------------------------------------------------------
    # 1. rule1~4_one_day_away = 1 時的 will_be_disposed_tomorrow 比率
    # ---------------------------------------------------------
    print("\n=== 1. rule1~4_one_day_away → 明天被處置比率 ===")

    for rule_col in [
        "rule1_one_day_away",
        "rule2_one_day_away",
        "rule3_one_day_away",
        "rule4_one_day_away",
    ]:
        sql = f"""
            SELECT 
                AVG(CASE WHEN will_be_disposed_tomorrow = 1 THEN 1.0 ELSE 0.0 END) AS p,
                COUNT(*) AS cnt
            FROM notice_behavior_feature
            WHERE any_rule_one_day_away = 1
              AND disposal_period_day_index = 0
              AND will_be_disposed_tomorrow IS NOT NULL
              AND {rule_col} = 1
        """

        df = db.query_to_df(sql)
        p = df["p"].iloc[0]
        cnt = df["cnt"].iloc[0]

        if cnt == 0:
            print(f"{rule_col}: 沒有樣本")
        else:
            print(f"{rule_col:25s} → 比率={p:.4f}，樣本數={cnt}")

    # ---------------------------------------------------------
    # 2. rule_one_day_away_count 各數值 → 明天被處置比率
    #    （只看 any_rule_one_day_away = 1 的資料）
    # ---------------------------------------------------------
    print("\n=== 2. rule_one_day_away_count 各數值 → 明天被處置比率 ===")

    sql2 = """
        SELECT 
            rule_one_day_away_count AS cnt_rules,
            AVG(CASE WHEN will_be_disposed_tomorrow = 1 THEN 1.0 ELSE 0.0 END) AS p,
            COUNT(*) AS cnt
        FROM notice_behavior_feature
        WHERE any_rule_one_day_away = 1
          AND disposal_period_day_index = 0
          AND will_be_disposed_tomorrow IS NOT NULL
        GROUP BY rule_one_day_away_count
        ORDER BY rule_one_day_away_count
    """

    df2 = db.query_to_df(sql2)

    for _, row in df2.iterrows():
        cnt_rules = row["cnt_rules"]
        p = row["p"]
        n = int(row["cnt"])
        print(f"rule_one_day_away_count = {int(cnt_rules)} → 比率={p:.4f}，樣本數={n}")

def cross_stats_rule_count_and_ruleX():

    print("=== 交叉統計：rule_one_day_away_count × ruleX_one_day_away ===")
    print("（只分析 any_rule_one_day_away = 1 & 未處置期間）\n")

    # ---------------------------------------------------------
    # Step1. 動態取得 rule_one_day_away_count 出現過的所有值
    # ---------------------------------------------------------
    sql_cnt = """
        SELECT DISTINCT rule_one_day_away_count AS cnt_val
        FROM notice_behavior_feature
        WHERE any_rule_one_day_away = 1
          AND disposal_period_day_index = 0
          AND will_be_disposed_tomorrow IS NOT NULL
        ORDER BY cnt_val
    """
    cnt_df = db.query_to_df(sql_cnt)
    count_values = [int(x) for x in cnt_df["cnt_val"].tolist()]

    print(f"偵測到的 rule_one_day_away_count 數值：{count_values}\n")

    # ---------------------------------------------------------
    # Step2. 要交叉的 ruleX_one_day_away 欄位
    # ---------------------------------------------------------
    rule_cols = [
        "rule1_one_day_away",
        "rule2_one_day_away",
        "rule3_one_day_away",
        "rule4_one_day_away",
    ]

    # ---------------------------------------------------------
    # Step3. 動態交叉統計
    # ---------------------------------------------------------
    for rule in rule_cols:
        print(f"\n====== {rule} = 1 ======")

        for cnt in count_values:

            sql = f"""
                SELECT 
                    AVG(CASE WHEN will_be_disposed_tomorrow = 1 THEN 1.0 ELSE 0.0 END) AS p,
                    COUNT(*) AS cnt
                FROM notice_behavior_feature
                WHERE any_rule_one_day_away = 1
                  AND disposal_period_day_index = 0
                  AND will_be_disposed_tomorrow IS NOT NULL
                  AND rule_one_day_away_count = {cnt}
                  AND {rule} = 1
            """

            df = db.query_to_df(sql)
            p = df["p"].iloc[0]
            n = df["cnt"].iloc[0]

            if n == 0:
                print(f"{rule}, count={cnt} → 無樣本")
            else:
                print(f"{rule}, count={cnt} → 比率={p:.4f}，樣本數={n}")

import itertools
def rule_combination_stats():

    print("=== 全部 rule 組合（1~3 個） → 明天被處置比率 ===")
    print("（限定 any_rule_one_day_away = 1 & 未處置期間）\n")

    rule_cols = [
        "rule1_one_day_away",
        "rule2_one_day_away",
        "rule3_one_day_away",
        "rule4_one_day_away",
    ]

    # 產生所有組合：1 個、2 個、3 個
    all_combinations = []
    for r in [1, 2, 3]:
        all_combinations += list(itertools.combinations(rule_cols, r))

    # 逐一統計
    for combo in all_combinations:

        # where 子句：所有指定 rule = 1
        cond = " AND ".join([f"{c} = 1" for c in combo])

        sql = f"""
            SELECT
                AVG(CASE WHEN will_be_disposed_tomorrow = 1 THEN 1.0 ELSE 0.0 END) AS p,
                COUNT(*) AS cnt
            FROM notice_behavior_feature
            WHERE any_rule_one_day_away = 1
              AND disposal_period_day_index = 0
              AND will_be_disposed_tomorrow IS NOT NULL
              AND {cond}
        """

        df = db.query_to_df(sql)
        p = df["p"].iloc[0]
        n = int(df["cnt"].iloc[0])

        combo_name = "+".join([c.replace("_one_day_away", "") for c in combo])
        count_level = len(combo)

        if n == 0:
            print(f"[count={count_level}] {combo_name:30s} → 無樣本")
        else:
            print(f"[count={count_level}] {combo_name:30s} → 比率={p:.4f}，樣本數={n}")
            
            
# -------- Regex 抽取價差 --------
def extract_price_diff(text):
    if not text:
        return None

    # 最常見 pattern：「價差達345元」「價差為 55 元」「價差64 元」
    pattern = r"價差(?:達|為)?\s*([0-9]+(?:\.[0-9]+)?)\s*元"
    match = re.search(pattern, text)
    return float(match.group(1)) if match else None


def repair_twse_price_diff_features():

    print("=== 開始補 TWSE 第一款 price_diff 特徵（加速版） ===")

    # 1️⃣ 抓 TWSE 第一款 + raw_text 中必須含「六個營業」字樣
    sql = """
        SELECT ai_key, target_id, target_table, raw_text
        FROM law_feature_base
        WHERE law_src='第一款'
          AND target_table='twse_announcement_notice'
          AND feature_key='acc_return_pct'
          AND raw_text LIKE '%六個營業%'
        ORDER BY target_id
    """
    df = db.query_to_df(sql)
    print(f"找到 {len(df)} 筆 TWSE 第一款（含六個營業字樣）")

    # 2️⃣ 避免重複
    existed_df = db.query_to_df("""
        SELECT target_id
        FROM law_feature_base
        WHERE target_table='twse_announcement_notice'
          AND feature_key='price_diff'
    """)
    existed_ids = set(existed_df["target_id"])
    print(f"已有 price_diff：{len(existed_ids)} 筆，將忽略")

    insert_count = 0

    # 3️⃣ 開始解析
    for _, row in df.iterrows():

        target_id  = row["target_id"]
        ai_key     = row["ai_key"]
        raw_text   = row["raw_text"]
        table_name = row["target_table"]

        if target_id in existed_ids:
            continue

        price_diff = extract_price_diff(raw_text)
        if price_diff is None:
            continue   # ✔ 配不到 → 不新增

        safe_raw = raw_text.replace("'", "''")

        # threshold_value = NULL （第一款 price_diff 無固定門檻）
        sql_insert = f"""
            INSERT INTO law_feature_base
                (ai_key, target_table, target_id, law_src,
                 feature_key, feature_value, threshold_value, raw_text)
            VALUES
                ('{ai_key}', '{table_name}', {target_id}, '第一款',
                 'price_diff', {price_diff}, NULL, '{safe_raw}')
        """
        db.execute_sql(sql_insert)
        insert_count += 1

    print(f"=== 補完成：成功新增 {insert_count} 筆 price_diff ===")            
            
            
            
# python -m main.predictDispostion2
if __name__ == "__main__":
    print("--- RUN main.predictDispostion2 ---")
    repair_twse_price_diff_features()
    
    