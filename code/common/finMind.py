import requests
import pandas as pd
from FinMind.data import DataLoader
import sys

sys.stdout.reconfigure(encoding='utf-8')

### FinMind api設定
apiUrl = "https://api.finmindtrade.com/api/v4/data"
api = DataLoader()
token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNS0wNi0yOCAxNToyODoxMSIsInVzZXJfaWQiOiJueWN1bGFiNjE1IiwiaXAiOiIxMTQuMTM3LjIxOS4yMTEiLCJleHAiOjE3NTE3MDA0OTF9.u4s5jxRFBz2ojJ01n-8c6Jm2G0FAhtn1-gSMsaspZWE"
api.login_by_token(api_token=token)

# 
def getTwStockInfo(includeCateHistory:bool=False) -> pd.DataFrame:
    df = api.taiwan_stock_info() # 台股總覽
    if not includeCateHistory:
        # 確保 date 欄位是 datetime 格式
        df['date'] = pd.to_datetime(df['date'])

        # 依 stock_id 分組，選取每組中 date 最大的那筆資料
        latest_df = df.sort_values('date').groupby('stock_id', as_index=False).tail(1)

        # 依照 stock_id 排序（可選）
        df = latest_df.sort_values(by='stock_id')
        print(df.head(3))
    return df

# 撈取上市清單
def getTwStockInfoTwse(includeCateHistory:bool=False) -> pd.DataFrame:
    df = getTwStockInfo(includeCateHistory)
    
    # 篩選 type 為 'twse'
    df_twse = df[df['type'] == 'twse']

    # 排除 industry_category 欄位含有指定關鍵字的資料
    exclude_keywords = ['ETF', 'Index', '受益證券', 'ETN', '大盤', '存託憑證', '創新板股票', '創新版股票']
    pattern = '|'.join(exclude_keywords)  # 建立 regex 模式
    df_twse_filtered = df_twse[~df_twse['industry_category'].str.contains(pattern, na=False)]

    return df_twse_filtered

# 排除興櫃的台股清單
def getTwStockInfoNoEmerging(includeCateHistory:bool=False) -> pd.DataFrame:
    df = getTwStockInfo(includeCateHistory)
    
    # 篩選 type 為 'twse'
    df_twse = df[df['type'] != 'emerging']

    # 排除 industry_category 欄位含有指定關鍵字的資料
    exclude_keywords = ['ETF', 'Index', '受益證券', 'ETN', '大盤', '存託憑證', '創新板股票', '創新版股票']
    pattern = '|'.join(exclude_keywords)  # 建立 regex 模式
    df_twse_filtered = df_twse[~df_twse['industry_category'].str.contains(pattern, na=False)]

    return df_twse_filtered