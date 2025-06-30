import pandas as pd

# 讀檔
filePath = r"..\data\analysis\momentumNew\oPeriod3_hPeriod_3\observerReturnList201001_202012-rank.csv"
df = pd.read_csv(filePath)

# 刪除欄位 b
df = df.drop(columns=["RT_rank"])

# 存回同名（會覆蓋）
df.to_csv(filePath, index=False, encoding="utf-8-sig")
