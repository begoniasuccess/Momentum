import pandas as pd
import os
from dateutil.relativedelta import relativedelta
from datetime import datetime

# 可調整觀察期（月數）
observeHoldingPeriod = 6
outputDir = r'..\data\analysis\momentum'
outputFilBaseName = f'Momentum0050_0051-20160501_20180601-HP_{observeHoldingPeriod}'

### Step01：製作基底資訊檔案
### Stock_id, Start_Date, End_Date, Start_Price, End_Price, Return, Combination
targetFile = f'{outputDir}/{outputFilBaseName}_base.csv'

if os.path.exists(targetFile):
    df = pd.read_csv(targetFile)
    print(f"✅ Step01：初步處理檔案已存在：{targetFile}")
    # print(df.head())  # 顯示前五筆資料
else:
    # 讀取原始資料 => (index), dates, tock_id, close
    srcDataPath = r'..\data\analysis\momentum\Combinations\priceSrc_2016-05-01_2018-06-01.csv'
    df = pd.read_csv(srcDataPath)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by='date')

    # 提取每月的第一日與最後一日
    startDateList = df.groupby(df['date'].dt.to_period('M')).first()['date'].tolist()
    endDateList = df.groupby(df['date'].dt.to_period('M')).last()['date'].tolist()

    # 提取股票清單
    stockIdList = df['stock_id'].unique().tolist()

    result = []
    for i in range(len(startDateList)):
        if i + observeHoldingPeriod - 1 >= len(endDateList):
            break
        start_date = startDateList[i]
        end_date = endDateList[i + observeHoldingPeriod - 1]

        for stock_id in stockIdList:
            stock_df = df[df['stock_id'] == stock_id]
            start_row = stock_df[stock_df['date'] == start_date]
            end_row = stock_df[stock_df['date'] == end_date]
            if not start_row.empty and not end_row.empty:
                start_price = start_row['close'].values[0]
                end_price = end_row['close'].values[0]
                ret = (end_price - start_price) / start_price
                result.append({
                    'Stock_id': stock_id,
                    'Combination': start_date.strftime('%Y%m') + "-" + end_date.strftime('%Y%m'),
                    'Start_Date': start_date.strftime('%Y-%m-%d'),
                    'End_Date': end_date.strftime('%Y-%m-%d'),
                    'Start_Price': start_price,
                    'End_Price': end_price,
                    'Return': ret                    
                })
    df = pd.DataFrame(result)

    df.to_csv(targetFile, index=False)
    print(f"✅ Step01：初步處理完成，已儲存檔案：{targetFile}")

### Step02：新增 RT_Percentile_Rank 欄位，根據每個 Combination 分組後算百分比排名
targetFile = f'{outputDir}/{outputFilBaseName}_returnPercent.csv'
if os.path.exists(targetFile):
    df = pd.read_csv(targetFile)
    print(f"✅ Step02：Return%欄位檔案已存在：{targetFile}")
    # print(df.head())  # 顯示前五筆資料
else:
    df["RT_Percentile_Rank"] = (
        df.groupby("Combination")["Return"]
        .rank(pct=True)  # 百分比排名（0~1之間）
    )

    df.to_csv(targetFile, index=False)
    print(f"✅ 報酬百分比欄位(RT_Percentile_Rank)計算完成，已儲存檔案：{targetFile}")


### Step03：完成Remark欄位
targetFile = f'{outputDir}/{outputFilBaseName}_remark.csv'
if os.path.exists(targetFile):
    df = pd.read_csv(targetFile)
    print(f"✅ Step03：Remark欄位檔案已存在：{targetFile}")
    # print(df.head())  # 顯示前五筆資料
else:
    # 1. 新增欄位 Remark，初始為空字串
    df["Remark"] = ""

    # 2. 將 RT_Percentile_Rank > 0.999 或 < 0.001 的資料標為 "Exclude"
    df.loc[(df["RT_Percentile_Rank"] > 0.999) | (df["RT_Percentile_Rank"] < 0.001), "Remark"] = "Exclude"

    # 3. 新增欄位 RT_Rank，先設為 NaN
    df["RT_Rank"] = None

    # 4. 排除 Exclude 資料後，每組 combination 用 Return 欄位排名，結果寫入 RT_Rank
    mask_include = df["Remark"] != "Exclude"
    df.loc[mask_include, "RT_Rank"] = (
        df[mask_include]
        .groupby("Combination")["Return"]
        .rank(ascending=False, method="min")
    )

    # 5. 再依每組 combination，將 RT_Rank 分為 10 組（等頻），PR90 為 Winner，PR10 為 Loser
    def assign_winner_loser(group):
        # 排除 Exclude
        group = group.copy()
        mask = group["Remark"] != "Exclude"
        if mask.sum() >= 10:  # 確保有足夠資料分成 10 分位
            group.loc[mask, "Quantile"] = pd.qcut(group.loc[mask, "RT_Rank"], 10, labels=False) + 1
            group.loc[group["Quantile"] == 1, "Remark"] = "Winner"
            group.loc[group["Quantile"] == 10, "Remark"] = "Loser"
        return group.drop(columns="Quantile", errors="ignore")

    df = df.groupby("Combination", group_keys=False).apply(assign_winner_loser)

    df.to_csv(targetFile, index=False)
    print(f"✅ Step03：Remark欄位處理完成，已儲存檔案：{targetFile}")


### Step04：寫入RT_6M_After欄位
targetFile = f'{outputDir}/{outputFilBaseName}_rt_6m_after.csv'
if os.path.exists(targetFile):
    df = pd.read_csv(targetFile)
    print(f"✅ Step04：寫入RT_6M_After欄位檔案已存在：{targetFile}")
    # print(df.head())  # 顯示前五筆資料
else:
    # 確保欄位無空白
    df.columns = df.columns.str.strip()  # 移除欄位名稱的空白

    # 將 Combination 加 6 個月的函數
    def shift_combination(comb_str, months=6):
        try:
            start_str, end_str = comb_str.split("-")
            start_dt = datetime.strptime(start_str, "%Y%m")
            end_dt = datetime.strptime(end_str, "%Y%m")
            new_start = start_dt + relativedelta(months=months)
            new_end = end_dt + relativedelta(months=months)
            return f"{new_start.strftime('%Y%m')}-{new_end.strftime('%Y%m')}"
        except:
            return None

    # 只對 Winner / Loser 做轉換，產生要找的 Combination
    df["Target_Combination"] = df.apply(
        lambda row: shift_combination(row["Combination"]) if str(row["Remark"]).strip() in ["Winner", "Loser"] else None,
        axis=1
    )

    # 建立查詢表：Stock_id + Combination → Return
    lookup_df = df[["Stock_id", "Combination", "Return"]].copy()
    lookup_df = lookup_df.rename(columns={
        "Combination": "Target_Combination",
        "Return": "RT_6M_After"
    })

    # 合併資料
    df = df.merge(lookup_df, on=["Stock_id", "Target_Combination"], how="left")

    # 移除中介欄位
    df.drop(columns=["Target_Combination"], inplace=True)

    # 調整欄位順序，把 RT_6M_After 移到最後
    cols = [col for col in df.columns if col != "RT_6M_After"] + ["RT_6M_After"]
    df = df[cols]

    df.to_csv(targetFile, index=False)
    print(f"✅ Step04：RT_6M_After欄位處理完成，已儲存檔案：{targetFile}")


### Step05：將Step04的檔案中，RT_6M_After有值的資料提取出來
targetFile = f'{outputDir}/{outputFilBaseName}_rt_6m_after-filter.csv'
if os.path.exists(targetFile):
    df = pd.read_csv(targetFile)
    print(f"✅ Step05：篩出RT_6M_After欄位檔案已存在：{targetFile}")
    # print(df.head())  # 顯示前五筆資料
else:
    # 篩選 RT_6M_After 欄位不為空值的資料
    filtered_df = df[df["RT_6M_After"].notna()]
    
    filtered_df.to_csv(targetFile, index=False)
    print(f"✅ Step05：篩出RT_6M_After欄位處理完成，已儲存檔案：{targetFile}")
    

