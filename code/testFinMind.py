import requests
import pandas as pd
from FinMind.data import DataLoader

# url = "https://api.finmindtrade.com/api/v4/data"
# token = "" # 參考登入，獲取金鑰
# headers = {"Authorization": f"Bearer {token}"}
# # parameter = {
# #     # "dataset": "TaiwanStockInfo", # 台股總攬
# #     # "dataset": "TaiwanStockPriceAdj", # 台灣股價還原資料
# #     # "dataset": "TaiwanStockInfo", # 台灣股價市值表
# #     "dataset": "TaiwanStockCapitalReductionReferencePrice", # 減資恢復買賣參考價個
# # }

# parameter = {
#     "dataset": "TaiwanStockInfo",
#     "data_id": "2327",
#     "start_date": "2010-01-01",
# }
# data = requests.get(url, headers=headers, params=parameter)
# data = data.json()
# data = pd.DataFrame(data['data'])
# print(data.head())

api = DataLoader()
df = api.taiwan_stock_info() # 台股總覽
df.to_csv("taiwan_stock_info.csv", index=False, encoding='utf-8-sig')   

df = api.taiwan_stock_delisting() # 
df.to_csv("taiwan_stock_delisting.csv", index=False, encoding='utf-8-sig')   