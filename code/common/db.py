import sys, os
sys.path.append(os.path.dirname(__file__))

import sqlite3
import pandas as pd
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime

# 資料庫路徑
DB_PATH = Path("../Data/data_center.db")

@contextmanager
def get_connection():
    """
    建立並自動關閉 SQLite 連線
    - WAL: 降低 read/write 互卡
    - busy_timeout: 遇到鎖等待
    """
    conn = sqlite3.connect(DB_PATH, timeout=60)  # 60 秒更耐鎖
    try:
        # --- 重要：提升抗 locked ---
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA busy_timeout=60000;")  # 60s
        yield conn
    finally:
        conn.close()

def query_to_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    """執行查詢並回傳 DataFrame"""
    with get_connection() as conn:
        df = pd.read_sql_query(sql, conn, params=params)
    return df

def query_single_value(sql: str, params: tuple = ()):
    """
    執行查詢並回傳單一值。
    例如 SELECT COUNT(*) FROM table
    如果沒有結果，回傳 None
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None

def execute_sql(sql: str, params: tuple | list[tuple] = ()):
    if not sql or not sql.strip():
        print("[SQLite Error] SQL is empty!")
        return -1
    if isinstance(params, list) and len(params) == 0:
        print("[SQLite Error] params list is empty!")
        return -1

    try:
        with get_connection() as conn:
            cur = conn.cursor()
            # ✅ 僅當 list of tuple 時才用 executemany
            if isinstance(params, list) and all(isinstance(p, tuple) for p in params):
                cur.executemany(sql, params)
            else:
                cur.execute(sql, params)
            conn.commit()
        return cur.rowcount
    except sqlite3.Error as e:
        print(f"[SQLite Error] {e}")
        return -1


    
def output_dump():
    output_path = f"dump_{datetime.today().strftime("%Y%m%d%H%M%S")}.sql"
    try:
        conn = sqlite3.connect(DB_PATH)
        with open(output_path, "w", encoding="utf-8") as f:
            for line in conn.iterdump():
                f.write(f"{line}\n")
        conn.close()
        print(f"✅ Dump 完成，已輸出到 {DB_PATH}")
    except Exception as e:
        print("❌ 發生錯誤：", e)
        
        
def outputCsv(querySql:str, fileName:str = None):
    if fileName is None or fileName == "":
        now = datetime.today().strftime("%Y%m%d_%H%M%S")
        fileName = f"dataCenter_output_{now}.csv"
        
    df = query_to_df(querySql)
    
    # 匯出成 CSV
    out_path = f"C:/Users/USER/Desktop/{fileName}"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"✅ 匯出完成 → {out_path}")

def export_table_to_csv(
    table_name: str,
    batch_size: int = 2000,
    output_dir: str = "C:/Users/USER/Desktop",
    verbose: bool = True,
):
    """
    🚀 分批匯出整張表或 View 為 CSV
    - 自動判斷是否為 View
    - 避免記憶體爆炸
    """

    import time, os
    from datetime import datetime

    t_start = time.time()
    last_rowid = 0
    batch_no = 1
    offset = 0

    out_file = os.path.join(
        output_dir,
        f"{table_name}_export_{datetime.today().strftime('%Y%m%d_%H%M%S')}.csv"
    )

    if verbose:
        print(f"🚀 開始匯出表：{table_name}")
        print(f"📁 輸出檔案：{out_file}")

    with get_connection() as conn:
        cur = conn.cursor()
        # 檢查是 table 還是 view
        cur.execute("SELECT type FROM sqlite_master WHERE name = ?", (table_name,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"❌ 找不到 {table_name} (table/view 不存在)")
        is_view = (row[0].lower() == "view")

        pk_col = None
        if not is_view:
            # 嘗試找出主鍵欄位
            cur.execute(f"PRAGMA table_info({table_name})")
            cols = cur.fetchall()
            pk_cols = [c[1] for c in cols if c[5] == 1]
            pk_col = pk_cols[0] if pk_cols else "rowid"

    dfs = []
    while True:
        if is_view:
            # View 無 rowid，用 LIMIT + OFFSET
            sql = f"SELECT * FROM {table_name} LIMIT {batch_size} OFFSET {offset}"
            params = ()
        else:
            sql = f"""
            SELECT *
            FROM {table_name}
            WHERE {pk_col} > ?
            ORDER BY {pk_col} ASC
            LIMIT {batch_size}
            """
            params = (last_rowid,)

        df = query_to_df(sql, params)
        if df.empty:
            if verbose:
                print("✅ 已無更多資料，停止分批")
            break

        # 更新狀態
        if not is_view:
            last_rowid = df[pk_col].max()
        offset += len(df)

        # 寫出
        mode = "w" if batch_no == 1 else "a"
        header = (batch_no == 1)
        df.to_csv(out_file, index=False, encoding="utf-8-sig", mode=mode, header=header)

        if verbose:
            key_val = last_rowid if not is_view else offset
            print(f"📦 批次 {batch_no}: {len(df)} 筆（目前進度={key_val}）")

        batch_no += 1
        dfs.append(df)

    total_time = time.time() - t_start
    print(f"🎯 匯出完成，共 {batch_no-1} 批，耗時 {total_time:.2f}s")
    print(f"📄 檔案路徑：{out_file}")

    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def export_sql_to_csv(
    sql: str,
    params: tuple = (),
    batch_size: int = 2000,
    output_dir: str = "C:/Users/USER/Desktop",
    file_name: str | None = None,
    verbose: bool = True,
):
    """
    🚀 分批執行任意 SQL 查詢並匯出成 CSV
    適用大型查詢避免記憶體爆炸。
    
    Args:
        sql: 任意 SQL 語法（不含分號）
        params: SQL 參數 tuple
        batch_size: 每批查詢筆數（預設 2000）
        output_dir: 輸出目錄
        file_name: 自訂輸出檔名（可省略）
        verbose: 是否顯示進度
    """
    import time, os
    from datetime import datetime

    t_start = time.time()
    offset = 0
    batch_no = 1
    dfs = []

    if not file_name:
        now = datetime.today().strftime("%Y%m%d_%H%M%S")
        file_name = f"query_output_{now}"
    file_name = file_name + ".csv"

    out_path = os.path.join(output_dir, file_name)
    if verbose:
        print(f"🚀 開始執行查詢匯出")
        print(f"📁 輸出檔案：{out_path}")

    while True:
        paged_sql = f"""
        SELECT * FROM (
            {sql}
        ) AS subquery
        LIMIT {batch_size} OFFSET {offset}
        """
        df = query_to_df(paged_sql, params)
        if df.empty:
            if verbose:
                print("✅ 已無更多資料，停止分批")
            break

        # 寫出CSV（首批寫入header，後續追加）
        mode = "w" if batch_no == 1 else "a"
        header = (batch_no == 1)
        df.to_csv(out_path, index=False, encoding="utf-8-sig", mode=mode, header=header)

        if verbose:
            print(f"📦 批次 {batch_no}: {len(df)} 筆（OFFSET={offset}）")

        dfs.append(df)
        batch_no += 1
        offset += len(df)

    total_time = time.time() - t_start
    print(f"🎯 匯出完成，共 {batch_no-1} 批，耗時 {total_time:.2f}s")
    print(f"📄 檔案路徑：{out_path}")

    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def batch_join_notice_law_src(
    tag: str = "stock_notice_law_src",
    target_table: str = "twse_announcement_notice",
    batch_size: int = 1000,
    output_csv: bool = True,
    verbose: bool = True,
):
    """
    🚀 終極穩定版：
    - SQL 與使用者 count() 版本完全一致
    - 分批依 target_id 遞增 (自動轉數字)
    - JOIN 條件：A.tag=A2.tag AND A.target_id=A2.target_id AND A.memo=A2.memo
    - 所有資料皆正確輸出
    """

    import time
    dfs: list[pd.DataFrame] = []
    last_target_id = 0
    batch_no = 1
    t_start = time.time()

    while True:
        sql = f"""
        SELECT A.*, A2.col_val AS law_src
        FROM (
            SELECT *
            FROM addition_info
            WHERE tag = ?
              AND col_name = '注意交易資訊'
              AND target_table = ?
              AND CAST(target_id AS INTEGER) > ?
            ORDER BY CAST(target_id AS INTEGER) ASC
            LIMIT {batch_size}
        ) AS A
        LEFT JOIN (
            SELECT *
            FROM addition_info
            WHERE tag = ?
              AND col_name = 'law_src'
              AND target_table = ?
        ) AS A2
        ON A.tag = A2.tag
         AND A.target_id = A2.target_id
         AND A.memo = A2.memo;
        """

        df = query_to_df(sql, (tag, target_table, last_target_id, tag, target_table))
        if df.empty:
            if verbose:
                print("✅ 已無更多資料，停止分批")
            break

        # 轉成整數方便排序
        df["target_id"] = pd.to_numeric(df["target_id"], errors="coerce")
        last_target_id = int(df["target_id"].max())
        dfs.append(df)

        if verbose:
            print(f"📦 批次 {batch_no}: {len(df)} 筆（最後 target_id={last_target_id}）")

        batch_no += 1

    if not dfs:
        print("⚠️ 查無任何資料，未輸出檔案")
        return pd.DataFrame()

    final_df = pd.concat(dfs, ignore_index=True)
    total_rows = len(final_df)

    if output_csv:
        now = datetime.today().strftime("%Y%m%d_%H%M%S")
        out_path = f"C:/Users/USER/Desktop/dataCenter_output_{now}.csv"
        final_df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"✅ 匯出完成 → {out_path} （共 {total_rows} 筆）")

    print(f"🎯 全部完成，總筆數 {total_rows}，耗時 {time.time()-t_start:.2f}s")

    return final_df


# python -m common.db
if __name__ == "__main__":     
    table = "v_law1_feature_ana_t1_long"
    export_table_to_csv(table)
    
    table = "v_law1_feature_ana_t1_short"
    export_table_to_csv(table)