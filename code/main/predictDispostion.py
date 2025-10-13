import sys, os
sys.path.append(os.path.dirname(__file__))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from common import utils, db
from module import data_provider
import re

# TODO
def handle_punish() -> bool:
    apiNames = ["上市公布處置有價證券", "上櫃處置有價證券資訊"]
    
    # TODO
    
    return False

def handle_notice() -> int:    
    apiNames = ["上市公布注意有價證券資訊", "上櫃公布注意有價證券資訊"]
    
    for apiName in apiNames:
        print("**開始處理：", apiName)
        apiInfo = utils.get_api_info(apiName)
        table = apiInfo["storage_table"].iloc[0]
        type = apiInfo["type"].iloc[0].lower()
        time_col = apiInfo["time_col"].iloc[0]
        
        # 擔心一次寫入太多資料sql吃不消，分次執行
        batch_cnt = 500 # 一次跑batch_cnt筆
        
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
        reportCnt = 500
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
            print(row.id, row.證券代號, row.證券名稱)
            print("exeResult=", exeResult, "sql=", sql)
            total_update += exeResult
            
        print("total_update", total_update)
    
    return False

if __name__ == "__main__": 
    handle_notice()