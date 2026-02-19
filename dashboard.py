import streamlit as st
import pandas as pd
import psycopg2

# --- 1. 頁面設定 ---
st.set_page_config(
    page_title="ERP 庫存即時報表",
    page_icon="📊",
    layout="wide"
)

st.title("📊 雲端庫存即時報表系統")
st.markdown("---")

# --- 2. 資料庫連線函數 ---
def get_connection():
    # 這裡會從 Streamlit Cloud 的 Secrets 讀取對應參數
    return psycopg2.connect(
        host=st.secrets["DB_HOST"],
        database=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        port=st.secrets["DB_PORT"],
        connect_timeout=10
    )

# --- 3. 讀取資料與顯示 ---
try:
    with st.spinner('正在從雲端資料庫抓取最新庫存...'):
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

    # --- 4. 頂部儀表板統計 ---
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("總品項數", len(df))
    
    with col2:
        low_stock_count = len(df[df['庫存數量'] < 5])
        st.metric("低庫存警示 (<5)", low_stock_count, delta=-low_stock_count, delta_color="inverse")
        
    with col3:
        total_stock = df['庫存數量'].sum()
        st.metric("總庫存總量", int(total_stock))

    st.markdown("### 📦 即時庫存清單")
    
    # 使用資料表格顯示，並加上搜尋功能
    st.dataframe(
        df, 
        use_container_width=True,
        column_config={
            "庫存數量": st.column_config.NumberColumn(format="%d 🛠️")
        }
    )

    # --- 5. 視覺化圖表 ---
    st.markdown("---")
    st.subheader("📈 庫存分佈分析")
    
    if not df.empty:
        # 簡單的橫向長條圖
        st.bar_chart(data=df, x="商品名稱", y="庫存數量")
    else:
        st.warning("目前資料庫中沒有商品資料。")

except Exception as e:
    st.error("❌ 無法連線至雲端資料庫")
    st.info(f"錯誤詳情: {e}")
    st.warning("請檢查 Streamlit Cloud 的 Secrets 設定是否包含正確的 DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT")
