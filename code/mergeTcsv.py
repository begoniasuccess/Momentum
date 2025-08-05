import pandas as pd
from pathlib import Path
import re
import os
from inputimeout import inputimeout, TimeoutOccurred
import time
import sys
from enum import Enum

class Project(Enum):
    A = 'momentumMv'
    B = 'momentumOver'

projectOptions = {
    "A": Project.A.value,
    "B": Project.B.value
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

num = None
if choice == "A":
    num = input("請輸入最大排名：").strip()
elif choice == "B":
    num = input("請輸入最小股價：").strip()

if not num.isdigit():
    print(f"不合法的數字：{num}")
    sys.exit()

project = project + num

targetCsvs = ['07-t_test.csv', '07-t_test-A.csv', '11-t_test-B.csv']
root_folder = Path(f"../data/analysis/{project}")
if not os.path.isdir(root_folder):
    print(f"資料夾不存在： {root_folder}")
    sys.exit()

for csvName in targetCsvs:
    print(f"目標csv檔案為： {csvName}")

    # 找到所有 07-t_test.csv
    all_files = list(root_folder.rglob(csvName))

    # 儲存最終整合結果
    resultDic = {}

    for file in all_files:
        # ..\data\analysis\momentumMv150\oPeriod12_hPeriod12\201001_201912\07-t_test.csv
        # print(file) 
        
        # 讀取檔案
        df = pd.read_csv(file)
        
        parts = file.parts # ('..', 'data', 'analysis', 'momentumMv150', 'oPeriod12_hPeriod12', '201001_201912', '07-t_test.csv')
        
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
        savePath = f"{saveFolder}/tTestReport-{timeRange}{csvName}.csv"
        
        inputTimeoutSecs = 10
        # 檢查檔名是否已存在
        if os.path.exists(savePath):
            print(f"⚠️ 檔案已存在：{savePath}")
            continue
            # try:
            #     suffix = inputimeout(prompt=f'請在{inputTimeoutSecs}秒內為檔名加入後綴詞（不加副檔名）：', timeout=inputTimeoutSecs)
            # except TimeoutOccurred:
            #     suffix = ts_int = int(time.time())
            #     print(f'⚠️ 用戶沒有輸入後綴，使用預設後綴詞：{suffix}')
            # savePath = f"{saveFolder}/tTestReport-{timeRange}{csvName}-{suffix}.csv"
            
        df = resultDic[timeRange]    
        df.to_csv(savePath, index=False)
        print("✅ 輸出完成：" + savePath)

        ### 輸出整理檔
        remarks = ['loser', 'winner', 'winner - loser']
        oPeriods = sorted(df['oPeriod'].unique())
        hPeriods = sorted(df['hPeriod'].unique())

        output_rows = []

        for o in oPeriods:
            for remark in remarks:
                sub = df[(df['oPeriod'] == o) & (df['remark'] == remark)]

                mean_row = [str(o), remark]
                tstat_row = ['', '']

                for h in hPeriods:
                    row = sub[sub['hPeriod'] == h]
                    if not row.empty:
                        mean = row['mean'].values[0]                        
                        t_stat = row['t_stat'].values[0]
                        mean_row.append(f"{mean:.4f}")
                        tstat_row.append(f"{t_stat:.4f}")
                    else:
                        mean_row.append('')
                        tstat_row.append('')

                output_rows.append(mean_row)
                output_rows.append(tstat_row)

        columns = ['J=', 'K='] + [f'{h}' for h in hPeriods]
        output_df = pd.DataFrame(output_rows, columns=columns)

        # 輸出乾淨版 Excel（無格式）
        filepath = Path(savePath)
        savePath = f"{saveFolder}/{filepath.stem}_p.xlsx"
        output_df.to_excel(savePath, index=False)
        print("✅ 輸出完成：" + savePath)


    