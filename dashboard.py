import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import date, datetime

st.set_page_config(page_title="排查 4：修復版本", layout="wide")

# 1. 連線
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# 2. 抓取 (分段抓取確保抓到 3000 筆)
@st.cache_data(ttl=5)
def fetch_data():
    r1 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(0, 999).execute()
    r2 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(1000, 1999).execute()
    r3 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(2000, 2999).execute()
    return pd.DataFrame(r1.data + r2.data + r3.data)

df = fetch_data()

# 3. 核心修正：防彈時間轉換邏輯
df.columns = [str(c).lower().strip() for c in df.columns]

# --- 這裡是最關鍵的修正點 ---
# 使用 errors='coerce' 避免報錯，並強制處理時區
df['tz_fixed'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
# 將無法解析的 NaT 先補上一個遠古日期，確保篩選時不會直接消失，或讓用戶知道格式壞了
df['pure_date'] = df['tz_fixed'].dt.tz_convert('Asia/Taipei').dt.tz_localize(None).dt.date

# 4. 介面篩選
st.write(f"當前載入總筆數：{len(df)}")
dr = st.date_input("選擇日期範圍", [date(2026, 3, 1), date.today()])

if len(dr) == 2:
    # 修正篩選邏輯：處理 NaT (空時間)，不讓它們在比較時被濾掉
    # 我們讓 pure_date 為空的資料預設為「通過篩選」，這樣你才能在列表看到它們並知道要補資料
    mask = (df['pure_date'].fillna(date(2000, 1, 1)) >= dr[0]) & \
           (df['pure_date'].fillna(date(2099, 12, 31)) <= dr[1])
    
    df_final = df[mask]
    
    st.write(f"📊 篩選後筆數：{len(df_final)}")
    st.write("### 檢查下方列表是否有 3/31 以前的資料：")
    # 顯示時間欄位來對照
    st.dataframe(df_final[['timestamp', 'pure_date', 'p_name', 'quantity']], use_container_width=True)

    # 統計壞掉的日期筆數
    bad_dates = df['pure_date'].isna().sum()
    if bad_dates > 0:
        st.warning(f"⚠️ 注意：有 {bad_dates} 筆資料的時間格式毀損，已強行顯示在列表中。")
