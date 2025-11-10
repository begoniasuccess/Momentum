# -*- coding: utf-8 -*-
"""
time-series punish prediction @ notice events (timestamp-only)
- 單位：每一筆「注意公告」作一次判斷
- 標籤：未來 N 個「交易日」內是否會被處置 (使用 coming_punish_interval_days <= N)
- 特徵：
    * 當次公告：notice_law_count、days_to_next_notice
    * 近 K 次公告（同股票）的滾動統計：law_count_sum/mean/max、gap_days_mean/min、notice_freq_近W交易日
    * 條款 one-hot（從 v_notice_law_src 聚合當次公告涉及的 law_src）
- 分割：嚴格「時間序」切割（訓練在過去，測試在未來）
- 全程只用 *_ts 欄位；不碰字串日期
"""

import os
from datetime import datetime
import numpy as np
import pandas as pd
from common.db import query_to_df
from common import utils
from module.finMind import getTwStockTradingDates

from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance

# -----------------------
# 可調參數
# -----------------------
PUNISH_HORIZON_DAYS = 10
ROLL_K_NOTICE = 3
FREQ_WINDOW_DAYS = 10
TEST_RATIO_BY_TIME = 0.2
OUT_DIR = r"C:/Users/USER/Desktop"

NOTICE_APIS = ["上市公布注意有價證券資訊", "上櫃公布注意有價證券資訊"]
PUNISH_APIS = ["上市公布處置有價證券", "上櫃處置有價證券資訊"]
V_NOTICE_LAW = "v_notice_law_src"


# -----------------------
# 工具：交易日 → timestamp list
# -----------------------
def load_trading_ts() -> list[int]:
    td = getTwStockTradingDates()
    ts = pd.to_datetime(td["date"]).astype("int64") // 10**9
    ts = ts.sort_values().tolist()
    return ts


# -----------------------
# 讀取 notice/punish
# -----------------------
def load_notice_frames():
    frames = []
    for api in NOTICE_APIS:
        info = utils.get_api_info(api)
        table = info["storage_table"].iloc[0]
        time_col = info["time_col"].iloc[0]
        ts_col = f"{time_col}_ts"

        sql = f"""
        SELECT 
            id AS notice_id,
            證券代號 AS stock_no,
            {ts_col} AS notice_ts,
            coming_punish_id,
            coming_punish_interval_days,
            next_notice_dt,
            days_to_next_notice,
            notice_law_count
        FROM {table}
        WHERE {ts_col} IS NOT NULL
        """
        df = query_to_df(sql)
        df["source_table"] = table
        frames.append(df)

    out = pd.concat(frames, ignore_index=True)
    out["notice_ts"] = pd.to_numeric(out["notice_ts"], errors="coerce").astype("Int64")
    out["coming_punish_interval_days"] = pd.to_numeric(out["coming_punish_interval_days"], errors="coerce").astype("Int64")
    out["days_to_next_notice"] = pd.to_numeric(out["days_to_next_notice"], errors="coerce")
    out["notice_law_count"] = pd.to_numeric(out["notice_law_count"], errors="coerce").fillna(0).astype(int)
    return out


def load_law_onehot_for_notice(notice_df: pd.DataFrame) -> pd.DataFrame:
    tables = notice_df["source_table"].dropna().unique().tolist()
    law_dfs = []
    for t in tables:
        v = query_to_df(f"SELECT target_table, target_id, law_src FROM {V_NOTICE_LAW} WHERE target_table='{t}'")
        if v.empty:
            continue
        pivot = (
            v.assign(val=1)
             .pivot_table(index=["target_table", "target_id"], columns="law_src", values="val", aggfunc="max", fill_value=0)
             .reset_index()
        )
        pivot.rename(columns={"target_id": "notice_id"}, inplace=True)
        pivot["notice_id"] = pd.to_numeric(pivot["notice_id"], errors="coerce").astype("Int64")
        law_dfs.append(pivot)
    if not law_dfs:
        return pd.DataFrame(columns=["notice_id"])
    law_all = pd.concat(law_dfs, ignore_index=True)
    cols = [c for c in law_all.columns if c not in ("target_table", "notice_id")]
    law_all = law_all.groupby("notice_id", as_index=False)[cols].max()
    return law_all


# -----------------------
# 建立時間序特徵
# -----------------------
def build_event_features(notice_df: pd.DataFrame) -> pd.DataFrame:
    df = notice_df.copy()
    keep = ["notice_id", "stock_no", "notice_ts", "coming_punish_id", "coming_punish_interval_days",
            "days_to_next_notice", "notice_law_count"]
    df = df[keep].dropna(subset=["notice_ts", "stock_no"]).copy()
    df = df.sort_values(["stock_no", "notice_ts"]).reset_index(drop=True)

    df["prev_notice_ts"] = df.groupby("stock_no")["notice_ts"].shift(1)
    df["gap_days_from_prev"] = ((df["notice_ts"] - df["prev_notice_ts"]) / 86400).fillna(np.nan)

    def roll_stats(g):
        g = g.copy()
        g["roll_law_sum"] = g["notice_law_count"].rolling(ROLL_K_NOTICE, min_periods=1).sum()
        g["roll_law_mean"] = g["notice_law_count"].rolling(ROLL_K_NOTICE, min_periods=1).mean()
        g["roll_law_max"] = g["notice_law_count"].rolling(ROLL_K_NOTICE, min_periods=1).max()
        g["roll_gap_mean"] = g["gap_days_from_prev"].rolling(ROLL_K_NOTICE, min_periods=1).mean()
        g["roll_gap_min"] = g["gap_days_from_prev"].rolling(ROLL_K_NOTICE, min_periods=1).min()
        return g

    df = df.groupby("stock_no", group_keys=False).apply(roll_stats)

    def freq_window(g):
        g = g.copy()
        ts = g["notice_ts"].astype("int64").to_numpy()
        out = []
        j = 0
        win_sec = FREQ_WINDOW_DAYS * 86400
        for i in range(len(ts)):
            t_hi = ts[i]
            t_lo = t_hi - win_sec
            while j < i and ts[j] < t_lo:
                j += 1
            out.append(i - j + 1)
        g["notice_freq_w"] = out
        return g

    df = df.groupby("stock_no", group_keys=False).apply(freq_window)
    df["label_y"] = (pd.to_numeric(df["coming_punish_interval_days"], errors="coerce") <= PUNISH_HORIZON_DAYS).fillna(False).astype(int)
    return df


# -----------------------
# 時序切割
# -----------------------
def time_order_split(df: pd.DataFrame, test_ratio=0.2):
    df = df.sort_values("notice_ts").reset_index(drop=True)
    cut_idx = int(len(df) * (1 - test_ratio))
    return df.iloc[:cut_idx].copy(), df.iloc[cut_idx:].copy()


# -----------------------
# 模型訓練與多門檻評估
# -----------------------
def train_and_eval(train_df: pd.DataFrame, test_df: pd.DataFrame, feature_cols: list[str], thresholds=(0.5, 0.4, 0.3)):
    X_tr, y_tr = train_df[feature_cols], train_df["label_y"].astype(int)
    X_te, y_te = test_df[feature_cols], test_df["label_y"].astype(int)

    clf = HistGradientBoostingClassifier(
        max_depth=4, learning_rate=0.08, max_iter=400, random_state=42, l2_regularization=0.0
    )
    clf.fit(X_tr, y_tr)
    proba = clf.predict_proba(X_te)[:, 1]

    reports = {}
    for thr in thresholds:
        pred = (proba >= thr).astype(int)
        rep = classification_report(y_te, pred, output_dict=True, zero_division=0)
        cm = confusion_matrix(y_te, pred)
        reports[thr] = (rep, cm)
    return clf, proba, reports


# -----------------------
# 特徵重要性分析
# -----------------------
def analyze_feature_importance(model, X_test, y_test, test_df, feature_cols):
    print("🚀 計算 permutation importance ...")
    result = permutation_importance(model, X_test, y_test, n_repeats=10, random_state=42, n_jobs=-1)
    imp_df = pd.DataFrame({
        "feature": feature_cols,
        "importance_mean": result.importances_mean,
        "importance_std": result.importances_std
    }).sort_values("importance_mean", ascending=False)

    stats = []
    for f in feature_cols:
        if f not in test_df.columns: continue
        pos_mean = test_df.loc[test_df["label_y"] == 1, f].mean()
        neg_mean = test_df.loc[test_df["label_y"] == 0, f].mean()
        stats.append((f, pos_mean, neg_mean, pos_mean - neg_mean))

    avg_df = pd.DataFrame(stats, columns=["feature", "mean_pos", "mean_neg", "mean_diff"])
    merged = imp_df.merge(avg_df, on="feature", how="left")
    merged["rank"] = range(1, len(merged) + 1)

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = os.path.join(OUT_DIR, f"feature_importance_detail_{now}.csv")
    merged.to_csv(out_csv, index=False, encoding="utf-8-sig")

    print(f"✅ 已輸出完整報告：{out_csv}")
    print("📊 前10名特徵：")
    print(merged.head(10).to_string(index=False))
    return merged


# -----------------------
# 主流程
# -----------------------
def main():
    print("🚀 準備資料（timestamp-only, event-level）")
    trading_ts = load_trading_ts()
    notice_df = load_notice_frames()
    law_onehot = load_law_onehot_for_notice(notice_df)

    df = notice_df.merge(law_onehot, on="notice_id", how="left")
    law_cols = [c for c in df.columns if c not in (
        "notice_id","stock_no","notice_ts","coming_punish_id","coming_punish_interval_days",
        "next_notice_dt","days_to_next_notice","notice_law_count","source_table")]
    df[law_cols] = df[law_cols].fillna(0).astype(int)

    feat_df = build_event_features(df)
    merged = feat_df.merge(df[["notice_id"] + law_cols], on="notice_id", how="left")
    merged[law_cols] = merged[law_cols].fillna(0).astype(int)

    base_feats = ["notice_law_count","days_to_next_notice","gap_days_from_prev",
                  "roll_law_sum","roll_law_mean","roll_law_max","roll_gap_mean",
                  "roll_gap_min","notice_freq_w"]
    base_feats = [c for c in base_feats if c in merged.columns]
    feat_cols = base_feats + law_cols

    for c in ["days_to_next_notice","gap_days_from_prev","roll_gap_mean","roll_gap_min"]:
        if c in merged.columns:
            fillv = float(merged[c].quantile(0.5)) if merged[c].notna().any() else 0.0
            merged[c] = pd.to_numeric(merged[c], errors="coerce").fillna(fillv)

    train_df, test_df = time_order_split(merged, test_ratio=TEST_RATIO_BY_TIME)
    clf, proba, reports = train_and_eval(train_df, test_df, feat_cols, thresholds=(0.5, 0.4, 0.3))

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_pred = test_df[["notice_id","stock_no","notice_ts","label_y"]].copy()
    out_pred["pred_proba"] = proba
    out_pred.to_csv(os.path.join(OUT_DIR, f"punish_event_test_pred_{now}.csv"), index=False, encoding="utf-8-sig")

    with open(os.path.join(OUT_DIR, f"punish_event_features_{now}.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(feat_cols))
    with open(os.path.join(OUT_DIR, f"punish_event_reports_{now}.txt"), "w", encoding="utf-8") as f:
        for thr, (rep, cm) in reports.items():
            f.write(f"=== threshold={thr} ===\n")
            f.write(pd.DataFrame(rep).round(4).to_string())
            f.write("\nConfusion matrix:\n")
            f.write(np.array2string(cm))
            f.write("\n\n")

    # 🧠 新增：特徵重要性分析
    X_te, y_te = test_df[feat_cols], test_df["label_y"].astype(int)
    analyze_feature_importance(clf, X_te, y_te, test_df, feat_cols)

    print("🎯 全部完成！")


if __name__ == "__main__":
    main()
