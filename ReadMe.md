
# Momentum Strategy Backtest for Taiwan Stock Market (台股動量策略回測)

本專案實作了 Jegadeesh & Titman (1993) 動能策略，並將樣本市場改為台股。可自訂回測區間、股票篩選條件與動能參數（排名區間、持有期間），輸出各期間報酬統計結果。

- 根據「月均市值前x大(上市股票)」與「月均股價前y大(上市+上櫃股票)」門檻進行篩選
	(x、y可自定義)
- 可自定義 觀察期（J）與 持有期（K）
- 使用 FinMind API 擷取台股歷史資料
- 使用調整後股價進行計算，支援撈取 2010年以後的資料
(因資料完整性問題，牽涉到2019年前的回測請以一般股價進行實作)

## 專案使用說明
1. 以下所有指令請確保在code資料夾底下運行
	```powershell
	cd code
	```
2. 運行前請先安裝python與相依套件
	```powershell
	pip install -r requirements.txt
	```
3. 觀察期o月、持有期h月，買賣日期對應關係
	|          | 買入時間  | 賣出時間 |
	| -------- | -------- | -------- |
	| 觀察期    |x月的第一交易日|(x+o-1)月的最後交易日|
	| 持有期(A) |(x+o)月的第一交易日|(x+o+h-1)月的最後交易日|
	| 持有期(B) |(x+o)月的第一交易日，<br>一週後的第一交易日|(x+o+h-1)月的最後交易日，<br>一週後的第一交易日|

## 回測「月均市值前x大」的策略報酬
1. 主程式位置：**code/momentumMvRank.py**
2. 運行指令
	```powershell
	### code/底下執行
	
	### [選項一](建議)
	# 指定powershell的編碼，每次重啟一個新的會話時都要運行
	$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
	# 運行主程式，且支援將terminal的訊息會存入文字檔log/momentumMvRank.log
	python -u momentumMvRank.py 2>&1 | Tee-Object -FilePath ../log/terminal_log.txt -Append

	### [選項二] 直接運行，terminal的訊息不會存入文字檔
	python momentumMvRank.py
	```

### momentumMvRank.py運行注意事項
 - 本程式會用到[FinMind](https://finmindtrade.com/)提供的API，所以請注意程式中的token必須是有效的
	```python
	### 檔案：code/common/finMind.py
	### FinMind api設定
	apiUrl  =  "https://api.finmindtrade.com/api/v4/data"
	api  =  DataLoader()
	token  =  "***此字串請填入自己的FinMind token***"
	api.login_by_token(api_token=token)
	```
 -  程式內參數設定
	```python
	### 檔案：code/momentumMvRank.py
	### 定義此回測的股價資料起始與終止年月(首尾計入)
	start_ym  =  "2010/01" # 取月初
	end_ym  =  "2024/12" # 取月底
	
	### oPeriods代表觀察期月數，hPeriods代表持有期月數
	oPeriods  = [3, 6, 9 ,12] # Observer Period，J
	hPeriods  = [3, 6, 9 ,12] # Holding Period，K
	
	### 設定每個月的股票候選名單，要取月均市值前多少名(e.g.150)
	maxIncludeRank  =  150	
		
	### 因為撈取FinMind資料費時且會大量消耗token的次數，
	### 建議如果確認該次策略的資料皆已儲存完畢，
	### 將此參數設為False，就可以略過下載/準備資料的步驟
	prepareDatas  =  True

	```

## 回測「月均股價大於y元」的策略報酬
1. 主程式位置：**code/momentumOverPrice.py**
2. 運行指令
	```powershell
	### code/底下執行
	
	### [選項一](建議)
	# 指定powershell的編碼，每次重啟一個新的會話時都要運行
	$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
	# 運行主程式，且支援將terminal的訊息會存入文字檔log/terminal.log
	python -u momentumOverPrice.py 2>&1 | Tee-Object -FilePath ../log/terminal.log -Append

	### [選項二] 直接運行，terminal的訊息不會存入文字檔
	python momentumOverPrice.py
	```
### momentumOverPrice.py運行注意事項
 - 本程式會用到[FinMind](https://finmindtrade.com/)提供的API，所以請注意程式中的token必須是有效的
	```python
	### 檔案：code/common/finMind.py
	### FinMind api設定
	apiUrl  =  "https://api.finmindtrade.com/api/v4/data"
	api  =  DataLoader()
	token  =  "***此字串請填入自己的FinMind token***"
	api.login_by_token(api_token=token)
	```
 -  程式內參數設定
	```python
	### 檔案：code/momentumOverPrice.py
	### 定義此回測的股價資料起始與終止年月(首尾計入)
	start_ym  =  "2010/01" # 取月初
	end_ym  =  "2024/12" # 取月底
	
	### oPeriods代表觀察期月數，hPeriods代表持有期月數
	oPeriods  = [3, 6, 9 ,12] # Observer Period，J
	hPeriods  = [3, 6, 9 ,12] # Holding Period，K
	
	### 設定每個月的股票候選人，月平均收盤價必須要在y元以上(e.g.10)
	minClosePrice = 10
		
	### 因為撈取FinMind資料費時且會大量消耗token的次數，
	### 建議如果確認該次策略的資料皆已儲存完畢，
	### 將此參數設為False，就可以略過下載/準備資料的步驟
	prepareDatas  =  True

	```

## 程式輸出結果說明
	- 本程式分析資料會分別存在下列資料夾底下：
		**data/analysis/momentumMv{maxIncludeRank}**
		**data/analysis/momentumOver{minClosePrice}**
	- 資料夾的名稱會對應策略的參數，例如：
		- oPeriod3_hPeriod3 >> 201001_202412
	- 資料夾內存儲了各步驟分析的檔案，若有疑慮可分階段排查：
		- 01-observerReturnList.csv
		- 02-observerReturnList_rank.csv
		- 03-winner_loser.csv
		- 04-holdingReturnList-A.csv
		- 05-holdingReturnList_static-A.csv
		- 06-holdingReturnList_static2-A.csv
		- 07-t_test-A.csv
		- 08-holdingReturnList-B.csv
		- 09-holdingReturnList_static-B.csv
		- 10-holdingReturnList_static2-B.csv
		- 11-t_test-B.csv
	- 本程式支援存檔功能，某階段的檔案存在後，該程式重新運行到對應階段會直接讀檔，**不會刪檔重新運算**。
	- 基於前項原因，若對運算邏輯進行修改，**請將對應階段及其後輸出的檔案刪除**後再重新運行。

## 利用mergeTcsv.py整合不同J、K的t_test.csv檔案
- 運行指令：
	```powershell
	### code/底下執行
	python mergeTcsv.py
	
	### terminal出現的選項對應要整合的資料
	A # MomentumMvRank => 月均市值前x大(mvX)
	B # MomentumOverPrice => 月均股價大於y元(overY)
	
	# 輸入對應的參數X、Y(排名or股價)
	```
- 檔案輸出位置：
	- 路徑：data/analysis/{momentumMvRank 或 momentumOverPrice}/mergeTtestResult
	- 檔案：
		- tTestReport-yyyymm_yyyyymm-{panelType}.csv (csv資料)
		- tTestReport-yyyymm_yyyyymm-{panelType}_p.xlsx (方便整理成論文中的圖)

## 其他指令(可略過)
	```powershell
	## 偵測專案中的所有套件
	python -m pip install pipreqs --upgrade
	python -m pipreqs.pipreqs . --force
	```