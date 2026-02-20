import streamlit as st
import pandas as pd
from supabase import create_client

# 頁面配置
st.set_page_config(page_title="ERP 綜合管理系統", layout="wide")

@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

# --- 分頁功能 ---
tab1, tab2 = st.tabs(["📦 庫存概況", "🚚 已出貨訂單"])

# --- Tab 1: 庫存概況 (原本的功能) ---
with tab1:
    st.header("即時庫存明細")
    res_p = supabase.table("products").select("name, stock, vendors(name)").execute()
    if res_p.data:
        df_p = pd.json_normalize(res_p.data)
        df_p.columns = ['商品名稱', '庫存數量', '供應商']
        st.dataframe(df_p, use_container_width=True)
    else:
        st.info("尚無庫存資料")

# --- Tab 2: 已出貨訂單 ---
with tab2:
    st.header("已出貨訂單紀錄")
    
    # 從 Supabase 抓取訂單，並關聯商品名稱
    # 注意：這裡假設你在 orders 表有設 product_id 關聯 products
    res_o = supabase.table("orders").select("order_number, customer_name, quantity, shipped_at, products(name)").execute()
    
    if res_o.data:
        df_o = pd.json_normalize(res_o.data)
        
        # 整理欄位名稱
        df_o = df_o[['order_number', 'products.name', 'quantity', 'customer_name', 'shipped_at']]
        df_o.columns = ['訂單編號', '商品名稱', '出貨數量', '客戶名稱', '出貨時間']
        
        # 轉換時間格式（讓閱讀更友善）
        df_o['出貨時間'] = pd.to_datetime(df_o['出貨時間']).dt.strftime('%Y-%m-%d %H:%M')

        # 顯示指標
        c1, c2 = st.columns(2)
        c1.metric("累計出貨訂單", len(df_o))
        c2.metric("總出貨件數", int(df_o['出貨數量'].sum()))

        # 顯示表格
        st.dataframe(df_o, use_container_width=True, hide_index=True)
        
        # 簡易趨勢圖 (按日期統計出貨量)
        st.subheader("出貨趨勢")
        df_o['日期'] = pd.to_datetime(df_o['出貨時間']).dt.date
        trend_df = df_o.groupby('日期')['出貨數量'].sum().reset_index()
        st.line_chart(data=trend_df, x="日期", y="出貨數量")
        
    else:
        st.warning("目前還沒有任何出貨紀錄。")
