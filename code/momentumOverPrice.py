import pandas as pd
import os
from datetime import datetime
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
import calendar
from common.constants import Panel
from common.constants import Iloc
import gc

### in PowerShell：
# $OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
# python -u momentumOverPrice.py 2>&1 | Tee-Object -FilePath ../log/momentumOverPrice.log -Append
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

# 起始訊息
print("")
utils.ptMsg("⚙️ momentumOverPrice.py Run")

### 策略參數設定
panelTypes = [Panel.A, Panel.B]

# 起始與結束年月
start_ym = "2010/01" # 取月初
end_ym = "2024/12" # 取月底

start_year, start_month = map(int, start_ym.split('/'))
end_year, end_month = map(int, end_ym.split('/'))
sDt = datetime(start_year, start_month, 1)
eDt = datetime(end_year, end_month, calendar.monthrange(end_year, end_month)[1])

# oPeriods = [3, 6, 9 ,12] # Observer Period
# hPeriods = [3, 6, 9 ,12] # Holding Period

oPeriods = [3] # Observer Period
hPeriods = [9] # Holding Period

minClosePrice = 10

prepareData = False

summaryDir = "../data/analysis/summary"
for oPeriod in oPeriods:
    for hPeriod in hPeriods:
        utils.ptMsg(f"⚙️ 參數設定：{sDt.strftime("%Y/%m/%d")}~{eDt.strftime("%Y/%m/%d")}/Period(o、h):{oPeriod}、{hPeriod}")

        dataExist = False
        
        ###### 備齊本策略的資料源
        if prepareData:            
            ## 取得上市櫃股票列表
            dfSI = finMind.twStockInfoNoEmerging(False)
            stockList = dfSI['stock_id'].drop_duplicates().tolist()
    
            ### 撈取FindMind的調整後股價資料
            outputDir = r'..\data\FinMind\TW\DailyPriceAdj'
            utils.ptMsg("📢 即將撈取[歷史修正股價]資料，股票清單的長度為：", len(stockList))
            runDataResult = finMind.runTwStockDailyPriceAdj(stockList, sDt, eDt)
            if not runDataResult:
                sys.exit()

            ### 計算每月平均股價，並且過濾出大於minCloseMinPrice股價的清單
            runDataResult = anaData.runAdjPriceMeanByMonth(sDt, eDt, minCloseMinPrice)
            if not runDataResult:
                sys.exit()
            
            ### 將收盤價按月整理
            runDataResult = anaData.runTwClosePriceByMonth(sDt, eDt)
            if not runDataResult:
                sys.exit()

            runDataResult = anaData.runTwClosePriceByMonth(sDt, eDt)
            if not runDataResult:
                sys.exit()
        
        ###### 開始計算本策略的統計資料
        filePrefixIdx = 0
        target_folder = f'../data/analysis/momentumOver{minClosePrice}/oPeriod{oPeriod}_hPeriod{hPeriod}/{sDt.strftime("%Y%m")}_{eDt.strftime("%Y%m")}'

        ### 計算觀察期報酬
        ### stock_id,start_date,end_date,SD_close,ED_close,combination,return
        dataExist = False
        filePrefixIdx = filePrefixIdx + 1
        output_file = utils.getOutputCsvPath(target_folder, filePrefixIdx, "observerReturnList")
        if os.path.exists(output_file):
            observer_df = pd.read_csv(output_file)
            utils.ptMsg(f"☑️ 檔案已存在：{output_file}")
            dataExist = True
        else:
            utils.process_observer_return(target_folder)
            if os.path.exists(output_file):
                observer_df = pd.read_csv(output_file)
                utils.ptMsg(f"☑️ 檔案已寫入：{output_file}")
                dataExist = True

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
                
            close_df_start = None # DataFrame
            close_df_end = None # DataFrame

            # 逐月迭代
            exist_y_str = None    
            while cur_dt <= eDt:
                ### 如果end_dt2超過資料範圍 就結束搜尋
                end_dt2 = cur_dt + relativedelta(months=oPeriod + hPeriod)            
                if (end_dt2 > eDt):
                    print(f"*** 持有期-賣出 時間：({end_dt2.strftime("%Y%m")})已超過資料時間範圍，結束計算。")
                    break

                curY = cur_dt.strftime("%Y")
                end_dt = cur_dt + relativedelta(months=oPeriod - 1)
                
                ym_str = cur_dt.strftime('%Y-%m')
                utils.ptMsg("**Observer RT " + ym_str + " 開始處理")                
                try:
                    ym_name = cur_dt.strftime('%Y%m')
                    close_df_path = f"{summaryDir}/closePrice/closePrice_{ym_name}.csv"
                    close_df_start = pd.read_csv(close_df_path)
                    close_df_start['date'] = pd.to_datetime(close_df_start['date'], errors='coerce')
                    
                    ym_name = end_dt.strftime('%Y%m')
                    close_df_path = f"{summaryDir}/closePrice/closePrice_{ym_name}.csv"
                    close_df_end = pd.read_csv(close_df_path)
                    close_df_end['date'] = pd.to_datetime(close_df_end['date'], errors='coerce')

                    gc.collect() # 釋放資源
                except Exception as error:
                    utils.ptMsg(f"⚠️ 尋找close_df失敗，錯誤：{error}")
                    sys.exit()
                    # continue

                result_rows = []
                
                # 找當月股票清單
                y_str = cur_dt.strftime('%Y')
                if (exist_y_str != y_str):
                    candidateSrc = f"{summaryDir}/adjPriceMeanByMonth/{y_str}_meanOver{minClosePrice}.csv"
                    if not os.path.exists(candidateSrc):
                        utils.ptMsg(f"⚠️ 必要檔案 {candidateSrc} 不存在，請除錯！")
                        sys.exit()
                    candidateList = pd.read_csv(candidateSrc)
                    # print(candidateList.head())
                    exist_y_str = y_str
                month_stocks = candidateList[
                    candidateList['year_month'].astype(str) == cur_dt.strftime("%Y%m")
                ]['stock_id'].unique()
                utils.ptMsg("** " + ym_str + "股票清單長度：" + str(len(month_stocks)))
                
                for stock in month_stocks:
                    # 找該股票當月第一個交易日
                    # reset_index方便篩選
                    sub_df_start = close_df_start.reset_index()
                    mask = (
                        (sub_df_start['stock_id'] == stock) &
                        (sub_df_start['date'].dt.year == cur_dt.year) &
                        (sub_df_start['date'].dt.month == cur_dt.month)
                    )
                    this_month = sub_df_start[mask].sort_values('date')
                    # print("this_month=")
                    # print(this_month.head(2))
                    if this_month.empty:
                        print(f"⚠️ {ym_str} Stock{stock} 沒有this_month的資料")
                        continue  # 沒有該月資料，跳過
                    
                    start_row = this_month.iloc[0]
                    start_date = start_row['date']
                    SD_close = start_row['close']
                    
                    # (c) 找end_date
                    sub_df_end = close_df_end.reset_index()             
                    mask_end = (
                        (sub_df_end['stock_id'] == stock) &
                        (sub_df_end['date'].dt.year == end_dt.year) &
                        (sub_df_end['date'].dt.month == end_dt.month)
                    )
                    end_dt_df = sub_df_end[mask_end].sort_values('date')
                    if end_dt_df.empty:
                        print(f"⚠️ {str(end_dt.year) + str(end_dt.month)} Stock {stock} 沒有end_dt_df的資料")
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
                    observer_df = pd.DataFrame(result_rows)
                    observer_df.sort_values(['stock_id'], inplace=True) # 排序
                else:
                    observer_df = pd.DataFrame([])

                ### 處理量巨大，保險起見分月暫存
                output_file_tmp = output_file + "-tmp_" + cur_dt.strftime("%Y%m")
                # 尋找前一個月的檔案
                prev_m_dt = cur_dt - relativedelta(months=1)
                output_file_tmp_lastM = output_file + "-tmp_" + prev_m_dt.strftime("%Y%m")
                if os.path.exists(output_file_tmp_lastM):
                    if hasData:
                        observer_df.to_csv(output_file_tmp_lastM, mode="a", header=False, index=False)
                    os.rename(output_file_tmp_lastM, output_file_tmp)
                else:
                    os.makedirs(os.path.dirname(output_file_tmp), exist_ok=True)
                    observer_df.to_csv(output_file_tmp, mode="w", index=False, float_format='%.8f')

                utils.ptMsg("📢 Observer RT " + ym_str + " 已處理完成")

                # 下個月
                cur_dt += relativedelta(months=1)

            del close_df_start
            del close_df_end
            gc.collect()
            
            # 輸出
            if os.path.exists(output_file_tmp):
                os.rename(output_file_tmp, output_file)
                utils.ptMsg('✅ 整合完成！檔案輸出：', output_file) 
            else:
                utils.ptMsg('⚠️ 因為沒有資料，未儲存任何檔案') 
            
            # observer_df = pd.read_csv(output_file)
            with open(output_file, encoding="utf-8") as f:
                first_line = f.readline().strip()

                if not first_line:
                    print("檔案沒有任何內容（或只有空行），用空 DataFrame")
                    observer_df = pd.DataFrame()
                else:
                    try:
                        observer_df = pd.read_csv(output_file)
                    except EmptyDataError:
                        print("檔案格式不正確，用空 DataFrame")
                        observer_df = pd.DataFrame()
        
        ### 增加各種rank相關欄位
        filePrefixIdx = filePrefixIdx + 1
        output_file = utils.getOutputCsvPath(target_folder, filePrefixIdx, "observerReturnList_rank")
        if os.path.exists(output_file):
            observer_df = pd.read_csv(output_file)
            utils.ptMsg(f"☑️ 檔案已存在：{output_file}")
        else:
            utils.ptMsg("📢 開始製作" + str(output_file))

            # 確保 return 是 float
            observer_df["return"] = pd.to_numeric(observer_df["return"], errors="coerce")

            # 計算 RT_%_Rank
            observer_df["RT_%_Rank"] = observer_df.groupby("combination")["return"].transform(utils.scale_to_0_100)

            # remark 初始化
            observer_df["remark"] = ""

            # 先標註 exclude
            exclude_mask = (observer_df["RT_%_Rank"] > 99.9) | (observer_df["RT_%_Rank"] < 0.1)
            observer_df.loc[exclude_mask, "remark"] = "exclude"

            observer_df = observer_df.groupby("combination", group_keys=False).apply(utils.compute_rt_rank)

            # 確保 RT_rank 是 numeric
            observer_df["RT_rank"] = pd.to_numeric(observer_df["RT_rank"], errors="coerce")

            observer_df = observer_df.groupby("combination", group_keys=False).apply(utils.mark_winner_loser)

            # 輸出
            observer_df.to_csv(output_file, index=False, encoding="utf-8-sig")
            utils.ptMsg(f"✅ 已輸出檔案：{output_file}")

        ### 產生winner_loser名單
        filePrefixIdx = filePrefixIdx + 1
        output_file = utils.getOutputCsvPath(target_folder, filePrefixIdx, "winner_loser")
        if os.path.exists(output_file):
            candidateWL_df = pd.read_csv(output_file)
            utils.ptMsg(f"☑️ 檔案已存在：{output_file}")
        else:
            utils.ptMsg("📢 開始製作" + str(output_file))
            # 篩選 remark 為 winner 或 loser
            candidateWL_df = observer_df[observer_df["remark"].isin(["winner", "loser"])].copy()

            # 存成新檔
            candidateWL_df.to_csv(output_file, index=False, encoding="utf-8-sig")

            utils.ptMsg(f"✅ 已輸出檔案：{output_file}")

        del observer_df
        gc.collect()

        ### 持有期開始的分析資料，分成 PanelA、B 處理
        for panelType in panelTypes:        
            holding_df = candidateWL_df.copy(deep=True)

            ### 計算持有期的報酬
            filePrefixIdx = filePrefixIdx + 1
            output_file = Path(utils.getOutputCsvPath(target_folder, filePrefixIdx, f"holdingReturnList-{panelType.value}"))
            if os.path.exists(output_file):
                holding_df = pd.read_csv(output_file)
                utils.ptMsg(f"☑️ 檔案已存在：{output_file}")
            else:
                utils.ptMsg("📢 開始製作" + str(output_file))

                price_folder = Path(r"..\data\analysis\summary")

                # 把日期字串轉成 datetime
                holding_df["start_date_dt"] = pd.to_datetime(holding_df["start_date"])
                holding_df["end_date_dt"] = pd.to_datetime(holding_df["end_date"])

                # 用於儲存結果
                start_date2_list = []
                SD_close2_list = []
                end_date2_list = []
                ED_close2_list = []

                close_df_sd2 = None # DataFrame
                close_df_sd2_ym_pre = None
                close_df_sd2_ym = None

                close_df_ed2 = None # DataFrame
                close_df_ed2_ym_pre = None
                close_df_ed2_ym = None

                # 處理每一列 
                for idx, row in holding_df.iterrows():
                    # print(f"row = ", row)
                    stock_id = str(row["stock_id"])

                    # =============== start_date2 ==============
                    sd2_dt = row["end_date_dt"] + relativedelta(months=+1)
                    sd2_year = sd2_dt.year
                    sd2_month_num = sd2_dt.month

                    start_date2 = None
                    SD_close2 = None

                    close_df_sd2_ym = sd2_dt.strftime("%Y%m")
                    if (close_df_sd2 is None) or (int(close_df_sd2_ym) != int(close_df_sd2_ym_pre)):
                        srcFile = f"{summaryDir}/closePrice/closePrice_{close_df_sd2_ym}.csv"
                        try:
                            close_df_sd2 = pd.read_csv(srcFile)
                            close_df_sd2["date_dt"] = pd.to_datetime(close_df_sd2["date"])
                            gc.collect()
                        except Exception as error:
                            utils.ptMsg(f"❌ closePrice_{close_df_sd2_ym}.csv讀取錯誤，填入 None，{error}")
                            start_date2 = None
                            SD_close2 = None                    
                        close_df_sd2_ym_pre = close_df_sd2_ym

                    if close_df_sd2.empty:
                        utils.ptMsg(f"❌ closePrice_{close_df_sd2_ym}.csv內容空白，填入 None")
                    else:
                        if panelType == Panel.A:
                            sd2_df_mask = (
                                (close_df_sd2["stock_id"] == stock_id)
                                & (close_df_sd2["date_dt"].dt.month == sd2_month_num)
                            )
                        elif panelType == Panel.B:
                            sd2_df_mask = (
                                (close_df_sd2["stock_id"] == stock_id)
                                & (close_df_sd2["date_dt"].dt.month == sd2_month_num)
                                & (close_df_sd2["date_dt"].dt.day > 6)
                                & (close_df_sd2["date_dt"].dt.day < 20)
                            )

                        sd2_candidates = close_df_sd2[sd2_df_mask]
                        if not sd2_candidates.empty:
                            sd2_first = sd2_candidates.sort_values("date_dt").iloc[0]
                            start_date2 = sd2_first["date"]
                            SD_close2 = sd2_first["close"]

                    start_date2_list.append(start_date2)
                    SD_close2_list.append(SD_close2)

                    if start_date2 is None:
                        utils.ptMsg(f"⚠️ [{close_df_sd2_ym}-{stock_id}] 持有期-買入 資料無法找到。")
                        end_date2_list.append(None)
                        ED_close2_list.append(None)
                        continue

                    # =============== end_date2 ==============
                    if panelType == Panel.A:
                        ed2_dt = row["end_date_dt"] + relativedelta(months=+(hPeriod))
                    elif panelType == Panel.B:
                        ed2_dt = row["end_date_dt"] + relativedelta(months=+(hPeriod + 1))
                        ed2_dt = ed2_dt.replace(day=1) # 調整到1日
                    ed2_year = ed2_dt.year
                    ed2_month_num = ed2_dt.month

                    end_date2 = None
                    ED_close2 = None   

                    close_df_ed2_ym = ed2_dt.strftime("%Y%m")
                    if (close_df_ed2 is None) or (int(close_df_ed2_ym) != int(close_df_ed2_ym_pre)):       
                        srcFile = f"{summaryDir}/closePrice/closePrice_{close_df_ed2_ym}.csv"
                        try:
                            close_df_ed2 = pd.read_csv(srcFile)
                            close_df_ed2["date_dt"] = pd.to_datetime(close_df_ed2["date"])
                            gc.collect()
                        except Exception as error:
                            utils.ptMsg(f"❌ closePrice_{close_df_ed2_ym}.csv讀取錯誤，填入 None，{error}")
                        close_df_ed2["date_dt"] = pd.to_datetime(close_df_ed2["date"])
                        close_df_ed2_ym_pre = close_df_ed2_ym

                    if close_df_ed2.empty:
                        utils.ptMsg(f"❌ closePrice_{close_df_ed2_ym}.csv內容空白，填入 None")
                    else:
                        if panelType == Panel.A:
                            sd2_df_mask = (
                                (close_df_ed2["stock_id"] == stock_id) 
                                & (close_df_ed2["date_dt"].dt.month == ed2_month_num)
                            )
                        elif panelType == Panel.B:
                            sd2_df_mask = (
                                (close_df_ed2["stock_id"] == stock_id) 
                                & (close_df_ed2["date_dt"].dt.month == ed2_month_num)
                                & (close_df_sd2["date_dt"].dt.day > 5)
                                & (close_df_sd2["date_dt"].dt.day < 19)
                            )
                        
                        ed2_candidates = close_df_ed2[sd2_df_mask]
                        if not ed2_candidates.empty:
                            iloc = -1 if panelType == Panel.A else 0
                            ed2_last = ed2_candidates.sort_values("date_dt").iloc[iloc]
                            end_date2 = ed2_last["date"]
                            ED_close2 = ed2_last["close"]

                    end_date2_list.append(end_date2)
                    ED_close2_list.append(ED_close2)
                    
                    if end_date2 is None:
                        utils.ptMsg(f"⚠️ [{close_df_ed2_ym}-{stock_id}] 持有期-賣出 資料無法找到。")
                        
                # 新增欄位
                holding_df["start_date2"] = start_date2_list
                holding_df["SD_close2"] = SD_close2_list
                holding_df["end_date2"] = end_date2_list
                holding_df["ED_close2"] = ED_close2_list

                # 轉數字
                holding_df["SD_close2"] = pd.to_numeric(holding_df["SD_close2"], errors="coerce")
                holding_df["ED_close2"] = pd.to_numeric(holding_df["ED_close2"], errors="coerce")

                # 計算 簡單報酬率、平均月報酬率、年化報酬率
                holding_df["return2"] = (holding_df["ED_close2"] - holding_df["SD_close2"]) / holding_df["SD_close2"]
                holding_df["avg_monthly_return"] = (1 + holding_df["return2"]) ** (1 / hPeriod) - 1
                holding_df["annualized_return"] = (1 + holding_df["avg_monthly_return"]) ** 12 - 1
                
                # 移除中間欄位
                holding_df = holding_df.drop(columns=["start_date_dt", "end_date_dt"])

                # 存檔
                output_file.parent.mkdir(parents=True, exist_ok=True)
                holding_df.to_csv(output_file, index=False, encoding="utf-8-sig")

                utils.ptMsg(f"✅ 已完成後續報酬計算，輸出至：{output_file}")

            ### 統計持有期間平均報酬
            filePrefixIdx = filePrefixIdx + 1
            output_file = Path(utils.getOutputCsvPath(target_folder, filePrefixIdx, f"holdingReturnList_static-{panelType.value}"))
            if os.path.exists(output_file):
                holding_meanRT_df = pd.read_csv(output_file)
                utils.ptMsg(f"☑️ 檔案已存在：{output_file}")
            else:
                utils.ptMsg("📢 開始製作" + str(output_file))
                # 確保 avg_monthly_return 是數字型態
                holding_df["avg_monthly_return"] = pd.to_numeric(holding_df["avg_monthly_return"], errors="coerce")

                # 以 combination 和 remark 分組，計算每組的筆數(count)與平均(mean)
                holding_meanRT_df = (
                    holding_df.groupby(["combination", "remark"], dropna=False)
                    .agg(
                        count=("avg_monthly_return", "count"),
                        mean_avg_monthly_return=("avg_monthly_return", "mean")
                    )
                    .reset_index()
                )

                # 移除 mean_avg_monthly_return 為 NaN 的組
                holding_meanRT_df = holding_meanRT_df.dropna(subset=["mean_avg_monthly_return"])

                # 輸出結果
                holding_meanRT_df.to_csv(output_file, index=False, encoding="utf-8-sig")

                utils.ptMsg(f"✅ 統計已完成，檔案輸出：{output_file}")

            del holding_df
            gc.collect()
            
            ### 計算winner - loser
            filePrefixIdx = filePrefixIdx + 1
            output_file = Path(utils.getOutputCsvPath(target_folder, filePrefixIdx, f"holdingReturnList_static2-{panelType.value}"))
            if os.path.exists(output_file):
                wMinusL_df = pd.read_csv(output_file)
                utils.ptMsg(f"☑️ 檔案已存在：{output_file}")
            else:
                utils.ptMsg("📢 開始製作" + str(output_file))
                # 用於儲存新結果
                rows = []

                # 依 combination 分組
                for comb, group in holding_meanRT_df.groupby("combination"):
                    # 先將原本的兩列放進去
                    for _, row in group.iterrows():
                        rows.append(row.to_dict())

                    # 取得 winner 與 loser 的 mean_avg_monthly_return
                    winner_row = group[group["remark"] == "winner"]
                    loser_row = group[group["remark"] == "loser"]

                    if not winner_row.empty and not loser_row.empty:
                        winner_mean = winner_row["mean_avg_monthly_return"].values[0]
                        loser_mean = loser_row["mean_avg_monthly_return"].values[0]
                        diff = winner_mean - loser_mean

                        # 新增一列資料
                        rows.append({
                            "combination": comb,
                            "remark": "winner - loser",
                            "count": "-",
                            "mean_avg_monthly_return": diff
                        })

                wMinusL_df = pd.DataFrame(rows)
                wMinusL_df.to_csv(output_file, index=False, encoding="utf-8-sig")
                utils.ptMsg(f"✅ 已輸出新檔案：{output_file}")

            del holding_meanRT_df
            gc.collect()
            
            ### t-test
            filePrefixIdx = filePrefixIdx + 1
            output_file = Path(utils.getOutputCsvPath(target_folder, filePrefixIdx, f"t_test-{panelType.value}"))
            if os.path.exists(output_file):
                utils.ptMsg(f"☑️ 檔案已存在：{output_file}")
            else:
                utils.ptMsg("📢 開始製作" + str(output_file))

                # 移除多餘逗號
                wMinusL_df.columns = wMinusL_df.columns.str.strip()
                
                results = []

                # 分組 t檢定
                for remark in ["loser", "winner", "winner - loser"]:
                    # 取出該 remark 資料
                    values = wMinusL_df.loc[wMinusL_df["remark"] == remark, "mean_avg_monthly_return"].dropna().values
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
                
                tTest_df = pd.DataFrame(results)
                # utils.ptMsg(tTest_df)

                tTest_df.to_csv(output_file, index=False, encoding="utf-8-sig")
                utils.ptMsg(f"✅ 已輸出結果：{output_file}")
                del tTest_df
                gc.collect()

            del wMinusL_df
            gc.collect()


# 結束訊息
utils.ptMsg("⚙️ momentumOverPrice.py Finish")
print("")
