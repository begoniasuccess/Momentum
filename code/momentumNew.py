from FinMind.data import DataLoader
import pandas as pd
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pathlib import Path
import sys
from scipy import stats

### python momentumNew.py >> terminal_log.txt 2>&1
sys.stdout.reconfigure(encoding='utf-8')

### 策略參數設定
sDt = datetime.strptime('2010/01/01', "%Y/%m/%d") # Start Date
eDt = datetime.strptime('2020/12/31', "%Y/%m/%d") # End Date
oPeriod = 3 # Observer Period
hPeriod = 3 # Holding Period
planType = "A" # A 

# ### FinMind api設定
# apiUrl = "https://api.finmindtrade.com/api/v4/data"
# api = DataLoader()
# token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNS0wNi0yOCAxNToyODoxMSIsInVzZXJfaWQiOiJueWN1bGFiNjE1IiwiaXAiOiIxMTQuMTM3LjIxOS4yMTEiLCJleHAiOjE3NTE3MDA0OTF9.u4s5jxRFBz2ojJ01n-8c6Jm2G0FAhtn1-gSMsaspZWE"
# api.login_by_token(api_token=token)

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


# ### 算出每個月各股票的平均市值
# outputDir = r'..\data\analysis\summary'
# outputPath = f'{outputDir}/TWMV_mean-{sDt.strftime("%Y%m")}_{eDt.strftime("%Y%m")}.csv'
# if os.path.exists(outputPath):
#     dfTWMVmean = pd.read_csv(outputPath)
#     print("☑️ 檔案已存在：", outputPath)    
# else:
#     # 資料夾路徑
#     marketValDataDir = f'../data/FinMind/TW/MarketValue/{sDt.strftime("%Y%m%d")}-{eDt.strftime("%Y%m%d")}'
#     marketValFolder = Path(marketValDataDir)

#     # 找到所有 CSV 檔案
#     TWMVfiles = list(marketValFolder.glob('*.csv'))
#     print("找到的檔案：", TWMVfiles)

#     # 存放所有檔案的結果
#     marketValMeans = []

#     for aTWMVfile in TWMVfiles:
#         # 檢查檔案大小
#         if aTWMVfile.stat().st_size == 0:
#             print(f"檔案 {aTWMVfile} 是空的，跳過")
#             continue

#         # 讀入資料
#         try:
#             dfTWMVmean = pd.read_csv(aTWMVfile)
#         except pd.errors.EmptyDataError:
#             print(f"檔案 {aTWMVfile} 無資料，跳過")
#             continue

#         if dfTWMVmean.empty:
#             print(f"檔案 {aTWMVfile} 內容為空，跳過")
#             continue

#         if 'market_value' not in dfTWMVmean.columns:
#             print(f"檔案 {aTWMVfile} 缺少 market_value 欄位，跳過")
#             continue
            
#         # 排除 market_value == 0
#         dfTWMVmean = dfTWMVmean[dfTWMVmean['market_value'] != 0]
        
#         # 轉成 datetime
#         dfTWMVmean['date'] = pd.to_datetime(dfTWMVmean['date'])
        
#         # 產生 year_month 欄位 (YYYY-MM)
#         dfTWMVmean['year_month'] = dfTWMVmean['date'].dt.strftime('%Y-%m')
        
#         # 以 year_month 分組計算平均
#         grouped = dfTWMVmean.groupby('year_month')['market_value'].mean().reset_index()
        
#         # 加上 stock_id (每檔資料都是同一個 stock_id)
#         stock_id = dfTWMVmean['stock_id'].iloc[0]
#         grouped['stock_id'] = stock_id
        
#         # 改欄位順序
#         grouped = grouped[['stock_id', 'year_month', 'market_value']]
        
#         # 改欄位名稱
#         grouped = grouped.rename(columns={'market_value': 'mean_market_value'})
        
#         # 加到總表
#         marketValMeans.append(grouped)

#     # 合併所有結果
#     dfTWMVmean = pd.concat(marketValMeans, ignore_index=True)

#     # 依 year_month 分組，計算排名 (1=最大)
#     dfTWMVmean['rank'] = dfTWMVmean.groupby('year_month')['mean_market_value'] \
#                 .rank(method='min', ascending=False)

#     # 輸出含排名的完整資料
#     dfTWMVmean.to_csv(outputPath, index=False, encoding='utf-8')

#     # 輸出成CSV
#     dfTWMVmean.to_csv(outputPath, index=False, encoding='utf-8')
#     print("✅ 檔案存取成功：", outputPath)

# ### 取出每個月前n大市值的名單
# maxIncludeRank = 200
# outputPath = f'{outputDir}/TWMV_mean-{sDt.strftime("%Y%m")}_{eDt.strftime("%Y%m")}-rank{maxIncludeRank}.csv'
# if os.path.exists(outputPath):
#     dfTWMVrank = pd.read_csv(outputPath)
#     print("☑️ 檔案已存在：", outputPath)
# else:
#     # 篩選 rank < 200
#     dfTWMVrank = dfTWMVmean[dfTWMVmean['rank'] <= 200]

#     # 輸出篩選結果
#     dfTWMVrank.to_csv(outputPath, index=False, encoding='utf-8')
#     print("✅ 檔案存取成功：", outputPath)

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

### 計算觀察期報酬
target_folder = Path(r"..\data\analysis\momentumNew" + f"/oPeriod{oPeriod}_hPeriod{hPeriod}")
target_folder.mkdir(parents=True, exist_ok=True)
output_file = target_folder / f"observerReturnList{sDt.strftime("%Y%m")}_{eDt.strftime("%Y%m")}.csv"
if os.path.exists(output_file):
    result_df = pd.read_csv(output_file)
    print(f"☑️ 檔案已存在：：{output_file}")
else:    
    # 預先讀取所有年度檔案
    source_folder = Path(r"..\data\analysis\summary")
    data_by_year = {}
    for year in range(sDt.year, eDt.year + 1):
        file = source_folder / f"closePrice_{year}.csv"
        if file.exists():
            result_df = pd.read_csv(file, parse_dates=["date"])
            data_by_year[year] = result_df
            print(f"已讀取資料：{file}")
        else:
            print(f"⚠️ 找不到檔案：{file}")

    # 結果清單
    result_rows = []

    # 時間游標
    current_dt = sDt
    while current_dt <= eDt:
        year = current_dt.year
        month = current_dt.month

        df_year = data_by_year.get(year)
        if df_year is not None:
            df_month = df_year[
                (df_year["date"].dt.year == year) &
                (df_year["date"].dt.month == month)
            ]

            grouped = df_month.groupby("stock_id", as_index=False)
            first_trading_days = grouped.apply(lambda g: g.nsmallest(1, "date")).reset_index(drop=True)

            for _, row in first_trading_days.iterrows():
                stock_id = row["stock_id"]
                start_date = row["date"]

                # 計算 end_month
                end_month_dt = start_date + relativedelta(months=oPeriod - 1)
                end_year = end_month_dt.year
                end_month = end_month_dt.month

                df_end_year = data_by_year.get(end_year)
                if df_end_year is not None:
                    df_end_month = df_end_year[
                        (df_end_year["stock_id"] == stock_id) &
                        (df_end_year["date"].dt.year == end_year) &
                        (df_end_year["date"].dt.month == end_month)
                    ]

                    if not df_end_month.empty:
                        end_date = df_end_month["date"].max()
                        ED_close = df_end_month[df_end_month["date"] == end_date]["close"].values[0]
                    else:
                        end_date = pd.NaT
                        ED_close = ""
                else:
                    end_date = pd.NaT
                    ED_close = ""

                # 組合 combination
                comb_start = start_date.strftime("%Y%m")
                comb_end = (start_date + relativedelta(months=oPeriod)).strftime("%Y%m")
                combination = f"{comb_start}-{comb_end}"

                # 計算 return
                SD_close = row["close"]
                if ED_close != "":
                    ret = (ED_close - SD_close) / SD_close
                else:
                    ret = ""

                result_rows.append({
                    "stock_id": stock_id,
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d") if pd.notna(end_date) else "",
                    "SD_close": SD_close,
                    "ED_close": ED_close,
                    "combination": combination,
                    "return": ret
                })

        current_dt += relativedelta(months=1)

    # 結果DataFrame
    result_df = pd.DataFrame(result_rows)

    # 輸出
    result_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"✅ 已輸出檔案：{output_file}")

### 增加各種rank相關欄位
output_file = target_folder / f"observerReturnList{sDt.strftime("%Y%m")}_{eDt.strftime("%Y%m")}-rank.csv"
if os.path.exists(output_file):
    result_df = pd.read_csv(output_file)
    print(f"☑️ 檔案已存在：{output_file}")
else:
    # 確保 return 是 float
    result_df["return"] = pd.to_numeric(result_df["return"], errors="coerce")

    # 百分比排名 (0~100)
    def scale_to_0_100(x):
        min_val = x.min()
        max_val = x.max()
        if pd.isna(min_val) or pd.isna(max_val) or max_val == min_val:
            return pd.Series([None] * len(x), index=x.index)
        else:
            return (x - min_val) / (max_val - min_val) * 100

    # 計算 RT_%_Rank
    result_df["RT_%_Rank"] = result_df.groupby("combination")["return"].transform(scale_to_0_100)

    # remark 初始化
    result_df["remark"] = ""

    # 先標註 exclude
    exclude_mask = (result_df["RT_%_Rank"] > 99.9) | (result_df["RT_%_Rank"] < 0.1)
    result_df.loc[exclude_mask, "remark"] = "exclude"

    # 計算 RT_rank，注意：不先創欄位
    def compute_rt_rank(group):
        mask = group["remark"] != "exclude"
        # 只針對非 exclude 算排名
        ranks = pd.Series(index=group.index, dtype="float")
        ranks.loc[mask] = group.loc[mask, "return"].rank(method="min", ascending=False)
        group["RT_rank"] = ranks
        return group

    result_df = result_df.groupby("combination", group_keys=False).apply(compute_rt_rank)

    # 確保 RT_rank 是 numeric
    result_df["RT_rank"] = pd.to_numeric(result_df["RT_rank"], errors="coerce")

    # 更新 remark: winner / loser
    def mark_winner_loser(group):
        valid = group[group["remark"] != "exclude"]
        if valid.empty:
            return group

        n = len(valid)
        top_n = max(1, int(n * 0.1))
        bottom_n = max(1, int(n * 0.1))

        top_threshold = valid.nsmallest(top_n, "RT_rank")["RT_rank"].max()
        bottom_threshold = valid.nlargest(bottom_n, "RT_rank")["RT_rank"].min()

        # 只更新 valid 部分
        for idx in valid.index:
            rt_rank = group.loc[idx, "RT_rank"]
            if pd.isna(rt_rank):
                continue
            if rt_rank <= top_threshold:
                group.loc[idx, "remark"] = "winner"
            elif rt_rank >= bottom_threshold and rt_rank > top_threshold:
                group.loc[idx, "remark"] = "loser"

        return group

    result_df = result_df.groupby("combination", group_keys=False).apply(mark_winner_loser)

    # 輸出
    result_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"✅ 已輸出檔案：{output_file}")

### 產生winner_loser名單
output_file = target_folder / f"winner_loser-{sDt.strftime("%Y%m")}_{eDt.strftime("%Y%m")}.csv"
if os.path.exists(output_file):
    filtered_df = pd.read_csv(output_file)
    print(f"☑️ 檔案已存在：{output_file}")
else:
    # 篩選 remark 為 winner 或 loser
    filtered_df = result_df[result_df["remark"].isin(["winner", "loser"])]

    # 存成新檔
    filtered_df.to_csv(output_file, index=False, encoding="utf-8-sig")

    print(f"✅ 已輸出檔案：{output_file}")

### 計算持有期的報酬
output_file = Path(r"..\data\analysis\momentumNew\oPeriod3_hPeriod3\afterwardReturn-201001_202012.csv")
if os.path.exists(output_file):
    filtered_df = pd.read_csv(output_file)
    print(f"☑️ 檔案已存在：{output_file}")
else:
    price_folder = Path(r"..\data\analysis\summary")

    # 把日期字串轉成 datetime
    filtered_df["start_date_dt"] = pd.to_datetime(filtered_df["start_date"])
    filtered_df["end_date_dt"] = pd.to_datetime(filtered_df["end_date"])

    # 用於儲存結果
    start_date2_list = []
    SD_close2_list = []
    end_date2_list = []
    ED_close2_list = []

    # 處理每一列 
    for idx, row in filtered_df.iterrows():
        stock_id = row["stock_id"]

        # =============== start_date2 ==============
        sd2_month = row["start_date_dt"] + relativedelta(months=+hPeriod)
        sd2_year = sd2_month.year
        sd2_month_num = sd2_month.month

        price_file_sd2 = price_folder / f"closePrice_{sd2_year}.csv"
        try:
            price_df_sd2 = pd.read_csv(price_file_sd2, dtype={"stock_id": str})
            price_df_sd2["date_dt"] = pd.to_datetime(price_df_sd2["date"])

            sd2_candidates = price_df_sd2[
                (price_df_sd2["stock_id"] == stock_id) &
                (price_df_sd2["date_dt"].dt.month == sd2_month_num)
            ]
            if not sd2_candidates.empty:
                sd2_first = sd2_candidates.sort_values("date_dt").iloc[0]
                start_date2 = sd2_first["date"]
                SD_close2 = sd2_first["close"]
            else:
                start_date2 = None
                SD_close2 = None
        except FileNotFoundError:
            print(f"❌ 找不到檔案：{price_file_sd2}，填入 None")
            start_date2 = None
            SD_close2 = None

        start_date2_list.append(start_date2)
        SD_close2_list.append(SD_close2)

        # =============== end_date2 ==============
        ed2_month = row["end_date_dt"] + relativedelta(months=+hPeriod)
        ed2_year = ed2_month.year
        ed2_month_num = ed2_month.month

        price_file_ed2 = price_folder / f"closePrice_{ed2_year}.csv"
        try:
            price_df_ed2 = pd.read_csv(price_file_ed2, dtype={"stock_id": str})
            price_df_ed2["date_dt"] = pd.to_datetime(price_df_ed2["date"])

            ed2_candidates = price_df_ed2[
                (price_df_ed2["stock_id"] == stock_id) &
                (price_df_ed2["date_dt"].dt.month == ed2_month_num)
            ]
            if not ed2_candidates.empty:
                ed2_last = ed2_candidates.sort_values("date_dt").iloc[-1]
                end_date2 = ed2_last["date"]
                ED_close2 = ed2_last["close"]
            else:
                end_date2 = None
                ED_close2 = None
        except FileNotFoundError:
            print(f"❌ 找不到檔案：{price_file_ed2}，填入 None")
            end_date2 = None
            ED_close2 = None

        end_date2_list.append(end_date2)
        ED_close2_list.append(ED_close2)

    # 新增欄位
    filtered_df["start_date2"] = start_date2_list
    filtered_df["SD_close2"] = SD_close2_list
    filtered_df["end_date2"] = end_date2_list
    filtered_df["ED_close2"] = ED_close2_list

    # 轉數字
    filtered_df["SD_close2"] = pd.to_numeric(filtered_df["SD_close2"], errors="coerce")
    filtered_df["ED_close2"] = pd.to_numeric(filtered_df["ED_close2"], errors="coerce")

    # 計算 return2
    filtered_df["return2"] = (filtered_df["ED_close2"] - filtered_df["SD_close2"]) / filtered_df["SD_close2"]

    # 移除中間欄位
    filtered_df = filtered_df.drop(columns=["start_date_dt", "end_date_dt"])

    # 存檔
    output_file.parent.mkdir(parents=True, exist_ok=True)
    filtered_df.to_csv(output_file, index=False, encoding="utf-8-sig")

    print(f"✅ 已完成後續報酬計算，輸出至：{output_file}")

### 統計持有期間平均報酬
output_file = Path(r"..\data\analysis\momentumNew\oPeriod3_hPeriod3\afterwardReturn-201001_202012-static.csv")
if os.path.exists(output_file):
    grouped = pd.read_csv(output_file)
    print(f"☑️ 檔案已存在：{output_file}")
else:
    # 確保 return2 是數字型態
    filtered_df["return2"] = pd.to_numeric(filtered_df["return2"], errors="coerce")

    # 以 combination 和 remark 分組，計算每組的筆數(count)與平均(mean)
    grouped = (
        filtered_df.groupby(["combination", "remark"], dropna=False)
        .agg(
            count=("return2", "count"),
            mean_return2=("return2", "mean")
        )
        .reset_index()
    )

    # 移除 mean_return2 為 NaN 的組
    grouped = grouped.dropna(subset=["mean_return2"])

    # 輸出結果
    grouped.to_csv(output_file, index=False, encoding="utf-8-sig")

    print(f"✅ 統計已完成，檔案輸出：{output_file}")

### 計算winner - loser
output_file = Path(r"..\data\analysis\momentumNew\oPeriod3_hPeriod3\afterwardReturn-201001_202012-static2.csv")
if os.path.exists(output_file):
    new_df = pd.read_csv(output_file)
    print(f"☑️ 檔案已存在：{output_file}")
else:
    # 用於儲存新結果
    rows = []

    # 依 combination 分組
    for comb, group in grouped.groupby("combination"):
        # 先將原本的兩列放進去
        for _, row in group.iterrows():
            rows.append(row.to_dict())

        # 取得 winner 與 loser 的 mean_return2
        winner_row = group[group["remark"] == "winner"]
        loser_row = group[group["remark"] == "loser"]

        if not winner_row.empty and not loser_row.empty:
            winner_mean = winner_row["mean_return2"].values[0]
            loser_mean = loser_row["mean_return2"].values[0]
            diff = winner_mean - loser_mean

            # 新增一列資料
            rows.append({
                "combination": comb,
                "remark": "winner - loser",
                "count": "-",
                "mean_return2": diff
            })

    new_df = pd.DataFrame(rows)
    new_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"✅ 已輸出新檔案：{output_file}")

### t-test
output_file = Path(r"..\data\analysis\momentumNew\oPeriod3_hPeriod3\t_test_results.csv")
if os.path.exists(output_file):
    print(f"☑️ 檔案已存在：{output_file}")
else:
    # 移除多餘逗號
    new_df.columns = new_df.columns.str.strip()

    # 將 mean_return2 去掉 % 並轉成數值
    new_df["mean_return2"] = new_df["mean_return2"].str.replace("%", "").astype(float) / 100
    
    results = []

    # 分組 t檢定
    for remark in ["loser", "winner", "winner - loser"]:
        # 取出該 remark 資料
        values = new_df.loc[new_df["remark"] == remark, "mean_return2"].dropna().values
        n = len(values)
        if n > 1:
            t_stat, p_value = stats.ttest_1samp(values, popmean=0)
            mean = values.mean()
            results.append({
                "remark": remark,
                "n": n,
                "mean": mean,
                "t_stat": t_stat,
                "p_value": p_value
            })
        else:
            results.append({
                "remark": remark,
                "n": n,
                "mean": values.mean() if n == 1 else None,
                "t_stat": None,
                "p_value": None
            })
    
    result_df = pd.DataFrame(results)
    # print(result_df)

    result_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"✅ 已輸出結果：{output_file}")