import pandas as pd
from datetime import datetime
from common.db import query_to_df, get_connection
from common import utils
from module import finMind

def add_notice_punish_to_db(
    punish_apiNames=["上市公布處置有價證券", "上櫃處置有價證券資訊"],
    notice_apiNames=["上市公布注意有價證券資訊", "上櫃公布注意有價證券資訊"]
):
    print("🚀 開始更新 notice-punish 關聯特徵（timestamp版）")

    trading_dates = finMind.getTwStockTradingDates()
    trading_dates["ts"] = pd.to_datetime(trading_dates["date"]).astype("int64") // 10**9
    trading_ts = trading_dates["ts"].tolist()

    for i, apiName in enumerate(notice_apiNames):
        apiInfo = utils.get_api_info(apiName)
        notice_table = apiInfo["storage_table"].iloc[0]
        time_col = apiInfo["time_col"].iloc[0]
        ts_col = time_col + "_ts"
        type_ = apiInfo["type"].iloc[0].lower()

        punish_info = utils.get_api_info(punish_apiNames[i])
        punish_table = punish_info["storage_table"].iloc[0]
        punish_time_col = punish_info["time_col"].iloc[0]
        punish_ts_col = punish_time_col + "_ts"

        print(f"📘 {type_.upper()}：{notice_table} ⇄ {punish_table}")

        punish_df = query_to_df(f"""
            SELECT id AS punish_id, 證券代號 AS stock_no, {punish_ts_col} AS punish_ts
            FROM {punish_table}
            WHERE {punish_ts_col} IS NOT NULL
        """)
        notice_df = query_to_df(f"""
            SELECT id AS notice_id, 證券代號 AS stock_no, {ts_col} AS notice_ts
            FROM {notice_table}
            WHERE {ts_col} IS NOT NULL
        """)

        # 🧩 關鍵修正：確保 timestamp 為整數
        punish_df["punish_ts"] = pd.to_numeric(punish_df["punish_ts"], errors="coerce").astype("Int64")
        notice_df["notice_ts"] = pd.to_numeric(notice_df["notice_ts"], errors="coerce").astype("Int64")

        updates = []
        for stock, n_group in notice_df.groupby("stock_no"):
            p_group = punish_df[punish_df["stock_no"] == stock]
            if p_group.empty:
                continue
            for _, n_row in n_group.iterrows():
                n_ts = n_row["notice_ts"]
                future_punish = p_group[p_group["punish_ts"] > n_ts]
                if future_punish.empty:
                    continue
                nearest_punish = future_punish["punish_ts"].min()
                punish_id = int(future_punish.loc[future_punish["punish_ts"] == nearest_punish, "punish_id"].iloc[0])
                tdays = [t for t in trading_ts if n_ts < t <= nearest_punish]
                coming_interval = len(tdays)
                updates.append((punish_id, coming_interval, n_row["notice_id"]))

        if updates:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.executemany(f"""
                    UPDATE {notice_table}
                    SET coming_punish_id = ?,
                        coming_punish_interval_days = ?
                    WHERE id = ?
                """, updates)
                conn.commit()
                print(f"✅ 更新 {len(updates)} 筆 → {notice_table}.coming_punish_*")

        # === 下一公告間距 ===
        notice_df = notice_df.sort_values(["stock_no", "notice_ts"])
        notice_df["next_notice_ts"] = notice_df.groupby("stock_no")["notice_ts"].shift(-1)

        # 🧩 關鍵修正：安全轉換 timestamp，處理 None / NaN
        notice_df["next_notice_ts"] = pd.to_numeric(notice_df["next_notice_ts"], errors="coerce").astype("Int64")
        notice_df["days_to_next_notice"] = (
            (notice_df["next_notice_ts"] - notice_df["notice_ts"]) / 86400
        ).round().astype("Int64")

        next_updates = []
        for _, r in notice_df.iterrows():
            if pd.isna(r["next_notice_ts"]):
                continue
            next_dt = pd.to_datetime(int(r["next_notice_ts"]), unit="s").strftime("%Y-%m-%d")
            days_gap = int(r["days_to_next_notice"])
            next_updates.append((next_dt, days_gap, r["notice_id"]))

        if next_updates:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.executemany(f"""
                    UPDATE {notice_table}
                    SET next_notice_dt = ?,
                        days_to_next_notice = ?
                    WHERE id = ?
                """, next_updates)
                conn.commit()
                print(f"✅ 更新 {len(next_updates)} 筆 → {notice_table}.next_notice_*")

    print("🎯 全部完成（timestamp 版）")
    
def update_notice_law_features(
    notice_apiNames=["上市公布注意有價證券資訊", "上櫃公布注意有價證券資訊"],
    v_table="v_notice_law_src",
    repeat_days=3
):
    """
    🚀 根據 v_notice_law_src 更新 notice_law_count 與 same_law_repeat_3d
    - notice_law_count：公告涉及的條款數量
    - same_law_repeat_3d：過去 N 個交易日內是否出現相同條款
    """
    print("🚀 開始更新 law 特徵：notice_law_count, same_law_repeat_3d")

    trading_days = pd.to_datetime(finMind.getTwStockTradingDates()["date"]).tolist()
    trading_days = sorted(trading_days)

    for apiName in notice_apiNames:
        apiInfo = utils.get_api_info(apiName)
        notice_table = apiInfo["storage_table"].iloc[0]
        time_col = apiInfo["time_col"].iloc[0]
        type_ = apiInfo["type"].iloc[0].lower()

        print(f"📘 {type_.upper()} → {notice_table}")

        # === 1️⃣ 讀取公告日期與ID ===
        notice_df = query_to_df(f"""
            SELECT id AS notice_id, 證券代號 AS stock_no, {time_col} AS notice_date
            FROM {notice_table}
        """)
        notice_df["notice_date"] = pd.to_datetime(notice_df["notice_date"], errors="coerce")

        # === 2️⃣ 讀取 v_notice_law_src ===
        v_df = query_to_df(f"""
            SELECT target_table, target_id, law_src
            FROM {v_table}
            WHERE target_table = '{notice_table}'
        """)
        v_df.rename(columns={"target_id": "notice_id"}, inplace=True)

        # === 3️⃣ 計算 notice_law_count ===
        law_count_df = v_df.groupby("notice_id")["law_src"].nunique().reset_index()
        law_count_df.rename(columns={"law_src": "notice_law_count"}, inplace=True)

        # === 4️⃣ 計算 same_law_repeat_3d ===
        merged = pd.merge(notice_df, v_df, on="notice_id", how="left")
        merged = merged.dropna(subset=["law_src"])
        merged = merged.sort_values(["stock_no", "law_src", "notice_date"])

        repeat_flags = []
        for stock, g_stock in merged.groupby("stock_no"):
            for law, g_law in g_stock.groupby("law_src"):
                dates = sorted(g_law["notice_date"].unique())
                for i, d in enumerate(dates):
                    prev_dates = [x for x in trading_days if (x < d) and (x >= d - pd.Timedelta(days=30))]
                    # 篩出前 N 個交易日（實際天數往前取 repeat_days 個交易日）
                    idx = [i for i, td in enumerate(trading_days) if td == d]
                    if len(idx) == 0:
                        continue
                    i_td = idx[0]
                    window = trading_days[max(0, i_td - repeat_days):i_td]
                    has_repeat = any(x in window for x in dates[:i])
                    notice_ids = g_law[g_law["notice_date"] == d]["notice_id"].unique().tolist()
                    for nid in notice_ids:
                        repeat_flags.append((nid, 1 if has_repeat else 0))

        repeat_df = pd.DataFrame(repeat_flags, columns=["notice_id", "same_law_repeat_3d"])
        repeat_df = repeat_df.groupby("notice_id")["same_law_repeat_3d"].max().reset_index()

        # === 5️⃣ 合併並寫回 ===
        result_df = pd.merge(law_count_df, repeat_df, on="notice_id", how="outer").fillna(0)
        updates = [(int(r.notice_law_count), int(r.same_law_repeat_3d), int(r.notice_id)) for _, r in result_df.iterrows()]

        if updates:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.executemany(f"""
                    UPDATE {notice_table}
                    SET notice_law_count = ?, same_law_repeat_3d = ?
                    WHERE id = ?
                """, updates)
                conn.commit()
                print(f"✅ 更新 {len(updates)} 筆 → {notice_table}.law_features")

    print("🎯 全部完成")
    
if __name__ == "__main__": 
    add_notice_punish_to_db()
    # update_notice_law_features()