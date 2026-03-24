import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 基本配置 ---
st.set_page_config(page_title="培玩雲端 ERP - 原始觀測版", layout="wide")

# --- 2. 初始化 ---
@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except:
        return None

supabase = init_connection()

# --- 3. 極簡化數據處理 (僅做時區，不做過濾) ---
def smart_process(df):
    if df is None or df.empty: return pd.DataFrame()
    df.columns = [str(c).strip().lower() for c in df.columns]
    # 全欄位去空格，防止字串比對失敗
    for col in df.select_dtypes(['object']).columns:
        df[col] = df[col].astype(str).str.strip()
    
    t_col = next((c for c in df.columns if any(k in c for k in ['timestamp', 'time', 'created_at'])), None)
    if t_col:
        df['tz_fixed'] = pd.to_datetime(df[t_col], utc=True).dt.tz_convert('Asia/Taipei').dt.tz_localize(None)
        df['pure_date'] = df['tz_fixed'].dt.date
    return df

# --- 4. 數據抓取 (暫存縮短至 10 秒以利推理) ---
@st.cache_data(ttl=10)
def fetch_data():
    res_o = supabase.table("order_history").select("*").execute()
    return pd.DataFrame(res_o.data)

df_o = smart_process(fetch_data())

# --- 5. 主介面 ---
st.title("📊 數據原始觀測中心")
st.info("此版本已移除所有排除邏輯，僅顯示原始資料庫內容以供推理。")

if not df_o.empty:
    today = date.today()
    
    # 頂部簡單指標
    c1, c2 = st.columns(2)
    c1.metric("資料庫總筆數", len(df_o))
    c2.metric("今日資料筆數", len(df_o[df_o['pure_date'] == today]))

    st.write("---")
    
    # 篩選區
    sc1, sc2 = st.columns(2)
    sel_date = sc1.date_input("📅 選擇日期", [today, today])
    sel_plt = sc2.selectbox("📱 平台", ["全部"] + sorted(list(df_o['platform'].unique())))

    # 執行過濾 (僅做基本的日期與平台過濾)
    start_d, end_d = (sel_date[0], sel_date[1]) if len(sel_date) > 1 else (sel_date[0], sel_date[0])
    mask = (df_o['pure_date'] >= start_d) & (df_o['pure_date'] <= end_d)
    if sel_plt != "全部":
        mask &= (df_o['platform'] == sel_plt)
    
    display_df = df_o[mask].sort_values('tz_fixed', ascending=False)
    
    # 顯示完整表格 (包含 p_name, mode, platform, logistics)
    st.markdown("### 📋 歷史明細 (包含物流與商品)")
    st.dataframe(display_df, use_container_width=True)

else:
    st.error("❌ 無法從 Supabase 取得資料，請檢查 RLS 或連線。")

if st.button("🔄 立即強制重新整理"):
    st.cache_data.clear()
    st.rerun()
