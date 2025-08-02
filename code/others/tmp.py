import os
import glob

# 設定你要處理的根目錄（換成你自己的路徑）
root_dir = f"../data/analysis"
print(os.path.exists(root_dir))

# 遞迴尋找所有 .csv 檔案
pattern = os.path.join(root_dir, '**', '*-A.csv')
file_list = glob.glob(pattern, recursive=True)
print(file_list)

# 開始處理檔案
for filepath in file_list:
    dir_name = os.path.dirname(filepath)
    filename = os.path.basename(filepath)

    # 新檔名（移除 -A）
    new_filename = filename.replace('-A.csv', '.csv')
    new_filepath = os.path.join(dir_name, new_filename)

    # 更名
    os.rename(filepath, new_filepath)
    print(f'Renamed: {filepath} -> {new_filepath}')
