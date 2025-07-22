import pandas as pd
from pathlib import Path

# project = "momentumNew"
project = "momentumImproved"

# 資料夾路徑
root_folder = Path(f"../data/analysis/{project}")

# 找到所有 07-t_test.csv
all_files = list(root_folder.rglob("07-t_test.csv"))

# 儲存最終整合結果
final_df = pd.DataFrame()

for file in all_files:
    # 讀取檔案
    df = pd.read_csv(file)
    
    # 根據路徑取得 oPeriod 與 hPeriod
    parts = file.parts
    folder_name = [p for p in parts if "oPeriod" in p and "_hPeriod" in p]
    if folder_name:
        name_part = folder_name[0]
        o_period = name_part.split("_")[0].replace("oPeriod", "")
        h_period = name_part.split("_")[1].replace("hPeriod", "")
    else:
        o_period = ""
        h_period = ""
    
    # 新增欄位
    df["oPeriod"] = o_period
    df["hPeriod"] = h_period
    
    # 合併進總表
    final_df = pd.concat([final_df, df], ignore_index=True)

savePath = f"../data/analysis/{project}/mergeTtestResult/merged_t_test.csv"
# 儲存
final_df.to_csv(savePath, index=False)
