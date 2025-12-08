import xgboost as xgb
import pandas as pd
import numpy as np
from common import db

def train_xgb_for_disposal():
    print("=== 讀取資料 ===")
    
    stock_types = ['twse', 'tpex']
    
    ## 事先清空預測欄位
    sql = "UPDATE notice_behavior_feature SET pred_prob_disposal = NULL"
    db.execute_sql(sql)
    
    for type in stock_types:
        print(f"*** 處理type：{type}")
        sql = f"""
            SELECT * FROM v_law1_feature_ana WHERE type = '{type}'
        """
        df = db.query_to_df(sql)

        # 特徵欄位（你可自行加入更多）
        feature_cols = [        
            "acc_notice_cnt"
            "src_close_price",
            "src_pe_ratio",
            "acc_return_pct",
            "a_threshold",
            "price_diff",
            "p_threshold"
        ]

        df = df.dropna(subset=["will_be_disposed_tomorrow"])

        X = df[feature_cols]
        y = df["will_be_disposed_tomorrow"]

        print("訓練樣本數：", len(df), "正樣本：", y.sum())

        # XGBoost DMatrix
        dtrain = xgb.DMatrix(X, label=y)

        params = {
            "objective": "binary:logistic",
            "eta": 0.1,
            "max_depth": 3,
            "subsample": 0.9,
            "colsample_bytree": 0.8,
            "eval_metric": "auc"
        }

        print("=== 開始訓練 XGBoost ===")
        bst = xgb.train(params, dtrain, num_boost_round=200)

        # 特徵重要度
        print("\n=== Feature Importance ===")
        importance = bst.get_score(importance_type="gain")
        importance = sorted(importance.items(), key=lambda x: x[1], reverse=True)
        for f, score in importance:
            print(f"{f}: {score:.4f}")

        # 用 XGBoost 預測並寫回 DB
        print("\n=== 寫回預測結果 pred_prob_disposal ===")
        pred_prob = bst.predict(dtrain)

        df["xgb_pred_prob"] = pred_prob

        for _, row in df[["notice_id", "xgb_pred_prob"]].iterrows():
            db.execute_sql(
                f"UPDATE notice_behavior_feature SET pred_prob_disposal = ? WHERE notice_id = ? AND type = '{type}'",
                (float(row["xgb_pred_prob"]), int(row["notice_id"]))
            )

        print("=== Done ===")


# python -m main.predictDispostion_xgboost
if __name__ == "__main__":
    print("--- RUN main.predictDispostion_xgboost ---")
    train_xgb_for_disposal()
    