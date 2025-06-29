import pandas as pd

# 請修改為你的檔案路徑
file_a = "../data/20160104_averagePrice_min.csv"
file_b = "../data/20160104_min_stock.csv"
file_c = "../data/compare_file_20160104.csv"

# 讀取兩個檔案
df_a = pd.read_csv(file_a, header=None)
df_b = pd.read_csv(file_b, header=None)

# 確認兩檔資料形狀一致
if df_a.shape != df_b.shape:
    raise ValueError("A 與 B 的資料大小不一致，無法逐格相減")

# 建立新的 DataFrame
df_c = pd.DataFrame()

# 第1列保留 A 的第一列
df_c = df_c._append(df_a.iloc[0], ignore_index=True)

# 從第2列開始做相減
diff = df_a.iloc[1:].astype(float) - df_b.iloc[1:].astype(float)
df_c = pd.concat([df_c, diff], ignore_index=True)

# 儲存結果
df_c.to_csv(file_c, index=False, header=False)
print(f"已生成檔案：{file_c}")
