import sys
import os
from datetime import datetime, timedelta
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
def runTwMarketValue(stockList:list, sDt:datetime, eDt:datetime) -> bool:
    result = True
    try:
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
    except Exception as e:
        utils.ptMsg(f"發生錯誤：{e}")
        return False
    return result

storageDir_twDailyPriceAdj =  f"{storageDir}/TW/DailyPriceAdj"
os.makedirs(storageDir_twStockInfo, exist_ok=True)
# 撈取股票每日調整後價格
def runTwStockDailyPriceAdj(stockList:list, sDt:datetime, eDt:datetime) -> bool:
    result = True
    try:
        utils.ptMsg("📢 即將撈取[歷史修正股價]資料，股票清單的長度為：", len(stockList))
        outputDir = storageDir_twDailyPriceAdj
        for stock_id in stockList:
            outputFile = f'{outputDir}/{sDt.strftime("%Y%m%d")}-{eDt.strftime("%Y%m%d")}/TWDPadj-{stock_id}.csv'
            if os.path.exists(outputFile):
                utils.ptMsg("☑️ 檔案已存在：", outputFile)
            else:
                os.makedirs(os.path.dirname(outputFile), exist_ok=True)  # 確保資料夾存在
                try:
                    # 嘗試一次抓全部資料
                    dfSDA = api.taiwan_stock_daily_adj(
                        stock_id=stock_id,
                        start_date=sDt.strftime("%Y-%m-%d"),
                        end_date=eDt.strftime("%Y-%m-%d")
                    )
                    # 如果沒報錯就直接存檔
                    dfSDA.to_csv(outputFile, index=False, encoding='utf-8-sig')
                    utils.ptMsg("✅ 檔案存取成功：", outputFile)
                except Exception as e:
                    utils.ptMsg(f"⚠️ 一次抓取失敗：{stock_id}，錯誤訊息：{e}")
                    # 分段再試
                    try:
                        # 分成兩段
                        midDt = sDt + timedelta(days=365 * 5)
                        utils.ptMsg(f"➡️ 嘗試分段抓取 {stock_id} 第1段：{sDt.date()} ~ {midDt.date()}")
                        dfSDA1 = api.taiwan_stock_daily_adj(
                            stock_id=stock_id,
                            start_date=sDt.strftime("%Y-%m-%d"),
                            end_date=midDt.strftime("%Y-%m-%d")
                        )
                        utils.ptMsg(f"➡️ 嘗試分段抓取 {stock_id} 第2段：{(midDt + timedelta(days=1)).date()} ~ {eDt.date()}")
                        dfSDA2 = api.taiwan_stock_daily_adj(
                            stock_id=stock_id,
                            start_date=(midDt + timedelta(days=1)).strftime("%Y-%m-%d"),
                            end_date=eDt.strftime("%Y-%m-%d")
                        )
                        # 合併兩段
                        dfSDA = pd.concat([dfSDA1, dfSDA2], ignore_index=True)
                        # 儲存
                        dfSDA.to_csv(outputFile, index=False, encoding='utf-8-sig')
                        utils.ptMsg("✅ 分段抓取並合併成功：", outputFile)

                    except Exception as e2:
                        utils.ptMsg(f"❌ 分段抓取失敗：{stock_id}，錯誤訊息：{e2}")
                        # 不要 raise，直接繼續跑下一支
                        continue
    except Exception as e:
        utils.ptMsg(f"發生錯誤：{e}")
        return False
    return result            
