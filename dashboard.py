import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 頁面配置 ---
st.set_page_config(page_title="培玩雲端 ERP WEB V0407.6", layout="wide")

# --- 2. 初始化 ---
@st.cache_resource
def init_connection():
    try: return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except: return None

supabase = init_connection()

# --- 3. 數據處理核心 (V0407.6：絕對保底邏輯) ---
def process_data(df):
    if df is None or df.empty: return pd.DataFrame()
    
    # 全部小寫化
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # 模糊找出品名欄位 (KeyError 救星)
    p_col = next((c for c in df.columns if any(x in c for x in ['p_name', 'product', '品名', '商品'])), None)
    if p_col and p_col != 'p_name': df = df.rename(columns={p_col: 'p_name'})
    
    # 模糊找出時間欄位
    t_col = next((c for c in df.columns if any(x in c for x in ['timestamp', 'time', 'created'])), None)
    if t_col and t_col != 'timestamp': df = df.rename(columns={t_col: 'timestamp'})
    
    # 建立日期與顯示字串 (保證 date_str 一定有值)
    if 'timestamp' in df.columns:
        ts_raw = df['timestamp'].astype(str).str.replace('T', ' ').str.replace('Z', '')
        df['date_str'] = ts_raw.str[:10]
        df['display_time'] = ts_raw.str[:16]
    else:
        df['date_str'] = "1900-01-01"
        df['display_time'] = "無時間紀錄"
        
    return df

# --- 4. 數據抓取 (改用最保險的直接抓取) ---
@st.cache_data(ttl=5)
def fetch_raw_data():
    try:
        # 改用更直接的抓取方式，不加 order 避免排擠
        r1 = supabase.table("order_history").select("*").range(0, 999).execute()
        r2 = supabase.table("order_history").select("*").range(1000, 1999).execute()
        r3 = supabase.table("order_history").select("*").range(2000, 2999).execute()
        raw_o = r1.data + r2.data + r3.data
        raw_p = supabase.table("products").select("*").execute().data
        return pd.DataFrame(raw_p), pd.DataFrame(raw_o)
    except Exception as e:
        st.error(f"資料抓取失敗: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_p_raw, df_o_raw = fetch_raw_data()
df_p = process_data(df_p_raw)
df_o = process_data(df_o_raw)

# --- 5. 主介面 ---
tabs = st.tabs(["📊 數據總覽", "☁️ 庫存狀態", "📦 出貨紀錄明細", "🚚 物流件數登記"])

with tabs[0]:
    st.write(f"### 🚀 系統狀態檢查")
    c1, c2 = st.columns(2)
    c1.metric("成功載入總量 (訂單表)", f"{len(df_o)} 筆")
    c2.metric("成功載入總量 (商品表)", f"{len(df_p)} 筆")
    
    if st.checkbox("🔍 查看原始資料前 5 筆 (診斷用)"):
        st.write(df_o.head())

with tabs[2]:
    st.markdown("### 📦 出貨紀錄明細")
    if df_o.empty:
        st.warning("目前資料庫回傳為空，請檢查 Supabase 連線。")
    else:
        # 移除複雜篩選，先看「不篩選」是否能顯示
        dr = st.date_input("📅 日期範圍", [date(2026, 3, 2), date.today()])
        
        # 關鍵：如果 p_name 不存在，不執行過濾
        if 'p_name' in df_o.columns:
            mask = (~df_o['p_name'].astype(str).str.contains("物流|包裹", na=False))
            # 確保 date_str 比較不會報錯
            if len(dr) == 2:
                s_s, e_s = dr[0].strftime("%Y-%m-%d"), dr[1].strftime("%Y-%m-%d")
                mask &= (df_o['date_str'] >= s_s) & (df_o['date_str'] <= e_s)
            
            res = df_o[mask].sort_values('timestamp', ascending=False)
            st.write(f"篩選後筆數: {len(res)}")
            st.dataframe(res, use_container_width=True)
        else:
            st.error("找不到品名欄位，請檢查資料庫結構。")
            st.write("目前偵測到的欄位有：", list(df_o.columns))

if st.button("🔄 刷新數據", use_container_width=True): st.cache_data.clear(); st.rerun()
