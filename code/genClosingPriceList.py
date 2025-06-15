import os
import pandas as pd
from collections import defaultdict

# 設定變數
fstM = "201605"  # 股價資料起始年月，此範例為201605(代表2016年5月)
lastM = "201605"  # 股價資料結束年月，此範例為201605(代表2016年5月)
J = 6  # observation period(months)，觀察股票在J個月前至建立組合日間所得到的報酬
K = 6   # holding Period(months)，持有投資組合k個月

# 資料路徑設定
base_path = "../data/min_data_2013-2019"
output_path = "../data/analysis/summary"
output_file = os.path.join(output_path, "closingPrice2013-2019.csv")

# 建立 summary 資料夾
os.makedirs(output_path, exist_ok=True)

# 用來儲存所有股票的日期與收盤價
price_data = defaultdict(dict)  # {stock_id: {date: price}}

# 年度迴圈
for year in range(2013, 2020):
    year_folder = os.path.join(base_path, str(year), "averageprice")
    if not os.path.exists(year_folder):
        continue

    # 找出所有檔案並整理出各月份的第一天與最後一天
    all_files = sorted([f for f in os.listdir(year_folder) if f.endswith("_averagePrice_min.csv")])
    month_days = defaultdict(list)  # {yyyymm: [file1, file2, ...]}
    for file in all_files:
        yyyymmdd = file[:8]
        yyyymm = yyyymmdd[:6]
        month_days[yyyymm].append(file)

    # 針對每個月選擇最早與最晚日期的檔案
    for yyyymm, files in month_days.items():
        if len(files) == 0:
            continue
        first_file = files[0]
        last_file = files[-1]
        for target_file in [first_file, last_file]:
            file_path = os.path.join(year_folder, target_file)
            try:
                df = pd.read_csv(file_path)
                if df.empty:
                    continue
                date = target_file[:8]  # yyyymmdd
                stock_ids = df.columns.tolist()
                close_prices = df.iloc[-1].tolist()
                for stock_id in stock_ids:
                    price = df[stock_id].iloc[-1]
                    if pd.isna(price):
                        price_data[stock_id][date] = "NoTraded"
                    else:
                        price_data[stock_id][date] = price
            except Exception as e:
                print(f"錯誤讀取 {file_path}: {e}")

# 建立 DataFrame 並儲存
all_dates = sorted({date for stock in price_data.values() for date in stock})
df_final = pd.DataFrame(index=all_dates)

for stock_id, price_dict in price_data.items():
    series = pd.Series(price_dict)
    df_final[stock_id] = series

df_final.index.name = "Date"
df_final = df_final.sort_index()
df_final = df_final.transpose()
df_final.index.name = "StockID"
df_final.to_csv(output_file, encoding="utf-8-sig")

print(f"已完成：{output_file}")
