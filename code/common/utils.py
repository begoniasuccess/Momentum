from datetime import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

def nowTime():
    """取得當前時間 (yyyy/mm/dd hh:mm:ss)"""
    return datetime.now().strftime("%Y/%m/%d %H:%M:%S")

def ptMsg(msg):
    """打印時間與日誌 (yyyy/mm/dd hh:mm:ss)"""
    
    print(f"{nowTime()}：{msg}")

def inTimeRange(targetDt, sDt , eDt):
    return sDt <= targetDt <= eDt