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

# --- 3. 數據預處理 (解決 3/31 前 None 的核心邏輯) ---
def smart_process(df):
    if df is None or df.empty: return pd.DataFrame()
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # 彈性時間解析
    if 'timestamp' in df.columns:
        # 第一步：嘗試標準轉換
        df['tz_fixed'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
        # 第二步：如果還有 None (NaT)，嘗試不指定時區的轉換 (處理地端舊格式)
        mask_nat = df['tz_fixed'].isna()
        if mask_nat.any():
            df.loc[mask_nat, 'tz_fixed'] = pd.to_datetime(df.loc[mask_nat, 'timestamp'], errors='coerce')
        
        # 統一轉為台北時間並提取日期
        df['tz_fixed'] = df['tz_fixed'].dt.tz_localize(None) # 移除時區屬性以便比較
        df['pure_date'] = df['tz_fixed'].dt.date
    
    # 字串補位與數值轉換
    for col in ['p_name', 'mode', 'platform', 'logistics', 'vendor']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace(['nan', 'None', ''], '-')
    if 'quantity' in df.columns:
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
    if 'stock' in df.columns:
        df['stock'] = pd.to_numeric(df['stock'], errors='coerce').fillna(0)
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
                else: st.error("🔒 密碼錯誤")
    st.stop()

# --- 5. 數據抓取 (保持 3000 筆分段) ---
@st.cache_data(ttl=5)
def fetch_all_data():
    try:
        r1 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(0, 999).execute()
        r2 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(1000, 1999).execute()
        r3 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(2000, 2999).execute()
        return pd.DataFrame(supabase.table("products").select("*").execute().data), pd.DataFrame(r1.data + r2.data + r3.data)
    except: return pd.DataFrame(), pd.DataFrame()

df_p_raw, df_o_raw = fetch_all_data()
df_p, df_o = smart_process(df_p_raw), smart_process(df_o_raw)

# --- 6. 主介面 ---
tabs = st.tabs(["📊 數據總覽", "☁️ 庫存狀態", "📦 出貨紀錄明細", "🚚 物流件數登記"])

with tabs[0]:
    today = date.today()
    this_month = today.replace(day=1)
    today_o = df_o[df_o['pure_date'] == today] if not df_o.empty else pd.DataFrame()
    st.markdown(f"### 🎯 今日統計 ({today})")
    target_prods = [{"name": "專注力訓練機", "search": "舒爾特專注力訓練機"},{"name": "24點數感大作戰", "search": "24點數感邏輯大作戰"},{"name": "顯微鏡相機", "search": "顯微鏡相機"},{"name": "創意卷軸畫", "search": "滾動創意卷軸畫"},{"name": "攜行盒-藍", "search": "攜行盒-藍"},{"name": "攜行盒-粉", "search": "攜行盒-粉"}]
    prod_cols = st.columns(6)
    df_items_only = today_o[~today_o['p_name'].str.contains("物流|包裹", na=False)] if not today_o.empty else pd.DataFrame()
    for i, item in enumerate(target_prods):
        with prod_cols[i]:
            qty = int(df_items_only[df_items_only['p_name'].str.contains(item['search'], na=False)]['quantity'].sum()) if not df_items_only.empty else 0
            st.markdown(f'<div class="product-tag"><div class="product-name">{item["name"]}</div><div class="product-qty">{qty}<span class="product-unit">個</span></div></div>', unsafe_allow_html=True)
    
    st.write("<br>", unsafe_allow_html=True)
    df_ship_all = df_o[df_o['p_name'].str.contains("物流|包裹", na=False)] if not df_o.empty else pd.DataFrame()
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.markdown(f'<div class="metric-card"><div class="metric-label">今日出貨包裹</div><div class="metric-value">{int(df_ship_all[df_ship_all["pure_date"]==today]["quantity"].sum())} 件</div></div>', unsafe_allow_html=True)
    with m2: st.markdown(f'<div class="metric-card"><div class="metric-label">本月累計包裹</div><div class="metric-value">{int(df_ship_all[df_ship_all["pure_date"]>=this_month]["quantity"].sum())} 件</div></div>', unsafe_allow_html=True)
    with m3: st.markdown(f'<div class="metric-card"><div class="metric-label">今日訂單明細</div><div class="metric-value">{len(df_items_only)} 筆</div></div>', unsafe_allow_html=True)
    with m4: st.markdown(f'<div class="metric-card"><div class="metric-label">低庫存警戒</div><div class="metric-value" style="color:red">{len(df_p[df_p["stock"] < 10]) if not df_p.empty else 0} 項</div></div>', unsafe_allow_html=True)

with tabs[1]:
    if not df_p.empty:
        sel_v = st.selectbox("🔍 供應商篩選", ["✨ 全部"] + sorted(list(df_p['vendor'].unique())))
        f_df_p = df_p if sel_v == "✨ 全部" else df_p[df_p['vendor'] == sel_v]
        st.dataframe(f_df_p[['name', 'stock', 'vendor']], use_container_width=True, hide_index=True)

with tabs[2]:
    if not df_o.empty:
        dr = st.date_input("📅 日期範圍", [date(2026, 3, 1), today])
        if len(dr) == 2:
            # 關鍵修正：fillna(date.min) 讓 None 也能通過篩選被看見
            mask = (df_o['pure_date'].fillna(date(2000,1,1)) >= dr[0]) & (df_o['pure_date'].fillna(date(2099,12,31)) <= dr[1])
            mask &= (~df_o['p_name'].str.contains("物流|包裹", na=False))
            st.dataframe(df_o[mask].sort_values('tz_fixed', ascending=False)[['tz_fixed', 'p_name', 'quantity', 'mode', 'platform', 'logistics']], use_container_width=True, hide_index=True)

with tabs[3]:
    if not df_o.empty:
        l_dr = st.date_input("📅 物流查詢日期", [date(2026, 3, 1), today])
        if len(l_dr) == 2:
            df_entry = df_o[df_o['p_name'].str.contains("物流|包裹", na=False)]
            e_mask = (df_entry['pure_date'].fillna(date(2000,1,1)) >= l_dr[0]) & (df_entry['pure_date'].fillna(date(2099,12,31)) <= l_dr[1])
            st.markdown(f'<div style="background:#E67E22; color:white; padding:15px; border-radius:15px; text-align:center; margin-bottom:20px">總計: {int(df_entry[e_mask]["quantity"].sum())} 件</div>', unsafe_allow_html=True)
            st.dataframe(df_entry[e_mask][['tz_fixed', 'platform', 'logistics', 'quantity']], use_container_width=True, hide_index=True)

    if st.button("🔄 刷新數據", use_container_width=True): st.cache_data.clear(); st.rerun()
