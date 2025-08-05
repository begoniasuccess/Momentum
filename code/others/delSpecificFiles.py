from pathlib import Path
import sys

# 設定你的主資料夾路徑
base_dir = Path(r"C:\Users\USER\Desktop\Han\學習\金融策略\分析程式\data\analysis\momentumMv150")  # 替換為實際路徑
if not base_dir.exists():
    print("dir error！")
    sys.exit()

patterns = [
    # '*holdingReturnList_static-A.csv', '*holdingReturnList_static2-A.csv', '*t_test-A.csv',
    # '*holdingReturnList_static-B.csv', '*holdingReturnList_static2-B.csv', '*t_test-B.csv'
    '*t_test-A.csv','*t_test-B.csv'
]

for pattern in patterns:
    # 遍歷所有子資料夾，尋找符合 pattern 的檔案
    files_to_delete = list(base_dir.rglob(pattern))

    # 確認找到的檔案數量與清單
    print(f"Pattern：{pattern} 找到 {len(files_to_delete)} 個檔案要刪除。")
    # sys.exit()

    # 刪除檔案
    for file_path in files_to_delete:
        try:
            file_path.unlink()
            print(f"已刪除: {file_path}")
        except Exception as e:
            print(f"刪除失敗: {file_path}，錯誤：{e}")
