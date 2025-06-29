import pandas as pd
from dateutil.relativedelta import relativedelta

# 可調整觀察期（月數）
observeHoldingPeriod = 6
# (index), dates, tock_id, close
srcDataPath = r'..\data\analysis\momentum\combinations\priceSrc_2016-05-01_2018-06-01.csv'
outputDir = r'..\data\analysis\momentum'

# 讀取原始資料
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
                'Start_Date': start_date.strftime('%Y-%m-%d'),
                'End_Date': end_date.strftime('%Y-%m-%d'),
                'Start_Price': start_price,
                'End_Price': end_price,
                'Return': ret
            })
result_df = pd.DataFrame(result)

# 新增 combination 欄位
result_df['combination'] = result_df['Start_Date'] + "_" + result_df['End_Date']

# 對每個 combination 群組依 Return 排序並加入 rank
result_df['rank'] = result_df.groupby('combination')['Return'].rank(method='min', ascending=False).astype(int)

# 儲存檔案
output_filename = f'{outputDir}/combinationReturn_2016-05-01_2018-06-01_HP-{observeHoldingPeriod}_ranked.csv'
result_df.to_csv(output_filename, index=False)

print(f"✅ 排名完成，已儲存檔案：{output_filename}")

# 新增 remark 欄位，預設為空
result_df['remark'] = ''

# 每個 combination 內依 rank 做分組
def assign_remark(group):
    n = len(group)
    if n < 10:
        return group  # 太少不分組
    group = group.sort_values(by='rank')  # rank越小報酬越高

    # 計算前10% 和 後10% 的 rank 數值閾值
    top_threshold = max(1, int(n * 0.9))  # PR90 = top 10%
    bottom_threshold = int(n * 0.1)       # PR10 = bottom 10%

    # 根據 rank 指定 Winner / Loser
    group.loc[group['rank'] <= bottom_threshold, 'remark'] = 'Winner'
    group.loc[group['rank'] >= top_threshold, 'remark'] = 'Loser'

    return group

# 分組套用邏輯
result_df = result_df.groupby('combination', group_keys=False).apply(assign_remark)

output_filename = f'{outputDir}/combinationReturn_2016-05-01_2018-06-01_HP-{observeHoldingPeriod}_remarked.csv'
result_df.to_csv(output_filename, index=False)

print(f"✅ Winner/Loser 標記已完成，已儲存 {output_filename} 檔案")


# 讀取資料
df = pd.read_csv(output_filename, parse_dates=["Start_Date", "End_Date"])

# 新增 YearMonth 欄位（取 Start_Date 的年月）
df["YearMonth"] = df["Start_Date"].dt.to_period("M")

# 篩選 Winner / Loser
df_filtered = df[df["remark"].isin(["Winner", "Loser"])].copy()

# 計算六個月後的年月
df_filtered["TargetYM"] = df_filtered["Start_Date"].apply(lambda x: (x + relativedelta(months=6)).to_period("M"))

# 建立查詢用的 DataFrame：Stock_id + YearMonth → Return
lookup_df = df[["Stock_id", "YearMonth", "Return"]].copy()
lookup_df = lookup_df.drop_duplicates(subset=["Stock_id", "YearMonth"])  # 避免多筆

# 合併查詢
merged = pd.merge(
    df_filtered[["Stock_id", "Start_Date", "TargetYM"]],
    lookup_df,
    left_on=["Stock_id", "TargetYM"],
    right_on=["Stock_id", "YearMonth"],
    how="left"
)

# 回填回原始 DataFrame
df["after6monthsReturn"] = float("nan")
df.loc[df_filtered.index, "after6monthsReturn"] = merged["Return"].values

# 儲存結果
output_filename = f'{outputDir}/combinationReturn_2016-05-01_2018-06-01_HP-{observeHoldingPeriod}_after6monthsReturn.csv'
df.to_csv(output_filename, index=False)

print(f"✅ 6個月後的報酬率填寫已完成，已儲存 {output_filename} 檔案")


# 篩選 after6monthsReturn 有值的資料
df_with_return = df[df["after6monthsReturn"].notna()]

# 儲存成另一個檔案
df_with_return.to_csv(f'{outputDir}/output_after6monthsReturn_only.csv', index=False)