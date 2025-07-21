import sys
import os
from datetime import datetime
import pandas as pd
from common import utils
from common import finMind
import re
from pathlib import Path
from collections import defaultdict

storageDir_twMarketValue =  f"../data/FinMind/TW/MarketValue"
os.makedirs(storageDir_twMarketValue, exist_ok=True)

storageDir = "../data/analysis"
os.makedirs(storageDir, exist_ok=True)

storageDir_summary =  f"{storageDir}/summary"

# # 計算各股票市值各月平均資料
# def twMarketValueMean(stockList:list, sDt:datetime, eDt:datetime) -> pd.DataFrame:
#     dfTWMVmean = None
#     runDataResult = finMind.runTwMarketValue(stockList, sDt, eDt)
#     if not runDataResult:
#         return dfTWMVmean

#     output_path = f"{storageDir_summary}/TWMV_mean-{sDt.strftime("%Y%m")}_{eDt.strftime("%Y%m")}.csv"
#     dataExist = False
#     if os.path.exists(output_path):
#         dfTWMVmean = pd.read_csv(output_path)
#         utils.ptMsg("☑️ 檔案已存在：" + output_path)   
#         dataExist = True 
#     else:
#         outputDir = os.path.dirname(output_path)
#         # 查看有沒有範圍更廣的資料區間
#         file_list = os.listdir(outputDir)

#         # 正則表達式：匹配 TWMV_mean-yyyymm_yyyymm.csv
#         pattern = re.compile(r"^TWMV_mean-(\d{6})_(\d{6})\.csv$")

#         # 找符合的檔案
#         matching_files = [f for f in file_list if pattern.match(f)]
#         if matching_files:
#             for f in matching_files:
#                 timeRange = utils.getSdtEdt(f)
#                 sDtInRange = utils.inTimeRange(sDt, timeRange.get("sDt"), timeRange.get("eDt"))
#                 dDtInRange = utils.inTimeRange(eDt, timeRange.get("sDt"), timeRange.get("eDt"))
#                 if sDtInRange and dDtInRange:
#                     dfTWMVmean = pd.read_csv(f'{outputDir}/{f}')
#                     utils.ptMsg("☑️ 已讀入既有檔案：" + f'{outputDir}/{f}') 
#                     dataExist = True  
#                     break
                
#     if not dataExist:
#         # 資料夾路徑
#         marketValDataDir = f'{storageDir_twMarketValue}/{sDt.strftime("%Y%m%d")}-{eDt.strftime("%Y%m%d")}'
#         marketValFolder = Path(marketValDataDir)

#         # 找到所有 CSV 檔案
#         TWMVfiles = list(marketValFolder.glob('*.csv'))
#         utils.ptMsg("找到的檔案：", TWMVfiles)

#         # 存放所有檔案的結果
#         marketValMeans = []

#         for aTWMVfile in TWMVfiles:
#             # 檢查檔案大小
#             if aTWMVfile.stat().st_size == 0:
#                 utils.ptMsg(f"檔案 {aTWMVfile} 是空的，跳過")
#                 continue

#             # 讀入資料
#             try:
#                 dfTWMVmean = pd.read_csv(aTWMVfile)
#             except pd.errors.EmptyDataError:
#                 utils.ptMsg(f"檔案 {aTWMVfile} 無資料，跳過")
#                 continue

#             if dfTWMVmean.empty:
#                 utils.ptMsg(f"檔案 {aTWMVfile} 內容為空，跳過")
#                 continue

#             if 'market_value' not in dfTWMVmean.columns:
#                 utils.ptMsg(f"檔案 {aTWMVfile} 缺少 market_value 欄位，跳過")
#                 continue
                
#             # 排除 market_value == 0
#             dfTWMVmean = dfTWMVmean[dfTWMVmean['market_value'] != 0]
            
#             # 轉成 datetime
#             dfTWMVmean['date'] = pd.to_datetime(dfTWMVmean['date'])
            
#             # 產生 year_month 欄位 (YYYY-MM)
#             dfTWMVmean['year_month'] = dfTWMVmean['date'].dt.strftime('%Y-%m')
            
#             # 以 year_month 分組計算平均
#             grouped = dfTWMVmean.groupby('year_month')['market_value'].mean().reset_index()
            
#             # 加上 stock_id (每檔資料都是同一個 stock_id)
#             stock_id = dfTWMVmean['stock_id'].iloc[0]
#             grouped['stock_id'] = stock_id
            
#             # 改欄位順序
#             grouped = grouped[['stock_id', 'year_month', 'market_value']]
            
#             # 改欄位名稱
#             grouped = grouped.rename(columns={'market_value': 'mean_market_value'})
            
#             # 加到總表
#             marketValMeans.append(grouped)

#         # 合併所有結果
#         dfTWMVmean = pd.concat(marketValMeans, ignore_index=True)

#         # 依 year_month 分組，計算排名 (1=最大)
#         dfTWMVmean['rank'] = dfTWMVmean.groupby('year_month')['mean_market_value'] \
#                     .rank(method='min', ascending=False)

#         # 輸出含排名的完整資料
#         dfTWMVmean.to_csv(output_path, index=False, encoding='utf-8')

#         # 輸出成CSV
#         dfTWMVmean.to_csv(output_path, index=False, encoding='utf-8')
#         utils.ptMsg("✅ 檔案存取成功：", output_path)

#     return dfTWMVmean

def twMarketValueMean(stockList: list, sDt: datetime, eDt: datetime) -> pd.DataFrame:
    runDataResult = finMind.runTwMarketValue(stockList, sDt, eDt)
    if not runDataResult:
        return None

    utils.ptMsg("📢 即將逐月計算與存檔 [平均市值 + 排名] 資料：")

    marketValDataDir = Path(storageDir_twMarketValue)
    summaryDir = Path(storageDir_summary)

    summaryFrames = []

    current_month = sDt.replace(day=1)
    end_month = eDt.replace(day=1)

    while current_month <= end_month:
        year_folder = marketValDataDir / str(current_month.year)
        month_str = current_month.strftime('%Y%m')

        monthly_results = []

        for stock_id in stockList:
            csv_file = year_folder / f"{month_str}/TWMV-{stock_id}.csv"

            if not csv_file.exists() or csv_file.stat().st_size == 0:
                continue

            try:
                dfTWMV = pd.read_csv(csv_file)
            except Exception as e:
                utils.ptMsg(f"⚠️ 檔案讀取失敗：{csv_file}，原因：{e}")
                continue

            if dfTWMV.empty or 'market_value' not in dfTWMV.columns:
                continue

            dfTWMV = dfTWMV[dfTWMV['market_value'] != 0]
            if dfTWMV.empty:
                continue

            dfTWMV['date'] = pd.to_datetime(dfTWMV['date'])
            dfTWMV['year_month'] = dfTWMV['date'].dt.strftime('%Y-%m')

            avg_value = dfTWMV['market_value'].mean()

            monthly_results.append({
                'stock_id': stock_id,
                'year_month': dfTWMV['year_month'].iloc[0],
                'mean_market_value': avg_value
            })

        if monthly_results:
            dfMonth = pd.DataFrame(monthly_results)
            dfMonth['rank'] = dfMonth['mean_market_value'].rank(method='min', ascending=False)

            # 儲存當月結果
            month_summary_folder = summaryDir / str(current_month.year)
            month_summary_folder.mkdir(parents=True, exist_ok=True)
            output_file = month_summary_folder / f"TWMV_mean-{month_str}.csv"

            dfMonth.to_csv(output_file, index=False, encoding='utf-8-sig')
            utils.ptMsg(f"✅ 月份 {month_str} 統計完成並儲存：{output_file}")

            summaryFrames.append(dfMonth)

        # 下一個月
        next_month = current_month.month % 12 + 1
        next_year = current_month.year + (current_month.month // 12)
        current_month = current_month.replace(year=next_year, month=next_month, day=1)

    if not summaryFrames:
        utils.ptMsg("❌ 沒有任何月份成功處理。")
        return None

    # 最後合併所有月份結果
    dfTWMVmean = pd.concat(summaryFrames, ignore_index=True)
    return dfTWMVmean

# 每個月前n大市值的名單
def twMarketValueSpeRankList(stockList:list, sDt:datetime, eDt:datetime, maxRank:int=0) -> pd.DataFrame:
    dfTWMVmean = twMarketValueMean(stockList, sDt, eDt)
    
    if maxRank <= 0:
        return dfTWMVmean      

    dfTWMVrank = None
    outputDir = storageDir_summary
    output_path = f'{outputDir}/TWMV_mean-{sDt.strftime("%Y%m")}_{eDt.strftime("%Y%m")}-rank{maxRank}.csv'
    dataExist = False
    
    if os.path.exists(output_path):
        dfTWMVrank = pd.read_csv(output_path)
        utils.ptMsg("☑️ 檔案已存在：" + output_path)
        dataExist = True
    else:
        # 查看有沒有範圍更廣的資料區間
        file_list = os.listdir(outputDir)

        # 正則表達式：匹配 TWMV_mean-yyyymm_yyyymm-rankXXX.csv
        pattern = re.compile(rf"^TWMV_mean-(\d{{6}})_(\d{{6}})-rank{maxRank}\.csv$")

        # 找符合的檔案
        matching_files = [f for f in file_list if pattern.match(f)]
        if matching_files:
            for f in matching_files:
                timeRange = utils.getSdtEdt(f)
                sDtInRange = utils.inTimeRange(sDt, timeRange.get("sDt"), timeRange.get("eDt"))
                dDtInRange = utils.inTimeRange(eDt, timeRange.get("sDt"), timeRange.get("eDt"))
                if sDtInRange and dDtInRange:
                    dfTWMVrank = pd.read_csv(f'{outputDir}/{f}')
                    utils.ptMsg("☑️ 已讀入既有檔案：" + f'{outputDir}/{f}')   
                    dataExist = True
                    break    

    if not dataExist:
        # 篩選 rank <= maxIncludeRank
        dfTWMVrank = dfTWMVmean[dfTWMVmean['rank'] <= maxRank]

        # 輸出篩選結果
        dfTWMVrank.to_csv(output_path, index=False, encoding='utf-8')
        utils.ptMsg("✅ 檔案存取成功：", output_path)

    return dfTWMVrank


# 每個月前n%市值的名單 TODO！！！
def twMarketValueTopList(stockList:list, sDt:datetime, eDt:datetime, topPercent:int=0) -> pd.DataFrame:
    dfTWMVmean = twMarketValueMean(stockList, sDt, eDt)
    
    if topPercent <= 0:
        return dfTWMVmean      

    dfTWMVrank = None
    outputDir = storageDir_summary
    output_path = f'{outputDir}/TWMV_mean-{sDt.strftime("%Y%m")}_{eDt.strftime("%Y%m")}-top{topPercent}.csv'
    dataExist = False
    
    if os.path.exists(output_path):
        dfTWMVrank = pd.read_csv(output_path)
        utils.ptMsg("☑️ 檔案已存在：" + output_path)
        dataExist = True
    else:
        # 查看有沒有範圍更廣的資料區間
        file_list = os.listdir(outputDir)

        # 正則表達式：匹配 TWMV_mean-yyyymm_yyyymm-rankXXX.csv
        pattern = re.compile(rf"^TWMV_mean-(\d{{6}})_(\d{{6}})-top{topPercent}\.csv$")

        # 找符合的檔案
        matching_files = [f for f in file_list if pattern.match(f)]
        if matching_files:
            for f in matching_files:
                timeRange = utils.getSdtEdt(f)
                sDtInRange = utils.inTimeRange(sDt, timeRange.get("sDt"), timeRange.get("eDt"))
                dDtInRange = utils.inTimeRange(eDt, timeRange.get("sDt"), timeRange.get("eDt"))
                if sDtInRange and dDtInRange:
                    dfTWMVrank = pd.read_csv(f'{outputDir}/{f}')
                    utils.ptMsg("☑️ 已讀入既有檔案：" + f'{outputDir}/{f}')   
                    dataExist = True
                    break    

    if not dataExist:
        # 篩選 rank <= maxIncludeRank
        dfTWMVrank = dfTWMVmean[dfTWMVmean['rank'] <= maxRank]

        # 輸出篩選結果
        dfTWMVrank.to_csv(output_path, index=False, encoding='utf-8')
        utils.ptMsg("✅ 檔案存取成功：", output_path)

    return dfTWMVrank


# 將收盤價按年整理
def runTwClosePriceByYear(sDt:datetime, eDt:datetime) -> bool:
    result = True

    try:
        # 年度範圍
        startYear = int(sDt.strftime("%Y"))
        endYear = int(eDt.strftime("%Y"))

        # 資料來源和目標資料夾
        source_folder = Path(f"../data/FinMind/TW/DailyPriceAdj/{sDt.strftime("%Y%m%d")}-{eDt.strftime("%Y%m%d")}")
        target_folder = Path(storageDir_summary)
        target_folder.mkdir(parents=True, exist_ok=True)

        # 預先建立年份的空清單
        year_data_dict = {year: [] for year in range(startYear, endYear + 1)}

        # 取得所有 csv
        csv_files = sorted(source_folder.glob("TWDPadj-*.csv"))
        utils.ptMsg("📢 即將處理的股價資料檔案數：", len(csv_files))

        # 遍歷所有檔案
        for file in csv_files:
            utils.ptMsg("讀取檔案：", file.name)
            df = pd.read_csv(file)

            # 只取 date, stock_id, close
            df = df.loc[:, ["date", "stock_id", "close"]]

            # 將日期轉成 datetime
            df["date"] = pd.to_datetime(df["date"])

            # 按行分配到對應年份
            for year in range(startYear, endYear + 1):
                # 篩選該年份的資料
                df_year = df[df["date"].dt.year == year]
                if not df_year.empty:
                    year_data_dict[year].append(df_year)

        # 輸出每年檔案
        for year in range(startYear, endYear + 1):
            if year_data_dict[year]:
                year_df = pd.concat(year_data_dict[year], ignore_index=True)
                output_file = target_folder / f"closePrice_{year}.csv"
                if os.path.exists(output_file):
                    utils.ptMsg(f"☑️ 檔案已存在：：{output_file}")
                else:
                    year_df.to_csv(output_file, index=False, encoding="utf-8-sig")
                    utils.ptMsg(f"✅ 檔案存取成功：{output_file}")
            else:
                utils.ptMsg(f"⚠️ 沒有資料：{year}")
    except Exception as e:
        utils.ptMsg(f"發生錯誤：{e}")
        return False

    return result

# 將收盤價按月整理
def runTwClosePriceByMonth(sDt: datetime, eDt: datetime) -> bool:
    result = True

    try:
        # 準備目標資料夾
        target_folder = Path(storageDir_summary)
        target_folder.mkdir(parents=True, exist_ok=True)

        # 年度範圍
        start_year = sDt.year
        end_year = eDt.year

        for year in range(start_year, end_year + 1):
            source_folder = Path(f"../data/FinMind/TW/DailyPriceAdj/{year}")
            csv_files = sorted(source_folder.glob("TWDPadj-*.csv"))
            utils.ptMsg(f"📅 處理年度：{year}，股票檔案數：{len(csv_files)}")

            # 建立當年內所有月份的暫存區
            month_data_dict = defaultdict(list)

            for file in csv_files:
                utils.ptMsg("讀取檔案：", file.name)
                try:
                    df = pd.read_csv(file)
                    df = df.loc[:, ["date", "stock_id", "close"]]    
                except Exception as e1:
                    utils.ptMsg(f"發生錯誤(1)：{e1}")
                    continue
                
                df["date"] = pd.to_datetime(df["date"])

                # 將資料依年月分類
                df["yyyymm"] = df["date"].dt.strftime("%Y%m")
                for yyyymm, group in df.groupby("yyyymm"):
                    # 檢查是否在日期範圍內
                    group_date = pd.to_datetime(yyyymm + "01")
                    if not (sDt <= group_date <= eDt):
                        continue
                    month_data_dict[yyyymm].append(group.drop(columns="yyyymm"))

            # 將當年各月份資料輸出
            for yyyymm, data_list in month_data_dict.items():
                output_file = target_folder / f"closePrice_{yyyymm}.csv"

                if output_file.exists():
                    utils.ptMsg(f"⏩ 檔案已存在，跳過：{output_file}")
                    continue

                month_df = pd.concat(data_list, ignore_index=True)
                month_df.to_csv(output_file, index=False, encoding="utf-8-sig")
                utils.ptMsg(f"✅ 檔案存取成功：{output_file}")

    except Exception as e:
        utils.ptMsg(f"發生錯誤：{e}")
        return False

    return result

# 計算每月平均收盤價（以年為單位存檔）
def runAdjPriceMeanByMonth(sDt: datetime, eDt: datetime, filterMeanClose: int=0) -> bool:
    result = True
    try:
        baseDataDir = Path("../data/FinMind/TW/DailyPriceAdj")
        outputDir = Path("../data/analysis/summary/adjPriceMeanByMonth")
        outputDir.mkdir(parents=True, exist_ok=True)

        cur_year = sDt.year
        end_year = eDt.year

        while cur_year <= end_year:
            year_folder = baseDataDir / str(cur_year)
            if not year_folder.exists():
                utils.ptMsg(f"⚠️ 缺少資料夾：{year_folder}，跳過 {cur_year}")
                cur_year += 1
                continue

            allFiles = list(year_folder.glob("TWDPadj-*.csv"))
            if not allFiles:
                utils.ptMsg(f"⚠️ 無股價檔案：{year_folder}，跳過 {cur_year}")
                cur_year += 1
                continue

            monthlyResults = []

            for file in allFiles:
                try:
                    df = pd.read_csv(file)

                    if df.empty or 'close' not in df.columns or 'date' not in df.columns:
                        utils.ptMsg(f"⚠️ 檔案無效，跳過：{file}")
                        continue

                    # 清理資料
                    df = df[['date', 'stock_id', 'close']].dropna()

                    # 排除極端值（例如負數或極端大值）
                    df = df[(df['close'] > 0) & (df['close'] < 1e5)]

                    if df.empty:
                        utils.ptMsg(f"⚠️ 清理後無有效資料，跳過：{file}")
                        continue

                    df['date'] = pd.to_datetime(df['date'], errors='coerce')
                    df = df.dropna(subset=['date'])

                    df['year_month'] = df['date'].dt.strftime('%Y%m')

                    stock_id = str(df['stock_id'].iloc[0])

                    # 月平均計算
                    grouped = df.groupby('year_month')['close'].mean().reset_index()
                    grouped['stock_id'] = stock_id
                    grouped = grouped[['year_month', 'stock_id', 'close']]
                    grouped = grouped.rename(columns={'close': 'mean_close'})

                    monthlyResults.append(grouped)

                except Exception as e:
                    utils.ptMsg(f"⚠️ 檔案處理失敗：{file}，錯誤：{e}")
                    continue

            if monthlyResults:
                dfYear = pd.concat(monthlyResults, ignore_index=True)
                output_file = outputDir / f"{cur_year}.csv"
                dfYear.to_csv(output_file, index=False, encoding='utf-8-sig')
                utils.ptMsg(f"✅ {cur_year} 年資料統計完成，存檔：{output_file}")

                if filterMeanClose > 0:
                # 過濾出 mean_close > filterMeanClose 的資料
                    df_filtered = dfYear[dfYear['mean_close'] > filterMeanClose]

                    # 另存為檔案
                    output_file = outputDir / f"{cur_year}_meanOver{filterMeanClose}.csv"
                    df_filtered.to_csv(output_file, index=False, encoding='utf-8-sig')
                    utils.ptMsg(f"✅ 過濾mean_close > 30以的資料，存檔：{output_file}")
            else:
                utils.ptMsg(f"⚠️ {cur_year} 年無任何有效資料，未輸出檔案。")

            cur_year += 1

    except Exception as e:
        utils.ptMsg(f"❌ 發生錯誤：{e}")
        return False

    return result

