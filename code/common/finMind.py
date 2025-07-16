import sys
import os
from datetime import datetime
import pandas as pd
from FinMind.data import DataLoader
from common import utils

sys.stdout.reconfigure(encoding='utf-8')

### FinMind api設定
apiUrl = "https://api.finmindtrade.com/api/v4/data"
api = DataLoader()
token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNS0wNy0xNiAxMDozNDowOCIsInVzZXJfaWQiOiJueWN1bGFiNjE1IiwiaXAiOiIyMTguMjEwLjIxOC40MSIsImV4cCI6MTc1MzIzODA0OH0.AIdZzqpwGXXngHyRTGHF2q4p5-tY4sNRi8Q_1Ur2lk4"
api.login_by_token(api_token=token)

storageDir = "../data/FinMind"
os.makedirs(storageDir, exist_ok=True)

storageDir_twStockInfo =  f"{storageDir}/TW/StockInfo"
os.makedirs(storageDir_twStockInfo, exist_ok=True)

# 撈取台股清單
def twStockInfo(includeCateHistory:bool=False) -> pd.DataFrame:
    df = None
    output_file = f"{storageDir_twStockInfo}/stock_info.csv"
    if os.path.exists(output_file):
        df = pd.read_csv(output_file)
        print(f"☑️ Data exist: {output_file}")
    else:        
        df = api.taiwan_stock_info() # 台股總覽
        df['date'] = pd.to_datetime(df['date'], errors='coerce') 
        df = df[df['date'].notna()] 
        if not includeCateHistory:
            # 確保 date 欄位是 datetime 格式
            df['date'] = pd.to_datetime(df['date'])

            # 依 stock_id 分組，選取每組中 date 最大的那筆資料
            latest_df = df.sort_values('date').groupby('stock_id', as_index=False).tail(1)

            # 依照 stock_id 排序（可選）
            df = latest_df.sort_values(by='stock_id')
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
    return df

# 撈取上市清單
def twStockInfoTwse(includeCateHistory:bool=False) -> pd.DataFrame:
    df_twse_filtered = None
    output_file = f"{storageDir_twStockInfo}/stock_info-twse.csv"
    if os.path.exists(output_file):
        df = pd.read_csv(output_file)
        print(f"☑️ Data exist: {output_file}")
    else:        
        df = twStockInfo(includeCateHistory)
        
        # 篩選 type 為 'twse' (上市)
        df_twse = df[df['type'] == 'twse']

        # 排除 industry_category 欄位含有指定關鍵字的資料
        exclude_keywords = ['ETF', 'Index', '受益證券', 'ETN', '大盤', '存託憑證', '創新板股票', '創新版股票']
        pattern = '|'.join(exclude_keywords)  # 建立 regex 模式
        df_twse_filtered = df_twse[~df_twse['industry_category'].str.contains(pattern, na=False)]

        df_twse_filtered.to_csv(output_file, index=False, encoding='utf-8-sig')
    return df_twse_filtered

# 排除興櫃的台股清單
def twStockInfoNoEmerging(includeCateHistory:bool=False) -> pd.DataFrame:
    df_twse_filtered = None
    output_file = f"{storageDir_twStockInfo}/stock_info-no_emerging.csv"
    if os.path.exists(output_file):
        df_twse_filtered = pd.read_csv(output_file)
        print(f"☑️ Data exist: {output_file}")
    else:          
        df = twStockInfo(includeCateHistory)
        
        # 排除 type 為 'emerging' (興櫃)
        df_twse = df[df['type'] != 'emerging']

        # 排除 industry_category 欄位含有指定關鍵字的資料
        exclude_keywords = ['ETF', 'Index', '受益證券', 'ETN', '大盤', '存託憑證', '創新板股票', '創新版股票']
        pattern = '|'.join(exclude_keywords)  # 建立 regex 模式
        df_twse_filtered = df_twse[~df_twse['industry_category'].str.contains(pattern, na=False)]

        df_twse_filtered.to_csv(output_file, index=False, encoding='utf-8-sig')
    return df_twse_filtered

storageDir_twMarketValue =  f"{storageDir}/TW/MarketValue"
os.makedirs(storageDir_twMarketValue, exist_ok=True)

# 撈取各股票市值資料
def twMarketValue(stockList:list, sDt:datetime, eDt:datetime):
    utils.ptMsg("📢 即將撈取[市值歷史]資料，股票清單的長度為：", len(stockList))
    
    outputDir = f"{storageDir_twMarketValue}/{sDt.strftime("%Y%m%d")}-{eDt.strftime("%Y%m%d")}"
    for stock_id in stockList:
        outputFile = f'{outputDir}/TWMV-{stock_id}.csv'
        if os.path.exists(outputFile):
            utils.ptMsg("☑️ 檔案已存在：", outputFile)
        else:
            os.makedirs(os.path.dirname(outputFile), exist_ok=True) # 確保資料夾存在
            dfMV = api.taiwan_stock_market_value(
                stock_id=stock_id,
                start_date=sDt.strftime("%Y-%m-%d"),
                end_date=eDt.strftime("%Y-%m-%d")
            )
            dfMV.to_csv(outputFile, index=False, encoding='utf-8-sig')
            utils.ptMsg("✅ 檔案存取成功：", outputFile)
    utils.ptMsg("📢 [市值歷史]資料撈取結束。")



