import requests
import pandas as pd
from common import utils
from common import finMind

twStock = finMind.getTwStockInfoNoEmerging()
twStock.to_csv("test.csv", index=False, encoding='utf-8-sig')