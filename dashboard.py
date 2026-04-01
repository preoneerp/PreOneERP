import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta
import pytz

# --- 1. 頁面配置與視覺設計 ---
st.set_page_config(page_title="培玩雲端 ERP (數據偵測版)", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stApp { background-color: #FDFBFA; }
    .metric-card {
        background: white; padding: 20px; border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05); border-left: 5px solid #E8A0BF;
        text-align: left; margin-bottom: 10px;
    }
    .metric-value { font-size: 1.8rem; font-weight: bold; color: #2C3E50; }
    .metric-label { color: #7F8C8D; font-size: 0.9rem; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 初始化 Supabase ---
@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except:
        return None

supabase = init_connection()

# --- 3. 數據處理工具 (偵測版關鍵邏輯) ---
def smart_process(df):
    if df is None or df.empty: return pd.DataFrame()
    # 關鍵：強制小寫化，解決 3/31 前後 DB 欄位大小寫不一的問題
    df.columns = [str(c).lower().strip() for c in df.columns]
    for col in df.select_dtypes(['object']).columns:
        df[col] = df[col].astype(str).str.strip().replace('nan', '')
    
    # 寬鬆匹配時間欄位
    t_col = next((c for c in df.columns if c in ['timestamp', 'time', 'created_at']), None)
    if t_col:
        df['tz_fixed'] = pd.to_datetime(df[t_col], utc=True, errors='coerce')
        df['tz_fixed'] = df['tz_fixed'].dt.tz_convert('Asia/Taipei').dt.tz_localize(None)
        df['pure_date'] = df['tz_fixed'].dt.date
    return df

# --- 4. 登入邏輯 ---
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

if not st.session_state["password_correct"]:
    _, col_mid, _ = st.columns([1.2, 1, 1.2])
    with col_mid:
        st.write("<br><br>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; color: #E8A0BF;'>🎀 雲端管理系統</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            u = st.text_input("帳號")
            p = st.text_input("密碼", type="password")
            if st.button("登入系統", use_container_width=True):
                auth = st.secrets.get("auth", {})
                if u in auth and str(p) == str(auth[u]["password"]):
                    st.session_state.update({"password_correct": True, "user_level": auth[u]["level"], "current_user": u})
                    st.rerun()
                else: st.error("🔒 帳號或密碼不正確")
    st.stop()

# --- 5. 數據抓取 (翻頁讀取突破 1000 筆限制) ---
@st.cache_data(ttl=10)
def fetch_all_data():
    try:
        # 分三次抓取，確保抓到 3000 筆，找回消失的 3/31 前資料
        r1 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(0, 999).execute()
        r2 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(1000, 1999).execute()
        r3 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(2000, 2999).execute()
        all_data = r1.data + r2.data + r3.data
        res_p = supabase.table("products").select("*").execute()
        return pd.DataFrame(res_p.data), pd.DataFrame(all_data)
    except Exception as e:
        st.error(f"讀取異常: {e}")
        return pd.DataFrame(), pd.DataFrame()

raw_p, raw_o = fetch_all_data()
df_p = smart_process(raw_p)
df_o = smart_process(raw_o)

# --- 6. 主介面設計 ---
tabs = st.tabs(["📊 全數據偵測", "☁️ 庫存狀態", "📦 歷史明細 (無過濾)", "🚚 物流統計"])

# --- TAB 0: 數據診斷 ---
with tabs[0]:
    if not df_o.empty:
        st.success(f"✅ 成功讀取資料庫筆數：{len(df_o)} 筆")
        st.write("最新一筆時間：", df_o['tz_fixed'].max())
        st.write("最舊一筆時間：", df_o['tz_fixed'].min())
        
    m1, m2 = st.columns(2)
    with m1:
        st.markdown('<div class="metric-card"><div class="metric-label">目前抓取上限</div><div class="metric-value">3,000 筆</div></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">低庫存警戒</div><div class="metric-value">{len(df_p[df_p["stock"] < 10]) if not df_p.empty else 0} 項</div></div>', unsafe_allow_html=True)

# --- TAB 1: 庫存狀態 ---
with tabs[1]:
    if not df_p.empty:
        st.dataframe(df_p, use_container_width=True)

# --- TAB 2: 歷史明細 (無過濾版) ---
with tabs[2]:
    if not df_o.empty:
        dr = st.date_input("📅 選擇日期範圍", [date.today() - timedelta(days=60), date.today()])
        start_d, end_d = (dr[0], dr[1]) if len(dr) > 1 else (dr[0], dr[0])
        # 偵測版關鍵：不設任何 mode 或 p_name 過濾，只要日期對就顯示
        mask = (df_o['pure_date'] >= start_d) & (df_o['pure_date'] <= end_d)
        st.dataframe(df_o[mask].sort_values('tz_fixed', ascending=False), use_container_width=True)

# --- TAB 3: 物流統計 ---
with tabs[3]:
    if not df_o.empty:
        # 只要包含「物流」或「包裹」關鍵字的通通列出來
        df_logi = df_o[df_o['p_name'].str.contains("物流|包裹", na=False)]
        st.dataframe(df_logi, use_container_width=True)

    if st.button("🔄 刷新雲端數據"):
        st.cache_data.clear()
        st.rerun()
