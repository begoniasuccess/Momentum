import sys, os
sys.path.append(os.path.dirname(__file__))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from common import utils, db
from module import data_provider
import re

### 寫入 Relation
def writein_relation():
    table = "relation_punish_notice"
    insert_cols = [
        "type", 
        "punish_id",
        "notice_id"
    ]
    
    apiNames = ["上市公布處置有價證券", "上櫃處置有價證券資訊"]
    for apiName in apiNames:
        print("**開始處理：", apiName)
        punish_apiInfo = utils.get_api_info(apiName)
        punish_table = punish_apiInfo["storage_table"].iloc[0]
        type = punish_apiInfo["type"].iloc[0].lower()
        punish_time_col = punish_apiInfo["time_col"].iloc[0]
        
        sql = f"SELECT COUNT(*) AS cnt FROM {punish_table}"
        sql += f" WHERE last_notice IS NULL OR notice_cnt IS NULL"
        
        totalCnt = db.query_single_value(sql)
        print("totalCnt=", int(totalCnt))
        
        if totalCnt < 1:
            continue        
        
        sql = f"SELECT * FROM {punish_table}"
        sql += f" WHERE last_notice IS NULL OR notice_cnt IS NULL"
        sql += f" ORDER BY {punish_time_col}_ts DESC"
        df_punishes = db.query_to_df(sql)
        # print("sql=", sql)
        # print(df_punishes.head(1))
        if df_punishes.empty:
            continue
        
        ## 遍歷資料
        idx = 0
        total_insert = 0
        total_update = 0
        reportCnt = 100
        for row_punish in df_punishes.itertuples(index=True, name="punish"): 
            idx += 1  
            if (idx % reportCnt == 1):
                print(f"***開始處理第{idx}筆資料...")
                
            notice_apiName = ""
            match type:
                case "twse":
                    notice_apiName = "上市公布注意有價證券資訊"
                case "tpex":
                    notice_apiName = "上櫃公布注意有價證券資訊"
            notice_apiInfo = utils.get_api_info(notice_apiName)
            notice_table = notice_apiInfo["storage_table"].iloc[0]
            notice_time_col = notice_apiInfo["time_col"].iloc[0]
            
            ### 搜尋可能關聯的注意股名單
            sql = f"SELECT * FROM {notice_table}"
            sql += f" WHERE 證券代號 = (SELECT 證券代號 FROM {punish_table} WHERE id+0 = {row_punish.id})"
            sql += f" AND {notice_time_col}_ts <= (SELECT {punish_time_col}_ts FROM {punish_table} WHERE id+0 = {row_punish.id})"
            sql += f" ORDER BY {notice_time_col}_ts DESC"
            
            df_notices = db.query_to_df(sql)
            # print("sql=", sql)
            # print(df_target.head(1))
            
            if df_notices.empty:
                print("*** 找不到注意股資料", sql)
                continue
        
            punish_date_ts = getattr(row_punish, punish_time_col + "_ts")
            insert_vals = []
            previous_notice_date_ts = None
            notice_idx = 0
            fst_notice_id = None            
            for row_notice in df_notices.itertuples(index=True, name="notice"): 
                notice_idx += 1
                notice_date_ts = getattr(row_notice, notice_time_col + "_ts")
                if notice_idx == 1:                        
                    if (punish_date_ts - notice_date_ts) > 86400*3 :
                        break # 跳出此批注意股
                    fst_notice_id = row_notice.id                    
                else:
                    if (previous_notice_date_ts - notice_date_ts) > 86400*4 :
                        break # 跳出此批注意股
                previous_notice_date_ts = notice_date_ts
                
                try:                            
                    insert_vals.append([
                        type,
                        row_punish.id,
                        row_notice.id
                    ])
                except:
                    print("***Data write in error：", row_notice)
                    continue
                
            if len(insert_vals) == 0:
                continue        
            
            ### 插入relation table
            sql = f"""
            INSERT OR REPLACE INTO {table} 
                ({",".join(insert_cols)})
            VALUES 
                ({", ".join(["?"] * len(insert_cols))})
            """
            insert_cnt =  db.execute_sql(sql, insert_vals)
            if (insert_cnt > 0):
                total_insert += insert_cnt
            else:
                print("***Relation table 寫入失敗", sql)
            
            ### 更新punish table
            sql = f"""
            UPDATE {punish_table} 
                SET last_notice = {fst_notice_id}, notice_cnt = {len(insert_vals)}
            WHERE id+0 = {row_punish.id}
            """
            update_cnt =  db.execute_sql(sql)
            if (update_cnt > 0):
                total_update += update_cnt
            else:
                print("***Punish table 更新失敗", sql, row_punish)
        
        print("total_update", total_update)
        print("total_insert", total_insert)
    return 

def ana_punish_content(type, row):
    match type.lower():
        case 'twse':
            text = row.處置內容
            # １處置原因：該有價證券之交易，連續三個營業日達本公司「公布注意交易資訊」標準。
            match_reason = re.search(r'１處置原因：(.+?)２處置期間：', text, re.S)
            # ２處置期間：自民國一百十四年九月二十三日起至一百十四年十月八日﹝十個營業日，如遇：ａ有價證券最後交易日在處置期間，僅處置至最後交易日，ｂ有價證券停止買賣、全日暫停交易則順延執行，ｃ開休市日變動則調整處置迄日〕。
            match_period = re.search(r'２處置期間：(.+?)３處置措施：', text, re.S)
            match_measures = re.search(r'３處置措施：(.*)', text, re.S)

            reason = match_reason.group(1).strip() if match_reason else None
            period = match_period.group(1).strip() if match_period else None
            measures = match_measures.group(1).strip() if match_measures else None

            # ３處置措施：
            # ａ以人工管制之撮合終端機執行撮合作業（約每五分鐘撮合一次）。
            # ｂ投資人每日委託買賣該有價證券數量單筆達十交易單位或多筆累積達三十交易單位以上時，應就其當日已委託之買賣，向該投資人收取全部之買進價金或賣出證券。
            #ｃ信用交易部分，應收足融資自備款或融券保證金。有關信用交易了結部分，則依相關規定辦理。
            measure_a = re.search(r'ａ(.*?)(?=ｂ|$)', measures, re.S)
            measure_b = re.search(r'ｂ(.*?)(?=ｃ|$)', measures, re.S)
            measure_c = re.search(r'ｃ(.*)', measures, re.S)
            return {
                "處置原因": [reason, 'str'],    
                "處置期間": [period, 'str'],
                "處置措施_a": [measure_a.group(1).strip() if measure_a else None, 'str'],
                "處置措施_b": [measure_b.group(1).strip() if measure_b else None, 'str'],
                "處置措施_c": [measure_c.group(1).strip() if measure_c else None, 'str'],
            }
        case 'tpex':
            text = row.處置內容
            
            # 1️⃣ 提取代號，例如：(代號：3313)
            match_id = re.search(r'代號：(\d+)', text)
            stock_id = match_id.group(1) if match_id else None

            # 2️⃣ 因連續 N 個營業日
            match_consecutive = re.search(r'因連續(\d+)個營業日', text)
            consecutive_days = int(match_consecutive.group(1)) if match_consecutive else None

            # 3️⃣ 達本中心作業要點第四條第一項第 X 款公布注意交易資訊
            match_law = re.search(r'達本中心作業要點(.*?)經本中心公布注意交易資訊', text)
            law_article = match_law.group(1) if match_law else None

            # 4️⃣ 約每 N 分鐘撮合一次
            match_interval = re.search(r'約每(\d+)分鐘撮合一次', text)
            interval_minutes = int(match_interval.group(1)) if match_interval else None

            # 5️⃣ 最近 N 個營業日內曾發布處置
            match_recent = re.search(r'最近(\d+)個營業日內曾發布處置', text)
            recent_days = int(match_recent.group(1)) if match_recent else None

            # ✅ 結果示範
            print("stock_id:", stock_id)
            print("consecutive_days:", consecutive_days)
            print("law_article:", law_article)
            print("interval_minutes:", interval_minutes)
            print("recent_days:", recent_days)
            return {
                "股票代號": [stock_id, 'str'],
                "連續違規營業日數": [consecutive_days, 'int'],
                "違規條款": [law_article, 'str'],
                "撮合頻率_分": [interval_minutes, 'int'],
                "最近n個營業日內發布處置": [recent_days, 'int']
            }   

### 對處置股的資料進行各種處理
def handle_punish():    
    apiNames = ["上市公布處置有價證券", "上櫃處置有價證券資訊"]
    
    tag = "stock_punish"
    for apiName in apiNames:
        print("**開始處理：", apiName)
        apiInfo = utils.get_api_info(apiName)
        table = apiInfo["storage_table"].iloc[0]
        type = apiInfo["type"].iloc[0].lower()
        time_col = apiInfo["time_col"].iloc[0]
        
        sql = f"SELECT COUNT(*) AS cnt FROM {table}"
        sql += f" WHERE law_src IS NULL or TRIM(law_src) = ''"
        
        totalCnt = db.query_single_value(sql)
        print("totalCnt=", int(totalCnt))
        
        if totalCnt < 1:
            continue
        
            
        sql = f"SELECT * FROM {table}"
        sql += f" WHERE law_src IS NULL or TRIM(law_src) = ''"
        sql += f" ORDER BY {time_col}_ts DESC"
        df_target = db.query_to_df(sql)
        # print("sql=", sql)
        # print(df_target.head(1))
        if df_target.empty:
            continue
        
        total_insert = 0
        total_update = 0
        
        ## 遍歷資料
        idx = 0
        reportCnt = 100
        add_vals = []
        for row in df_target.itertuples(index=True, name="MyRow"): 
            idx += 1  
            if (idx % reportCnt == 1):
                print(f"***開始處理第{idx}筆資料...")

            ### 寫入 [連續違規次數]
            violation_times = 0 
            # TODO：count violation_times            
            ele_violate_cnt = AddInfo()
            ele_violate_cnt.tag = tag
            ele_violate_cnt.target_table = table
            ele_violate_cnt.target_id = row.id
            ele_violate_cnt.col_name = "連續違規次數"
            ele_violate_cnt.col_val = violation_times
            ele_violate_cnt.val_type = "int"
            add_vals.append(ele_violate_cnt)
            
            ### 寫入 [處置起訖時間]
            punish_start_at = None
            punish_end_at = None
            # TODO:: handle punish_start_at、punish_end_at
            ele_punish_start = AddInfo()
            ele_punish_start.tag = tag
            ele_punish_start.target_table = table
            ele_punish_start.target_id = row.id
            ele_punish_start.col_name = "處置起始日"
            ele_punish_start.col_val = punish_start_at
            ele_punish_start.val_type = "ts"
            add_vals.append(ele_punish_start)
            
            ele_punish_end = AddInfo()
            ele_punish_end.tag = tag
            ele_punish_end.target_table = table
            ele_punish_end.target_id = row.id
            ele_punish_end.col_name = "處置終止日"
            ele_punish_end.col_val = punish_end_at
            ele_punish_end.val_type = "ts"
            add_vals.append(ele_punish_end)
            
            ### 處理twse的處置內容
            punish_content_obj = ana_punish_content(type, row)
            for col_name, col_val in punish_content_obj:
                ele = AddInfo()
                ele.tag = tag
                ele.target_table = table
                ele.target_id = row.id
                ele.col_name = col_name
                ele.col_val = col_val[0]
                ele.val_type = col_val[1]
                add_vals.append(ele)
                    
            sys.exit() # test
            insert_cnt = insert_addition_info(add_vals)
            total_insert += insert_cnt
            
        print("total_insert", total_insert)
        print("total_update", total_update)
    return




class AddInfo:
    def __init__(self):
        self.id = None
        ###
        self.tag = None
        self.target_table = None
        self.target_id = None
        self.col_name = None
        self.col_val = None
        self.val_type = None
        self.memo = None
        
    def output_list(self) -> list:
        data_list = [
            self.tag,
            self.target_table,
            self.target_id,
            self.col_name,
            self.col_val,
            self.val_type,
            self.memo
        ]
        if self.id is not None:
            data_list.insert(0, self.id)
        return data_list

def insert_addition_info(datas:list, report_cnt:int = 100)-> int:
    table = "addition_info"
    insert_cols = [
        "tag",
        "target_table",
        "target_id",
        "col_name",
        "col_val",
        "val_type",
        "memo"
    ]
    
    insert_vals = []
    for oneData in datas:
        if isinstance(oneData, list) or isinstance(oneData, tuple):
            insert_vals = datas
            break
        
        if isinstance(oneData, AddInfo):
            insert_vals.append(oneData.output_list())
        
    sql = f"""
            INSERT OR REPLACE INTO {table} 
                ({",".join(insert_cols)})
            VALUES 
                ({", ".join(["?"] * len(insert_cols))})
            """
    insert_cnt =  db.execute_sql(sql, insert_vals)
    if (insert_cnt > 0):
        return insert_cnt
    else:
        print("***Relation table 寫入失敗", sql)
    
    return 0

### 把注意股的"觸發法條(law_src)"擷取出來
def handle_notice():    
    apiNames = ["上市公布注意有價證券資訊", "上櫃公布注意有價證券資訊"]
    
    for apiName in apiNames:
        print("**開始處理：", apiName)
        apiInfo = utils.get_api_info(apiName)
        table = apiInfo["storage_table"].iloc[0]
        type = apiInfo["type"].iloc[0].lower()
        time_col = apiInfo["time_col"].iloc[0]
        
        sql = f"SELECT COUNT(*) AS cnt FROM {table}"
        sql += f" WHERE law_src IS NULL or TRIM(law_src) = ''"
        
        totalCnt = db.query_single_value(sql)
        print("totalCnt=", int(totalCnt))
        
        if totalCnt < 1:
            continue
        
        total_update = 0
            
        sql = f"SELECT * FROM {table}"
        sql += f" WHERE law_src IS NULL or TRIM(law_src) = ''"
        sql += f" ORDER BY {time_col}_ts DESC"
        df_target = db.query_to_df(sql)
        # print("sql=", sql)
        # print(df_target.head(1))
        if df_target.empty:
            continue
        
        ## 遍歷資料
        idx = 0
        reportCnt = 100
        for row in df_target.itertuples(index=True, name="MyRow"): 
            idx += 1  
            if (idx % reportCnt == 1):
                print(f"***開始處理第{idx}筆資料...")
            ### 寫入law_src欄位                
            regex = r"﹝(.*?)﹞"
            match type:
                case "twse":
                    regex = r"﹝(.*?)﹞"
                case "tpex":
                    regex = r"[（(](第.*?)[）)]" 
                    
            matches = re.findall(regex, row.注意交易資訊)
            if matches is None:
                print("**未寫入：", row.id, row.證券代號, row.證券名稱)
                continue
            
            updateVal = ""
            for m in matches:
                # print(m)               
                if updateVal != "":
                    updateVal += "," 
                    
                updateVal += "".join(m)  
            
            if updateVal.strip() == "":
                print("**未寫入：", row.id, row.證券代號, row.證券名稱)
                continue
            
            sql = f"""
                UPDATE {table} 
                    SET law_src = '{updateVal}'
                    WHERE id+0 = {row.id}                 
                """                            
            exeResult = db.execute_sql(sql)
            # print(row.id, row.證券代號, row.證券名稱)
            # print("exeResult=", exeResult, "sql=", sql)
            total_update += exeResult
            
        print("total_update", total_update)
    return

if __name__ == "__main__": 
    writein_relation()
    # handle_notice()