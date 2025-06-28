import pandas as pd
import os
from FinMind.data import DataLoader

srcFilePath = "../data/FinMind/TW/taiwan_stock_info.csv"

# 1. 讀取 CSV 檔案
if os.path.exists(srcFilePath):
    df = pd.read_csv("taiwan_stock_info.csv")
else:
    print(f'檔案{srcFilePath}不存在，從FindMind下載資料...')
    api = DataLoader()
    df = api.taiwan_stock_info()
    df.to_csv(srcFilePath, index=False, encoding='utf-8-sig')    

targetFilePath = "../data/analysis/taiwan_stock_info-twse.csv"
if os.path.exists(targetFilePath):
    print("檔案已存在：" + targetFilePath)
else:    
    # 2. 篩選 type 為 'twse'
    df_twse = df[df['type'] == 'twse']

    # 3. 排除 industry_category 欄位含有指定關鍵字的資料
    exclude_keywords = ['ETF', 'Index', '受益證券', 'ETN', '大盤', '存託憑證', '創新板股票', '創新版股票']
    pattern = '|'.join(exclude_keywords)  # 建立 regex 模式
    df_twse_filtered = df_twse[~df_twse['industry_category'].str.contains(pattern, na=False)]

    # 4. 存成新檔案
    df_twse_filtered.to_csv(targetFilePath, index=False, encoding='utf-8-sig')

    print("已成功儲存：" + targetFilePath)
