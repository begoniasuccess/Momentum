import sys
import os
from datetime import datetime
import pandas as pd
from common import utils
from common import finMind
import re
from pathlib import Path
from collections import defaultdict
from dateutil.relativedelta import relativedelta

storageDir_twMarketValue =  f"../data/FinMind/TW/MarketValue"
os.makedirs(storageDir_twMarketValue, exist_ok=True)

storageDir = "../data/analysis"
os.makedirs(storageDir, exist_ok=True)

storageDir_summary =  f"{storageDir}/summary"

# 計算各股票市值各月平均資料
def twMarketValueMean(stockList: list, sDt: datetime, eDt: datetime) -> pd.DataFrame:
    dfTWMVmean = None
    storageDir_summary = "../data/analysis/summary"
    output_path = f"{storageDir_summary}/TWMV_mean-{sDt.strftime('%Y%m')}_{eDt.strftime('%Y%m')}.csv"

    # ✅ 若檔案已存在，直接讀取
    if os.path.exists(output_path):
        dfTWMVmean = pd.read_csv(output_path)
        utils.ptMsg("☑️ 檔案已存在：" + output_path)
        return dfTWMVmean

    # ✅ 檢查是否已有覆蓋區間的檔案
    outputDir = os.path.dirname(output_path)
    file_list = os.listdir(outputDir)
    pattern = re.compile(r"^TWMV_mean-(\d{6})_(\d{6})\.csv$")
    matching_files = [f for f in file_list if pattern.match(f)]

    for f in matching_files:
        timeRange = utils.getSdtEdt(f)
        sDtInRange = utils.inTimeRange(sDt, timeRange.get("sDt"), timeRange.get("eDt"))
        eDtInRange = utils.inTimeRange(eDt, timeRange.get("sDt"), timeRange.get("eDt"))
        if sDtInRange and eDtInRange:
            dfTWMVmean = pd.read_csv(f'{outputDir}/{f}')
            utils.ptMsg("☑️ 已讀入既有檔案：" + f'{outputDir}/{f}')
            return dfTWMVmean

    # ✅ 執行資料準備
    runDataResult = finMind.runTwMarketValue(stockList, sDt, eDt)
    if not runDataResult:
        return None

    # ✅ 合併資料
    base_dir = "../data/FinMind/TW/MarketValue"
    all_data = []

    for stock_id in stockList:
        for y in range(sDt.year, eDt.year + 1):
            file_path = f"{base_dir}/{y}/TWMV-{stock_id}.csv"
            if not os.path.exists(file_path):
                continue
            try:
                df = pd.read_csv(file_path)
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df = df.dropna(subset=['date', 'market_value'])
                df = df[(df['date'] >= sDt) & (df['date'] <= eDt)]
                all_data.append(df)
            except Exception as e:
                print(f"❌ 無法讀取 {file_path}，錯誤：{e}")
                continue

    if not all_data:
        print("⚠️ 無任何有效資料可用")
        return None

    df_all = pd.concat(all_data, ignore_index=True)

    # ✅ 處理資料：加上年月欄位、排除市值為 0 或負數
    df_all['year_month'] = df_all['date'].dt.strftime('%Y%m')
    df_all = df_all[df_all['market_value'] > 0]

    # ✅ 計算平均市值
    dfTWMVmean = df_all.groupby(['stock_id', 'year_month'], as_index=False)['market_value'].mean()

    # ✅ 儲存結果
    dfTWMVmean.to_csv(output_path, index=False)
    utils.ptMsg("✅ 已儲存平均市值檔案：" + output_path)

    return dfTWMVmean


# 每個月前n大市值的名單
def twMarketValueSpeRankList(stockList:list, sDt:datetime, eDt:datetime, maxRank:int=0) -> pd.DataFrame:
    dfTWMVrank = None
    outputDir = storageDir_summary
    output_path = f'{outputDir}/TWMV_mean-{sDt.strftime("%Y%m")}_{eDt.strftime("%Y%m")}-rank{maxRank}.csv'
    dataExist = False
    
    if os.path.exists(output_path):
        dfTWMVrank = pd.read_csv(output_path)
        utils.ptMsg("☑️ 檔案已存在：" + output_path)
        return dfTWMVrank

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
        dfTWMVmean = twMarketValueMean(stockList, sDt, eDt)    
        if maxRank <= 0:
            return dfTWMVmean
              
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
def runTwClosePriceByYear(sDt: datetime, eDt: datetime) -> bool:
    result = True

    try:
        # 年度範圍
        startYear = int(sDt.strftime("%Y"))
        endYear = int(eDt.strftime("%Y"))

        # 目標資料夾
        target_folder = Path(storageDir_summary)
        target_folder.mkdir(parents=True, exist_ok=True)

        # 預先建立年份的空清單
        year_data_dict = {year: [] for year in range(startYear, endYear + 1)}

        total_files = 0

        for year in range(startYear, endYear + 1):
            source_folder = Path(f"../data/FinMind/TW/DailyPriceAdj/{year}")
            if not source_folder.exists():
                utils.ptMsg(f"⚠️ 資料夾不存在：{source_folder}")
                continue

            csv_files = sorted(source_folder.glob("TWDPadj-*.csv"))
            utils.ptMsg(f"📢 {year}年 檔案數：", len(csv_files))
            total_files += len(csv_files)

            for file in csv_files:
                utils.ptMsg("讀取檔案：", file.name)
                try:
                    df = pd.read_csv(file)
                except pd.errors.EmptyDataError:
                    utils.ptMsg(f"⚠️ 檔案為空，跳過：{file.name}")
                    continue

                if df.empty:
                    utils.ptMsg(f"⚠️ 檔案內容為空，跳過：{file.name}")
                    continue

                if not set(["date", "stock_id", "close"]).issubset(df.columns):
                    utils.ptMsg(f"⚠️ 檔案欄位缺失，跳過：{file.name}")
                    continue

                df = df.loc[:, ["date", "stock_id", "close"]]
                df["date"] = pd.to_datetime(df["date"], errors='coerce')
                df = df.dropna(subset=["date"])

                df_year = df[df["date"].dt.year == year]
                if not df_year.empty:
                    year_data_dict[year].append(df_year)

        utils.ptMsg("📊 總處理檔案數：", total_files)

        for year in range(startYear, endYear + 1):
            if year_data_dict[year]:
                year_df = pd.concat(year_data_dict[year], ignore_index=True)
                output_file = target_folder / f"closePrice_{year}.csv"
                if output_file.exists():
                    utils.ptMsg(f"☑️ 檔案已存在：：{output_file}")
                else:
                    year_df.to_csv(output_file, index=False, encoding="utf-8-sig")
                    utils.ptMsg(f"✅ 檔案存取成功：{output_file}")
            else:
                utils.ptMsg(f"⚠️ {year}年 沒有任何股價資料。")

    except Exception as e:
        utils.ptMsg(f"發生錯誤：{e}")
        return False

    return result


# 將收盤價按月整理
def runTwClosePriceByMonth(sDt: datetime, eDt: datetime) -> bool:
    result = True

    try:
        # 準備目標資料夾
        target_folder = Path(storageDir_summary + "/closePirce")
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
                    os.remove(file)
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
