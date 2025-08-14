import os
import sys
import io
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common import finMind, utils
from datetime import datetime
from FinMind.data import DataLoader

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# $OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
# python -u test.py 2>&1 | Tee-Object -FilePath ../log/test.log -Append

### FinMind api設定
apiUrl = "https://api.finmindtrade.com/api/v4/data"
api = DataLoader()
token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNS0wOC0xMCAyMTo1MjozMSIsInVzZXJfaWQiOiJueWN1bGFiNjE1IiwiaXAiOiI0Mi43Mi4yNTMuMTQyIn0.b_9r9FGuBJqMPtqL04UlWV-8SFvxDds8P18IdmYnLkE"
api.login_by_token(api_token=token)

sDt = datetime(2005, 1, 1)
eDt = datetime(2024, 12, 31)

outputFile = '../data/analysis/summary/weightIdx/20050101_20241231.csv'
dfSDA = api.taiwan_stock_daily_adj(
            stock_id='TAIEX',
            start_date=sDt.strftime("%Y-%m-%d"),
            end_date=eDt.strftime("%Y-%m-%d")
        )
dfSDA.to_csv(outputFile, index=False, encoding='utf-8-sig')
utils.ptMsg("✅ 檔案存取成功：", outputFile)