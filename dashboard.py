import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta
import pytz

# --- 1. 頁面配置 ---
st.set_page_config(page_title="培玩雲端 ERP (修復版)", layout="wide")

# --- 2. 初始化 ---
@st.cache_resource
def init_connection():
    try: return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except: return None

supabase = init_connection()

# --- 3. 數據自動處理 (核心修復：確保舊資料一定有時間欄位) ---
def smart_process(df):
    if df is None or df.empty: return pd.DataFrame()
    
    # 統一轉小寫，防止大小寫造成的辨識失敗
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # 【關鍵修復】: 暴力搜尋所有可能的時間欄位名稱
    possible_time_cols = ['timestamp', 'time', 'created_at', '作成時間', '日期']
    t_col = next((c for c in df.columns if c in possible_time_cols), None)
    
    # 如果還是找不到，抓第一個看起來像時間的欄位
    if not t_col:
        for col in df.columns:
            if 'time' in col or 'date' in col:
                t_col = col
                break

    if t_col:
        # 強制轉換，errors='coerce' 會把無法解析的轉為 NaT，我們再用今日補位防止消失
        df['tz_fixed'] = pd.to_datetime(df[t_col], utc=True, errors='coerce')
        # 補丁：如果轉換失敗變成空值，給它一個預設值，防止資料在過濾時消失
        df['tz_fixed'] = df['tz_fixed'].fillna(pd.Timestamp('2024-03-01', tz='UTC'))
        
        df['tz_fixed'] = df['tz_fixed'].dt.tz_convert('Asia/Taipei').dt.tz_localize(None)
        df['pure_date'] = df['tz_fixed'].dt.date
    else:
        # 萬一真的沒時間欄位，強行補上，確保過濾器不會報錯
        df['tz_fixed'] = pd.Timestamp.now()
        df['pure_date'] = date.today()
        
    return df

# --- 4. 登入邏輯 ---
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

if not st.session_state["password_correct"]:
    _, col_mid, _ = st.columns([1, 1, 1])
    with col_mid:
        st.write("<br><br>", unsafe_allow_html=True)
        st.title("🎀 系統登入")
        with st.container(border=True):
            u = st.text_input("帳號")
            p = st.text_input("密碼", type="password")
            if st.button("登入", use_container_width=True):
                auth = st.secrets.get("auth", {})
                if u in auth and str(p) == str(auth[u]["password"]):
                    st.session_state.update({"password_correct": True})
                    st.rerun()
                else: st.error("密碼錯誤")
    st.stop()

# --- 5. 數據抓取 (突破 1000 筆) ---
@st.cache_data(ttl=10)
def fetch_all_data():
    try:
        # 連續抓取 3000 筆
        r1 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(0, 999).execute()
        r2 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(1000, 1999).execute()
        r3 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(2000, 2999).execute()
        raw_o = r1.data + r2.data + r3.data
        raw_p = supabase.table("products").select("*").execute().data
        return pd.DataFrame(raw_p), pd.DataFrame(raw_o)
    except:
        return pd.DataFrame(), pd.DataFrame()

df_p_raw, df_o_raw = fetch_all_data()
df_p = smart_process(df_p_raw)
df_o = smart_process(df_o_raw)

# --- 6. 介面呈現 ---
tabs = st.tabs(["📊 數據總覽", "📦 歷史明細"])

with tabs[0]:
    if not df_o.empty:
        st.metric("目前總資料筆數", len(df_o))
        st.write("資料時間範圍:", df_o['pure_date'].min(), "至", df_o['pure_date'].max())

with tabs[1]:
    if not df_o.empty:
        # 預設範圍拉大，確保 3/31 在裡面
        dr = st.date_input("選擇日期範圍", [date(2024, 3, 1), date.today()])
        if len(dr) == 2:
            mask = (df_o['pure_date'] >= dr[0]) & (df_o['pure_date'] <= dr[1])
            # 關鍵：這裡暫時移除其餘過濾條件，只看日期
            st.dataframe(df_o[mask].sort_values('tz_fixed', ascending=False), use_container_width=True)

    if st.button("🔄 強制刷新"):
        st.cache_data.clear()
        st.rerun()
