from FinMind.data import DataLoader
import os
import pandas as pd
from dateutil.relativedelta import relativedelta
from datetime import datetime
from scipy import stats
from scipy.stats import ttest_1samp
import numpy as np

# 整體資料區間
startYMD = "20160501" # included
endYMD = "20180601" # excluded

# 可調整觀察期（月數）
oHP = 6 # observeHoldingPeriod
rtHP = oHP # returnHoldingPeriod # 目前程式只能寫兩者設定是一樣的資料

outputDir = f'../data/analysis/momentum/{oHP}'
outputFilBaseName = f'Momentum0050_0051-{startYMD}_{endYMD}-HP_{oHP}_{rtHP}'


### 第一部分：抓取股價資料
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








### 第二部分：提取資料檔案



### 第三部分：進行T檢定