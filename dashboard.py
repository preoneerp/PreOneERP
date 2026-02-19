import streamlit as st
import pandas as pd
import psycopg2
import socket

# 頁面基本設定
st.set_page_config(page_title="ERP 庫存報表", layout="wide")
st.title("📊 雲端庫存即時報表")

# 連線函數：強制解析 IPv4 避開 IPv6 錯誤
def get_connection():
    host = st.secrets["DB_HOST"]
    port = st.secrets["DB_PORT"]
    # 強制解析網址為 IPv4 數字地址
    ipv4 = socket.getaddrinfo(host, port, socket.AF_INET)[0][4][0]
    return psycopg2.connect(
        host=ipv4,
        database=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        port=port,
        connect_timeout=15
    )

# 執行讀取
try:
    with st.spinner('抓取資料中...'):
        conn = get_connection()
        query = "SELECT p.name, p.stock, v.name as vendor FROM products p LEFT JOIN vendors v ON p.v_id = v.id ORDER BY p.stock ASC"
        df = pd.read_sql(query, conn)
        conn.close()

    # 顯示數據
    if not df.empty:
        df.columns = ["商品名稱", "庫存數量", "供應商"]
        st.metric("總品項數", len(df))
        st.dataframe(df, use_container_width=True)
        st.bar_chart(data=df, x="商品名稱", y="庫存數量")
    else:
        st.warning("資料庫目前是空的。")

except Exception as e:
    st.error(f"連線失敗: {e}")
