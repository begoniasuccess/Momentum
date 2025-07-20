import os
import pandas as pd
from pathlib import Path
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 定義路徑
base_dir = Path("../data/FinMind/TW/DailyPriceAdj")

# 搜尋所有時間區間資料夾
pattern = re.compile(r"^(\d{8})-(\d{8})$")
folders = []
start_dates = []
end_dates = []

for folder in base_dir.iterdir():
    if folder.is_dir():
        match = pattern.match(folder.name)
        if match:
            folders.append(folder)
            start_dates.append(match.group(1))
            end_dates.append(match.group(2))

# 自動計算整合資料夾名稱
min_start = min(start_dates)
max_end = max(end_dates)
output_dir = base_dir / f"{min_start}-{max_end}"
output_dir.mkdir(parents=True, exist_ok=True)
print(f"整合資料夾：{output_dir}")

# 找出所有股票代號 (TWMV-xxxx.csv)
csv_files = {}
for folder in folders:
    for file in folder.glob("TWDPadj-*.csv"):
        stock_id = file.name
        csv_files.setdefault(stock_id, []).append(file)

# 整合每支股票資料
for stock_id, file_list in csv_files.items():
    combined_df = pd.DataFrame()
    for file_path in sorted(file_list):
        if file_path.stat().st_size == 0:
            print(f"跳過空檔：{file_path}")
            continue
        try:
            df = pd.read_csv(file_path)
            if df.empty or df.columns.size == 0:
                print(f"跳過無有效欄位檔案：{file_path}")
                continue
        except pd.errors.EmptyDataError:
            print(f"跳過格式異常檔案：{file_path}")
            continue
        except Exception as e:
            print(f"讀取失敗：{file_path}，原因：{e}")
            continue

        combined_df = pd.concat([combined_df, df], ignore_index=True)

    combined_df.drop_duplicates(inplace=True)
    output_path = output_dir / stock_id
    combined_df.to_csv(output_path, index=False)
    print(f"{stock_id} 整合完成，共 {len(combined_df)} 筆資料 -> {output_path}")
