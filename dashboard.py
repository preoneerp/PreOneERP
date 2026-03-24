import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 初始化與配置 ---
st.set_page_config(page_title="培玩雲端 ERP", layout="wide")

@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

# --- 2. 數據抓取 (確保最新) ---
@st.cache_data(ttl=30)
def fetch_all_data():
    try:
        # 關鍵：按 id 倒序，抓取最新 10,000 筆，徹底解決資料遺失問題
        res_o = supabase.table("order_history").select("*").order("id", desc=True).limit(10000).execute()
        res_p = supabase.table("products").select("*").execute()
        return pd.DataFrame(res_p.data), pd.DataFrame(res_o.data)
    except Exception as e:
        st.error(f"連線失敗: {e}")
        return pd.DataFrame(), pd.DataFrame()

# --- 3. 數據處理 ---
def smart_process(df):
    if df is None or df.empty: return pd.DataFrame()
    df.columns = [str(c).strip().lower() for c in df.columns]
    for col in df.select_dtypes(['object']).columns:
        df[col] = df[col].astype(str).str.strip()
    
    t_col = next((c for c in df.columns if any(k in c for k in ['timestamp', 'time', 'created_at'])), None)
    if t_col:
        df['tz_fixed'] = pd.to_datetime(df[t_col], utc=True).dt.tz_convert('Asia/Taipei').dt.tz_localize(None)
        df['pure_date'] = df['tz_fixed'].dt.date
    return df

raw_p, raw_o = fetch_all_data()
df_p = smart_process(raw_p)
df_o = smart_process(raw_o)

# --- 4. 介面呈現 ---
tabs = st.tabs(["📊 數據總覽", "📦 出貨紀錄明細"])

with tabs[0]:
    today = date.today()
    today_o = df_o[df_o['pure_date'] == today]
    
    st.markdown(f"### 🎯 今日出貨統計 ({today})")
    
    # 定義要追蹤的商品 (search 使用包含字樣即可)
    targets = [
        {"name": "專注力訓練機", "search": "舒爾特專注力訓練機"},
        {"name": "24點數感大作戰", "search": "24點數感邏輯大作戰"},
        {"name": "顯微鏡相機", "search": "顯微鏡相機"},
        {"name": "創意卷軸畫", "search": "滾動創意卷軸畫"},
        {"name": "攜行盒-藍", "search": "攜行盒-藍"},
        {"name": "攜行盒-粉", "search": "攜行盒-粉"}
    ]
    
    # 僅計算 mode 包含 "出貨" 且 p_name 不是 "物流登記" 的商品
    df_items = today_o[(today_o['mode'].str.contains("出貨", na=False)) & (today_o['p_name'] != "物流登記")]
    
    cols = st.columns(6)
    for i, item in enumerate(targets):
        with cols[i]:
            qty = int(df_items[df_items['p_name'].str.contains(item['search'], na=False)]['quantity'].sum())
            st.metric(item['name'], f"{qty} 個")

    st.write("---")
    # 物流總量 (兼容 物流登記 或 物流統計)
    df_ship = today_o[(today_o['p_name'] == "物流登記") | (today_o['mode'] == "物流統計")]
    st.metric("今日出貨包裹總量", f"{int(df_ship['quantity'].sum())} 件")
    if not df_ship.empty:
        st.dataframe(df_ship.groupby('logistics')['quantity'].sum().reset_index(name='件數'), use_container_width=True, hide_index=True)

with tabs[1]:
    st.markdown("### 📋 完整出貨明細")
    sel_date = st.date_input("選擇日期", today)
    final_df = df_o[df_o['pure_date'] == sel_date]
    st.dataframe(final_df.sort_values('id', ascending=False), use_container_width=True, hide_index=True)

if st.button("🔄 立即刷新"):
    st.cache_data.clear()
    st.rerun()
