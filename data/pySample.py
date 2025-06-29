"""
Python 常用功能範例（整理自你的投資研究專案）
Author: ChatGPT
"""

# =======================================
# 1️⃣ 檔案與資料夾操作
# =======================================
import os

# 建立資料夾（如果不存在）
folder_path = "../data/analysis/summary"
os.makedirs(folder_path, exist_ok=True)

# 組合檔案路徑
file_path = os.path.join(folder_path, "output.csv")

# 檢查檔案是否存在
if os.path.exists(file_path):
    print("檔案已存在：", file_path)
else:
    print("檔案不存在：", file_path)

# =======================================
# 2️⃣ Pandas 操作
# =======================================
import pandas as pd

# 讀取 CSV
df = pd.read_csv("example.csv")

# 排序
df = df.sort_values(by="date")

# 取出date欄位的資料形成一陣列
df['date'].tolist()
df['date'].drop_duplicates().tolist() # 去除重複

# groupby 取每月第一筆資料
df["date"] = pd.to_datetime(df["date"])
monthly_first = df.groupby(df["date"].dt.to_period("M")).first()

# 百分比排名
df["pct_rank"] = df.groupby("group")["value"].rank(pct=True)

# 分箱（等頻分組）
df["quantile"] = pd.qcut(df["value"], q=4, labels=False)

# 缺漏值處理
df = df.replace("nan", pd.NA)
df = df.dropna(subset=["value"])

# merge 合併
df_merged = pd.merge(df, monthly_first, on="id", how="left")

# =======================================
# 3️⃣ tqdm 進度條
# =======================================
from tqdm import tqdm

stock_ids = ["2330", "2303", "2317"]

for stock in tqdm(stock_ids, desc="處理股票"):
    # 模擬處理
    pass

# =======================================
# 4️⃣ datetime 與 dateutil 日期計算
# =======================================
from datetime import datetime
from dateutil.relativedelta import relativedelta

# 字串轉日期
d = datetime.strptime("2020-05-01", "%Y-%m-%d")

# 加6個月
d_plus6m = d + relativedelta(months=6)

# 格式化
date_str = d_plus6m.strftime("%Y%m")
print("六個月後:", date_str)

# =======================================
# 5️⃣ 資料快取（避免重複查詢）
# =======================================
price_cache = {}

def fetch_price(stock_id, date):
    key = (stock_id, date)
    if key in price_cache:
        return price_cache[key]
    
    # 模擬查詢
    price = 100  # 假設查到100
    price_cache[key] = price
    return price

p = fetch_price("2330", "2020-05-01")
print("查到價格:", p)

# =======================================
# 6️⃣ FinMind 與 yfinance 資料抓取
# =======================================
from FinMind.data import DataLoader
import yfinance as yf

# FinMind
api = DataLoader()
api.login_by_token(api_token="YOUR_TOKEN")

df_fm = api.taiwan_stock_daily(
    stock_id="2330",
    start_date="2020-01-01",
    end_date="2020-01-10"
)
print(df_fm.head())

# yfinance
df_yf = yf.download("2330.TW", start="2020-01-01", end="2020-01-10", progress=False)
print(df_yf.head())

# =======================================
# 7️⃣ scipy 統計檢定
# =======================================
from scipy import stats
import numpy as np

data = np.array([0.01, 0.02, 0.03, 0.04])

# 單樣本 t 檢定 (平均是否大於0)
t_stat, p_value_two = stats.ttest_1samp(data, popmean=0)
# 單尾 p 值
p_value_one = p_value_two / 2 if t_stat > 0 else 1 - (p_value_two / 2)

print(f"t統計量: {t_stat}, 單尾p值: {p_value_one}")

# 成對樣本 t 檢定
before = np.array([0.01, 0.02, 0.03])
after = np.array([0.02, 0.03, 0.05])

t_stat_pair, p_value_pair = stats.ttest_rel(after, before)
print(f"成對t統計量: {t_stat_pair}, p值: {p_value_pair}")

# =======================================
# 8️⃣ try/except 錯誤處理
# =======================================
try:
    df_test = pd.read_csv("not_exist.csv")
except Exception as e:
    print("讀取錯誤：", e)
