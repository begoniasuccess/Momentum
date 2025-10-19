import sys, os
sys.path.append(os.path.dirname(__file__))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from common import utils, db
from module import data_provider
import re
import copy

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
    result = None
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
            
            result = {
                "處置原因": [reason, 'str'],    
                "處置期間": [period, 'str'],
                "處置措施_a": [measure_a.group(1).strip() if measure_a else None, 'str'],
                "處置措施_b": [measure_b.group(1).strip() if measure_b else None, 'str'],
                "處置措施_c": [measure_c.group(1).strip() if measure_c else None, 'str'],
            }
            
        case 'tpex':
            text = row.處置內容
            
            # OK
            def extract_recent_days(text: str):
                """擷取『最近XX個營業日內曾發布處置』"""
                m = re.search(r"最近(\d+)個營業日內曾發布處置", text)
                if not m:
                    return None
                return {'發布處置_最近n日內': [int(m.group(1)), 'int']}

            # OK
            def extract_attention_trigger(text: str):
                """
                解析完整句型：
                『連續X個營業日達本中心作業要點第Y條第Z項第K款經本中心公告注意交易資訊』
                回傳 dict：
                    {
                    "連續觸發注意公告_天數": x,
                    "連續觸發注意公告_條項款": "000y000z000k"
                    }
                若找不到完整句型則回傳 None
                """
                pattern = (
                    r"連續(\d+)個營業日達本中心作業要點"
                    r"第([一二三四五六七八九十]+)條"
                    r"第([一二三四五六七八九十]+)項"
                    r"第([一二三四五六七八九十]+)款"
                    r"經本中心公告注意交易資訊"
                )

                m = re.search(pattern, text)
                if not m:
                    return None  # 沒有完整結構就跳過

                n_days = int(m.group(1))
                t = utils.chinese_to_int(m.group(2))
                i = utils.chinese_to_int(m.group(3))
                k = utils.chinese_to_int(m.group(4))
                clause_code = f"{t:04d}{i:04d}{k:04d}"

                return {
                    "注意公告_連續觸發_天數": [n_days, 'int'],
                    "注意公告_連續觸發_條項款": [clause_code, 'str'],
                }

            # OK
            def extract_interval(text: str):
                """擷取『約X分鐘撮合一次』"""
                m = re.search(r"約(\d+)分鐘", text)
                if not m:
                    return None
                return {
                    "撮合頻率_n分一次": [int(m.group(1)), 'int']
                }
            
            def parse_recent_days_notice(text: str):
                """
                解析「最近X個營業日內有Y個營業日經本中心公布注意交易資訊」
                回傳 {
                    "注意公告_近日多次_n個營業日": X,Y,
                    "注意公告_近日多次_次數":                    
                    }
                """
                pattern = r"最近(\d+)個營業日內有(\d+)個營業日經本中心公布注意交易資訊"
                m = re.search(pattern, text)
                if not m:
                    return None
                return {
                    "注意公告_近日多次_n個營業日": [int(m.group(1)), 'int'],
                    "注意公告_近日多次_次數": [int(m.group(2)), 'int']
                }
                
            def parse_consecutive_days_notice(text: str):
                """
                解析「連續X個營業日經本中心公布注意交易資訊」
                回傳 {'注意公告_連續觸發_天數': X}
                """
                pattern = r"連續(\d+)個營業日經本中心公布注意交易資訊"
                m = re.search(pattern, text)
                if not m:
                    return None
                return {"注意公告_連續觸發_天數": [int(m.group(1)), 'int']}
            
            def parse_recent_rule_trigger(text: str):
                """
                解析：
                「最近X個營業日曾達本中心作業要點第<中文數字>條第<中文數字>項第<中文數字>款經本中心公布注意交易資訊」

                回傳：
                {
                "注意公告_近日曾達_n個營業日": X,
                "注意公告_近日曾達_條項款": "<條(4位)><項(4位)><款(4位)>"
                }
                若找不到完整句型回傳 None。
                """
                pattern = (
                    r"最近(\d+)個營業日曾達本中心作業要點"
                    r"第([一二三四五六七八九十百千零]+)條"
                    r"第([一二三四五六七八九十百千零]+)項"
                    r"第([一二三四五六七八九十百千零]+)款"
                    r"經本中心公[布告]注意交易資訊"
                )

                m = re.search(pattern, text)
                if not m:
                    return None

                obs_days = int(m.group(1))

                ch_t = m.group(2)
                ch_i = m.group(3)
                ch_k = m.group(4)

                t = utils.chinese_to_int(ch_t)
                i = utils.chinese_to_int(ch_i)
                k = utils.chinese_to_int(ch_k)

                if t is None or i is None or k is None:
                    return None

                clause_code = f"{t:04d}{i:04d}{k:04d}"

                return {
                    "注意公告_近日曾達_n個營業日": [obs_days, 'int'],
                    "注意公告_近日曾達_條項款": [clause_code, 'str']
                }
            
            fun_list = [extract_recent_days, extract_attention_trigger, extract_interval, parse_recent_days_notice, parse_consecutive_days_notice, parse_recent_rule_trigger]
            
            result = {}
            for fun in fun_list:
                feature = fun(text)
                if feature is None:
                    continue
                result.update(feature)
    
    return result

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
        if type == 'tpex':
            # 可轉債股票不是特定關係戶買不到，這邊略過
            sql += " ADN 處置內容 NOT LIKE '公司債(%''"       
        
        totalCnt = db.query_single_value(sql)
        print("totalCnt=", int(totalCnt))
        
        if totalCnt < 1:
            continue
        
            
        sql = f"SELECT * FROM {table}"
        sql += f" WHERE law_src IS NULL or TRIM(law_src) = ''"
        if type == 'tpex':
            # 可轉債股票不是特定關係戶買不到，這邊略過
            sql += " ADN 處置內容 NOT LIKE '%公司債%''"       
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

            ele_base = AddInfo()
            ele_base.tag = tag
            ele_base.target_table = table
            ele_base.target_id = row.id
            
            ### 處理處置內容
            punish_content_obj = ana_punish_content(type, row)
            print("punish_content_obj", punish_content_obj)
            for col_name, col_val in punish_content_obj:
                ele = copy.deepcopy(ele_base)
                ele.col_name = col_name
                ele.col_val = col_val[0]
                ele.val_type = col_val[1]
                add_vals.append(ele)
                    
            print(punish_content_obj, add_vals)
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
        if type == 'tpex':
            # 可轉債股票不是特定關係戶買不到，這邊略過
            sql += " ADN 處置內容 NOT LIKE '%公司債%''"        
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
    handle_punish()
    # handle_notice()