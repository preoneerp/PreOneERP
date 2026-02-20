import streamlit as st
import pandas as pd
import psycopg2
import socket

st.set_page_config(page_title="ERP 庫存報表", layout="wide")
st.title("📊 東京機房 - 即時庫存報表")

def get_connection():
    # --- 關鍵修正：強制將網址解析為 IPv4 ---
    host = st.secrets["DB_HOST"]
    port = st.secrets["DB_PORT"]
    
    try:
        # 這裡會強迫解析出 13.115.x.x 這種 IPv4 格式
        resolved_ip = socket.getaddrinfo(host, port, socket.AF_INET)[0][4][0]
    except Exception:
        resolved_ip = host # 萬一解析失敗則用原網址
    
    return psycopg2.connect(
        host=resolved_ip,
        database=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        port=port,
        connect_timeout=15
    )

try:
    with st.spinner('正在與東京機房連線中...'):
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

    # 顯示表格與圖表
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        st.bar_chart(data=df, x="商品名稱", y="庫存數量")

except Exception as e:
    st.error(f"❌ 網頁連線資料庫失敗")
    st.info(f"技術細節：{e}")
