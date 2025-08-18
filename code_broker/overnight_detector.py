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
    table = "tw_broker_daily_bs_stock_b"
    
    sql = "SELECT * FROM public." + table
    sql += " WHERE stock_id = '2330'"
    sql += " ORDER BY DATE date, securities_trader_id, stock_id"
    sql += " LIMIT 2000"
    
    table = "tw_stock_daily_price"
    # sql += "tw_stock_daily_price"

    df = pd.read_sql_query(sql, conn)
    df.to_csv(table + "_test.csv")
    
    print(df.head())
    
