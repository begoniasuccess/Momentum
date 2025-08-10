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

prepareDatas = False

# 抓加權指數日價
# df = dl.taiwan_stock_price(stock_id="TAIEX", start_date="2010-01-01", end_date="2024-12-31")


# 轉成每月最後一天的收盤價
df["date"] = pd.to_datetime(df["date"])
df_monthly = df.resample("M", on="date").last()

# 計算月報酬率
df_monthly["ret"] = df_monthly["close"].pct_change()


# 結束訊息
utils.ptMsg("⚙️ momentumAna.py Finish")
print("")