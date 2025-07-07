from FinMind.data import DataLoader
import pandas as pd
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pathlib import Path
import sys
import glob
from scipy import stats
from common import utils
import re
from pandas.errors import EmptyDataError

sys.stdout.reconfigure(encoding='utf-8')

def nowTime():
    """取得當前時間 (yyyy/mm/dd hh:mm:ss)"""
    return datetime.now().strftime("%Y/%m/%d %H:%M:%S")

def ptMsg(msg, msg2=None):
    """打印時間與日誌 (yyyy/mm/dd hh:mm:ss)"""
    
    print(f"{nowTime()}：{msg}")
    if msg2 is not None:
        print(msg2)

def inTimeRange(targetDt: datetime, sDt: datetime , eDt: datetime) -> bool:
    return sDt <= targetDt <= eDt

def getSdtEdt(filePath: str) -> dict[str, datetime]:
    filename = Path(filePath).stem # 去除附檔名後的檔名

    # 找到兩組6位數字
    matches = re.findall(r'(\d{6})', filename)

    start_str = matches[0]
    end_str = matches[1]

    sDt = datetime.strptime(start_str + '01', "%Y%m%d") # Start Date
    eDt = datetime.strptime(end_str + '01', "%Y%m%d") # End Date

    eDt = eDt + pd.offsets.MonthEnd(0) # 時間推移到月底

    result = {
        "sDt": sDt,
        "eDt": eDt
    }
    return result

def getCloseDf(sYear: str , searchY: int) -> pd.DataFrame:
    base_dir = r'..\data\analysis\summary'
    sYear_int = int(sYear)
    
    # 產生三年的檔案清單
    years = [str(sYear_int + i) for i in range(searchY)]
    filenames = [f'closePrice_{y}.csv' for y in years]
    filepaths = [os.path.join(base_dir, fname) for fname in filenames]
    
    close_dfs = []
    for fp in filepaths:
        if os.path.exists(fp):
            try:
                df = pd.read_csv(fp, parse_dates=['date'], dtype={'stock_id': str})
                close_dfs.append(df)
                print(f"讀取檔案：{fp}，筆數：{len(df)}")
            except Exception as e:
                print(f"讀取檔案 {fp} 發生錯誤：{e}")
        else:
            print(f"檔案不存在：{fp}")

    # 合併或建立空 DataFrame
    if close_dfs:
        close_df = pd.concat(close_dfs, ignore_index=True)
    else:
        close_df = pd.DataFrame()

    print(f"closePrice：年份 {sYear} ~ {int(sYear) + searchY - 1} 合併資料筆數：{len(close_df)}")
    print(close_df.head(3))
    ## for test
    close_df.to_csv(f"{base_dir}/closePrice_tmp.csv")
    return close_df
    