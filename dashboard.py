import streamlit as st
import pandas as pd
import psycopg2
import urllib.parse

st.set_page_config(page_title="ERP 庫存報表", layout="wide")
st.title("📊 雲端 ERP 即時報表 (東京連線)")

def get_connection():
    # 使用 URL 編碼密碼，防止特殊字元導致報錯
    encoded_pw = urllib.parse.quote_plus(st.secrets["DB_PASSWORD"])
    
    # 組合連線字串 (使用 Transaction Pooler 的域名通常較穩定)
    # 這裡我們強迫指定 sslmode=require
    conn_str = f"postgresql://postgres:{encoded_pw}@{st.secrets['DB_HOST']}:{st.secrets['DB_PORT']}/postgres?sslmode=require"
    
    return psycopg2.connect(conn_str)

try:
    with st.spinner('正在建立安全連線...'):
        conn = get_connection()
        query = "SELECT p.name AS 商品名稱, p.stock AS 庫存數量, v.name AS 供應商 FROM products p LEFT JOIN vendors v ON p.v_id = v.id ORDER BY p.stock ASC;"
        df = pd.read_sql(query, conn)
        conn.close()

    st.metric("總品項數", len(df))
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        st.bar_chart(data=df, x="商品名稱", y="庫存數量")

except Exception as e:
    st.error("❌ 連線嘗試失敗")
    st.info(f"技術錯誤：{e}")
