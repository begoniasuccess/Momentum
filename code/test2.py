import os
import pandas as pd
from pathlib import Path
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 定義路徑
base_dir = Path("../data/FinMind/TW/MarketValue")

# 搜尋所有時間區間資料夾
pattern = re.compile(r"^(\d{8})-(\d{8})$")
folders = []

for folder in base_dir.iterdir():
    if folder.is_dir() and pattern.match(folder.name):
        folders.append(folder)

# 找出所有股票代號 (TWMV-xxxx.csv)
csv_files = {}
for folder in folders:
    for file in folder.glob("TWMV-*.csv"):
        stock_id = file.name
        csv_files.setdefault(stock_id, []).append(file)

# 整合並依年份輸出
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

    if combined_df.empty:
        print(f"{stock_id} 沒有有效資料，跳過。")
        continue

    combined_df.drop_duplicates(inplace=True)

    # 假設有 'date' 欄位 (格式為 yyyy-mm-dd 或 yyyymmdd)
    if 'date' not in combined_df.columns:
        print(f"{stock_id} 缺少日期欄位，無法依年份儲存，跳過。")
        continue

    # 標準化日期欄位
    combined_df['date'] = pd.to_datetime(combined_df['date'].astype(str), errors='coerce')
    combined_df.dropna(subset=['date'], inplace=True)

    # 按年份拆分
    combined_df['year'] = combined_df['date'].dt.year

    for year, year_df in combined_df.groupby('year'):
        year_folder = base_dir / str(year)
        year_folder.mkdir(parents=True, exist_ok=True)

        output_path = year_folder / stock_id
        year_df.drop(columns=['year'], inplace=True)
        year_df.to_csv(output_path, index=False)

        print(f"{stock_id} 年度 {year} 完成，共 {len(year_df)} 筆資料 -> {output_path}")
