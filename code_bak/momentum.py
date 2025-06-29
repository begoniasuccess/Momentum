from FinMind.data import DataLoader
import os
import pandas as pd
import csv


def caculateEndDate(startDate, intervalMonths):
    start = pd.to_datetime(startDate)
    end = start + pd.DateOffset(months=intervalMonths)

    endDate = end.strftime('%Y-%m-%d')
    print(endDate)
    return endDate

def getRepositorySavePath(stockId, filename):    
    repositoryDir = "../data/FinMind/TW/DailyPrice"
    savePath = f"{repositoryDir}/{stockId}/{filename}"
    os.makedirs(os.path.dirname(savePath), exist_ok=True)
    return savePath

def searchStocskData(stockId, filename):
    srcPath = getRepositorySavePath(stockId, filename)
    if not os.path.exists(srcPath):
        return None
    df = pd.read_csv(srcPath)
    return df

# "../data/min_data_2013-2019/2016/averageprice/20160104_averagePrice_min.csv"\
def getStockListSrcCsvPath(dateStr):
    dt = pd.to_datetime(dateStr)
    base_dir = "../data/min_data_2013-2019"    
    csvPath = f"{base_dir}/{dt.strftime("%Y")}/averageprice/{dt.strftime("%Y%m%d")}_averagePrice_min.csv"
    if not os.path.exists(csvPath):
        dt = dt + pd.DateOffset(days=1)        
        return getStockListSrcCsvPath(dt.strftime("%Y-%m-%d"))
    return csvPath

api = DataLoader()
# 台股日交易資料是免費的 => 不用登入！
token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNS0wNi0xNSAxMDo0MDoxNCIsInVzZXJfaWQiOiJueWN1bGFiNjE1IiwiaXAiOiI0Mi43Mi4xNDIuMjQiLCJleHAiOjE3NTA1NjAwMTR9.3MiziI-uBY2TgQNNpvvB7TK1ZTBK2t3Db69k0QTqNVo"
api.login_by_token(api_token=token)
# api.login(user_id='user_id',password='password')

outputFileDir = "../data/analysis/momentum/combinations"
os.makedirs(outputFileDir, exist_ok=True)

wholeSD = "2016-05-01"
wholeED = "2018-06-01"

observerPeriod = 6 # J monthes
holdingPeriod = 6 # K monthes

### Step01 取得組合
fstCombinationSD = wholeSD
lastCombinationSD = caculateEndDate(wholeED, 0 - observerPeriod)

 # MS = Month Start，每月1號
CombinationIterator = pd.date_range(start=fstCombinationSD, end=lastCombinationSD, freq='MS') 
for combinationSDdt in CombinationIterator:
    combinationSD = combinationSDdt.strftime("%Y-%m-%d")
    combinationED = caculateEndDate(combinationSD, observerPeriod)

    fileName = f"combination_{combinationSD}_{combinationED}.csv"
    csvPath = f"{outputFileDir}/{fileName}"

    if os.path.exists(csvPath):
        continue

    nowStockListSrcCsv = getStockListSrcCsvPath(combinationSD)
    with open(nowStockListSrcCsv, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        stockIds = next(reader)

        mergedDF = None
        stockDF = None
        for stockId in stockIds:
            print("== Now processing stock：" + stockId)
            fileName = "TW" + stockId + "_" + combinationSD + "_" + combinationED + ".csv"
            stockDF = searchStocskData(stockId, fileName)
            if stockDF is None:
                stockDF = api.taiwan_stock_daily(
                    stock_id=stockId,
                    start_date=combinationSD,
                    end_date=combinationED
                )
                savePath = getRepositorySavePath(stockId, fileName)
                stockDF.to_csv(savePath, index=True, encoding='utf-8-sig')
            
            stockDF = stockDF[['date', 'stock_id', 'close']]

            # 合併df
            if mergedDF is None:
                mergedDF = stockDF
            else:
                mergedDF = pd.concat([mergedDF, stockDF], ignore_index=True)

        mergedDF.to_csv(csvPath, index=True, encoding='utf-8-sig')
        print(mergedDF)