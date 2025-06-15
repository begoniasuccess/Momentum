from FinMind.data import DataLoader
import os
import pandas as pd


api = DataLoader()

# 台股日交易資料是免費的 => 不用登入！
# api.login_by_token(api_token='token')
# api.login(user_id='user_id',password='password')

fileDir = "../data/tmp"
os.makedirs(fileDir, exist_ok=True)


startDate = "2016-05-01"
endDate = "2016-06-01"

stockIds = ['2330', '1102', '1216']

mergedDF = None
stockDF = None
for stockId in stockIds:
    print("== Now processing stock：" + stockId)
    stockDF = api.taiwan_stock_daily(
        stock_id=stockId,
        start_date=startDate,
        end_date=endDate
    )
    fileName = "TW" + stockId + "_" + startDate + "_" + endDate + ".csv"
    csvPath = fileDir + "/" + fileName
    stockDF.to_csv(csvPath, index=True, encoding='utf-8-sig')
    stockDF = stockDF[['date', 'stock_id', 'close']]

    # 合併df
    if mergedDF is None:
        mergedDF = stockDF
    else:
        mergedDF = pd.concat([mergedDF, stockDF], ignore_index=True)

fileName = "TW_summary_" + startDate + "_" + endDate + ".csv"
csvPath = fileDir + "/" + fileName
mergedDF.to_csv(csvPath, index=True, encoding='utf-8-sig')
print(mergedDF)