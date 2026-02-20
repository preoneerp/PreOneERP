import streamlit as st
import pandas as pd
import psycopg2
import socket

st.set_page_config(page_title="ERP 庫存報表", layout="wide")
st.title("📊 雲端 ERP 即時報表 (東京連線)")

def get_connection():
    host = st.secrets["DB_HOST"]
    port = st.secrets["DB_PORT"]
    
    # 【核心修正】強迫解析為 IPv4
    try:
        # 將網址翻譯成 13.x.x.x 這種 IPv4 格式
        resolved_ip = socket.getaddrinfo(host, port, socket.AF_INET)[0][4][0]
    except Exception:
        resolved_ip = host

    return psycopg2.connect(
        host=resolved_ip,
        database=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        port=port,
        connect_timeout=20
    )

try:
    with st.spinner('正在與東京機房握手中...'):
        conn = get_connection()
        query = """
        SELECT p.name AS 商品名稱, p.stock AS 庫存數量, v.name AS 供應商
        FROM products p
        LEFT JOIN vendors v ON p.v_id = v.id
        ORDER BY p.stock ASC;
        """
        df = pd.read_sql(query, conn)
        conn.close()

    st.success("✅ 連線成功！")
    st.metric("總品項數", len(df))
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        st.bar_chart(data=df, x="商品名稱", y="庫存數量")

except Exception as e:
    st.error("❌ 連線依然受阻")
    st.info(f"最新錯誤訊息：{e}")
