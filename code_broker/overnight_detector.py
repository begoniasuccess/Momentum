import psycopg2
import pandas as pd

# 連線資料庫
def connect_db() -> psycopg2.extensions.connection:
    conn = psycopg2.connect(
        host='140.113.87.91',
        database='finDB',
        user='nycu_findb_user',
        password='NYCUd@t@b@se8791'
    )
    conn.autocommit = True
    return conn


# 讀取資料表：tw_broker_daily_bs_stock_b
if __name__ == '__main__':
    conn = connect_db()
    sql = "SELECT * FROM public.tw_broker_daily_bs_stock_b"
    sql += " WHERE stock_id = '2330'"
    sql += " ORDER BY DATE date, securities_trader_id, stock_id"
    sql += " LIMIT 2000"
    # sql += ""

    df = pd.read_sql_query(sql, conn)
    df.to_csv("test2.csv")
    
    print(df.head())
    
