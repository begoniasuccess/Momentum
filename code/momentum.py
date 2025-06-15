from FinMind.data import DataLoader
import os
import pandas as pd
import csv

outputFileDir = "../data/tmp"
os.makedirs(outputFileDir, exist_ok=True)


startDate = "2016-05-01"
endDate = "2016-06-01"

api = DataLoader()

# 台股日交易資料是免費的 => 不用登入！
# api.login_by_token(api_token='token')
# api.login(user_id='user_id',password='password')

repositoryDir = "../data/FinMind/TW/DailyPrice"
def getRepositorySavePath(stockId, filename):    
    savePath = repositoryDir + "/" + stockId + "/" + filename    
    os.makedirs(os.path.dirname(savePath), exist_ok=True)
    return savePath

def searchStocskData(stockId, filename):
    srcPath = getRepositorySavePath(stockId, filename)
    if not os.path.exists(srcPath):
        return None
    df = pd.read_csv(srcPath)
    return df

nowStockListSrcCsv = "../data/min_data_2013-2019/2016/averageprice/20160104_averagePrice_min.csv"
with open(nowStockListSrcCsv, newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    stockIds = next(reader)
    # print(stockIds)

    mergedDF = None
    stockDF = None
    for stockId in stockIds:
        print("== Now processing stock：" + stockId)
        fileName = "TW" + stockId + "_" + startDate + "_" + endDate + ".csv"
        stockDF = searchStocskData(stockId, fileName)
        if stockDF is None:
            stockDF = api.taiwan_stock_daily(
                stock_id=stockId,
                start_date=startDate,
                end_date=endDate
            )
            savePath = getRepositorySavePath(stockId, fileName)
            stockDF.to_csv(savePath, index=True, encoding='utf-8-sig')
        
        stockDF = stockDF[['date', 'stock_id', 'close']]

        # 合併df
        if mergedDF is None:
            mergedDF = stockDF
        else:
            mergedDF = pd.concat([mergedDF, stockDF], ignore_index=True)

    fileName = "TW_summary_" + startDate + "_" + endDate + ".csv"
    csvPath = outputFileDir + "/" + fileName
    mergedDF.to_csv(csvPath, index=True, encoding='utf-8-sig')
    print(mergedDF)