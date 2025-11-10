import sys, os
sys.path.append(os.path.dirname(__file__))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from common import utils, db
from module import finMind
import re
from datetime import datetime
import pytz
import re
from typing import List, Optional, Iterable
from datetime import datetime
import time

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


def update_notice_behavior_features(batch_size: int = 1000):
    """
    🚀 批次更新 notice_behavior_feature 六個新欄位
        law1_consecutive_days
        law1to8_count_10d
        law1to8_count_30d
        notice_count_7d
        unique_law_count_7d
        same_law_repeat_5d
    """
    t0 = time.time()

    sql = "SELECT * FROM notice_behavior_feature ORDER BY notice_dt_ts ASC"
    df = db.query_to_df(sql)
    if df.empty:
        print("⚠️ 無資料可更新")
        return

    df["notice_dt_ts"] = pd.to_numeric(df["notice_dt_ts"], errors="coerce")
    df = df.dropna(subset=["notice_dt_ts"])
    df = df.sort_values(["stock_no", "notice_dt_ts"]).reset_index(drop=True)

    updates = []
    for stock_no, g in df.groupby("stock_no"):
        g = g.sort_values("notice_dt_ts")
        for i, row in g.iterrows():
            ts = row["notice_dt_ts"]
            law = row["law_src"] or ""
            law_list = [l.strip() for l in law.split(",") if l.strip()]

            # 過去區間
            past_10d = g[(g["notice_dt_ts"] >= ts - 10 * 86400) & (g["notice_dt_ts"] < ts)]
            past_30d = g[(g["notice_dt_ts"] >= ts - 30 * 86400) & (g["notice_dt_ts"] < ts)]
            past_7d = g[(g["notice_dt_ts"] >= ts - 7 * 86400) & (g["notice_dt_ts"] < ts)]
            past_5d = g[(g["notice_dt_ts"] >= ts - 5 * 86400) & (g["notice_dt_ts"] < ts)]

            # 特徵
            law1_consecutive = 0
            if "第一款" in law_list:
                prev = g[g["notice_dt_ts"] < ts].tail(3)
                law1_consecutive = 1
                for _, p in prev.iterrows():
                    if "第一款" in str(p["law_src"]):
                        law1_consecutive += 1
                    else:
                        break

            law1to8_10d = sum(
                any(f"第{i}款" in (p or "") for i in range(1, 9))
                for p in past_10d["law_src"]
            )
            law1to8_30d = sum(
                any(f"第{i}款" in (p or "") for i in range(1, 9))
                for p in past_30d["law_src"]
            )
            notice_7d = len(past_7d)
            unique_law_7d = len(
                set(l for p in past_7d["law_src"] if p for l in p.split(","))
            )
            same_law_repeat_5d = sum(
                any(l in (p or "") for l in law_list)
                for p in past_5d["law_src"]
            )

            updates.append((
                law1_consecutive,
                law1to8_10d,
                law1to8_30d,
                notice_7d,
                unique_law_7d,
                same_law_repeat_5d,
                row["id"]
            ))

            if len(updates) >= batch_size:
                db.execute_sql("""
                    UPDATE notice_behavior_feature
                    SET law1_consecutive_days=?,
                        law1to8_count_10d=?,
                        law1to8_count_30d=?,
                        notice_count_7d=?,
                        unique_law_count_7d=?,
                        same_law_repeat_5d=?
                    WHERE id=?;
                """, updates)
                print(f"📦 已更新 {len(updates)} 筆")
                updates.clear()

    if updates:
        db.execute_sql("""
            UPDATE notice_behavior_feature
            SET law1_consecutive_days=?,
                law1to8_count_10d=?,
                law1to8_count_30d=?,
                notice_count_7d=?,
                unique_law_count_7d=?,
                same_law_repeat_5d=?
            WHERE id=?;
        """, updates)

    print(f"✅ 全部完成，共更新 {len(df)} 筆，耗時 {time.time()-t0:.1f}s")

def update_risk_score_regulation(batch_size: int = 1000):
    """
    🚀 修正版：確保 risk_score_regulation 正確寫入
    """
    t0 = time.time()
    sql = """
    SELECT id,
           COALESCE(law1_consecutive_days,0) AS law1_consecutive_days,
           COALESCE(law1to8_count_10d,0) AS law1to8_count_10d,
           COALESCE(law1to8_count_30d,0) AS law1to8_count_30d
    FROM notice_behavior_feature
    """
    df = db.query_to_df(sql)
    if df.empty:
        print("⚠️ 無資料可更新")
        return

    updates = []
    count_high, count_med, count_low = 0, 0, 0

    for _, row in df.iterrows():
        s1 = int(row["law1_consecutive_days"])
        s2 = int(row["law1to8_count_10d"])
        s3 = int(row["law1to8_count_30d"])

        score = 0
        if s1 >= 3:
            score = 100
            count_high += 1
        elif s2 >= 6:
            score = 80
            count_high += 1
        elif s3 >= 12:
            score = 70
            count_med += 1
        elif s2 >= 4 and s1 >= 2:
            score = 50
            count_low += 1
        else:
            score = 0

        updates.append((score, row["id"]))

        if len(updates) >= batch_size:
            db.execute_sql(
                "UPDATE notice_behavior_feature SET risk_score_regulation=? WHERE id=?",
                updates
            )
            updates.clear()

    if updates:
        db.execute_sql(
            "UPDATE notice_behavior_feature SET risk_score_regulation=? WHERE id=?",
            updates
        )

    elapsed = time.time() - t0
    print(f"✅ 全部完成，共更新 {len(df)} 筆，耗時 {elapsed:.1f}s")
    print(f"📊 命中情況：高風險={count_high} 中風險={count_med} 低風險={count_low}")
    
# python -m main.predictDispostion
if __name__ == "__main__":
    update_risk_score_regulation()