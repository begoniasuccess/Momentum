import pandas as pd
import numpy as np
from scipy import stats

observeHoldingPeriod = 6
outputDir = r'..\data\analysis\momentum'
outputFilBaseName = f'Momentum0050_0051-20160501_20180601-HP_{observeHoldingPeriod}'
srcFile = f'{outputDir}/{outputFilBaseName}_rt_6m_after-filter.csv'

# 讀取 CSV，確保 RT_6M_After 是數值
df = pd.read_csv(srcFile)

# 去除 % 符號，轉成數值（百分比轉為小數）
df["RT_6M_After"] = df["RT_6M_After"].replace('%', '', regex=True).astype(float) / 100

# 結果儲存用
results = []

# 取得所有不同的 Combination
for combo, group in df.groupby("Combination"):
    for remark in ["Winner", "Loser"]:
        subset = group[group["Remark"] == remark]["RT_6M_After"].dropna()
        if len(subset) > 1:
            mean_val = subset.mean()
            t_stat, p_val = stats.ttest_1samp(subset, popmean=0, alternative="greater")
        else:
            mean_val = np.nan
            t_stat = np.nan
            p_val = np.nan

        results.append({
            "Combination": combo,
            "Remark": remark,
            "Count": len(subset),
            "RT_6M_After_Mean": mean_val,
            "T_statistic": t_stat,
            "P_value(one-sided > 0)": p_val
        })

# 輸出為 DataFrame 並印出
result_df = pd.DataFrame(results)
# print(result_df)

# 若想另存成 CSV
targetFile = f'{outputDir}/{outputFilBaseName}_RT_6M_After-tTest_results.csv'

result_df.to_csv(targetFile, index=False)
print(f"✅ Step05：T-test檢定完成，已儲存檔案：{targetFile}")
