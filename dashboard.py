import streamlit as st
import pandas as pd
from supabase import create_client

# --- 頁面配置 ---
st.set_page_config(page_title="ERP 雲端管理系統", layout="wide")

# --- 初始化連線 ---
@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

# --- 自定義 CSS ---
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 28px; color: #1E88E5; }
    .low-stock { color: #D32F2F; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 資料讀取函數 ---
def get_products():
    res = supabase.table("products").select("name, stock, vendors(name)").execute()
    if res.data:
        df = pd.json_normalize(res.data)
        df.columns = ['商品名稱', '庫存數量', '供應商']
        return df
    return pd.DataFrame()

def get_orders():
    res = supabase.table("orders").select("order_number, customer_name, quantity, platform, logistics, shipped_at, products(name)").execute()
    if res.data:
        df = pd.json_normalize(res.data)
        df.columns = ['訂單編號', '客戶名稱', '出貨數量', '平台', '物流', '出貨時間', '商品名稱']
        return df
    return pd.DataFrame()

# --- 主程式 ---
st.title("🚀 ERP 雲端戰情室")

tab1, tab2 = st.tabs(["📦 即時庫存概況", "🚚 已出貨訂單"])

# --- Tab 1: 即時庫存概況 ---
with tab1:
    df_p = get_products()
    if not df_p.empty:
        # 側邊欄篩選: 供應商
        vendors = ["全部"] + sorted(df_p['供應商'].unique().tolist())
        sel_vendor = st.sidebar.selectbox("📦 篩選供應商", vendors)
        
        # 側邊欄設定: 低庫存門檻
        threshold = st.sidebar.number_input("⚠️ 低庫存警示門檻", value=10, min_value=0)

        # 執行篩選
        if sel_vendor != "全部":
            df_p = df_p[df_p['供應商'] == sel_vendor]

        # 顯示指標
        low_stock_list = df_p[df_p['庫存數量'] <= threshold]
        c1, c2 = st.columns(2)
        c1.metric("當前篩選品項", len(df_p))
        c2.metric("低庫存預警", len(low_stock_list), delta=f"低於 {threshold}", delta_color="inverse")

        # 警告通知
        if not low_stock_list.empty:
            st.error(f"🚨 注意：以下商品庫存低於 {threshold} 件！")
            st.dataframe(low_stock_list, use_container_width=True, hide_index=True)
        else:
            st.success("✅ 目前所有品項庫存水位正常")

        st.subheader("完整庫存清單")
        st.dataframe(df_p.style.highlight_between(left=0, right=threshold, subset=['庫存數量'], color='#FFEBEE'), use_container_width=True)
    else:
        st.info("尚無庫存資料。")

# --- Tab 2: 已出貨訂單 ---
with tab2:
    df_o = get_orders()
    if not df_o.empty:
        col_f1, col_f2 = st.columns(2)
        
        # 篩選控制項
        platforms = ["全部"] + sorted(df_o['平台'].unique().astype(str).tolist())
        logistics_list = ["全部"] + sorted(df_o['物流'].unique().astype(str).tolist())
        
        with col_f1:
            sel_platform = st.selectbox("🛒 篩選出貨平台", platforms)
        with col_f2:
            sel_logistics = st.selectbox("🚛 篩選物流方式", logistics_list)

        # 執行篩選
        filtered_o = df_o.copy()
        if sel_platform != "全部":
            filtered_o = filtered_o[filtered_o['平台'] == sel_platform]
        if sel_logistics != "全部":
            filtered_o = filtered_o[filtered_o['物流'] == sel_logistics]

        # 顯示統計
        st.metric("顯示訂單總數", len(filtered_o))
        
        # 顯示清單
        st.subheader("出貨明細紀錄")
        st.dataframe(filtered_o, use_container_width=True, hide_index=True)
    else:
        st.info("尚無訂單資料。")
