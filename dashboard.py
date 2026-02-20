import streamlit as st
import pandas as pd
import psycopg2

st.set_page_config(page_title="ERP 庫存報表", layout="wide")
st.title("📊 東京機房 - 即時庫存報表")

# 建立連線函數
def get_connection():
    return psycopg2.connect(
        host=st.secrets["DB_HOST"],
        database=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        port=st.secrets["DB_PORT"]
    )

try:
    with st.spinner('正在從東京抓取最新庫存...'):
        conn = get_connection()
        query = """
        SELECT p.name AS 商品名稱, p.stock AS 庫存數量, v.name AS 供應商
        FROM products p
        LEFT JOIN vendors v ON p.v_id = v.id
        ORDER BY p.stock ASC;
        """
        df = pd.read_sql(query, conn)
        conn.close()

    # 顯示指標
    col1, col2 = st.columns(2)
    with col1:
        st.metric("總品項數", len(df))
    with col2:
        st.metric("庫存總量", int(df['庫存數量'].sum()) if not df.empty else 0)

    # 顯示表格
    st.dataframe(df, use_container_width=True)
    
    # 顯示圖表
    if not df.empty:
        st.bar_chart(data=df, x="商品名稱", y="庫存數量")

except Exception as e:
    st.error(f"❌ 網頁連線資料庫失敗：{e}")
