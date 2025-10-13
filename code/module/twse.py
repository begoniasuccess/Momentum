import requests
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os

twseUrl = "https://www.twse.com.tw/rwd/zh"

# ======== 共用工具 ========
def _date_to_str(date: datetime = None, formate: str = None) -> str:
    """將 datetime 轉為 yyyymmdd 字串，若未指定則取今日"""
    if date is None:
        date = datetime.today()
    if formate is None:
        formate = "%Y%m%d"
    return date.strftime(formate)

def _save_to_csv(df: pd.DataFrame, apiEndpoint: str, filename: str):
    data_center = "../data/TwStockExchange"
    
    # 1. 檢查 data_center 是否存在
    if not os.path.exists(data_center):
        raise FileNotFoundError(f"❌ data_center 不存在：{data_center}")
    
    # 2. 確保目標資料夾存在
    dir_path = os.path.join(data_center, apiEndpoint)
    os.makedirs(dir_path, exist_ok=True)  # 如果不存在就建立
    
    path = os.path.join(dir_path, f"{filename}.csv")
    
    # 3. 儲存 CSV
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"✅ 已儲存：{path}")

# ======== 1. 個股成交日資訊 ========
def get_stock_day(stock_no: str, date: datetime | None = None) -> pd.DataFrame:
    date_str = _date_to_str(date)
    apiEndpoint = "afterTrading/STOCK_DAY"
    apiParams = f"date={date_str}&stockNo={stock_no}&response=json"
    apiUrl = f"{twseUrl}/{apiEndpoint}?{apiParams}"

    res = requests.get(apiUrl)
    data = res.json()

    df = pd.DataFrame(data.get("data", []), columns=data.get("fields", []))
    _save_to_csv(df, apiEndpoint, f"{stock_no}_{date_str}")
    return df

# ======== 2. 個股收盤價 ========
def get_stock_day_avg(stock_no: str, date: datetime | None = None) -> pd.DataFrame:
    date_str = _date_to_str(date)
    apiEndpoint = "afterTrading/STOCK_DAY_AVG"
    apiParams = f"date={date_str}&stockNo={stock_no}&response=json"
    apiUrl = f"{twseUrl}/{apiEndpoint}?{apiParams}"

    res = requests.get(apiUrl)
    data = res.json()

    df = pd.DataFrame(data.get("data", []), columns=data.get("fields", []))
    _save_to_csv(df, apiEndpoint, f"{stock_no}_{date_str}")
    return df

# ======== 3. 三大法人 ========
def get_institutional_investors(date: datetime | None = None) -> pd.DataFrame:
    date_str = _date_to_str(date)
    apiEndpoint = "fund/BFI82U"
    apiParams = f"type=day&dayDate={date_str}&weekDate={date_str}&monthDate={date_str}&response=json"
    apiUrl = f"{twseUrl}/{apiEndpoint}?{apiParams}"

    res = requests.get(apiUrl)
    data = res.json()

    df = pd.DataFrame(data.get("data", []), columns=data.get("fields", []))
    _save_to_csv(df, apiEndpoint, f"{date_str}")
    return df

# ======== 4. 融資融券餘額 ========
def get_margin_trading(date: datetime | None = None) -> pd.DataFrame:
    date_str = _date_to_str(date)
    apiEndpoint = "marginTrading/MI_MARGN"
    apiParams = f"date={date_str}&selectType=MS&response=json"
    apiUrl = f"{twseUrl}/{apiEndpoint}?{apiParams}"

    res = requests.get(apiUrl)
    data = res.json()

    # tables[0] 才有資料
    tables = data.get("tables", [])
    if not tables or "fields" not in tables[0] or "data" not in tables[0]:
        raise ValueError(f"❌ API 回傳格式異常: {data}")

    fields = tables[0]["fields"]
    rows = tables[0]["data"]

    df = pd.DataFrame(rows, columns=fields)

    _save_to_csv(df, apiEndpoint, f"{date_str}")
    return df

# ======== 5. 注意股公告 ========
def get_notice(start_date: datetime | None = None, end_date: datetime | None = None) -> pd.DataFrame:
    start_str = _date_to_str(start_date)
    end_str = _date_to_str(end_date)
    apiEndpoint = "announcement/notice"
    apiParams = f"querytype=1&stockNo=&selectType=&startDate={start_str}&endDate={end_str}&sortKind=STKNO&response=json"
    apiUrl = f"{twseUrl}/{apiEndpoint}?{apiParams}"

    res = requests.get(apiUrl)
    data = res.json()

    df = pd.DataFrame(data.get("data", []), columns=data.get("fields", []))
    _save_to_csv(df, apiEndpoint, f"{start_str}_{end_str}")
    return df

# ======== 範例測試 ========
if __name__ == "__main__":
    test = datetime.today()
    test = test - relativedelta(months=1)

    # 測試下載各項資料
    get_stock_day("2330", test)
    get_stock_day_avg("0050", test)
    get_institutional_investors(test)
    get_margin_trading(test)
    get_notice(datetime(2025, 10, 1), datetime(2025, 10, 4))
