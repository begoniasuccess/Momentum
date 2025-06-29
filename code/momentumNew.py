from FinMind.data import DataLoader
import pandas as pd
import os
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')

### 索取參數設定
sDt = datetime.strptime('2010/01/01', "%Y/%m/%d")
eDt = datetime.strptime('2020/12/31', "%Y/%m/%d")

### FinMind api設定
apiUrl = "https://api.finmindtrade.com/api/v4/data"
api = DataLoader()
token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNS0wNi0yOCAxNToyODoxMSIsInVzZXJfaWQiOiJueWN1bGFiNjE1IiwiaXAiOiIxMTQuMTM3LjIxOS4yMTEiLCJleHAiOjE3NTE3MDA0OTF9.u4s5jxRFBz2ojJ01n-8c6Jm2G0FAhtn1-gSMsaspZWE"
api.login_by_token(api_token=token)

# ### 撈取市值資料  => DONE
# outputDir = r'..\data\FinMind\TW\MarketValue'

# ## 取得上市股票列表 (create by finTwseList.py)
# stockListSrc = f"../data/analysis/summary/taiwan_stock_info-twse.csv" 
# dfSI = pd.read_csv(stockListSrc)
# stockList = dfSI['stock_id'].drop_duplicates().tolist()
# print("📢 即將撈取[市值歷史]資料，股票清單的長度為：", len(stockList))

# for stock_id in stockList:
#     outputFile = f'{outputDir}/{sDt.strftime("%Y%m%d")}-{eDt.strftime("%Y%m%d")}/TWMV-{stock_id}.csv'
#     if os.path.exists(outputFile):
#         print("☑️ 檔案已存在：", outputFile)
#     else:
#         os.makedirs(os.path.dirname(outputFile), exist_ok=True) # 確保資料夾存在
#         dfMV = api.taiwan_stock_market_value(
#             stock_id=stock_id,
#             start_date=sDt.strftime("%Y-%m-%d"),
#             end_date=eDt.strftime("%Y-%m-%d")
#         )
#         dfMV.to_csv(outputFile, index=False, encoding='utf-8-sig')
#         print("✅ 檔案存取成功：", outputFile)


### 算出每個月各股票的平均市值
outputDir = r'..\data\analysis\summary'
outputPath = f'{outputDir}/TWMV_mean-{sDt.strftime("%Y%m")}_{eDt.strftime("%Y%m")}.csv'
if os.path.exists(outputPath):
    dfTWMVmean = pd.read_csv(outputPath)
    print("☑️ 檔案已存在：", outputPath)    
else:
    # 資料夾路徑
    marketValDataDir = f'../data/FinMind/TW/MarketValue/{sDt.strftime("%Y%m%d")}-{eDt.strftime("%Y%m%d")}'
    marketValFolder = Path(marketValDataDir)

    # 找到所有 CSV 檔案
    TWMVfiles = list(marketValFolder.glob('*.csv'))
    print("找到的檔案：", TWMVfiles)

    # 存放所有檔案的結果
    marketValMeans = []

    for aTWMVfile in TWMVfiles:
        # 檢查檔案大小
        if aTWMVfile.stat().st_size == 0:
            print(f"檔案 {aTWMVfile} 是空的，跳過")
            continue

        # 讀入資料
        try:
            dfTWMVmean = pd.read_csv(aTWMVfile)
        except pd.errors.EmptyDataError:
            print(f"檔案 {aTWMVfile} 無資料，跳過")
            continue

        if dfTWMVmean.empty:
            print(f"檔案 {aTWMVfile} 內容為空，跳過")
            continue

        if 'market_value' not in dfTWMVmean.columns:
            print(f"檔案 {aTWMVfile} 缺少 market_value 欄位，跳過")
            continue
            
        # 排除 market_value == 0
        dfTWMVmean = dfTWMVmean[dfTWMVmean['market_value'] != 0]
        
        # 轉成 datetime
        dfTWMVmean['date'] = pd.to_datetime(dfTWMVmean['date'])
        
        # 產生 year_month 欄位 (YYYY-MM)
        dfTWMVmean['year_month'] = dfTWMVmean['date'].dt.strftime('%Y-%m')
        
        # 以 year_month 分組計算平均
        grouped = dfTWMVmean.groupby('year_month')['market_value'].mean().reset_index()
        
        # 加上 stock_id (每檔資料都是同一個 stock_id)
        stock_id = dfTWMVmean['stock_id'].iloc[0]
        grouped['stock_id'] = stock_id
        
        # 改欄位順序
        grouped = grouped[['stock_id', 'year_month', 'market_value']]
        
        # 改欄位名稱
        grouped = grouped.rename(columns={'market_value': 'mean_market_value'})
        
        # 加到總表
        marketValMeans.append(grouped)

    # 合併所有結果
    dfTWMVmean = pd.concat(marketValMeans, ignore_index=True)

    # 依 year_month 分組，計算排名 (1=最大)
    dfTWMVmean['rank'] = dfTWMVmean.groupby('year_month')['mean_market_value'] \
                .rank(method='min', ascending=False)

    # 輸出含排名的完整資料
    dfTWMVmean.to_csv(outputPath, index=False, encoding='utf-8')

    # 輸出成CSV
    dfTWMVmean.to_csv(outputPath, index=False, encoding='utf-8')
    print("✅ 檔案存取成功：", outputPath)

### 取出每個月前n大市值的名單
maxIncludeRank = 200
outputPath = f'{outputDir}/TWMV_mean-{sDt.strftime("%Y%m")}_{eDt.strftime("%Y%m")}-rank{maxIncludeRank}.csv'
if os.path.exists(outputPath):
    dfTWMVrank = pd.read_csv(outputPath)
    print("☑️ 檔案已存在：", outputPath)
else:
    # 篩選 rank < 200
    dfTWMVrank = dfTWMVmean[dfTWMVmean['rank'] <= 200]

    # 輸出篩選結果
    dfTWMVrank.to_csv(outputPath, index=False, encoding='utf-8')
    print("✅ 檔案存取成功：", outputPath)

# ### 撈取FindMind的調整後股價資料  => DONE
# outputDir = r'..\data\FinMind\TW\DailyPriceAdj'
# stockList = dfTWMVrank['stock_id'].drop_duplicates().tolist()
# print("📢 即將撈取[歷史修正股價]資料，股票清單的長度為：", len(stockList))
# for stock_id in stockList:
#     outputFile = f'{outputDir}/{sDt.strftime("%Y%m%d")}-{eDt.strftime("%Y%m%d")}/TWDPadj-{stock_id}.csv'
#     if os.path.exists(outputFile):
#         print("☑️ 檔案已存在：", outputFile)
#     else:
#         os.makedirs(os.path.dirname(outputFile), exist_ok=True)  # 確保資料夾存在
#         try:
#             # 嘗試一次抓全部資料
#             dfSDA = api.taiwan_stock_daily_adj(
#                 stock_id=stock_id,
#                 start_date=sDt.strftime("%Y-%m-%d"),
#                 end_date=eDt.strftime("%Y-%m-%d")
#             )
#             # 如果沒報錯就直接存檔
#             dfSDA.to_csv(outputFile, index=False, encoding='utf-8-sig')
#             print("✅ 檔案存取成功：", outputFile)
#         except Exception as e:
#             print(f"⚠️ 一次抓取失敗：{stock_id}，錯誤訊息：{e}")
#             # 分段再試
#             try:
#                 # 分成兩段
#                 midDt = sDt + timedelta(days=365 * 5)
#                 print(f"➡️ 嘗試分段抓取 {stock_id} 第1段：{sDt.date()} ~ {midDt.date()}")
#                 dfSDA1 = api.taiwan_stock_daily_adj(
#                     stock_id=stock_id,
#                     start_date=sDt.strftime("%Y-%m-%d"),
#                     end_date=midDt.strftime("%Y-%m-%d")
#                 )
#                 print(f"➡️ 嘗試分段抓取 {stock_id} 第2段：{(midDt + timedelta(days=1)).date()} ~ {eDt.date()}")
#                 dfSDA2 = api.taiwan_stock_daily_adj(
#                     stock_id=stock_id,
#                     start_date=(midDt + timedelta(days=1)).strftime("%Y-%m-%d"),
#                     end_date=eDt.strftime("%Y-%m-%d")
#                 )
#                 # 合併兩段
#                 dfSDA = pd.concat([dfSDA1, dfSDA2], ignore_index=True)
#                 # 儲存
#                 dfSDA.to_csv(outputFile, index=False, encoding='utf-8-sig')
#                 print("✅ 分段抓取並合併成功：", outputFile)

#             except Exception as e2:
#                 print(f"❌ 分段抓取失敗：{stock_id}，錯誤訊息：{e2}")
#                 # 不要 raise，直接繼續跑下一支
#                 continue

# ### 將收盤價按年整理 => DONE
# # 年度範圍
# startYear = int(sDt.strftime("%Y"))
# endYear = int(eDt.strftime("%Y"))

# # 資料來源和目標資料夾
# source_folder = Path(r"..\data\FinMind\TW\DailyPriceAdj\20100101-20201231")
# target_folder = Path(r"..\data\analysis\summary")
# target_folder.mkdir(parents=True, exist_ok=True)

# # 預先建立年份的空清單
# year_data_dict = {year: [] for year in range(startYear, endYear + 1)}

# # 取得所有 csv
# csv_files = sorted(source_folder.glob("TWDPadj-*.csv"))
# print("📢 即將處理的股價資料檔案數：", len(csv_files))

# # 遍歷所有檔案
# for file in csv_files:
#     print("讀取檔案：", file.name)
#     df = pd.read_csv(file)

#     # 只取 date, stock_id, close
#     df = df.loc[:, ["date", "stock_id", "close"]]

#     # 將日期轉成 datetime
#     df["date"] = pd.to_datetime(df["date"])

#     # 按行分配到對應年份
#     for year in range(startYear, endYear + 1):
#         # 篩選該年份的資料
#         df_year = df[df["date"].dt.year == year]
#         if not df_year.empty:
#             year_data_dict[year].append(df_year)

# # 輸出每年檔案
# for year in range(startYear, endYear + 1):
#     if year_data_dict[year]:
#         year_df = pd.concat(year_data_dict[year], ignore_index=True)
#         output_file = target_folder / f"closePrice_{year}.csv"
#         if os.path.exists(output_file):
#             print(f"☑️ 檔案已存在：：{output_file}")
#         else:
#             year_df.to_csv(output_file, index=False, encoding="utf-8-sig")
#             print(f"✅ 檔案存取成功：{output_file}")
#     else:
#         print(f"⚠️ 沒有資料：{year}")

