import os
import sys
import io
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common import finMind
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# $OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
# python -u test.py 2>&1 | Tee-Object -FilePath ../log/test.log -Append

sDt = datetime(2005, 1, 1)
eDt = datetime(2024, 12, 31)

result = finMind.getWeightIdxDailyPriceAdj(sDt, eDt)
print(result)