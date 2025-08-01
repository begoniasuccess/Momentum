import os

# 設定根目錄
root_dir = "../data/analysis"

# 要改名的檔案清單與對應新結尾
target_files = [
    "04-holdingReturnList.csv",
    "05-holdingReturnList_static.csv",
    "06-holdingReturnList_static2.csv",
    "07-t_test.csv",
]

# 遍歷所有子目錄
for dirpath, dirnames, filenames in os.walk(root_dir):
    for filename in filenames:
        if filename in target_files:
            old_path = os.path.join(dirpath, filename)
            name, ext = os.path.splitext(filename)
            new_filename = name + "-A" + ext
            new_path = os.path.join(dirpath, new_filename)
            os.rename(old_path, new_path)
            print(f"✅ Renamed: {old_path} → {new_path}")
