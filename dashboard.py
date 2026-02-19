import streamlit as st
import pandas as pd
import psycopg2
import socket

# --- 1. 頁面設定 ---
st.set_page_config(
    page_title="ERP 庫存即時報表",
    page_icon="📊",
    layout="wide"
)

st.title("📊 雲端庫存即時報表系統")
st.markdown("---")

# --- 2. 強制 IPv4 連線函數 ---
def get_connection():
    try:
        # 關鍵點：強制將 Host 解析為 IPv4，避開 Streamlit Cloud 的 IPv6 錯誤
        host = st.secrets["DB_HOST"]
        port = st.secrets["DB_PORT"]
        
        # 取得該網址的所有 IP 資訊，並只篩選 IPv4 (AF_INET)
        addr_info = socket.getaddrinfo(host, port, socket.AF_INET)
        ipv4_address = addr_info[0][4][0]
        
        return psycopg2.connect(
            host=ipv4_address,
            database=st.secrets["DB_NAME"],
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASSWORD"],
            port=port,
            connect_timeout=15
        )
    except Exception as e:
        # 如果 IPv4 解析失敗，嘗試直接連線
        return psycopg2.connect(
            host=st.secrets["DB_HOST"],
            database=st.secrets["DB_NAME"],
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASSWORD"],
            port=st.secrets["DB_PORT"],
            connect_timeout=15
        )

# --- 3. 讀取資料與顯示 ---
try:
    with st.spinner('正在同步雲端庫存數據...'):
        conn = get_connection()
        
        # SQL 語法：聯集商品與供應商名稱
        query = """
        SELECT 
            p.name AS "商品名稱", 
            p.stock AS "庫存數量", 
            v.name AS "供應商"
        FROM products p
        LEFT JOIN vendors v ON p.v_id = v.id
        ORDER BY p.stock ASC;
        """
        
        df = pd.read_sql(query, conn)
        conn.close()

    # --- 4. 頂部統計指標 ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("總品項數", len(df))
    with col2:
        low_stock = len(df[df['庫存數量'] < 5])
        st.metric("低庫存警示 (<5)", low_stock)
    with col3:
        st.metric("庫存總量", int(df['庫存數量'].sum()) if not df.empty else 0)

    st.markdown("### 📦 目前庫存清單")
    st.dataframe(df, use_container_width=True)

    # --- 5. 圖表分析 ---
    if not df.empty:
        st.markdown("---")
        st.subheader("📈 庫存分佈圖")
        st.bar_chart(data=df, x="商品名稱", y="庫存數量")

except Exception as e:
    st.error("❌ 雲端資料庫連線失敗")
    st.info(f"技術錯誤訊息
