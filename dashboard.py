import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 配置 ---
st.set_page_config(page_title="培玩雲端 ERP - 終極診斷版", layout="wide")

# --- 2. 初始化 ---
@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except: return None

supabase = init_connection()

# --- 3. 暴力數據處理 (確保資料不因格式錯誤而消失) ---
def smart_process(df):
    if df is None or df.empty: return pd.DataFrame()
    
    # 欄位標準化
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    # 文字去空格
    for col in df.select_dtypes(['object']).columns:
        df[col] = df[col].astype(str).str.strip()
    
    # 尋找時間欄位
    t_col = next((c for c in df.columns if any(k in c for k in ['timestamp', 'time', 'created_at'])), None)
    
    if t_col:
        # 【暴力解析】使用 errors='coerce'，若解析失敗會變 NaT，但資料列會保留
        df['dt_object'] = pd.to_datetime(df[t_col], errors='coerce', utc=True)
        
        # 處理解析失敗的情況 (給予一個預設日期，防止資料消失)
        df['dt_object'] = df['dt_object'].fillna(pd.Timestamp.now(tz='UTC'))
        
        # 轉台北時間
        df['tz_fixed'] = df['dt_object'].dt.tz_convert('Asia/Taipei').dt.tz_localize(None)
        df['pure_date'] = df['tz_fixed'].dt.date
    else:
        df['pure_date'] = date.today()
        df['tz_fixed'] = datetime.now()
        
    return df

# --- 4. 數據抓取 ---
@st.cache_data(ttl=5) # 縮短至 5 秒
def fetch_data():
    try:
        res = supabase.table("order_history").select("*").execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"連線異常: {e}")
        return pd.DataFrame()

raw_df = fetch_data()
df_o = smart_process(raw_df)

# --- 5. 主介面 ---
st.title("🧪 數據診斷實驗室")

if not df_o.empty:
    # 這裡提供一個「不設日期過濾」的原始檢查表
    st.subheader("🛠️ 全量原始數據清單 (不限日期)")
    st.info(f"目前資料庫中共有 {len(df_o)} 筆資料。")
    
    # 增加一個搜尋功能，直接搜 ID 或 物流名稱
    search_q = st.text_input("🔍 快速搜尋 (可輸入 '新竹' 或 '3559')", "")
    
    if search_q:
        # 全表模糊搜尋
        search_mask = df_o.astype(str).apply(lambda x: x.str.contains(search_q)).any(axis=1)
        search_result = df_o[search_mask]
        st.write(f"搜尋結果：{len(search_result)} 筆")
        st.dataframe(search_result, use_container_width=True)
    else:
        # 顯示最近 50 筆
        st.dataframe(df_o.sort_values('tz_fixed', ascending=False).head(50), use_container_width=True)

    st.write("---")
    st.subheader("📅 日期過濾測試")
    today = date.today()
    sel_date = st.date_input("選擇測試日期", today)
    
    filtered = df_o[df_o['pure_date'] == sel_date]
    st.write(f"該日期共有 {len(filtered)} 筆資料")
    st.dataframe(filtered, use_container_width=True)

else:
    st.error("目前雲端資料庫無回傳資料。")

if st.button("🔄 強制重整"):
    st.cache_data.clear()
    st.rerun()
