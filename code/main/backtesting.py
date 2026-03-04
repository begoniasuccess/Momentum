from module import finMind as fm
from module import twse, tpex
from common import db
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import sys, os
from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
from xgboost import XGBClassifier

def prepare_v_law1_feature_ana_stock_price():
    sql = """
        SELECT stock_no, notice_date FROM v_law1_feature_ana
        WHERE T1_close IS NULL
        ORDER BY stock_no, notice_date ASC
    """
    df = db.query_to_df(sql)
    
    pre_stock = None
    date_list = []
    for idx, row in df.iterrows():
        if (pre_stock is not None and row["stock_no"] != pre_stock):
            # sql = f"""
            #     DELETE FROM date_span WHERE idx_key = '{pre_stock}' 
            # """
            db.execute_sql(sql)
            fst_dt = datetime.strptime(date_list[0], "%Y-%m-%d")
            last_dt = datetime.strptime(date_list[-1], "%Y-%m-%d") + relativedelta(months=1)
            print(f"get day stock price：{pre_stock} {fst_dt.strftime('%Y-%m-%d')}~{last_dt.strftime('%Y-%m-%d')}")
            df = fm.get_tw_stock_daily_price(pre_stock, fst_dt, last_dt)
            # print(df.head(1), df.tail(1))
                            
            date_list = []
        date_list.append(row["notice_date"])
        pre_stock = row["stock_no"]
    
    # last loop data
    fst_dt = datetime.strptime(date_list[0], "%Y-%m-%d")
    last_dt = datetime.strptime(date_list[-1], "%Y-%m-%d") + relativedelta(months=1)
    print(f"get day stock price：{pre_stock} {fst_dt.strftime('%Y-%m-%d')}~{fst_dt.strftime('%Y-%m-%d')}")
    df = fm.get_tw_stock_daily_price(pre_stock, fst_dt, last_dt)
    

# 確保可以 import common.db
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# =========================================
# 1) 用 SQL 準備 ML 用的資料表
# =========================================

def prepare_ml_tables():
    # ---- T+1 做空樣本表 ----
    db.execute_sql("DROP TABLE IF EXISTS ml_law1_t1_short;")

    sql_short = """
    CREATE TABLE ml_law1_t1_short AS
    SELECT
        feature_id,
        type,
        stock_no,
        notice_date,

        -- 特徵（交易前可見）
        pred_prob_disposal,
        acc_return_pct,
        price_diff,
        src_close_price,
        src_pe_ratio,
        acc_notice_cnt,

        -- 目標：T+1 做空報酬
        T1_short_ret,

        -- 分類用標籤：>0 視為“賺錢”
        CASE
            WHEN T1_short_ret IS NOT NULL AND T1_short_ret > 0
            THEN 1 ELSE 0
        END AS y_short_win

    FROM v_law1_feature_ana_t1_short
    WHERE T1_short_ret IS NOT NULL;
    """
    db.execute_sql(sql_short)

    # ---- T+1 做多樣本表 ----
    db.execute_sql("DROP TABLE IF EXISTS ml_law1_t1_long;")

    sql_long = """
    CREATE TABLE ml_law1_t1_long AS
    SELECT
        feature_id,
        type,
        stock_no,
        notice_date,

        -- 特徵（交易前可見）
        pred_prob_disposal,
        acc_return_pct,
        price_diff,
        src_close_price,
        src_pe_ratio,
        acc_notice_cnt,

        -- 目標：T+1 做多報酬
        T1_long_ret,

        -- 分類用標籤：>0 視為“賺錢”
        CASE
            WHEN T1_long_ret IS NOT NULL AND T1_long_ret > 0
            THEN 1 ELSE 0
        END AS y_long_win

    FROM v_law1_feature_ana_t1_long
    WHERE T1_long_ret IS NOT NULL;
    """
    db.execute_sql(sql_long)

    print("✅ 已建立 ml_law1_t1_short / ml_law1_t1_long")


# =========================================
# 2) 前處理 helper：組 X, y
# =========================================

def prepare_xy_classification(df: pd.DataFrame, target_col: str, drop_cols: list[str]):
    df = df.copy()

    # 類別型欄位 one-hot：目前只有 type
    if "type" in df.columns:
        df = pd.get_dummies(df, columns=["type"], drop_first=True)

    # 一律排除不該當特徵的欄位
    leak_cols = {"T1_short_ret", "T1_long_ret"}  # 防止洩漏
    cols_to_drop = [c for c in drop_cols + [target_col] if c in df.columns]
    cols_to_drop += [c for c in leak_cols if c in df.columns]

    X = df.drop(columns=cols_to_drop)
    y = df[target_col].astype(int)

    return X, y


# =========================================
# 3) XGBoost：對 short / long 各跑一套分類
# =========================================

def run_xgboost_for_short():
    df_short = db.query_to_df("SELECT * FROM ml_law1_t1_short")
    print(f"📊 short rows: {len(df_short)}")

    X_short, y_short = prepare_xy_classification(
        df_short,
        target_col="y_short_win",
        drop_cols=["feature_id", "stock_no", "notice_date"],
    )

    Xtr_s, Xte_s, ytr_s, yte_s = train_test_split(
        X_short,
        y_short,
        test_size=0.3,
        random_state=42,
        stratify=y_short,
    )

    clf_short = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",  # 有 GPU 的話可以改成 'gpu_hist'
        random_state=42,
    )

    clf_short.fit(Xtr_s, ytr_s)

    pred_prob_s = clf_short.predict_proba(Xte_s)[:, 1]
    pred_label_s = (pred_prob_s > 0.5).astype(int)

    print("\n===== T+1 SHORT Strategy (Classification) =====")
    print(classification_report(yte_s, pred_label_s, digits=4))
    try:
        auc_s = roc_auc_score(yte_s, pred_prob_s)
        print("ROC AUC:", auc_s)
    except ValueError:
        print("ROC AUC 無法計算（可能是測試集只有單一類別）")

    fi_short = (
        pd.Series(clf_short.feature_importances_, index=X_short.columns)
        .sort_values(ascending=False)
    )
    print("\nTop features for SHORT:")
    print(fi_short.head(20))

    return clf_short, fi_short


def run_xgboost_for_long():
    df_long = db.query_to_df("SELECT * FROM ml_law1_t1_long")
    print(f"📊 long rows: {len(df_long)}")

    X_long, y_long = prepare_xy_classification(
        df_long,
        target_col="y_long_win",
        drop_cols=["feature_id", "stock_no", "notice_date"],
    )

    Xtr_l, Xte_l, ytr_l, yte_l = train_test_split(
        X_long,
        y_long,
        test_size=0.3,
        random_state=42,
        stratify=y_long,
    )

    clf_long = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        random_state=42,
    )

    clf_long.fit(Xtr_l, ytr_l)

    pred_prob_l = clf_long.predict_proba(Xte_l)[:, 1]
    pred_label_l = (pred_prob_l > 0.5).astype(int)

    print("\n===== T+1 LONG Strategy (Classification) =====")
    print(classification_report(yte_l, pred_label_l, digits=4))
    try:
        auc_l = roc_auc_score(yte_l, pred_prob_l)
        print("ROC AUC:", auc_l)
    except ValueError:
        print("ROC AUC 無法計算（可能是測試集只有單一類別）")

    fi_long = (
        pd.Series(clf_long.feature_importances_, index=X_long.columns)
        .sort_values(ascending=False)
    )
    print("\nTop features for LONG:")
    print(fi_long.head(20))

    return clf_long, fi_long


# =========================================
# 4) main
# =========================================

# python -m main.backtesting
if __name__ == "__main__":
    sDt = datetime(2011, 1, 1)
    eDt = datetime(2026, 1, 1)
    # df = twse.get_notice(sDt, eDt)
    # print(df.head(5))
    # df = twse.get_punish(sDt, eDt)
    # print(df.head(5))
    # df = tpex.get_notice(sDt, eDt)
    # print(df.head(5))
    df = tpex.get_punish(sDt, eDt)
    print(df.head(5))