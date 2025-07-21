import shutil
import math
from FinMind.data import DataLoader
import pandas as pd
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pathlib import Path
import sys
import glob
from scipy import stats
from common import utils
from common import finMind
from common import anaData
import re
from pandas.errors import EmptyDataError
import itertools

### in PowerShell：
# $OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
# python -u momentumNew.py 2>&1 | Tee-Object -FilePath ../log/terminal_log.txt -Append
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

# 起始訊息
print("")
utils.ptMsg("⚙️ momentumNew.py Run")

### 策略參數設定
switchs = []

# sDt = datetime.strptime('2010/01/01', "%Y/%m/%d") # Start Date
# eDt = datetime.strptime('2019/12/31', "%Y/%m/%d") # End Date

sDt = datetime.strptime('2010/01/01', "%Y/%m/%d") # Start Date
eDt = datetime.strptime('2024/12/31', "%Y/%m/%d") # End Date

### FinMind api設定
apiUrl = "https://api.finmindtrade.com/api/v4/data"
api = DataLoader()
token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNS0wNi0yOCAxNToyODoxMSIsInVzZXJfaWQiOiJueWN1bGFiNjE1IiwiaXAiOiIxMTQuMTM3LjIxOS4yMTEiLCJleHAiOjE3NTE3MDA0OTF9.u4s5jxRFBz2ojJ01n-8c6Jm2G0FAhtn1-gSMsaspZWE"
api.login_by_token(api_token=token)

planType = "A" # A 
# oPeriods = [3, 6, 9 ,12] # Observer Period
# hPeriods = [3, 6, 9 ,12] # Holding Period
oPeriods = [3] # Observer Period
hPeriods = [6] # Holding Period
maxIncludeRank = 150
for oPeriod in oPeriods:
    for hPeriod in hPeriods:
        utils.ptMsg(f"⚙️ 參數設定：{sDt.strftime("%Y/%m/%d")}~{eDt.strftime("%Y/%m/%d")}/Period(o、h):{oPeriod}、{hPeriod}")

        dataExist = False
        
        ###### 備齊本策略的資料源
        ## 取得上市櫃股票列表
        dfSI = finMind.twStockInfoTwse(False)
        stockList = dfSI['stock_id'].drop_duplicates().tolist()

        base_folder = Path("../data/FinMind/TW/MarketValue")
        valid_stock_set = set(str(sid) for sid in stockList)

        for year in range(2010, 2025):
            year_folder = base_folder / str(year)
            if not year_folder.exists():
                continue

            no_use_folder = year_folder / "no_use"
            no_use_folder.mkdir(exist_ok=True)

            for file in year_folder.glob("TWMV-*.csv"):
                stock_id = file.stem.replace("TWMV-", "")
                if stock_id not in valid_stock_set:
                    target_file = no_use_folder / file.name
                    print(f"📦 移動檔案：{file} -> {target_file}")
                    try:
                        shutil.move(str(file), str(target_file))
                    except Exception as e:
                        print(f"⚠️ 無法移動 {file}，原因：{e}")

        sys.exit()
        
        ### 取出每個月前n大市值的名單
        dataExist = False
        dfTWMVrank = anaData.twMarketValueSpeRankList(stockList, sDt, eDt, maxIncludeRank)
        
        prepareDatas = True
        if prepareDatas:    
            ### 撈取FindMind的調整後股價資料
            outputDir = r'..\data\FinMind\TW\DailyPriceAdj'
            stockList = dfTWMVrank['stock_id'].drop_duplicates().tolist()
            utils.ptMsg("📢 即將撈取[歷史修正股價]資料，股票清單的長度為：", len(stockList))

            runDataResult = finMind.runTwStockDailyPriceAdj(stockList, sDt, eDt)
            if not runDataResult:
                sys.exit()

            ### 將收盤價按年整理
            runDataResult = anaData.runTwClosePriceByYear(sDt, eDt)
            if not runDataResult:
                sys.exit()

        sys.exit() # 先抓資料

        ###### 開始計算本策略的統計資料
        filePrefixIdx = 0
        target_folder = r'..\data\analysis\momentumNew' + f'/oPeriod{oPeriod}_hPeriod{hPeriod}/{sDt.strftime("%Y%m")}_{eDt.strftime("%Y%m")}'
        def getOutputCsvPath(target_folder, filePrefixIdx, csvName):        
            os.makedirs(target_folder, exist_ok=True) 
            outputPath = f'{target_folder}/{str(filePrefixIdx).zfill(2)}-{csvName}.csv'
            return outputPath

        ### 計算觀察期報酬
        ### stock_id,start_date,end_date,SD_close,ED_close,combination,return
        dataExist = False
        filePrefixIdx = filePrefixIdx + 1
        output_file = getOutputCsvPath(target_folder, filePrefixIdx, "observerReturnList")
        if os.path.exists(output_file):
            result_df = pd.read_csv(output_file)
            utils.ptMsg(f"☑️ 檔案已存在：{output_file}")
            dataExist = True
        else:
            # 查看有沒有範圍更廣的資料區間
            os.makedirs(os.path.dirname(output_file), exist_ok=True) # 確保資料夾存在
            file_list = os.listdir(os.path.dirname(output_file))

            # 正則表達式：匹配 observerReturnListyyyymm_yyyymm.csv
            pattern = re.compile(r"^observerReturnList(\d{6})_(\d{6})\.csv$")

            # 找符合的檔案
            matching_files = [f for f in file_list if pattern.match(f)]
            if matching_files:
                for f in matching_files:
                    timeRange = utils.getSdtEdt(f)
                    sDtInRange = utils.inTimeRange(sDt, timeRange.get("sDt"), timeRange.get("eDt"))
                    dDtInRange = utils.inTimeRange(eDt, timeRange.get("sDt"), timeRange.get("eDt"))
                    if sDtInRange and dDtInRange:
                        result_df = pd.read_csv(f'{os.path.dirname(output_file)}/{f}')
                        utils.ptMsg("☑️ 已讀入既有檔案：" + f'{os.path.dirname(output_file)}/{f}')   
                        dataExist = True
                        break    

        if not dataExist:
            utils.ptMsg("📢 開始製作" + str(output_file))
            cur_dt = sDt

            ### 嘗試讀取進度：
            pattern = output_file + "-tmp_*"
            matching_files = glob.glob(pattern)
            if matching_files and os.path.exists(matching_files[0]):
                progressYM = matching_files[0].rsplit("-tmp_", 1)[-1]
                utils.ptMsg("📢 Observer RT偵測並讀取進度：" + progressYM)

                progressDt = datetime.strptime(progressYM, "%Y%m")
                cur_dt = progressDt + relativedelta(months=1)
                
            close_df = None
            close_df_year = "0"
            closeDfYears = (oPeriod) // 12 + 2

            # 逐月迭代    
            while cur_dt <= eDt:
                ### 如果end_dt2超過資料範圍 就結束搜尋
                end_dt2 = cur_dt + relativedelta(months=oPeriod + hPeriod)            
                if (end_dt2 > eDt):
                    print(f"*** end_dt2({end_dt2.strftime("%Y%m")})已超過資料時間範圍，結束計算。")
                    break

                curY = cur_dt.strftime("%Y")

                # 讀取近n(closeDfYears)年收盤價資料    
                if (close_df is None) or (int(close_df_year) != int(curY)):            
                    close_df = utils.getCloseDf(curY, closeDfYears)
                    close_df_year = cur_dt.strftime("%Y")

                result_rows = []
                
                ym_str = cur_dt.strftime('%Y-%m')
                utils.ptMsg("**Observer RT " + ym_str + " 開始處理")

                # (a) 找當月股票清單
                month_stocks = dfTWMVrank[dfTWMVrank['year_month'] == ym_str]['stock_id'].unique()
                utils.ptMsg("** " + ym_str + "股票清單長度：" + str(len(month_stocks)))
                
                for stock in month_stocks:
                    # (b) 找該股票當月第一個交易日
                    # reset_index方便篩選
                    sub_df = close_df.reset_index()
                    mask = (
                        (sub_df['stock_id'] == stock) &
                        (sub_df['date'].dt.year == cur_dt.year) &
                        (sub_df['date'].dt.month == cur_dt.month)
                    )
                    this_month = sub_df[mask].sort_values('date')
                    # print("this_month=")
                    # print(this_month.head(2))
                    if this_month.empty:
                        print(f"⚠️ {ym_str} Stock{stock} 沒有this_month的資料")
                        continue  # 沒有該月資料，跳過
                    
                    start_row = this_month.iloc[0]
                    # print("## start_row=")
                    # print(start_row)
                    start_date = start_row['date']
                    SD_close = start_row['close']
                    
                    # (c) 找end_date  
                    end_dt = cur_dt + relativedelta(months=oPeriod - 1)           
                    mask_end = (
                        (sub_df['stock_id'] == stock) &
                        (sub_df['date'].dt.year == end_dt.year) &
                        (sub_df['date'].dt.month == end_dt.month)
                    )
                    end_dt_df = sub_df[mask_end].sort_values('date')
                    if end_dt_df.empty:
                        print(f"⚠️ {str(end_dt.year) + str(end_dt.month)} Stock {stock} 沒有end_dt_df的資料")
                        # print("*** sub_df=")
                        # print(sub_df)
                        # print("*** sub_df[mask_end]=", sub_df[mask_end])
                        # print(sub_df['stock_id'].dtype)
                        # print("stock =", stock, "型別 =", type(stock))
                        # sys.exit() # for Debug
                        continue  # 沒有該月資料，跳過
                    
                    end_row = end_dt_df.iloc[-1]
                    # print("## end_row=")
                    # print(end_row)
                    end_date = end_row['date']
                    ED_close = end_row['close']
                    
                    # (e) 組合欄位
                    combination = f"{cur_dt.strftime('%Y%m')}-{(end_dt + relativedelta(months=1)).strftime('%Y%m')}"
                    ret = (ED_close - SD_close) / SD_close
                    
                    # 加入結果
                    result_rows.append({
                        'stock_id': stock,
                        'start_date': start_date.strftime('%Y-%m-%d'),
                        'end_date': end_date.strftime('%Y-%m-%d'),
                        'SD_close': SD_close,
                        'ED_close': ED_close,
                        'combination': combination,
                        'return': ret
                    })
                
                hasData = False
                if len(result_rows) > 0:
                    hasData = True

                utils.ptMsg("本月處理資料筆數：" + str(len(result_rows)))

                if not hasData:
                    utils.ptMsg("⚠️ No Observer RT Data " + ym_str + " ")
                
                if hasData:
                    result_df = pd.DataFrame(result_rows)
                    result_df.sort_values(['stock_id'], inplace=True) # 排序
                else:
                    result_df = pd.DataFrame([])

                ### 處理量巨大，保險起見分月暫存
                output_file_tmp = output_file + "-tmp_" + cur_dt.strftime("%Y%m")
                # 尋找前一個月的檔案
                prev_m_dt = cur_dt - relativedelta(months=1)
                output_file_tmp_lastM = output_file + "-tmp_" + prev_m_dt.strftime("%Y%m")
                if os.path.exists(output_file_tmp_lastM):
                    if hasData:
                        result_df.to_csv(output_file_tmp_lastM, mode="a", header=False, index=False)
                    os.rename(output_file_tmp_lastM, output_file_tmp)
                else:
                    os.makedirs(os.path.dirname(output_file_tmp), exist_ok=True)
                    result_df.to_csv(output_file_tmp, mode="w", index=False, float_format='%.8f')

                utils.ptMsg("📢 Observer RT " + ym_str + " 已處理完成")

                # 下個月
                cur_dt += relativedelta(months=1)

            # 輸出
            if os.path.exists(output_file_tmp):
                os.rename(output_file_tmp, output_file)
                utils.ptMsg('✅ 整合完成！檔案輸出：', output_file) 
            else:
                utils.ptMsg('⚠️ 因為沒有資料，未儲存任何檔案') 
            
            # result_df = pd.read_csv(output_file)
            with open(output_file, encoding="utf-8") as f:
                first_line = f.readline().strip()

                if not first_line:
                    print("檔案沒有任何內容（或只有空行），用空 DataFrame")
                    result_df = pd.DataFrame()
                else:
                    try:
                        result_df = pd.read_csv(output_file)
                    except EmptyDataError:
                        print("檔案格式不正確，用空 DataFrame")
                        result_df = pd.DataFrame()
            
        
        ### 增加各種rank相關欄位
        filePrefixIdx = filePrefixIdx + 1
        output_file = getOutputCsvPath(target_folder, filePrefixIdx, "observerReturnList_rank")
        if os.path.exists(output_file):
            result_df = pd.read_csv(output_file)
            utils.ptMsg(f"☑️ 檔案已存在：{output_file}")
        else:
            utils.ptMsg("📢 開始製作" + str(output_file))

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
            utils.ptMsg(f"✅ 已輸出檔案：{output_file}")

        ### 產生winner_loser名單
        filePrefixIdx = filePrefixIdx + 1
        output_file = getOutputCsvPath(target_folder, filePrefixIdx, "winner_loser")
        if os.path.exists(output_file):
            filtered_df = pd.read_csv(output_file)
            utils.ptMsg(f"☑️ 檔案已存在：{output_file}")
        else:
            utils.ptMsg("📢 開始製作" + str(output_file))
            # 篩選 remark 為 winner 或 loser
            filtered_df = result_df[result_df["remark"].isin(["winner", "loser"])].copy()

            # 存成新檔
            filtered_df.to_csv(output_file, index=False, encoding="utf-8-sig")

            utils.ptMsg(f"✅ 已輸出檔案：{output_file}")

        ### 計算持有期的報酬
        filePrefixIdx = filePrefixIdx + 1
        output_file = Path(getOutputCsvPath(target_folder, filePrefixIdx, "holdingReturnList"))
        if os.path.exists(output_file):
            filtered_df = pd.read_csv(output_file)
            utils.ptMsg(f"☑️ 檔案已存在：{output_file}")
        else:
            utils.ptMsg("📢 開始製作" + str(output_file))

            price_folder = Path(r"..\data\analysis\summary")

            # 把日期字串轉成 datetime
            filtered_df["start_date_dt"] = pd.to_datetime(filtered_df["start_date"])
            filtered_df["end_date_dt"] = pd.to_datetime(filtered_df["end_date"])

            # 用於儲存結果
            start_date2_list = []
            SD_close2_list = []
            end_date2_list = []
            ED_close2_list = []

            close_df_sd2 = None
            close_df_sd2_y_pre = None
            close_df_sd2_y = None

            close_df_ed2 = None
            close_df_ed2_y_pre = None
            close_df_ed2_y = None

            # 處理每一列 
            for idx, row in filtered_df.iterrows():
                stock_id = str(row["stock_id"])

                # =============== start_date2 ==============
                sd2_month = row["end_date_dt"] + relativedelta(months=+1)
                sd2_year = sd2_month.year
                sd2_month_num = sd2_month.month

                close_df_sd2_y = sd2_month.strftime("%Y")
                if (close_df_sd2 is None) or (int(close_df_sd2_y) != int(close_df_sd2_y_pre)):
                    close_df_sd2 = utils.getCloseDf(close_df_sd2_y, 1)
                    close_df_sd2["date_dt"] = pd.to_datetime(close_df_sd2["date"])
                    close_df_sd2_y_pre = close_df_sd2_y

                if close_df_sd2.empty:
                    utils.ptMsg(f"❌ 找不到檔案：closePrice_{close_df_sd2_y}.csv，填入 None")
                    start_date2 = None
                    SD_close2 = None
                else:
                    sd2_candidates = close_df_sd2[
                        (close_df_sd2["stock_id"] == stock_id) &
                        (close_df_sd2["date_dt"].dt.month == sd2_month_num)
                    ]
                    if not sd2_candidates.empty:
                        sd2_first = sd2_candidates.sort_values("date_dt").iloc[0]
                        start_date2 = sd2_first["date"]
                        SD_close2 = sd2_first["close"]
                    else:
                        start_date2 = None
                        SD_close2 = None

                    start_date2_list.append(start_date2)
                    SD_close2_list.append(SD_close2)
                    if start_date2 is None:
                        print("⚠️start_date2 is None")
                    if SD_close2 is None:
                        print("SD_close2 is None")

                    # print("close_df_sd2", close_df_sd2)
                    # print("close_df_sd2_y_pre", close_df_sd2_y_pre)
                    # print("close_df_sd2_y", close_df_sd2_y)
                    # print("filtered_df", filtered_df.head(3))

                    # =============== end_date2 ==============
                    ed2_month = row["end_date_dt"] + relativedelta(months=+(hPeriod))
                    ed2_year = ed2_month.year
                    ed2_month_num = ed2_month.month

                    close_df_ed2_y = ed2_month.strftime("%Y")
                    if (close_df_ed2 is None) or (int(close_df_ed2_y) != int(close_df_ed2_y_pre)):
                        if int(close_df_ed2_y) == int(close_df_sd2_y):
                            close_df_ed2 = close_df_sd2
                        else:
                            close_df_ed2 = utils.getCloseDf(close_df_ed2_y, 1)
                            close_df_ed2["date_dt"] = pd.to_datetime(close_df_ed2["date"])
                        close_df_ed2_y_pre = close_df_ed2_y

                    if close_df_ed2.empty:
                        utils.ptMsg(f"❌ 找不到檔案：closePrice_{close_df_ed2_y}.csv，填入 None")
                        end_date2 = None
                        ED_close2 = None
                    else:
                        ed2_candidates = close_df_ed2[
                            (close_df_ed2["stock_id"] == stock_id) &
                            (close_df_ed2["date_dt"].dt.month == ed2_month_num)
                        ]
                        if not ed2_candidates.empty:
                            ed2_last = ed2_candidates.sort_values("date_dt").iloc[-1]
                            end_date2 = ed2_last["date"]
                            ED_close2 = ed2_last["close"]
                        else:
                            end_date2 = None
                            ED_close2 = None

                        end_date2_list.append(end_date2)
                        ED_close2_list.append(ED_close2)
                        if end_date2 is None:
                            print("end_date2 is None")
                        if ED_close2 is None:
                            print("ED_close2 is None")

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

            utils.ptMsg(f"✅ 已完成後續報酬計算，輸出至：{output_file}")

        ### 統計持有期間平均報酬
        filePrefixIdx = filePrefixIdx + 1
        output_file = Path(getOutputCsvPath(target_folder, filePrefixIdx, "holdingReturnList_static"))
        if os.path.exists(output_file):
            grouped = pd.read_csv(output_file)
            utils.ptMsg(f"☑️ 檔案已存在：{output_file}")
        else:
            utils.ptMsg("📢 開始製作" + str(output_file))
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

            utils.ptMsg(f"✅ 統計已完成，檔案輸出：{output_file}")

        ### 計算winner - loser
        filePrefixIdx = filePrefixIdx + 1
        output_file = Path(getOutputCsvPath(target_folder, filePrefixIdx, "holdingReturnList_static2"))
        if os.path.exists(output_file):
            new_df = pd.read_csv(output_file)
            utils.ptMsg(f"☑️ 檔案已存在：{output_file}")
        else:
            utils.ptMsg("📢 開始製作" + str(output_file))
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
            utils.ptMsg(f"✅ 已輸出新檔案：{output_file}")

        ### t-test
        filePrefixIdx = filePrefixIdx + 1
        output_file = Path(getOutputCsvPath(target_folder, filePrefixIdx, "t_test"))
        if os.path.exists(output_file):
            utils.ptMsg(f"☑️ 檔案已存在：{output_file}")
        else:
            utils.ptMsg("📢 開始製作" + str(output_file))

            # 移除多餘逗號
            new_df.columns = new_df.columns.str.strip()

            # print(new_df["mean_return2"].head(10))
            # print(new_df["mean_return2"].dtype)
            
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
            # utils.ptMsg(result_df)

            result_df.to_csv(output_file, index=False, encoding="utf-8-sig")
            utils.ptMsg(f"✅ 已輸出結果：{output_file}")


# 結束訊息
utils.ptMsg("⚙️ momentumNew.py Finish")
print("")
