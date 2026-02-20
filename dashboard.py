import streamlit as st
import pandas as pd
import psycopg2

st.set_page_config(page_title="ERP 庫存報表", layout="wide")
st.title("📊 東京機房 - 直連報表")

def get_connection():
    return psycopg2.connect(
        host=st.secrets["DB_HOST"],
        database=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        port=st.secrets["DB_PORT"],
        connect_timeout=20
    )

try:
    with st.spinner('連線中...'):
        conn = get_connection()
        query = "SELECT p.name AS 商品名稱, p.stock AS 庫存數量, v.name AS 供應商 FROM products p LEFT JOIN vendors v ON p.v_id = v.id ORDER BY p.stock ASC;"
        df = pd.read_sql(query, conn)
        conn.close()

    st.success("✅ 連線成功！")
    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error("❌ 連線失敗")
    st.info(f"錯誤訊息：{e}")
