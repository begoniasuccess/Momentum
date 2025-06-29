import yfinance as yf

fileDir = "../data/tmp"
startDate = "2016-05-01"
endDate = "2018-06-01"

# tickNum = "2330"
# tickCountry = "TW"
# symbol = tickNum + "." + tickCountry

# fileName = tickCountry + tickNum + "_" + startDate + "_" + endDate + ".csv"
# csvPath = fileDir + "/" + fileName

# list = yf.download(symbol, startDate, endDate)
# list.to_csv(csvPath, index=True, index_label="", encoding='utf-8-sig')
# print(list)

tickNums = ["2330.TW", "1101.TW", "1102.TW"]
fileName = "test.csv"
csvPath = fileDir + "/" + fileName

list = yf.download(tickNums, startDate, endDate)

list.to_csv(csvPath, index=True, index_label="", encoding='utf-8-sig')
print(list)

# # 只取收盤價
# close_only = list[["Close"]]
# close_only.to_csv(csvPath, index=True, index_label="", encoding='utf-8-sig')
# print(close_only)