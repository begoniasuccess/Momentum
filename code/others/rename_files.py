import os
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')

# 指定資料夾路徑
folder = Path(r"..\data\FinMind\TW\DailyPriceAdj\20100101-20201231")

# 遍歷所有檔案
for file in folder.glob("TWMV*"):
    if file.is_file():
        new_name = file.name.replace("TWMV", "TWDPadj", 1)  # 只改最前面的TWMV
        new_path = file.with_name(new_name)
        file.rename(new_path)
        print(f"✅ 已重新命名：{file.name} -> {new_name}")
