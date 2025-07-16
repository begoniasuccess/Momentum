import requests
import pandas as pd
from common import utils
from common import finMind

twStock = finMind.getTwStockInfoNoEmerging()
print(twStock.head(10))