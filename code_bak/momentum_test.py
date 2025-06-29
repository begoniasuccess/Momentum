# import pandas as pd
# from scipy.stats import ttest_1samp
# import numpy as np

# observeHoldingPeriod = 6
# outputDir = r'..\data\analysis\momentum'
# outputFilBaseName = f'Momentum0050_0051-20160501_20180601-HP_{observeHoldingPeriod}'
# srcFile = f'{outputDir}/{outputFilBaseName}_rt_6m_after-filter.csv'

# # 讀取 CSV，確保 RT_6M_After 是數值
# df = pd.read_csv(srcFile)

# # 將百分比欄位去除 % 並轉為 float
# df["RT_6M_After"] = df["RT_6M_After"].replace('%', '', regex=True).astype(float) / 100

# # 過濾出 Remark 是 Winner 或 Loser 的資料，且 RT_6M_After 不為 NaN
# filtered = df[df["Remark"].isin(["Winner", "Loser"])].dropna(subset=["RT_6M_After"])

# # 儲存結果的列表
# result = []

# # 按 Combination 分組
# for comb, group in filtered.groupby("Combination"):
#     winner = group[group["Remark"] == "Winner"]["RT_6M_After"]
#     loser = group[group["Remark"] == "Loser"]["RT_6M_After"]

#     # Winner
#     if not winner.empty:
#         result.append({
#             "Combination": comb,
#             "Remark": "Winner",
#             "Count": len(winner),
#             "RT_6M_After_Mean": winner.mean()
#         })

#     # Loser
#     if not loser.empty:
#         result.append({
#             "Combination": comb,
#             "Remark": "Loser",
#             "Count": len(loser),
#             "RT_6M_After_Mean": loser.mean()
#         })

#     # Winner - Loser 差異
#     if not winner.empty and not loser.empty:
#         diff = winner.mean() - loser.mean()
#         result.append({
#             "Combination": comb,
#             "Remark": "Winner - Loser",
#             "Count": "-",
#             "RT_6M_After_Mean": diff
#         })

# # 建立 DataFrame
# summary_df = pd.DataFrame(result)


# # 存成 CSV
# targetFile = f'{outputDir}/{outputFilBaseName}_RT_6M_After-prepare.csv'

# summary_df.to_csv(targetFile, index=False)
# print(f"✅ T-test檢定完成，已儲存檔案：{targetFile}")

# import pandas as pd
# from scipy import stats

# observeHoldingPeriod = 6
# outputDir = r'..\data\analysis\momentum'
# outputFilBaseName = f'Momentum0050_0051-20160501_20180601-HP_{observeHoldingPeriod}'
# srcFile = f'{outputDir}/{outputFilBaseName}_rt_6m_after-filter.csv'

# # 讀取 CSV，確保 RT_6M_After 是數值
# df = pd.read_csv(srcFile)

# # 將 RT_6M_After 欄位從百分比字串轉為 float（小數）
# df['RT_6M_After'] = df['RT_6M_After'].str.replace('%', '').astype(float) / 100

# # 僅保留有 RT_6M_After 資料的資料列
# df = df.dropna(subset=['RT_6M_After'])

# # 分組統計 Winner 和 Loser
# group_stats = []
# for (comb, remark), group in df.groupby(['Combination', 'Remark']):
#     values = group['RT_6M_After']
#     count = len(values)
#     mean = values.mean()
#     t_stat, p_value = stats.ttest_1samp(values, popmean=0, alternative='greater')
#     group_stats.append({
#         'Combination': comb,
#         'Remark': remark,
#         'Count': count,
#         'RT_6M_After_Mean': mean,
#         'T_statistic': t_stat,
#         'P_value(one-sided > 0)': p_value
#     })

# # 將結果轉成 DataFrame
# stats_df = pd.DataFrame(group_stats)

# # 計算 Winner - Loser 的差異
# winner_loser_diff = []
# for comb in stats_df['Combination'].unique():
#     try:
#         w = stats_df[(stats_df['Combination'] == comb) & (stats_df['Remark'] == 'Winner')]
#         l = stats_df[(stats_df['Combination'] == comb) & (stats_df['Remark'] == 'Loser')]
#         if not w.empty and not l.empty:
#             diff = w['RT_6M_After_Mean'].values[0] - l['RT_6M_After_Mean'].values[0]
#             # 擷取該組 Winner 與 Loser 的原始值
#             winner_values = df[(df['Combination'] == comb) & (df['Remark'] == 'Winner')]['RT_6M_After'].reset_index(drop=True)
#             loser_values = df[(df['Combination'] == comb) & (df['Remark'] == 'Loser')]['RT_6M_After'].reset_index(drop=True)
#             # 確保數量一致才能做成對 t-test
#             min_len = min(len(winner_values), len(loser_values))
#             t_stat, p_value = stats.ttest_rel(winner_values[:min_len], loser_values[:min_len], alternative='greater')
#             winner_loser_diff.append({
#                 'Combination': comb,
#                 'Remark': 'Winner - Loser',
#                 'Count': '-',
#                 'RT_6M_After_Mean': diff,
#                 'T_statistic': t_stat,
#                 'P_value(one-sided > 0)': p_value
#             })
#     except Exception as e:
#         print(f"組合 {comb} 計算失敗：{e}")

# # 合併全部結果
# final_df = pd.concat([stats_df, pd.DataFrame(winner_loser_diff)], ignore_index=True)

# # 儲存為 CSV
# final_df.to_csv('t_test_results.csv', index=False)

# # # 顯示結果
# # print(final_df)

# # 存成 CSV
# targetFile = f'{outputDir}/{outputFilBaseName}_RT_6M_After-tTest.csv'

# final_df.to_csv(targetFile, index=False)
# print(f"✅ T-test檢定完成，已儲存檔案：{targetFile}")

import pandas as pd
from scipy import stats

observeHoldingPeriod = 6
outputDir = r'..\data\analysis\momentum'
outputFilBaseName = f'Momentum0050_0051-20160501_20180601-HP_{observeHoldingPeriod}'
srcFile = f'{outputDir}/{outputFilBaseName}_RT_6M_After-prepare.csv'

# 讀取 CSV，確保 RT_6M_After 是數值
df = pd.read_csv(srcFile)

# 篩選關注的三組
df = df[df['Remark'].isin(['Winner', 'Loser', 'Winner - Loser'])]

results = []

for remark in ['Winner', 'Loser', 'Winner - Loser']:
    group_data = df[df['Remark'] == remark]['RT_6M_After_Mean']
    
    # 單樣本t檢定（檢驗平均是否大於0）
    t_stat, p_two_tailed = stats.ttest_1samp(group_data, popmean=0)
    
    # 單尾p值（H1: mean > 0）
    if t_stat > 0:
        p_one_tailed = p_two_tailed / 2
    else:
        p_one_tailed = 1 - (p_two_tailed / 2)
    
    results.append({
        'Remark': remark,
        'mean': group_data.mean(),
        'n': len(group_data),
        't-statistic': t_stat,
        'p-value (one-tailed)': p_one_tailed
    })

result_df = pd.DataFrame(results)
print(result_df)

# 存成 CSV
targetFile = f'{outputDir}/{outputFilBaseName}_RT_6M_After-tTestAll.csv'

result_df.to_csv(targetFile, index=False)
print(f"✅ T-test檢定完成，已儲存檔案：{targetFile}")