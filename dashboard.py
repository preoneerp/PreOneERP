import streamlit as st
import pandas as pd
from supabase import create_client

# 頁面配置
st.set_page_config(page_title="ERP 庫存管理系統", layout="wide", initial_sidebar_state="expanded")

# 自定義 CSS 美化
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def fetch_data():
    supabase = init_connection()
    # 抓取資料並關聯供應商名稱
    response = supabase.table("products").select("name, stock, vendors(name)").execute()
    data = response.data
    if data:
        # 扁平化 JSON 資料
        df = pd.json_normalize(data)
        df.columns = ['商品名稱', '庫存數量', '供應商']
        return df
    return pd.DataFrame()

# --- 側邊欄篩選 ---
st.sidebar.header("🛠️ 篩選控制台")
df = fetch_data()

if not df.empty:
    all_vendors = ["全部"] + sorted(df['供應商'].unique().tolist())
    selected_vendor = st.sidebar.selectbox("選擇供應商", all_vendors)
    
    # 庫存預警門檻
    low_stock_threshold = st.sidebar.slider("低庫存預警門檻", 0, 50, 10)

    # 根據篩選器過濾資料
    display_df = df.copy()
    if selected_vendor != "全部":
        display_df = display_df[display_df['供應商'] == selected_vendor]

    # --- 主介面 ---
    st.title("📊 東京機房 - 即時庫存儀表板")
    
    # 1. 頂部 KPI 指標
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("品項總數", len(display_df))
    with col2:
        st.metric("當前總庫存", int(display_df['庫存數量'].sum()))
    with col3:
        low_stock_count = len(display_df[display_df['庫存數量'] <= low_stock_threshold])
        st.metric("低庫存警示", low_stock_count, delta_color="inverse")

    st.divider()

    # 2. 圖表分析
    c1, c2 = st.columns([6, 4])
    with c1:
        st.subheader("📦 庫存分布圖")
        st.bar_chart(data=display_df, x="商品名稱", y="庫存數量", color="#29b5e8")
    
    with c2:
        st.subheader("⚠️ 低庫存清單")
        warning_df = display_df[display_df['庫存數量'] <= low_stock_threshold].sort_values('庫存數量')
        if not warning_df.empty:
            st.warning(f"以下 {len(warning_df)} 項商品庫存不足！")
            st.table(warning_df)
        else:
            st.success("目前庫存充足")

    # 3. 詳細資料表格 (具備搜尋功能)
    st.subheader("📑 詳細資料明細")
    search_query = st.text_input("搜尋商品關鍵字...")
    if search_query:
        display_df = display_df[display_df['商品名稱'].str.contains(search_query, case=False)]
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)

else:
    st.error("暫無資料，請確認資料庫中已有內容。")
