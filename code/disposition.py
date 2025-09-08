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

anaDir = "../data/analysis/disposition"
### Part01：計算處置股公布日放空報酬率
outputFile = f"{anaDir}/short_return_{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}.csv"
if os.path.exists(outputFile):
    df_disp = pd.read_csv(outputFile, dtype={"證券代號": str, "公布日期": datetime, "處置起始": datetime, "處置結束": datetime})
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
    df_disp = df_disp.dropna(
        
        subset=["開盤價", "收盤價"])

    # 計算放空報酬率
    df_disp["short_return"] = ((df_disp["開盤價"] - df_disp["收盤價"]) / df_disp["開盤價"]).round(4)

    df_disp.to_csv(outputFile, index=False, encoding="utf-8-sig")    


### Part02：查看特定券商該日有無購股
outputFile = f"{anaDir}/short_return_{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}-broker_buy.csv"
if os.path.exists(outputFile):
    df_disp = pd.read_csv(outputFile, dtype={"證券代號": str, "公布日期": datetime, "處置起始": datetime, "處置結束": datetime})
    print(f'已知特定券商該日有無購股：{outputFile}')
else:
    print(f'開始查找：特定券商該日有無購股')

    # 確保日期欄位轉成 datetime 格式
    df_disp["公布日期"] = pd.to_datetime(df_disp["公布日期"])
    data_dir = "../data/FinDB/disposition/tw_broker_daily_bs_stock_b"

    # 預設 broker_bought = -1
    df_disp["broker_bought"] = -1

    brokerList = ['9268','1650','9600','9800','1480','8440','5850','1440','1560','980K','8150','9666','585U','8560','592A','9101','9692','8888','9227','5920','918E','9A9R','700C','8880','7790','5854','9300','9A89','779Z','585C']

    for year in range(sDt.year, eDt.year + 1):
        for month in range(1, 13):
            print(f"******{year}/{month}")

            file_path = os.path.join(data_dir, f"{year}_{month}.csv")

            if not os.path.exists(file_path):
                print(f"⚠️ 檔案不存在: {file_path}")
                continue

            # 讀參照檔
            df_findBroker = pd.read_csv(file_path, parse_dates=["date"])

            # 篩出當年月的 disp 資料
            mask = (df_disp["公布日期"].dt.year == year) & (df_disp["公布日期"].dt.month == month)
            df_month = df_disp.loc[mask].copy()

            # 計算 df_findBroker 中的 (date, stock_id) 出現次數
            broker_counts = (
                df_findBroker.groupby(["date", "stock_id"])
                .size()
                .reset_index(name="count")
            )

            # 合併回 df_month（用 公布日期、證券代號 對應 date、stock_id）
            df_month = df_month.merge(
                broker_counts,
                left_on=["公布日期", "證券代號"],
                right_on=["date", "stock_id"],
                how="left"
            )

            # 更新 df_disp
            df_disp.loc[mask, "broker_bought"] = df_month["count"].fillna(0).astype(int).values
            df_disp.to_csv(outputFile, index=False, encoding="utf-8-sig") # 逐月存檔


### Part03：新增欄位T-20~T-1、T+1~T+10
outputFile = f"{anaDir}/short_return_{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}-series_close.csv"
backupDatesFile = f"{anaDir}/short_return_{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}-series_close-backup_dates.csv"
if os.path.exists(outputFile):
    df_disp = pd.read_csv(outputFile, dtype={"證券代號": str, "公布日期": datetime, "處置起始": datetime, "處置結束": datetime})
    print(f'***已存在-新增欄位T-20~T-1、T+1~T+10：{outputFile}')
else:
    print(f'***開始寫入-新增欄位T-20~T-1、T+1~T+10')
    df_disp = df_disp[["公布日期","證券代號","證券名稱","處置起始","處置結束","short_return","broker_bought"]]
    df_backup = df_disp[["公布日期","證券代號","證券名稱"]] 
    
    ### 新增欄位
    for i in range(1, (20 + 1)):
        df_disp[f'T-{i}'] = None
        df_backup[f'T-{i}_date'] = None
        df_backup[f'T-{i}'] = None

    for i in range(1, (10 + 1)):
        df_disp[f'T+{i}'] = None
        df_backup[f'T+{i}_date'] = None
        df_backup[f'T+{i}'] = None    
    
    for idx, row in df_disp.iterrows():
        # 找前20日：T-1~T-20
        sql = f"SELECT date, stock_id, close FROM public.tw_stock_daily_price_adj"
        sql += f" WHERE stock_id = '{row["證券代號"]}'"
        sql += f" AND date < '{row["公布日期"]}'"
        sql += f" ORDER BY date DESC, stock_id"
        sql += f" LIMIT 20"
        df_close_prices = finDB.exeQuery(sql, conn)
        
        for idx2, row2 in df_close_prices.iterrows():
            df_disp.at[idx, f"T-{(idx2 + 1)}"] = row2["close"]
            df_backup.at[idx, f"T-{(idx2 + 1)}_date"] = row2["date"]
            df_backup.at[idx, f"T-{(idx2 + 1)}"] = row2["close"]

        # 後10日：T+1~T+10
        sql = f"SELECT date, stock_id, close FROM public.tw_stock_daily_price_adj"
        sql += f" WHERE stock_id = '{row["證券代號"]}'"
        sql += f" AND date > '{row["公布日期"]}'"
        sql += f" ORDER BY date ASC, stock_id"
        sql += f" LIMIT 10"
        df_close_prices = finDB.exeQuery(sql, conn)

        for idx2, row2 in df_close_prices.iterrows():
            df_disp.at[idx, f"T+{(idx2 + 1)}"] = row2["close"]
            df_backup.at[idx, f"T+{(idx2 + 1)}_date"] = row2["date"]
            df_backup.at[idx, f"T+{(idx2 + 1)}"] = row2["close"]

        print(idx, row["公布日期"], row["證券代號"], row["證券名稱"])

    df_disp.to_csv(outputFile, index=False, encoding="utf-8-sig")
    df_backup.to_csv(backupDatesFile, index=False, encoding="utf-8-sig")

### Part04：對交易前後的價格進行分析


conn.close()