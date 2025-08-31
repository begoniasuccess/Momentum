import sys
import os
from datetime import datetime
import pandas as pd
import re

sys.stdout.reconfigure(encoding='utf-8')

# 民國 → 西元日期轉換
def roc_to_ad(date_str):
    year, month, day = map(int, date_str.split("/"))
    year += 1911  # ROC 轉 AD
    return pd.to_datetime(f"{year}-{month:02d}-{day:02d}")

def parse_disposition(text):
    pattern = r"１處置原因：(.*?)２處置期間：(.*?)３處置措施：(.*)"
    match = re.search(pattern, text, re.S)
    if not match:
        return pd.Series({"處置原因": None, "處置期間": None, "處置措施": None})
    
    reason = match.group(1).strip()
    period = match.group(2).strip()
    measure = match.group(3).strip()

    return pd.Series({
        "處置原因": reason,
        "處置期間": period,
        "處置措施": measure
    })

# 中文數字對照表
cn_num = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    "十": 10
}

def chinese_to_number(cn: str) -> int:
    """簡單轉換常見中文數字為阿拉伯數字"""
    if cn.isdigit():
        return int(cn)

    if cn == "十":
        return 10
    if len(cn) == 2 and cn[0] == "十":  # 十一、十二...
        return 10 + cn_num[cn[1]]
    if len(cn) == 2 and cn[1] == "十":  # 二十、三十...
        return cn_num[cn[0]] * 10
    if len(cn) == 3 and cn[1] == "十":  # 二十一、三十二...
        return cn_num[cn[0]] * 10 + cn_num[cn[2]]

    return cn_num.get(cn, None)

def extract_days(text: str):
    match = re.search(r"﹝(.*?)個營業日", text)
    if match:
        cn_days = match.group(1)
        return chinese_to_number(cn_days)
    return None

def handleDispositionStockFile(sDt: datetime, eDt: datetime, simpleMode=None) -> bool:
    srcFolder = "../data/TwStockExchange/DispositionStock"    
    srcFile = f"{srcFolder}/{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}.csv"
    if not os.path.exists(srcFile):
        print(f'檔案不存在：{srcFile}')
        return False

    df = pd.read_csv(srcFile, dtype={"證券代號": str})

    # 去掉 Excel 加的 ="..." 外殼
    df["證券代號"] = df["證券代號"].str.replace(r'^="|"$', '', regex=True)

    df[["處置原因", "處置期間", "處置措施"]] = df["處置內容"].apply(parse_disposition)

    # 拆分起訖時間
    df[["處置起始", "處置結束"]] = df["處置起迄時間"].str.split("~", expand=True)

    # 轉換成西元日期
    df["處置起始"] = df["處置起始"].apply(roc_to_ad)
    df["處置結束"] = df["處置結束"].apply(roc_to_ad)
    df["公布日期"] = df["公布日期"].apply(roc_to_ad)

    # 計算處置天數（包含起始日與結束日）
    df["處置天數"] = (df["處置結束"] - df["處置起始"]).dt.days + 1

    # 生成新欄位
    df["處置營業日數"] = df["處置期間"].apply(extract_days)

    df = df.drop(columns=["編號", "處置內容", "Unnamed: 10", "處置起迄時間", "處置期間", "備註"])

    df = df.sort_values(by=["公布日期", "證券代號"], ascending=[True, True])

    # df["撮合頻率(分鐘)"] = df["處置措施"].str.extract(r'(約每.*?分鐘撮合一次)')
    df["撮合頻率(分鐘)"] = (
        df["處置措施"]
        .str.extract(r'約每(.*?)分鐘撮合一次')[0]   # 抓出中文數字
        .apply(chinese_to_number)                    # 轉成阿拉伯數字
    )

    suffix = "handled"
    if simpleMode is not None:
       df = df.drop(columns=["處置措施", "處置條件", "處置原因", "累計"])
       suffix = "simple"

    outputFile = f'{srcFolder}/{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}-{suffix}.csv'
    df.to_csv(outputFile, mode="w", index=False)
    return os.path.exists(outputFile)

sDt = datetime.strptime("2021/01/01", "%Y/%m/%d")
eDt = datetime.strptime("2025/08/24", "%Y/%m/%d")
handleDispositionStockFile(sDt, eDt, True)
