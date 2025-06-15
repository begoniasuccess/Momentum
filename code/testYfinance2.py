import yfinance as yf
import os

fileDir = "../data/tmp"
os.makedirs(fileDir, exist_ok=True)

startDate = "2016-05-01"
endDate = "2018-06-01"
tickNums = ["2330.TW", "1101.TW", "1102.TW"]
fileName = "test2.csv"
csvPath = fileDir + "/" + fileName

# 下載資料 # auto_adjust一定要設false
data = yf.download(tickNums, start=startDate, end=endDate, auto_adjust=True)

# # 只取收盤價 Close，會變成日期為 index，股票為欄位的表格
close_prices = data["Close"]

# 存成 CSV（index 為日期、columns 為股票代號）
close_prices.to_csv(csvPath, index=True, index_label="Date", encoding='utf-8-sig')

# 顯示前幾列確認結果
print(close_prices.head())
