import sys
import pandas as pd
import calendar
import os
from module import finDB
from module import handleTwseTpex
from common import anaData
from scipy.stats import kurtosis

### in PowerShell：
# $OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
# python -u momentumMvRank.py 2>&1 | Tee-Object -FilePath ../log/momentumMvRank.log -Append
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

sDt = pd.to_datetime("2021-01-01")
eDt = pd.to_datetime("2025-08-24")

conn = finDB.getConn()

anaDir = "../data/analysis/disposition"
outputIdx = 0

### Part01：計算處置股公布日放空報酬率
outputIdx = outputIdx + 1
outputFile = f"{anaDir}/{outputIdx}-short_return_{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}.csv"
if os.path.exists(outputFile):
    df_disp = pd.read_csv(outputFile, dtype={"證券代號": str}, parse_dates=["公布日期", "處置起始", "處置結束"])
    print(f'***已知處置股放空報酬率：', outputFile)
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
        subset=["開盤價", "收盤價"]
    )

    # 計算放空報酬率
    df_disp["short_return"] = ((df_disp["開盤價"] - df_disp["收盤價"]) / df_disp["開盤價"]).round(4)

    df_disp.to_csv(outputFile, index=False, encoding="utf-8-sig")    

### Part02：查看特定券商該日有無購股
outputIdx = outputIdx + 1
outputFile = f"{anaDir}/{outputIdx}-short_return_{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}-broker_buy.csv"
if os.path.exists(outputFile):
    df_disp = pd.read_csv(outputFile, dtype={"證券代號": str}, parse_dates=["公布日期", "處置起始", "處置結束"])
    print(f'***已知特定券商該日有無購股：', outputFile)
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

### Part03：找尋公布日期前後的收盤價T-20~T-1、T+1~T+10
outputIdx = outputIdx + 1
outputFile = f"{anaDir}/{outputIdx}-series_close_price-{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}.csv"
if os.path.exists(outputFile):
    df_close_dates = pd.read_csv(outputFile, dtype={"stock_id": str}, parse_dates=["date"])
    print(f'***已存在-收盤價T-20~T-1、T+1~T+10：', outputFile)
else:
    print(f'***開始寫入-收盤價T-20~T-1、T+1~T+10')
    df_close_dates = pd.DataFrame(columns=["key", "stock_id", "T+n", "date", "close"])
    df_disp = df_disp[["公布日期","證券代號","證券名稱","收盤價"]]
    for idx, row in df_disp.iterrows():
        tDate = row["公布日期"].strftime("%Y-%m-%d")
        stockId = row["證券代號"]
        print(idx, tDate, stockId, row["證券名稱"])

        key =  row["公布日期"].strftime("%Y%m%d") + "-" + stockId
        df_close_dates.loc[len(df_close_dates)] = [key, stockId, 0, tDate, row["收盤價"]]
        
        # 找前20日：T-1~T-20
        sql = f"SELECT date, stock_id, close"
        sql += f" FROM public.tw_stock_daily_price_adj"
        sql += f" WHERE stock_id = '{row["證券代號"]}'"
        sql += f" AND date < '{row["公布日期"]}'"
        sql += f" ORDER BY date DESC, stock_id"
        sql += f" LIMIT 20"
        df_close_prices = finDB.exeQuery(sql, conn)
        for idx2, row2 in df_close_prices.iterrows():
            df_close_dates.loc[len(df_close_dates)] = [key, stockId, -(idx2 + 1), row2["date"].strftime("%Y-%m-%d"), row2["close"]]

        # 後10日：T+1~T+10
        sql = f"SELECT date, stock_id, close"
        sql += f" FROM public.tw_stock_daily_price_adj"
        sql += f" WHERE stock_id = '{row["證券代號"]}'"
        sql += f" AND date > '{row["公布日期"]}'"
        sql += f" ORDER BY date ASC, stock_id"
        sql += f" LIMIT 10"
        df_close_prices = finDB.exeQuery(sql, conn)

        for idx2, row2 in df_close_prices.iterrows():
            df_close_dates.loc[len(df_close_dates)] = [key, stockId, (idx2 + 1), row2["date"].strftime("%Y-%m-%d"), row2["close"]]

        # 每N筆存檔一次
        if idx % 100 == 0:
            df_close_dates.to_csv(outputFile, index=False, encoding="utf-8-sig")        
        
    df_close_dates.to_csv(outputFile, index=False, encoding="utf-8-sig")

### Part04：對T-1~T-20的收盤價進行型態分析
outputIdx = outputIdx + 1
outputFile = f"{anaDir}/{outputIdx}-ana_pre_series_close-{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}.csv"
if os.path.exists(outputFile):
    df_ana_series_close = pd.read_csv(outputFile)
    print(f'***已存在-對T-1~T-20的收盤價進行型態分析：', outputFile)
else:
    print(f'***開始寫入-對T-1~T-20的收盤價進行型態分析')
    # # for test
    # df_close_dates = df_close_dates.head(31*5)

    # ---------- 篩選 T-1 ~ T-20 ----------
    df_sub = df_close_dates[df_close_dates["T+n"].between(-20, -1)].copy()

    # ---------- 每個 key 計算統計量 ----------
    summary = (
        df_sub.groupby("key")["close"]
        .agg(["mean", "std", "min", "max", "skew", lambda x: kurtosis(x, fisher=True)])
        .rename(columns={"<lambda_0>":"kurt"})
        .reset_index()
    )

    # ---------- 加上 trend_slope 與 max_drawdown ----------
    summary["trend_slope"] = df_sub.groupby("key").apply(anaData.trend_slope).values
    summary["max_drawdown"] = df_sub.groupby("key").apply(anaData.max_drawdown).values

    # ---------- 生成中文描述 ----------
    summary["std_cm"] = summary["std"].apply(anaData.interpret_volatility)
    summary["skew_cm"] = summary["skew"].apply(anaData.interpret_skew)
    summary["kurt_cm"] = summary["kurt"].apply(anaData.interpret_kurt)
    summary["trend_slope_cm"] = summary["trend_slope"].apply(anaData.interpret_trend_slope)
    summary["max_drawdown_cm"] = summary["max_drawdown"].apply(anaData.interpret_maxdd)

    # ---------- 拆 key ----------
    summary[["date","stock_id"]] = summary["key"].str.split("-", expand=True)

    # ---------- 輸出 ----------
    summary.to_csv(outputFile, index=False, encoding="utf-8-sig")
    print("完成 ✅，結果已輸出至", outputFile)

### Part05：對T+1~T+10的收盤價進行型態分析
outputIdx = outputIdx + 1
outputFile = f"{anaDir}/{outputIdx}-ana_aft_series_close-{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}.csv"
if os.path.exists(outputFile):
    df_ana_series_close = pd.read_csv(outputFile)
    print(f'***已存在-對T+1~T+10的收盤價進行型態分析：', outputFile)
else:
    print(f'***開始寫入-對T+1~T+10的收盤價進行型態分析')
    # ---------- 篩選 T+1 ~ T+10 ----------
    df_sub = df_close_dates[df_close_dates["T+n"].between(1, 10)].copy()

    # ---------- 每個 key 計算統計量 ----------
    summary = (
        df_sub.groupby("key")["close"]
        .agg(["mean", "std", "min", "max", "skew", lambda x: kurtosis(x, fisher=True)])
        .rename(columns={"<lambda_0>":"kurt"})
        .reset_index()
    )

    # ---------- 加上 trend_slope 與 max_drawdown ----------
    summary["trend_slope"] = df_sub.groupby("key").apply(anaData.trend_slope).values
    summary["max_drawdown"] = df_sub.groupby("key").apply(anaData.max_drawdown).values

    # ---------- 生成中文描述 ----------
    summary["std_cm"] = summary["std"].apply(anaData.interpret_volatility)
    summary["skew_cm"] = summary["skew"].apply(anaData.interpret_skew)
    summary["kurt_cm"] = summary["kurt"].apply(anaData.interpret_kurt)
    summary["trend_slope_cm"] = summary["trend_slope"].apply(anaData.interpret_trend_slope)
    summary["max_drawdown_cm"] = summary["max_drawdown"].apply(anaData.interpret_maxdd)

    # ---------- 拆 key ----------
    summary[["date","stock_id"]] = summary["key"].str.split("-", expand=True)

    # ---------- 輸出 ----------
    summary.to_csv(outputFile, index=False, encoding="utf-8-sig")
    print("完成 ✅，結果已輸出至", outputFile)

### 釋放資源
del df_close_dates 
del df_ana_series_close

### Part06：處置股資料串交易量
# 新增的欄位：avg_vol_5T、max_vol_5T、vol_diff_5T
outputIdx = outputIdx + 1
outputFile = f"{anaDir}/{outputIdx}-volume-{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}.csv"
if os.path.exists(outputFile):
    df_vols = pd.read_csv(outputFile)
    print(f'***已存在-處置股資料串交易量：', outputFile)
else:
    print(f'***開始寫入-處置股資料串交易量')

    # ### test
    # df_disp = df_disp.head(10)

    # 新增欄位
    for N in [5, 10, 20]:
        df_disp[f"avg_vol_{N}T"] = None
        df_disp[f"max_vol_{N}T"] = None
        df_disp[f"vol_diff_{N}T"] = None

    for idx, row in df_disp.iterrows():
        tDate = row["公布日期"].strftime("%Y-%m-%d")
        stockId = row["證券代號"]

        sql = f'SELECT date, stock_id, t_volume'
        sql += f' FROM public.tw_stock_daily_price_adj'
        sql += f" WHERE date <= '{tDate}' AND stock_id = '{stockId}'"
        sql += f" ORDER BY date DESC"
        sql += f" LIMIT 20"
        df_vols = finDB.exeQuery(sql, conn)
        
        df_vols["date"] = pd.to_datetime(df_vols["date"])
        df_vols = df_vols.sort_values("date")
        # print(df_vols)
        # df_vols.to_csv("test.csv")

        # 計算 5、10、20 日
        for N in [5, 10, 20]:
            stats = anaData.calc_vol_stats(N, df_vols, row["公布日期"])
            df_disp.at[idx, f"avg_vol_{N}T"] = stats["avg_vol"]
            df_disp.at[idx, f"max_vol_{N}T"] = stats["max_vol"]
            df_disp.at[idx, f"vol_diff_{N}T"] = stats["vol_diff"]

    df_disp.to_csv(outputFile, index=False, encoding="utf-8-sig")
    print("完成 ✅，結果已輸出至", outputFile)    
    
conn.close()