import pandas as pd
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pathlib import Path
import sys
import glob
from scipy import stats
import gc

import re
from pandas.errors import EmptyDataError
import calendar

from common import utils
from common import finMind
from common import anaData
from common.constants import Panel
from common.constants import Iloc

### in PowerShell：
# $OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
# python -u momentumAna.py 2>&1 | Tee-Object -FilePath ../log/momentumAna.log -Append
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

# 起始訊息
print("")
utils.ptMsg("⚙️ momentumAna.py Run")

# 起始與結束年月
start_ym = "2010/01" # 取月初
end_ym = "2024/12" # 取月底
# end_ym = "2019/12" # 取月底

start_year, start_month = map(int, start_ym.split('/'))
end_year, end_month = map(int, end_ym.split('/'))
sDt = datetime(start_year, start_month, 1)
eDt = datetime(end_year, end_month, calendar.monthrange(end_year, end_month)[1])

prepareDatas = False

### 計算加權指數月報酬
output_file = f'../data/analysis/summary/weightIdx/dPriceAdj-200501_202412-mRet.csv'
if os.path.exists(output_file):
    observer_df = pd.read_csv(output_file)
    utils.ptMsg(f"☑️ 檔案已存在：{output_file}")
else:
    utils.ptMsg("📢 開始製作" + str(output_file))
    
    # 抓加權指數日價
    src_file = f'../data/analysis/summary/weightIdx/dPriceAdj-200501_202412.csv'
    df = pd.read_csv(src_file, encoding="utf-8")

    # 轉成每月最後一天的收盤價
    df["date"] = pd.to_datetime(df["date"])
    df_monthly = df.resample("ME", on="date").last()
    df_monthly = df_monthly.drop(columns=['Trading_Volume','Trading_money','spread','Trading_turnover'])

    # 計算月報酬率
    df_monthly["ret"] = df_monthly["close"].pct_change()
    df_monthly.to_csv(output_file, index=True, encoding="utf-8-sig")
    utils.ptMsg(f"✅ 已輸出檔案：{output_file}")
    

### 計算無風險月利率 (用五大銀行定存利率估算)
output_file = f'../data/CentralBank/五大行平均一年期固定定存利率月利率-200101_202507.csv'
if os.path.exists(output_file):
    observer_df = pd.read_csv(output_file)
    utils.ptMsg(f"☑️ 檔案已存在：{output_file}")
else:
    utils.ptMsg("📢 開始製作" + str(output_file))

    # 抓加權指數日價
    src_file = f'../data/CentralBank/五大銀行存放款利率歷史月資料-200101_202507.csv'
    df = pd.read_csv(src_file, encoding="utf-8")
    
    # 每月五大銀行一年期定存平均
    monthly_avg = (
        df.groupby("西元年月")["定存利率-一年期-固定"]
        .mean()
        .reset_index(name="avg_rate_yr")
    )

    # 轉成月利率
    monthly_avg["risk_free_monthly"] = (1 + monthly_avg["avg_rate_yr"] / 100) ** (1/12) - 1
    monthly_avg.to_csv(output_file, index=False, encoding="utf-8-sig")
    utils.ptMsg(f"✅ 已輸出檔案：{output_file}")

    # # 載入策略報酬率
    # strategy_df = pd.read_csv("strategy_returns.csv")  # 假設你的策略資料
    # merged = pd.merge(strategy_df, monthly_avg, on="西元年月", how="left")

    # # 超額報酬
    # merged["excess_return"] = merged["strategy_return"] - merged["risk_free_monthly"]

    # print(merged.head())

# 結束訊息
utils.ptMsg("⚙️ momentumAna.py Finish")
print("")