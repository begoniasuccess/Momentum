import pandas as pd
import os
from datetime import datetime, timedelta
from pathlib import Path
import sys
import re
from common.constants import Panel
from common.constants import Iloc

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
    base_dir = f'../data/analysis/summary/closePrice'
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
    # print(close_df.head(3))
    ## for test
    close_df.to_csv(f"{base_dir}/closePrice_tmp.csv")
    return close_df
    
def delete_empty_csv_files(folder_path):
    deleted_files = []

    for filename in os.listdir(folder_path):
        if filename.lower().endswith('.csv'):
            filepath = os.path.join(folder_path, filename)
            try:
                with open(filepath, encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip()]
                    if not lines:
                        os.remove(filepath)
                        deleted_files.append(filename)
                        print(f"已刪除空檔案：{filename}")
            except Exception as e:
                print(f"讀取檔案時發生錯誤：{filename}，原因：{e}")

    print(f"\n總共刪除 {len(deleted_files)} 個空白CSV檔案。")
    return deleted_files
def is_really_empty_file(filepath):
    """強化版本：整份檔案去除空白、換行、BOM、制表符後，確認是否完全無內容"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            cleaned_content = content.replace("\n", "").replace("\r", "").replace("\t", "").strip()
            return len(cleaned_content) == 0
    except Exception as e:
        print(f"檢查失敗：{filepath}，原因：{e}")
        return False


def delete_empty_csv_files_recursive(folder_path, size_threshold=2*1024):
    """檔案大小小且內容純空白，即刪除"""
    deleted_files = []
    checked_files = 0

    for root, dirs, files in os.walk(folder_path):
        for filename in files:
            if filename.lower().endswith('.csv'):
                filepath = os.path.join(root, filename)
                checked_files += 1

                try:
                    # 檔案過小才進一步檢查內容
                    if os.path.getsize(filepath) <= size_threshold:
                        if is_really_empty_file(filepath):
                            os.remove(filepath)
                            deleted_files.append(filepath)
                            print(f"已刪除純空白檔案：{filepath}")
                except Exception as e:
                    print(f"處理失敗：{filepath}，原因：{e}")

                if checked_files % 100 == 0:
                    print(f"已檢查 {checked_files} 個檔案...")

    print(f"\n總共檢查 {checked_files} 個檔案，刪除 {len(deleted_files)} 個空白或純換行檔案。")
    return deleted_files

def getOperiodDataRow(stock_id: str, closeDf: pd.DataFrame, baseDt: datetime, iloc: Iloc) -> pd.Series:
    dataRow = None
    candidates = closeDf[
        (closeDf['stock_id'] == stock_id) &
        (closeDf['date'].dt.year == baseDt.year) &
        (closeDf['date'].dt.month == baseDt.month)
    ]
    if not candidates.empty:
        dataRow = candidates.sort_values("date").iloc[iloc.value]
        
    if dataRow is None:
        return dataRow
    
    ### 確保 月初/月底 的資料要分別落在特定的日期內
    if (iloc == Iloc.Fst) and (dataRow["date"].day > 15):
        ptMsg(f'[{stock_id}]月初資料日期過大 => {dataRow["date"].strftime("%Y%m%d")}')
        return None
    
    if (iloc == Iloc.Last) and (dataRow["date"].day < 16):
        ptMsg(f'[{stock_id}]月底資料日期過小 => {dataRow["date"].strftime("%Y%m%d")}')
        return None
    
    return dataRow


# 找出 持有期-買入(0)賣出(-1)日期 對應的資料列
def getHperiodDataRow(panelType: Panel, stock_id: str, closeDf: pd.DataFrame, baseDt: datetime, iloc: Iloc) -> pd.Series:
    ### Panel A
    if panelType == Panel.A:
        candidates = closeDf[
            (closeDf["stock_id"] == stock_id) &
            (closeDf["date_dt"].dt.year == baseDt.year) &
            (closeDf["date_dt"].dt.month == baseDt.month)
        ]
        if not candidates.empty:
            return candidates.sort_values("date_dt").iloc[iloc.value]

    ## Panel B
    if panelType == Panel.B:
        candidates = closeDf[
            (closeDf["stock_id"] == stock_id) &
            (closeDf["date_dt"] >= baseDt) &
            (closeDf["date_dt"] <= baseDt + timedelta(days=7))
        ]
        
        if not candidates.empty:
            return candidates.sort_values("date_dt").iloc[iloc.value]
        
    return None