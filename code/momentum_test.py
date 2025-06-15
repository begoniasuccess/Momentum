import pandas as pd

# 讀取前面輸出的已排名檔案
input_filename = r'..\data\analysis\momentum\combinations\combinationReturn_2016-05-01_2018-06-01_HP-6_ranked.csv'
df = pd.read_csv(input_filename)

# 新增 remark 欄位，預設為空
df['remark'] = ''

# 每個 combination 內依 rank 做分組
def assign_remark(group):
    n = len(group)
    if n < 10:
        return group  # 太少不分組
    group = group.sort_values(by='rank')  # rank越小報酬越高

    # 計算前10% 和 後10% 的 rank 數值閾值
    top_threshold = max(1, int(n * 0.9))  # PR90 = top 10%
    bottom_threshold = int(n * 0.1)       # PR10 = bottom 10%

    # 根據 rank 指定 Winner / Loser
    group.loc[group['rank'] <= bottom_threshold, 'remark'] = 'Winner'
    group.loc[group['rank'] >= top_threshold, 'remark'] = 'Loser'

    return group

# 分組套用邏輯
df = df.groupby('combination', group_keys=False).apply(assign_remark)

# 匯出 remark 不為空的資料
result_df = df[df['remark'] != '']
result_df.to_csv(r'..\data\analysis\momentum\combinations\result.csv', index=False)

print("✅ Winner/Loser 標記已完成，已儲存 result.csv 檔案")