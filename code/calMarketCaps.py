import requests
import pandas as pd
from datetime import datetime, timedelta
from tqdm import tqdm

FINMIND_TOKEN = "你的 FinMind Token"  # << 請填入你的 Token

def find_nearest_trading_day(year: int, month: int):
    """往後找月初最接近的交易日"""
    date = datetime(year, month, 1)
    for _ in range(10):  # 最多往後找10天
        date_str = date.strftime("%Y-%m-%d")
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": "2330",  # 台積電，幾乎天天有交易
            "start_date": date_str,
            "end_date": date_str,
            "token": FINMIND_TOKEN,
        }
        r = requests.get(url, params=params).json()
        if r["data"]:  # 有交易資料就代表是交易日
            return date_str
        date += timedelta(days=1)
    raise Exception("找不到月初的有效交易日")


def get_all_common_stocks():
    """取得所有普通股（排除 ETF、債、認購權證等）"""
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockInfo",
        "token": FINMIND_TOKEN,
    }
    r = requests.get(url, params=params).json()
    df = pd.DataFrame(r["data"])

    # 過濾只留下普通股票
    df = df[df["type"] == "stock"]
    return df[["stock_id", "stock_name", "capital"]]


def get_stock_price(stock_id, date_str):
    """取得某檔股票在指定日期的收盤價"""
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": stock_id,
        "start_date": date_str,
        "end_date": date_str,
        "token": FINMIND_TOKEN
    }
    r = requests.get(url, params=params).json()
    if r["data"]:
        return r["data"][0]["close"]
    else:
        return None


def get_top_150_market_cap(year: int, month: int):
    trade_date = find_nearest_trading_day(year, month)
    print(f"📅 查詢交易日：{trade_date}")

    stock_df = get_all_common_stocks()
    print(f"共取得 {len(stock_df)} 檔普通股")

    results = []
    missing = []

    print("📈 開始取得每檔股票市值...")
    for _, row in tqdm(stock_df.iterrows(), total=len(stock_df)):
        stock_id = row["stock_id"]
        name = row["stock_name"]
        capital = row["capital"]
        issued_shares = capital / 10  # 1張 = 10股

        price = get_stock_price(stock_id, trade_date)
        if price is None:
            missing.append(stock_id)
            continue

        market_cap = price * issued_shares
        results.append({
            "stock_id": stock_id,
            "stock_name": name,
            "price": price,
            "market_cap": market_cap
        })

    df = pd.DataFrame(results)
    df = df.sort_values(by="market_cap", ascending=False).head(150)

    print(f"✅ 取得前 150 名市值公司，漏掉 {len(missing)} 檔：{missing[:5]} ...")

    return df[["stock_id", "stock_name", "price", "market_cap"]]


# ✅ 測試：取得 2024 年 6 月的台股市值前 150 檔
top150 = get_top_150_market_cap(2024, 6)
print(top150)

# ✅ 若你要存檔，可加這一行
top150.to_csv("top150_market_cap_202406.csv", index=False, encoding="utf-8-sig")
