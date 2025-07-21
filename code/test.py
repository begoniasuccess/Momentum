import os
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# $OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
# python -u test.py 2>&1 | Tee-Object -FilePath ../log/test.log -Append

from common import utils


folder = f"../data/FinMind/TW/DailyPriceAdj"
utils.delete_empty_csv_files_recursive(folder)
