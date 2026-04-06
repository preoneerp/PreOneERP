import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 頁面配置 ---
st.set_page_config(page_title="數據診斷模式", layout="wide")

st.title("🔍 數據診斷模式 (無過濾全輸出)")
st.info("此版本不含任何 UI 設計與過濾邏輯，僅用於確認資料庫原始內容。")

# --- 2. 初始化 Supabase ---
@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"連線失敗: {e}")
        return None

supabase = init_connection()

# --- 3. 原始數據處理 ---
def diagnostic_process(df):
    if df is None or df.empty: return pd.DataFrame()
    # 僅做基礎對齊，不做任何刪減
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # 嘗試建立時間欄位供排序，若失敗不影響資料顯示
    t_targets = ['timestamp', 'created_at', 'time', '作成時間']
    t_col = next((c for c in df.columns if c in t_targets), None)
    
    if t_col:
        df['診斷時間軸'] = pd.to_datetime(df[t_col], errors='coerce')
        # 建立一個純日期欄位方便肉眼觀察
        df['資料日期'] = df['診斷時間軸'].dt.date
    
    return df

# --- 4. 數據抓取 (暴力抓取 3000 筆) ---
@st.cache_data(ttl=5)
def fetch_diagnostic_data():
    try:
        # 分段抓取確保突破 1000 筆限制
        r1 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(0, 999).execute()
        r2 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(1000, 1999).execute()
        r3 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(2000, 2999).execute()
        
        combined_data = r1.data + r2.data + r3.data
        return pd.DataFrame(combined_data)
    except Exception as e:
        st.error(f"抓取失敗: {e}")
        return pd.DataFrame()

# --- 5. 執行與顯示 ---
raw_df = fetch_diagnostic_data()
df = diagnostic_process(raw_df)

if not df.empty:
    st.success(f"📈 資料庫回傳總筆數：{len(df)} 筆")
    
    # 診斷指標
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("最新資料日期", str(df['資料日期'].max()) if '資料日期' in df.columns else "未知")
    with col2:
        st.metric("最舊資料日期", str(df['資料日期'].min()) if '資料日期' in df.columns else "未知")
    with col3:
        st.metric("欄位總數", len(df.columns))

    st.write("### 📝 原始資料列表 (前 500 筆)")
    st.caption("提示：請檢查是否存在 3/31 以前的日期，並觀察其 p_name 或 mode 欄位是否為空值。")
    st.dataframe(df, use_container_width=True)
    
    st.write("### 📊 欄位狀態檢查 (查看是否有大量空值)")
    st.write(df.isnull().sum().to_frame(name="空值數量"))

else:
    st.warning("目前抓不到任何資料，請檢查 Supabase 連線或資料表名稱。")

if st.button("🔄 立即重新整理"):
    st.cache_data.clear()
    st.rerun()
