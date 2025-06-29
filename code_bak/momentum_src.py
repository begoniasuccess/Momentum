from FinMind.data import DataLoader
import os
import pandas as pd

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

api = DataLoader()

# 台股日交易資料是免費的 => 理論上可以不用登入！
# 如果呼叫次數太多，還是需要登入(會被擋！)
token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNS0wNi0yMyAyMjoyNzoyNCIsInVzZXJfaWQiOiJueWN1bGFiNjE1IiwiaXAiOiI0Mi43My4xODcuNzAiLCJleHAiOjE3NTEyOTM2NDR9.PgiV0M8-hNg-YO5gXZVELOh24IMK2JLS840OSGGLufE"
api.login_by_token(api_token=token)
# api.login(user_id='user_id',password='password')

outputFileDir = "../data/analysis/momentum/combinations"
os.makedirs(outputFileDir, exist_ok=True)

wholeSD = "2016-05-01"
wholeED = "2018-06-01"

stockListsDF = pd.read_csv("../data/analysis/summary/closingPrice2013-2019.csv") 
stockIds = stockListsDF.iloc[:, 0].astype(str).tolist()

mergedDF = None
stockDF = None
for stockId in stockIds:
    print("== Now processing stock：" + stockId)
    fileName = "TW" + stockId + "_" + wholeSD + "_" + wholeED + ".csv"
    stockDF = searchStocskData(stockId, fileName)
    if stockDF is None:
        stockDF = api.taiwan_stock_daily(
            stock_id=stockId,
            start_date=wholeSD,
            end_date=wholeED
        )
        savePath = getRepositorySavePath(stockId, fileName)
        stockDF.to_csv(savePath, index=True, encoding='utf-8-sig')
    
    try:
        stockDF = stockDF[['date', 'stock_id', 'close']]
        # 合併df
        if mergedDF is None:
            mergedDF = stockDF
        else:
            mergedDF = pd.concat([mergedDF, stockDF], ignore_index=True)
    except Exception as e:
        print(f"[Warning]：{e}")
        

fileName = f"priceSrc_{wholeSD}_{wholeED}.csv"
csvPath = f"{outputFileDir}/{fileName}"
mergedDF.to_csv(csvPath, index=True, encoding='utf-8-sig')
print(mergedDF)