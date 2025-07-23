import pandas as pd
from pathlib import Path
import re
import os
from inputimeout import inputimeout, TimeoutOccurred
import time
import sys

projectOptions = {
    "A":"momentumNew",
    "B":"momentumImproved"
}

# 顯示選項
print("")
print("當前Momentum Project列表：")
for key, ip in projectOptions.items():
    print(f"{key}. {ip}")
print("")
choice = input("要處理的專案：").strip().upper()
if choice in projectOptions:
    project = projectOptions[choice]
else:
    print(f"選項有誤({choice})")
    sys.exit()

# project = "momentumNew"

# 資料夾路徑
root_folder = Path(f"../data/analysis/{project}")
root_folder = Path(f"../data/analysis/{project}")

# 找到所有 07-t_test.csv
all_files = list(root_folder.rglob("07-t_test.csv"))

# 儲存最終整合結果
resultDic = {}

for file in all_files:
    # print(file) # ..\data\analysis\momentumNew\oPeriod12_hPeriod12\201001_201912\07-t_test.csv
    
    # 讀取檔案
    df = pd.read_csv(file)
    
    parts = file.parts # ('..', 'data', 'analysis', 'momentumNew', 'oPeriod12_hPeriod12', '201001_201912', '07-t_test.csv')
    
    # 根據時間區間(yyyymm_yyyymm)拆分csv做存檔
    folder_ym = next((p for p in parts if re.match(r'^\d{6}_\d{6}$', p)), None) # 201001_201912
    if folder_ym not in resultDic:
        resultDic[folder_ym] = pd.DataFrame()
    
    # 根據路徑取得 oPeriod 與 hPeriod
    folder_period = [p for p in parts if "oPeriod" in p and "_hPeriod" in p] # oPeriod12_hPeriod12
    
    # print(folder_ym)
    if folder_period:
        name_part = folder_period[0]
        o_period = name_part.split("_")[0].replace("oPeriod", "")
        h_period = name_part.split("_")[1].replace("hPeriod", "")
    else:
        o_period = ""
        h_period = ""
    
    # 新增欄位
    df["oPeriod"] = o_period
    df["hPeriod"] = h_period
    
    # 合併進總表
    resultDic[folder_ym] = pd.concat([resultDic[folder_ym], df], ignore_index=True)

# print(resultDic)
for timeRange in resultDic:
    saveFolder = f"{root_folder}/mergeTtestResult"
    os.makedirs(saveFolder, exist_ok=True)
    savePath = f"{saveFolder}/tTestReport-{timeRange}.csv"
    
    inputTimeoutSecs = 5
    # 檢查檔名是否已存在
    while os.path.exists(savePath):
        print(f"⚠️ 檔案已存在：{savePath}")
        try:
            suffix = inputimeout(prompt=f'請在{inputTimeoutSecs}秒內為檔名加入後綴詞（不加副檔名）：', timeout=inputTimeoutSecs)
        except TimeoutOccurred:
            suffix = ts_int = int(time.time())
            print(f'⚠️ 用戶沒有輸入後綴，使用預設後綴詞：{suffix}')
        savePath = f"{saveFolder}/tTestReport-{timeRange}-{suffix}.csv"
        
    resultDic[timeRange].to_csv(savePath, index=False)