import requests
import pandas as pd
from common import utils
from common import finMind
from datetime import datetime, timedelta

# test = finMind.twStockInfoTwse()
# print(test)

# test = finMind.twStockInfoNoEmerging()
# print(test)


sDt = datetime.strptime('2005/01/01', "%Y/%m/%d") # Start Date
eDt = datetime.strptime('2025/12/31', "%Y/%m/%d") # End Date

test = finMind.twMarketValueMean(["1101", "2330"], sDt, eDt)
print(test)
