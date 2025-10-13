import sys
import os
from datetime import datetime
import pandas as pd
import re

sys.stdout.reconfigure(encoding='utf-8')

# 民國 → 西元日期轉換
def roc_to_ad(date_str):
    if pd.isna(date_str):  # 遇到 NaN
        return None
    
    if not isinstance(date_str, str):  # 不是字串
        date_str = str(date_str)
    
    if "/" not in date_str:  # 格式不符
        return None
    
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

def extract_days(text: str, type: str):
    if not isinstance(text, str):  # 如果不是字串就直接回傳 None 或 0
        return None
    
    match type:
        case "twse":
            matches = re.search(r"﹝(.*?)個營業日", text)
            if matches:
                cn_days = matches.group(1)
                return chinese_to_number(cn_days)
                
        case "tpex":
            matches = re.search(r"日起(\d+)個營業日", text)
            if matches:
                cn_days = matches.group(1)
                return chinese_to_number(cn_days)
    return None

def handleDispositionStockFile(sDt: datetime, eDt: datetime, simpleMode=None, type: str="twse") -> bool:
    match type:
        case "twse":
            srcFolder = "../data/TwStockExchange/DispositionStock"    
            srcFile = f"{srcFolder}/{type}-{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}.csv"
            if not os.path.exists(srcFile):
                print(f'檔案不存在：{srcFile}')
                return False

            df = pd.read_csv(srcFile, dtype={"證券代號": str})
            df = df.dropna(subset=["證券代號"])

            # 去掉 Excel 加的 ="..." 外殼
            df["證券代號"] = df["證券代號"].str.replace(r'^="|"$', '', regex=True)

            df[["處置原因", "處置期間", "處置措施"]] = df["處置內容"].apply(parse_disposition)

            # 拆分起訖時間
            df[["處置起始", "處置結束"]] = df["處置起迄時間"].str.split("~", expand=True)

            # 轉換成西元日期
            df["處置起始"] = df["處置起始"].apply(roc_to_ad)
            df["處置結束"] = df["處置結束"].apply(roc_to_ad)
            df["公布日期"] = df["公布日期"].apply(roc_to_ad)

            # 擷取處置期間
            df["處置營業日數"] = df["處置期間"].apply(lambda x: extract_days(x, type))
            df["處置營業日數"] = df["處置營業日數"].fillna(0).astype(int)

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

        case "tpex":
            srcFolder = "../data/TpeExchange/DispositionStock"    
            srcFile = f"{srcFolder}/{type}-{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}.csv"
            if not os.path.exists(srcFile):
                print(f'檔案不存在：{srcFile}')
                return False

            df = pd.read_csv(srcFile, dtype={"證券代號": str})
            df = df.dropna(subset=["證券代號"])

            # 拆分起訖時間
            df[["處置起始", "處置結束"]] = df["處置起訖時間"].str.split("~", expand=True)

            # 擷取處置期間
            df["處置營業日數"] = df["處置內容"].apply(lambda x: extract_days(x, type))
            df["處置營業日數"] = df["處置營業日數"].fillna(0).astype(int)

            df["撮合頻率(分鐘)"] = (
                df["處置內容"].str.extract(r'\(約每(\d+)分鐘撮合一次\)')[0]  # 取出數字
            )

            # 民國年轉西元
            df["公布日期"] = df["公布日期"].apply(roc_to_ad)
            df["處置起始"] = df["處置起始"].apply(roc_to_ad)
            df["處置結束"] = df["處置結束"].apply(roc_to_ad)

            df = df.drop(columns=["編號","處置起訖時間"])

            suffix = "handled"
            if simpleMode is not None:
                df = df.drop(columns=["處置原因", "處置內容", "本益比", "收盤價"])
                suffix = "simple"
            
    outputFile = f'{srcFolder}/{type}-{sDt.strftime("%Y%m%d")}_{eDt.strftime("%Y%m%d")}-{suffix}.csv'
    df.to_csv(outputFile, mode="w", index=False, encoding="utf-8-sig")
    return os.path.exists(outputFile)

if __name__ == '__main__':
    sDt = datetime.strptime("2021/01/01", "%Y/%m/%d")
    eDt = datetime.strptime("2025/08/24", "%Y/%m/%d")
    handleDispositionStockFile(sDt, eDt, True, "twse")