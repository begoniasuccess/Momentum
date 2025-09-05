import sys
import pandas as pd
import psycopg2
import calendar
import datetime
from sqlalchemy import create_engine
import os
from common import finDB
from common import handleTwseTpex

### in PowerShell：
# $OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
# python -u momentumMvRank.py 2>&1 | Tee-Object -FilePath ../log/momentumMvRank.log -Append
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

sDt = pd.to_datetime("2021-01-01")
eDt = pd.to_datetime("2025-08-24")

conn = finDB.getConn()

### Part01：計算處置股公布日放空報酬率
outputFile = f"../data/analysis/disposition/short_return_{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}.csv"
if os.path.exists(outputFile):
    df_disp = pd.read_csv(outputFile)
    print(f'處置股放空報酬率已計算完成：{outputFile}')
else:
    print(f'開始計算：處置股放空報酬率')
    
    ### 合併上市、上櫃的處置原始資料
    pre_df_disp = None
    srcDataInfos = [
        {"stockType": "twse", "srcDir": "../data/TwStockExchange/DispositionStock"},
        {"stockType": "tpex", "srcDir": "../data/TpeExchange/DispositionStock"}
    ]
    for srcDataInfo in srcDataInfos:
        stockType = srcDataInfo["stockType"]
        srcDir = srcDataInfo["srcDir"]
        srcDataPath = f"{srcDir}/{stockType}-{sDt.strftime('%Y%m%d')}_{eDt.strftime('%Y%m%d')}-simple.csv"
        if not os.path.exists(srcDataPath):
            if not handleTwseTpex.handleDispositionStockFile(sDt, eDt, True, stockType):
                print(f"Not exit： {srcDataPath}")
                sys.exit()    
        
        df_disp = pd.read_csv(srcDataPath, parse_dates=["公布日期", "處置起始", "處置結束"])
        if pre_df_disp is not None:
            df_disp = pd.concat([pre_df_disp, df_disp], ignore_index=True)
        pre_df_disp = df_disp

    df_disp = df_disp.sort_values(by=["公布日期", "證券代號"]).reset_index(drop=True)
    for year in range(sDt.year, eDt.year + 1):
        for month in range(1, 13):
            print(f"******{year}/{month}")

            last_day = calendar.monthrange(year, month)[1]
            startDate = pd.to_datetime(f"{year}-{month}-01")
            endDate = pd.to_datetime(f"{year}-{month}-{last_day}")

            mask = (df_disp["公布日期"] >= startDate) & (df_disp["公布日期"] <= endDate)
            df_filter_month = df_disp.loc[mask]

            stockList = df_filter_month["證券代號"].unique().tolist()
            if not stockList:
                continue

            stockSql = "','".join(map(str, stockList))
            sql = f"SELECT date, stock_id, open, close FROM public.tw_stock_daily_price_adj WHERE date BETWEEN '{startDate:%Y-%m-%d}' AND '{endDate:%Y-%m-%d}' AND stock_id IN ('{stockSql}') ORDER BY date, stock_id"
            df_price = finDB.exeQuery(sql, conn)
            df_price["date"] = pd.to_datetime(df_price["date"])

            # 建立 key 對應字典
            df_price_dict_open = df_price.set_index(['date','stock_id'])['open'].to_dict()
            df_price_dict_close = df_price.set_index(['date','stock_id'])['close'].to_dict()

            # 填回原 df_disp
            for idx, row in df_filter_month.iterrows():
                key = (row['公布日期'], row['證券代號'])
                df_disp.at[idx, '開盤價'] = df_price_dict_open.get(key)
                df_disp.at[idx, '收盤價'] = df_price_dict_close.get(key)
        
        # 每月存檔一次
        df_disp.to_csv(outputFile, index=False, encoding="utf-8-sig")

    # 刪掉開盤價或收盤價為空的列
    df_disp = df_disp.dropna(subset=["開盤價", "收盤價"])

    # 計算放空報酬率
    df_disp["short_return"] = ((df_disp["開盤價"] - df_disp["收盤價"]) / df_disp["開盤價"]).round(4)

    df_disp.to_csv(outputFile, index=False, encoding="utf-8-sig")    

### Part02：查看特定券商該日有無購股
outputFile = f"../data/analysis/disposition/short_return_{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}-broker_buy.csv"
if os.path.exists(outputFile):
    df_disp = pd.read_csv(outputFile)
    print(f'已知特定券商該日有無購股：{outputFile}')
else:
    print(f'開始查找：特定券商該日有無購股')

    # 確保日期欄位轉成 datetime 格式
    df_disp["公布日期"] = pd.to_datetime(df_disp["公布日期"])

    brokerList = ['9268','1650','9600','9800','1480','8440','5850','1440','1560','980K','8150','9666','585U','8560','592A','9101','9692','8888','9227','5920','918E','9A9R','700C','8880','7790','5854','9300','9A89','779Z','585C']

    for year in range(sDt.year, eDt.year + 1):
        for month in range(1, 13):
            print(f"******{year}/{month}")
            
            last_day = calendar.monthrange(year, month)[1]
            startDate = pd.to_datetime(f"{year}-{month}-01")
            endDate = pd.to_datetime(f"{year}-{month}-{last_day}")

            searchPath = f'../data/FinDB/disposition/tw_broker_daily_bs_stock_b/{year}_{month}.csv'
            if (os.path.exists(searchPath)):
                df_findBroker = pd.read_csv(searchPath)
            else:
                mask = (df_disp["公布日期"] >= startDate) & (df_disp["公布日期"] <= endDate)
                df_filter_month = df_disp.loc[mask]

                stockList = df_filter_month["證券代號"].unique().tolist()
                if not stockList:
                    continue

                stockSql = "','".join(map(str, stockList))
                brokerSql = "','".join(map(str, brokerList))
                sql = f"SELECT date, securities_trader_id AS broker_id, stock_id FROM public.tw_broker_daily_bs_stock_b"
                sql += f" WHERE date BETWEEN '{startDate:%Y-%m-%d}' AND '{endDate:%Y-%m-%d}'"
                sql += f" AND securities_trader_id IN ('{brokerSql}')"
                sql += f" AND stock_id IN ('{stockSql}')"
                # sql += f" ORDER BY date, stock_id" # 脫慢速度
                print(sql)
                df_findBroker = finDB.exeQuery(sql, conn)
                
                # 庫這邊搜尋速度很慢，所以存檔以利之後重跑
                df_findBroker.drop_duplicates(subset=['date','broker_id','stock_id'], inplace=True)
                df_findBroker.sort_values(by=['date', 'stock_id'], inplace=True)
                df_findBroker.to_csv(searchPath, index=False, encoding='utf-8-sig')
            
            if df_findBroker.empty:
                print(f"tw_broker_daily_bs_stock_b沒有對應資料！")
                continue # 前往下個月

            # continue # test
            
            # 轉 datetime（容錯）
            df_disp["公布日期"] = pd.to_datetime(df_disp["公布日期"], errors="coerce")
            df_findBroker["date"] = pd.to_datetime(df_findBroker["date"], errors="coerce")

            # 只比對 date 部分（移除 time 的影響）
            df_disp["公布日期_date"] = df_disp["公布日期"].dt.date
            df_findBroker["date_only"] = df_findBroker["date"].dt.date

            # 將證券代號/stock_id 統一成 str 並去空白
            df_disp["證券代號_str"] = df_disp["證券代號"].astype(str).str.strip()
            df_findBroker["stock_id_str"] = df_findBroker["stock_id"].astype(str).str.strip()

            # 建 lookup set
            lookup = set(zip(df_findBroker["date_only"], df_findBroker["stock_id_str"]))

            # 初始 broker_brought 為 pd.NA（若不存在）
            if "broker_brought" not in df_disp.columns:
                df_disp["broker_brought"] = pd.NA

            # 日期範圍與尚未處理的 mask
            start = pd.to_datetime(startDate)
            end = pd.to_datetime(endDate)
            mask_range = (df_disp["公布日期"] >= start) & (df_disp["公布日期"] <= end)
            mask_unprocessed = mask_range & df_disp["broker_brought"].isna()

            indices = df_disp.loc[mask_unprocessed].index.tolist()
            if not indices:
                print("No rows to process in this range.")
                continue

            # 逐列檢查（但只檢查未處理的列）
            vals = []
            for i in indices:
                key = (df_disp.at[i, "公布日期_date"], df_disp.at[i, "證券代號_str"])
                vals.append(1 if key in lookup else 0)

            df_disp.loc[indices, "broker_brought"] = vals

            # 簡短回報
            print(f"Processed {len(indices)} rows; matched = {sum(vals)}")
            df_disp.to_csv(outputFile, index=False, encoding="utf-8-sig") # 逐月存檔

conn.close()


