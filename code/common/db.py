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
    """建立並自動關閉 SQLite 連線，增加 timeout 避免 locked"""
    conn = sqlite3.connect(DB_PATH, timeout=10)  # 最多等 10 秒
    try:
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
    """
    執行 INSERT/UPDATE/DELETE
    支援單筆 tuple 或多筆 list[tuple]
    成功回傳 affected row 數，失敗回傳 -1
    """
    # 空 SQL 或空 params 都直接跳過
    if not sql or not sql.strip():
        print("[SQLite Error] SQL is empty!")
        return -1
    if isinstance(params, list) and len(params) == 0:
        print("[SQLite Error] params list is empty!")
        return -1

    try:
        with get_connection() as conn:
            cur = conn.cursor()
            if isinstance(params, list):
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
        
        
def outputCsv(sql:str, fileName:str = None):
    if fileName is None or fileName == "":
        now = datetime.today().strftime("%Y%m%d_%H%M%S")
        fileName = f"dataCenter_output_{now}.csv"
        
    df = query_to_df(sql)
    
    # 匯出成 CSV
    out_path = f"C:/Users/USER/Desktop/{fileName}"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"✅ 匯出完成 → {out_path}")
        
if __name__ == "__main__": 
    output_dump()