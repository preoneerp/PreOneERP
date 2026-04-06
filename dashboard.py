import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 頁面配置與視覺設計 ---
st.set_page_config(page_title="培玩雲端 ERP", layout="wide", initial_sidebar_state="expanded")

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
    .product-tag {
        background: #ffffff; border: 1px solid #eee; border-radius: 12px;
        padding: 15px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .product-name {
        font-size: 0.95rem; color: #5D6D7E; margin-bottom: 5px; font-weight: 500;
        height: 2.5rem; display: flex; align-items: center; justify-content: center;
    }
    .product-qty { font-size: 2.2rem; font-weight: 800; color: #E67E22; }
    .product-unit { font-size: 0.8rem; color: #ABB2B9; margin-left: 3px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 初始化 ---
@st.cache_resource
def init_connection():
    try: return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except: return None

supabase = init_connection()

# --- 3. 數據處理 (終極防禦：暴力對齊所有欄位) ---
def smart_process(df):
    if df is None or df.empty: return pd.DataFrame()
    
    # 1. 強制全部小寫化
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # 2. 暴力掃描關鍵欄位 (解決 KeyError)
    rename_map = {}
    for col in df.columns:
        if any(x in col for x in ['p_name', 'product', '品名', '商品']): rename_map[col] = 'p_name'
        if any(x in col for x in ['qty', 'quantity', '數量', '件數']): rename_map[col] = 'quantity'
        if any(x in col for x in ['timestamp', 'time', 'created', '時間']): rename_map[col] = 'timestamp'
        if any(x in col for x in ['vendor', '供應']): rename_map[col] = 'vendor'
        if any(x in col for x in ['logistics', '物流']): rename_map[col] = 'logistics'
    
    df = df.rename(columns=rename_map)
    
    # 3. 補齊缺失欄位，防止後續代碼報錯
    must_have = ['p_name', 'quantity', 'timestamp', 'platform', 'mode', 'logistics', 'vendor']
    for m in must_have:
        if m not in df.columns: df[m] = "-"
    
    # 4. 時間解析與日期生成
    df['dt_raw'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df['pure_date'] = df['dt_raw'].dt.date
    
    # 5. 補全字串並清理空值
    for col in must_have:
        df[col] = df[col].astype(str).str.strip().replace(['nan', 'None', ''], '-')
    
    return df

# --- 4. 登入 ---
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

if not st.session_state["password_correct"]:
    _, col_mid, _ = st.columns([1.2, 1, 1.2])
    with col_mid:
        st.write("<br><br>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; color: #E8A0BF;'>🎀 雲端管理系統</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            u = st.text_input("帳號"); p = st.text_input("密碼", type="password")
            if st.button("登入系統", use_container_width=True):
                auth = st.secrets.get("auth", {})
                if u in auth and str(p) == str(auth[u]["password"]):
                    st.session_state.update({"password_correct": True})
                    st.rerun()
                else: st.error("🔒 密碼不正確")
    st.stop()

# --- 5. 數據抓取 (確保 3000 筆物理量) ---
@st.cache_data(ttl=5)
def fetch_all_data():
    try:
        r1 = supabase.table("order_history").select("*").range(0, 999).execute()
        r2 = supabase.table("order_history").select("*").range(1000, 1999).execute()
        r3 = supabase.table("order_history").select("*").range(2000, 2999).execute()
        raw_o = r1.data + r2.data + r3.data
        raw_p = supabase.table("products").select("*").execute().data
        return pd.DataFrame(raw_p), pd.DataFrame(raw_o)
    except: return pd.DataFrame(), pd.DataFrame()

df_p_raw, df_o_raw = fetch_all_data()
df_p, df_o = smart_process(df_p_raw), smart_process(df_o_raw)

# --- 6. 主介面 ---
tabs = st.tabs(["📊 數據總覽", "☁️ 庫存狀態", "📦 出貨紀錄明細", "🚚 物流件數登記"])

with tabs[0]:
    today = date.today()
    today_o = df_o[df_o['pure_date'] == today] if not df_o.empty else pd.DataFrame()
    st.markdown(f"### 🎯 今日統計 ({today})")
    target_prods = [{"name": "專注力訓練機", "search": "舒爾特專注力訓練機"},{"name": "24點數感大作戰", "search": "24點數感邏輯大作戰"},{"name": "顯微鏡相機", "search": "顯微鏡相機"},{"name": "創意卷軸畫", "search": "滾動創意卷軸畫"},{"name": "攜行盒-藍", "search": "攜行盒-藍"},{"name": "攜行盒-粉", "search": "攜行盒-粉"}]
    prod_cols = st.columns(6)
    
    # 確保不會因為沒資料而崩潰
    df_items_only = today_o[~today_o['p_name'].str.contains("物流|包裹", na=False)] if not today_o.empty else pd.DataFrame()
    for i, item in enumerate(target_prods):
        with prod_cols[i]:
            qty = int(pd.to_numeric(df_items_only[df_items_only['p_name'].str.contains(item['search'], na=False)]['quantity'], errors='coerce').sum()) if not df_items_only.empty else 0
            st.markdown(f'<div class="product-tag"><div class="product-name">{item["name"]}</div><div class="product-qty">{qty}<span class="product-unit">個</span></div></div>', unsafe_allow_html=True)
    
    st.write("<br>", unsafe_allow_html=True)
    df_ship_all = df_o[df_o['p_name'].str.contains("物流|包裹", na=False)]
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.markdown(f'<div class="metric-card"><div class="metric-label">今日出貨包裹</div><div class="metric-value">{int(pd.to_numeric(df_ship_all[df_ship_all["pure_date"]==today]["quantity"], errors="coerce").sum())} 件</div></div>', unsafe_allow_html=True)
    with m2: st.metric("總載入筆數", f"{len(df_o)} 筆")
    with m3: st.markdown(f'<div class="metric-card"><div class="metric-label">今日訂單明細</div><div class="metric-value">{len(df_items_only)} 筆</div></div>', unsafe_allow_html=True)
    with m4: st.markdown(f'<div class="metric-card"><div class="metric-label">低庫存(診斷)</div><div class="metric-value">{len(df_p)} 項</div></div>', unsafe_allow_html=True)

with tabs[1]:
    if not df_p.empty:
        st.dataframe(df_p[['name', 'stock', 'vendor']], use_container_width=True, hide_index=True)

with tabs[2]:
    if not df_o.empty:
        dr = st.date_input("📅 日期篩選", [])
        mask = (~df_o['p_name'].str.contains("物流|包裹", na=False))
        if len(dr) == 2:
            mask &= (df_o['pure_date'].fillna(date(2000,1,1)) >= dr[0]) & (df_o['pure_date'].fillna(date(2099,12,31)) <= dr[1])
        st.dataframe(df_o[mask].sort_values('dt_raw', ascending=False, na_position='last')[['timestamp', 'p_name', 'quantity', 'mode', 'platform']], use_container_width=True, hide_index=True)

with tabs[3]:
    df_entry = df_o[df_o['p_name'].str.contains("物流|包裹", na=False)]
    st.dataframe(df_entry[['timestamp', 'platform', 'logistics', 'quantity']], use_container_width=True, hide_index=True)

    if st.button("🔄 刷新雲端數據", use_container_width=True): st.cache_data.clear(); st.rerun()
