import streamlit as st
import pandas as pd
import psycopg2

# --- 1. 連線設定 (從 Streamlit Secrets 讀取) ---
def get_connection():
    # 這些資訊我們待會會設定在 Streamlit Cloud 的後台
    return psycopg2.connect(
        host=st.secrets["DB_HOST"],
        database=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        port=st.secrets["DB_PORT"]
    )

st.set_page_config(page_title="ERP 庫存報表系統", layout="wide")
st.title("📊 雲端庫存即時報表")

# --- 2. 讀取資料 ---
try:
    conn = get_connection()
    
    # 讀取商品與供應商資料 (SQL 語法與 SQLite 略有不同)
    query = """
    SELECT p.name AS 商品名稱, p.stock AS 庫存數量, v.name AS 供應商
    FROM products p
    LEFT JOIN vendors v ON p.v_id = v.id
    """
    df = pd.read_sql(query, conn)
    conn.close()

    # --- 3. 報表呈現 ---
    # 數據統計資訊
    col1, col2 = st.columns(2)
    with col1:
        st.metric("總品項數", len(df))
    with col2:
        st.metric("低庫存警示 (<5)", len(df[df['庫存數量'] < 5]))

    st.divider()

    # 顯示表格
    st.subheader("📦 目前庫存清單")
    st.dataframe(df, use_container_width=True)

    # 簡單圖表
    st.subheader("📈 庫存分佈圖")
    st.bar_chart(data=df, x="商品名稱", y="庫存數量")

except Exception as e:
    st.error(f"❌ 無法連線至雲端資料庫：{e}")
