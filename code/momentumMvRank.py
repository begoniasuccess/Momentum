import pandas as pd
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pathlib import Path
import sys
import glob
from scipy import stats
import gc

import re
from pandas.errors import EmptyDataError
import calendar

from common import utils
from common import finMind
from common import anaData
from common.constants import Panel
from common.constants import Iloc

### in PowerShell：
# $OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
# python -u momentumMvRank.py 2>&1 | Tee-Object -FilePath ../log/momentumMvRank.log -Append
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

# 起始訊息
print("")
utils.ptMsg("⚙️ momentumMvRank.py Run")

### 策略參數設定
panelTypes = [Panel.A, Panel.B] 

# 起始與結束年月
start_ym = "2010/01" # 取月初
end_ym = "2024/12" # 取月底
end_ym = "2019/12" # 取月底

start_year, start_month = map(int, start_ym.split('/'))
end_year, end_month = map(int, end_ym.split('/'))
sDt = datetime(start_year, start_month, 1)
eDt = datetime(end_year, end_month, calendar.monthrange(end_year, end_month)[1])

oPeriods = [3, 6, 9 ,12] # Observer Period
hPeriods = [3, 6, 9 ,12] # Holding Period

# oPeriods = [3] # Observer Period
# hPeriods = [9] # Holding Period

maxIncludeRank = 150

prepareDatas = False
for oPeriod in oPeriods:
    for hPeriod in hPeriods:
        utils.ptMsg(f"⚙️ 參數設定：{sDt.strftime("%Y/%m/%d")}~{eDt.strftime("%Y/%m/%d")}/Period(o、h):{oPeriod}、{hPeriod}")

        dataExist = False
        
        ###### 備齊本策略的資料源
        ## 取得上市櫃股票列表
        dfSI = finMind.twStockInfoTwse(False)
        stockList = dfSI['stock_id'].drop_duplicates().tolist()

        ## 移除多餘的市值資料
        # base_folder = Path("../data/FinMind/TW/MarketValue")
        # valid_stock_set = set(str(sid) for sid in stockList)
        # for year in range(2010, 2025):
        #     year_folder = base_folder / str(year)
        #     if not year_folder.exists():
        #         continue

        #     no_use_folder = year_folder / "no_use"
        #     no_use_folder.mkdir(exist_ok=True)

        #     for file in year_folder.glob("TWMV-*.csv"):
        #         stock_id = file.stem.replace("TWMV-", "")
        #         if stock_id not in valid_stock_set:
        #             target_file = no_use_folder / file.name
        #             print(f"📦 移動檔案：{file} -> {target_file}")
        #             try:
        #                 shutil.move(str(file), str(target_file))
        #             except Exception as e:
        #                 print(f"⚠️ 無法移動 {file}，原因：{e}")
        
        ### 取出每個月前n大市值的名單
        dataExist = False
        dfTWMVrank = anaData.twMarketValueSpeRankList(stockList, sDt, eDt, maxIncludeRank)

        if prepareDatas:    
            ### 撈取FindMind的調整後股價資料
            outputDir = r'..\data\FinMind\TW\DailyPriceAdj'
            stockList = dfTWMVrank['stock_id'].drop_duplicates().tolist()

            runDataResult = finMind.runTwStockDailyPriceAdj(stockList, sDt, eDt)
            if not runDataResult:
                sys.exit()

            ### 將收盤價按年整理
            runDataResult = anaData.runTwClosePriceByYear(stockList, sDt, eDt)
            if not runDataResult:
                sys.exit()

        # sys.exit() # 先抓資料

        ###### 開始計算本策略的統計資料
        filePrefixIdx = 0
        target_folder = r'..\data\analysis\momentumMvRank' + f'/oPeriod{oPeriod}_hPeriod{hPeriod}/{sDt.strftime("%Y%m")}_{eDt.strftime("%Y%m")}'


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
            dataExist = False
            # TODO:: 因為資料存儲格式改變，所以這段要重寫
            # 查看有沒有範圍更廣的資料區間 
            # os.makedirs(os.path.dirname(output_file), exist_ok=True) # 確保資料夾存在
            # file_list = os.listdir(os.path.dirname(output_file))

            # # 正則表達式：匹配 observerReturnListyyyymm_yyyymm.csv
            # pattern = re.compile(r"^observerReturnList(\d{6})_(\d{6})\.csv$")

            # # 找符合的檔案
            # matching_files = [f for f in file_list if pattern.match(f)]
            # if matching_files:
            #     for f in matching_files:
            #         timeRange = utils.getSdtEdt(f)
            #         sDtInRange = utils.inTimeRange(sDt, timeRange.get("sDt"), timeRange.get("eDt"))
            #         dDtInRange = utils.inTimeRange(eDt, timeRange.get("sDt"), timeRange.get("eDt"))
            #         if sDtInRange and dDtInRange:
            #             observer_df = pd.read_csv(f'{os.path.dirname(output_file)}/{f}')
            #             observer_df['start_date_dt'] =  pd.to_datetime(observer_df["start_date"])
            #             observer_df['end_date_dt'] =  pd.to_datetime(observer_df["end_date"])
            #             observer_df = [
            #                 (observer_df["start_date_dt"].dt >= sDt)
            #                 & (observer_df["end_date_dt"].dt <= eDt)
            #             ]                        
            #             observer_df = observer_df.drop(columns=["start_date_dt", "end_date_dt"]) # 移除中間欄位
            #             observer_df.to_csv(output_file, mode="w", index=False, float_format='%.8f')
            #             utils.ptMsg("☑️ 已讀入既有檔案：" + output_file)   
            #             dataExist = True
            #             break    

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
            dfNum = (oPeriod) // 12 + 2

            # 逐月迭代    
            while cur_dt <= eDt:
                ### 如果end_dt2超過資料範圍 就結束搜尋
                end_dt2 = cur_dt + relativedelta(months=oPeriod + hPeriod)            
                if (end_dt2 > eDt):
                    utils.ptMsg(f"*** 持有期-賣出 時間：({end_dt2.strftime("%Y-%m")}) 已超過資料時間範圍，結束計算。")
                    break

                curY = cur_dt.strftime("%Y")

                # 讀取近n(closeDfYears)年收盤價資料    
                if (close_df is None) or (int(close_df_year) != int(curY)):            
                    close_df = utils.getCloseDf(curY, dfNum)
                    close_df_year = cur_dt.strftime("%Y")
                    gc.collect() # 釋放資源

                result_rows = []
                
                ym_str = cur_dt.strftime('%Y-%m')
                utils.ptMsg("**Observer RT " + ym_str + " 開始處理")

                # 從月均市值排名名單 提取 當月股票清單
                month_stocks = dfTWMVrank[dfTWMVrank['year_month'] == ym_str]['stock_id'].unique()
                utils.ptMsg("** " + ym_str + "股票清單長度：" + str(len(month_stocks)))
                
                for stock in month_stocks:
                    # 找 觀察期-買入(start_date) 的資料 => 月初
                    sub_df = close_df.reset_index()
                    start_row = utils.getOperiodDataRow(stock, sub_df, cur_dt, Iloc.Fst)
                    if start_row is None:
                        print(f"⚠️ [{stock}-{cur_dt.strftime('%Y%m')}] 沒有 觀察期-買入 的資料，跳過。")
                        continue # 該月資料不完整，不寫入
                    
                    start_date = start_row['date']
                    SD_close = start_row['close']
                    
                    # 找 觀察期-賣出(end_date) 的資料 => 月底
                    end_dt = cur_dt + relativedelta(months=oPeriod - 1)
                    end_row = utils.getOperiodDataRow(stock, sub_df, end_dt, Iloc.Last)
                    if end_row is None:
                        print(f"⚠️ [{stock}-{end_dt.strftime('%Y%m')}] 沒有 觀察期-賣出 的資料，跳過。")
                        continue # 該月資料不完整，不寫入
                    
                    end_date = end_row['date']
                    ED_close = end_row['close']
                    
                    # 組合欄位
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

            # 計算 RT_rank，注意：不先創欄位
            def compute_rt_rank(group):
                mask = group["remark"] != "exclude"
                # 只針對非 exclude 算排名
                ranks = pd.Series(index=group.index, dtype="float")
                ranks.loc[mask] = group.loc[mask, "return"].rank(method="min", ascending=False)
                group["RT_rank"] = ranks
                return group

            observer_df = observer_df.groupby("combination", group_keys=False).apply(compute_rt_rank)


            # 確保 RT_rank 是 numeric
            observer_df["RT_rank"] = pd.to_numeric(observer_df["RT_rank"], errors="coerce")

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

            observer_df = observer_df.groupby("combination", group_keys=False).apply(mark_winner_loser)

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
        gc.collect() # 釋放資源

        dfNum = (hPeriod) // 12 + 2
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

                price_folder = Path(f"../data/analysis/summary")

                # 把日期字串轉成 datetime
                holding_df["start_date_dt"] = pd.to_datetime(holding_df["start_date"])
                holding_df["end_date_dt"] = pd.to_datetime(holding_df["end_date"])

                # 用於儲存結果
                start_date2_list = []
                SD_close2_list = []
                end_date2_list = []
                ED_close2_list = []

                close_df_sd2 = None # DataFrame
                close_df_sd2_y_pre = None
                close_df_sd2_y = None

                close_df_ed2 = None  # DataFrame
                close_df_ed2_y_pre = None
                close_df_ed2_y = None

                # 處理每一列 
                for idx, row in holding_df.iterrows():
                    stock_id = str(row["stock_id"])

                    # =============== start_date2 ==============
                    start_date2 = None
                    SD_close2 = None
                    sd2_baseDt = row["end_date_dt"] + relativedelta(months=+1)
                    sd2_baseDt = sd2_baseDt.replace(day=1) # 調整到1日
                    if panelType == Panel.B:
                        sd2_baseDt = sd2_baseDt + relativedelta(days=+7)

                    # 組織查詢表
                    close_df_sd2_y = sd2_baseDt.strftime("%Y")
                    if (close_df_sd2 is None) or (int(close_df_sd2_y) != int(close_df_sd2_y_pre)):
                        close_df_sd2 = utils.getCloseDf(close_df_sd2_y, dfNum)
                        close_df_sd2["date_dt"] = pd.to_datetime(close_df_sd2["date"])
                        close_df_sd2_y_pre = close_df_sd2_y
                        gc.collect() # 釋放資源

                    if close_df_sd2.empty:
                        utils.ptMsg(f"❌ 找不到檔案：closePrice_{close_df_sd2_y}.csv，填入 None")
                    else:
                        sd2_dataRow = utils.getHperiodDataRow(panelType, stock_id, close_df_sd2, sd2_baseDt, Iloc.Fst)
                        if sd2_dataRow is not None:
                            start_date2 = sd2_dataRow["date"]
                            SD_close2 = sd2_dataRow["close"]

                    start_date2_list.append(start_date2)
                    SD_close2_list.append(SD_close2)
                    if start_date2 is None:
                        print(f"⚠️ [{sd2_baseDt.strftime("%Y%m")}-{stock_id}] 持有期-買入 資料無法找到。")
                        end_date2_list.append(None)
                        ED_close2_list.append(None)
                        continue
                            
                    # =============== end_date2 ==============
                    end_date2 = None
                    ED_close2 = None
                    ed2_baseDt = row["end_date_dt"] + relativedelta(months=+(hPeriod))
                    if panelType == Panel.B:
                        # 月底延後7天 理論上會跨月！
                        ed2_baseDt = ed2_baseDt + relativedelta(days=+7)

                    # 組織查詢表
                    close_df_ed2_y = ed2_baseDt.strftime("%Y")
                    if (close_df_ed2 is None) or (int(close_df_ed2_y) != int(close_df_ed2_y_pre)):
                        if int(close_df_ed2_y) == int(close_df_sd2_y) and panelType == Panel.A:
                            close_df_ed2 = close_df_sd2
                        else:
                            if panelType == Panel.B:
                                close_df_ed2 = utils.getCloseDf(close_df_ed2_y, dfNum + 1)
                            else:
                                close_df_ed2 = utils.getCloseDf(close_df_ed2_y, dfNum)
                            close_df_ed2["date_dt"] = pd.to_datetime(close_df_ed2["date"])
                            gc.collect() # 釋放資源
                        close_df_ed2_y_pre = close_df_ed2_y

                    if close_df_ed2.empty:
                        utils.ptMsg(f"❌ 找不到檔案：closePrice_{close_df_ed2_y}.csv，填入 None")
                    else:
                        ed2_dataRow = utils.getHperiodDataRow(panelType, stock_id, close_df_sd2, ed2_baseDt, Iloc.Last)
                        if ed2_dataRow is not None:
                            end_date2 = ed2_dataRow["date"]
                            ED_close2 = ed2_dataRow["close"]

                    end_date2_list.append(end_date2)
                    ED_close2_list.append(ED_close2)
                    if end_date2 is None:
                        print(f"⚠️ [{ed2_baseDt.strftime("%Y%m")}-{stock_id}] 持有期-賣出 資料無法找到。")

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

                del close_df_sd2
                del close_df_ed2
                gc.collect() # 釋放資源

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

            ### t-test
            filePrefixIdx = filePrefixIdx + 1
            output_file = Path(utils.getOutputCsvPath(target_folder, filePrefixIdx, f"t_test-{panelType.value}"))
            if os.path.exists(output_file):
                utils.ptMsg(f"☑️ 檔案已存在：{output_file}")
            else:
                utils.ptMsg("📢 開始製作" + str(output_file))

                # 移除多餘逗號
                wMinusL_df.columns = wMinusL_df.columns.str.strip()

                # print(wMinusL_df["mean_avg_monthly_return"].head(10))
                # print(wMinusL_df["mean_avg_monthly_return"].dtype)
                
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

# 結束訊息
utils.ptMsg("⚙️ momentumMvRank.py Finish")
print("")
