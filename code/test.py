import requests
import pandas as pd
from common import utils
from common import finMind

twStock = finMind.twStockInfoTwse()
print(twStock)

twStock = finMind.twStockInfoNoEmerging()
print(twStock)