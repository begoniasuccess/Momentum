import sys
import pandas as pd
import psycopg2
import calendar
import datetime
from sqlalchemy import create_engine
import os
from common import finDB
from code.common import handleTwseTpex

### in PowerShell：
# $OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
# python -u momentumMvRank.py 2>&1 | Tee-Object -FilePath ../log/momentumMvRank.log -Append
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

sDt = pd.to_datetime("2021-01-01")
eDt = pd.to_datetime("2025-08-24")


### Part01：計算上市處置股公布日放空報酬率
stockType = "twse"
outputFile = f"../data/analysis/disposition/short_return_{type}-{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}.csv"
if os.path.exists(outputFile):
    df_disp_twse = pd.read_csv(outputFile)
    print(f'上市處置股放空報酬率已計算完成：{outputFile}')
else:
    print(f'開始計算：上市處置股放空報酬率')
    srcDir = f"../data/TwStockExchange/DispositionStock"
    srcDataPath = f"{srcDir}/twse-{sDt.strftime('%Y%m%d')}_{eDt.strftime('%Y%m%d')}-simple.csv"
    if not os.path.exists(srcDataPath):
        if not handleTwseTpex.handleDispositionStockFile(sDt, eDt, True, stockType):
            print(f"Not exit： {srcDataPath}")
            sys.exit()    
    df_disp_twse = pd.read_csv(srcDataPath, parse_dates=["公布日期", "處置起始", "處置結束"])

    table = "tw_stock_daily_price_adj"

    for year in range(sDt.year, eDt.year + 1):
        for month in range(1, 13):
            print(f"******{year}/{month}")

            last_day = calendar.monthrange(year, month)[1]
            startDate = pd.to_datetime(f"{year}-{month}-01")
            endDate = pd.to_datetime(f"{year}-{month}-{last_day}")

            mask = (df_disp_twse["公布日期"] >= startDate) & (df_disp_twse["公布日期"] <= endDate)
            df_filter_month = df_disp_twse.loc[mask]

            stockList = df_filter_month["證券代號"].unique().tolist()
            if not stockList:
                continue

            stockSql = "','".join(map(str, stockList))
            sql = f"SELECT date, stock_id, open, close FROM public.{table} WHERE date BETWEEN '{startDate:%Y-%m-%d}' AND '{endDate:%Y-%m-%d}' AND stock_id IN ('{stockSql}') ORDER BY date, stock_id"
            df_price = finDB.exeQuery(sql)
            df_price["date"] = pd.to_datetime(df_price["date"])

            # 建立 key 對應字典
            df_price_dict_open = df_price.set_index(['date','stock_id'])['open'].to_dict()
            df_price_dict_close = df_price.set_index(['date','stock_id'])['close'].to_dict()

            # 填回原 df_disp_twse
            for idx, row in df_filter_month.iterrows():
                key = (row['公布日期'], row['證券代號'])
                df_disp_twse.at[idx, '開盤價'] = df_price_dict_open.get(key)
                df_disp_twse.at[idx, '收盤價'] = df_price_dict_close.get(key)
        
        # 每月存檔一次
        df_disp_twse.to_csv(outputFile, index=False)

    # 刪掉開盤價或收盤價為空的列
    df_disp_twse = df_disp_twse.dropna(subset=["開盤價", "收盤價"])

    # 計算放空報酬率
    df_disp_twse["short_return"] = ((df_disp_twse["開盤價"] - df_disp_twse["收盤價"]) / df_disp_twse["開盤價"]).round(4)

    df_disp_twse.to_csv(outputFile, index=False, encoding="utf-8-sig")

### Part02：計算[上櫃]處置股公布日放空報酬率
stockType = "tpex"
outputFile = f"../data/analysis/disposition/short_return_{type}-{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}.csv"
if os.path.exists(outputFile):
    df_disp_twse = pd.read_csv(outputFile)
    print(f'上櫃處置股放空報酬率已計算完成：{outputFile}')
else:
    print(f'開始計算：上櫃處置股放空報酬率')
    
