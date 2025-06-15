import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
from tqdm import tqdm

# === 設定 FinMind Token ===
api = DataLoader()
api.login_by_token(api_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNS0wNi0wOSAyMToxOToxMyIsInVzZXJfaWQiOiJueWN1bGFiNjE1IiwiaXAiOiI0Mi43My4xOTAuMTMyIiwiZXhwIjoxNzUwMDc5OTUzfQ.R-VGBiXfCzImunsOxKTZM6Ajng2zwcLE2HzYj_BIH1w")  # ← 請替換成你的 token

# === 檔案路徑設定 ===
input_file = "../data/analysis/summary/closingPrice2013-2019.csv"
output_file = "../data/analysis/summary/closingPrice2013-2019_fill.csv"

# === 讀取原始檔案 ===
df = pd.read_csv(input_file, index_col=0, dtype=str)
df = df.replace("nan", pd.NA)

# === 快取已查過的資料，避免重複耗額度 ===
price_cache = {}

# === 取得股價的查詢函數 ===
def fetch_price(stock_id, date):
    cache_key = (stock_id, date)
    if cache_key in price_cache:
        return price_cache[cache_key]
    
    # --- 優先使用 yfinance ---
    try:
        yf_id = f"{stock_id}.TW"
        yf_data = yf.download(yf_id, start=date, end=date, progress=False)
        if not yf_data.empty:
            price = round(yf_data["Close"].iloc[0], 2)
            price_cache[cache_key] = price
            return price
    except Exception:
        pass

    # --- 若 yfinance 查不到，再用 FinMind ---
    # try:
    #     df_api = api.taiwan_stock_price(
    #         stock_id=stock_id,
    #         start_date=date,
    #         end_date=date
    #     )
    #     df_api = df_api[df_api["date"] == date]
    #     if not df_api.empty:
    #         price = round(df_api["close"].iloc[0], 2)
    #         price_cache[cache_key] = price
    #         return price
    # except Exception:
    #     pass

    # --- 若都查不到，標記為 NoTraded2 ---
    price_cache[cache_key] = "NoTraded2"
    return "NoTraded2"

# === 主要補值流程 ===
for stock_id in tqdm(df.index, desc="股票代號"):
    for date in df.columns:
        value = df.at[stock_id, date]

        # 條件：只有空白（不是 NoTraded、不是 NoTraded2）才查
        if pd.isna(value) or value == "":
            new_val = fetch_price(stock_id, date)
            df.at[stock_id, date] = new_val

# === 儲存最終結果 ===
df.to_csv(output_file, encoding="utf-8-sig")
print(f"補值完成，儲存於：{output_file}")
