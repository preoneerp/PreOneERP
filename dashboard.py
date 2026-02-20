import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(page_title="ERP 庫存報表", layout="wide")
st.title("📊 企業級穩定報表 (API 模式)")

# 初始化 Supabase 客戶端
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_connection()
    
    # 直接抓取資料表內容，這走的是 HTTPS，幾乎不會失敗
    response = supabase.table("products").select("name, stock, vendors(name)").execute()
    
    # 轉換成 DataFrame
    data = response.data
    if data:
        df = pd.json_normalize(data)
        # 整理欄位名稱
        df.columns = ['商品名稱', '庫存數量', '供應商']
        
        st.metric("總品項數", len(df))
        st.dataframe(df, use_container_width=True)
        st.bar_chart(data=df, x="商品名稱", y="庫存數量")
    else:
        st.info("目前資料庫中尚無資料。")

except Exception as e:
    st.error(f"連線失敗：{e}")
