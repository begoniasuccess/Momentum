import pandas as pd

# 可調整觀察期（月數）
observeHoldingPeriod = 6

# 讀取原始資料
df = pd.read_csv(r'..\data\analysis\momentum\combinations\priceSrc_2016-05-01_2018-06-01.csv')
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values(by='date')

# 提取每月的第一日與最後一日
startDateList = df.groupby(df['date'].dt.to_period('M')).first()['date'].tolist()
endDateList = df.groupby(df['date'].dt.to_period('M')).last()['date'].tolist()
stockIdList = df['stock_id'].unique().tolist()

# 建立結果清單
result = []

# 遍歷組合窗口
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

# 轉成 DataFrame
result_df = pd.DataFrame(result)

# 新增 combination 欄位
result_df['combination'] = result_df['Start_Date'] + "_" + result_df['End_Date']

# 對每個 combination 群組依 Return 排序並加入 rank
result_df['rank'] = result_df.groupby('combination')['Return'].rank(method='min', ascending=False).astype(int)

# 儲存檔案
outputDir = r'..\data\analysis\momentum\combinations'
output_filename = f'{outputDir}/combinationReturn_2016-05-01_2018-06-01_HP-{observeHoldingPeriod}_ranked.csv'
result_df.to_csv(output_filename, index=False)

print(f"✅ 排名完成，已儲存檔案：{output_filename}")
