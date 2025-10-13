import sys, os
sys.path.append(os.path.dirname(__file__))
sys.stdout.reconfigure(encoding='utf-8')

import requests
import pandas as pd
from datetime import datetime, timedelta
from common import utils

twseUrl = "https://www.twse.com.tw/rwd/zh"
common_params = "response=json"

# ======== 注意股公告 ========
def fetch_notice(type: str, sDt: datetime, eDt: datetime):
    if (sDt > eDt):
        return None

    if eDt > datetime.today():
        eDt = datetime.today()

    match type.lower():
        case "twse":
            apiName = '上市公布注意有價證券資訊'
            apiInfo = utils.get_api_info(apiName)
            apiUrl = apiInfo["url"].iloc[0]
            start_str = sDt.strftime("%Y%m%d")
            end_str = eDt.strftime("%Y%m%d")
            apiParams = {
                "startDate" : start_str,
                "endDate" : end_str,
                "querytype" : "1",
                "stockNo" : None,
                "selectType" : None,
                "sortKind" : "DATE",
                "response" : "json"
            }
            
            # 發送 GET 請求
            response = requests.get(apiUrl, params=apiParams)
            
        case "tpex":
            apiName = '上櫃公布注意有價證券資訊'    
            apiInfo = utils.get_api_info(apiName)
            apiUrl = apiInfo["url"].iloc[0]
            start_str = sDt.strftime("%Y/%m/%d")
            end_str = eDt.strftime("%Y/%m/%d")
            apiParams = {
                "startDate" : start_str,
                "endDate" : end_str,
                "code" : None,
                "cate" : None,
                "type" : "all",
                "order" : "date",
                "id" : None,
                "response" : "json"
            }

            # 發送 POST 請求
            response = requests.post(apiUrl, data=apiParams)
        
        case _:
            return None
        
    response.raise_for_status()  # 檢查 HTTP 錯誤
    
    # 取得回應
    print("Status code:", response.status_code)
    # print("Response text:", response.text)

    # 嘗試把回傳內容轉成 JSON
    raw_data = response.json()

    return raw_data

# ======== 處置股公告 ========
def fetch_punish(type: str, sDt: datetime, eDt: datetime):
    if (sDt > eDt):
        return None

    if eDt > datetime.today():
        eDt = datetime.today()
        
    print(sDt, eDt)

    response = None
    match type.lower():
        case "twse":
            apiName = '上市公布處置有價證券'
            apiInfo = utils.get_api_info(apiName)
            apiUrl = apiInfo["url"].iloc[0]
            
            start_str = sDt.strftime("%Y%m%d")
            end_str = eDt.strftime("%Y%m%d")
            apiParams = {
                "startDate" : start_str,
                "endDate" : end_str,
                "querytype" : 3,
                "stockNo" : None,
                "selectType" : None,
                "proceType" : None,
                "remarkType" : "",
                "sortKind" : "DATE",
                "response" : "json"
            }
            # 發送 GET 請求
            response = requests.get(apiUrl, params=apiParams)
            
        case "tpex":
            apiName = '上櫃處置有價證券資訊'
            apiInfo = utils.get_api_info(apiName)
            apiUrl = apiInfo["url"].iloc[0]
            
            start_str = sDt.strftime("%Y%m%d")
            end_str = eDt.strftime("%Y%m%d")
            apiParams = {
                "startDate" : start_str,
                "endDate" : end_str,
                "code" : None,
                "cate" : None,
                "type" : "all",
                "reason" : -1,
                "measure" : -1,
                "order" : "date",
                "id" : None,
                "response" : "json"
            }

            # 發送 POST 請求
            response = requests.post(apiUrl, data=apiParams)
            
        case _:
            return None
            
    response.raise_for_status()  # 檢查 HTTP 錯誤
    
    # 取得回應
    print("Status code:", response.status_code)
    # print("Response text:", response.text)

    # 嘗試把回傳內容轉成 JSON
    raw_data = response.json()

    return raw_data

# ======== 4. 融資融券餘額 ========
# 項目,買進,賣出,現金(券)償還,前日餘額,今日餘額
def fetch_margin_trading(date: datetime | None = None):
    date_str = date.strftime("%Y%m%d")
    apiEndpoint = "marginTrading/MI_MARGN"
    apiParams = f"date={date_str}&selectType=MS&{common_params}"
    apiUrl = f"{twseUrl}/{apiEndpoint}?{apiParams}"

    res = requests.get(apiUrl)
    data = res.json()

    # tables[0] 才有資料
    tables = data.get("tables", [])
    if not tables or "fields" not in tables[0] or "data" not in tables[0]:
        print(f"❌ API 回傳格式異常: {data}")
        return None

    return tables[0]

# # ======== 4.2 融資融券餘額 區間版 ========
# # 日期,項目,買進,賣出,現金_券_償還,前日餘額,今日餘額
def fetch_margin_trading_range(sDt: datetime, eDt: datetime):
    if sDt > eDt:
        return None
    
    data = []    
    current = sDt
    while current <= eDt:
        currentData = fetch_margin_trading(current)
        if currentData is None:
            current += timedelta(days=1)
            continue
        
        rows = currentData["data"]
        for aRow in rows:
            aRow.insert(0, current.strftime("%Y%m%d"))
        data = data + rows
        current += timedelta(days=1)
        
    result = {
        "fields": ['日期', '項目', '買進', '賣出', '現金_券_償還', '前日餘額', '今日餘額'],
        "data": data
    }
    return result

if __name__ == "__main__":
    sDt = datetime(2025, 9, 25)
    eDt = datetime(2025, 10, 5)
    data = fetch_punish("twse", sDt, eDt)
    print(data)