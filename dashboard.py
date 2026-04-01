import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta
import pytz

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

# --- 3. 數據自動處理 (核心：類型強制對齊) ---
def smart_process(df):
    if df is None or df.empty: return pd.DataFrame()
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # 暴力搜尋時間欄位
    t_targets = ['timestamp', 'created_at', 'time', '作成時間', '日期']
    t_col = next((c for c in df.columns if c in t_targets), None)
    if not t_col:
        for col in df.columns:
            if 'time' in col or 'date' in col: t_col = col; break

    if t_col:
        # 強制轉換時間戳並校準時區
        df['tz_fixed'] = pd.to_datetime(df[t_col], errors='coerce', utc=True)
        df['tz_fixed'] = df['tz_fixed'].dt.tz_convert('Asia/Taipei').dt.tz_localize(None)
        # 關鍵：強制將 pure_date 轉為 DatetimeIndex 格式的日期，避免 TypeError 比較錯誤
        df['pure_date'] = pd.to_datetime(df['tz_fixed']).dt.date
    
    # 強制將 object 欄位補空，防止 Mask 運算遇到 NaN 崩潰
    str_cols = ['p_name', 'mode', 'platform', 'logistics', 'vendor']
    for col in str_cols:
        if col not in df.columns: df[col] = ""
        df[col] = df[col].astype(str).str.strip().replace(['nan', 'None', 'None', ''], '')
        
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
            u = st.text_input("帳號"); p = st.text_input("密碼", type="password")
            if st.button("登入系統", use_container_width=True):
                auth = st.secrets.get("auth", {})
                if u in auth and str(p) == str(auth[u]["password"]):
                    st.session_state.update({"password_correct": True, "user_level": auth[u].get("level")})
                    st.rerun()
                else: st.error("🔒 密碼不正確")
    st.stop()

# --- 5. 數據抓取 (保持 3000 筆翻頁) ---
@st.cache_data(ttl=10)
def fetch_all_data():
    try:
        r1 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(0, 999).execute()
        r2 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(1000, 1999).execute()
        r3 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(2000, 2999).execute()
        return pd.DataFrame(supabase.table("products").select("*").execute().data), pd.DataFrame(r1.data + r2.data + r3.data)
    except: return pd.DataFrame(), pd.DataFrame()

raw_p, raw_o = fetch_all_data()
df_p, df_o = smart_process(raw_p), smart_process(raw_o)

# --- 6. 主介面 ---
tabs = st.tabs(["📊 數據總覽", "☁️ 庫存狀態", "📦 出貨紀錄明細", "🚚 物流件數登記"])

with tabs[0]:
    today = date.today()
    today_o = df_o[df_o['pure_date'] == today] if not df_o.empty else pd.DataFrame()
    st.markdown(f"### 🎯 今日統計 ({today})")
    target_prods = [{"name": "專注力訓練機", "search": "舒爾特專注力訓練機"},{"name": "24點數感大作戰", "search": "24點數感邏輯大作戰"},{"name": "顯微鏡相機", "search": "顯微鏡相機"},{"name": "創意卷軸畫", "search": "滾動創意卷軸畫"},{"name": "攜行盒-藍", "search": "攜行盒-藍"},{"name": "攜行盒-粉", "search": "攜行盒-粉"}]
    prod_cols = st.columns(6)
    df_items_only = today_o[~today_o['p_name'].str.contains("物流|包裹", na=False)] if not today_o.empty else pd.DataFrame()
    for i, item in enumerate(target_prods):
        with prod_cols[i]:
            # 強制數值轉換，避免舊資料 quantity 為字串導致 sum() 失敗
            qty = int(pd.to_numeric(df_items_only[df_items_only['p_name'].str.contains(item['search'], na=False)]['quantity'], errors='coerce').sum()) if not df_items_only.empty else 0
            st.markdown(f'<div class="product-tag"><div class="product-name">{item["name"]}</div><div class="product-qty">{qty}<span class="product-unit">個</span></div></div>', unsafe_allow_html=True)
    
    st.write("<br>", unsafe_allow_html=True)
    df_ship_all = df_o[df_o['p_name'].str.contains("物流|包裹", na=False)] if not df_o.empty else pd.DataFrame()
    # 確保指標計算不崩潰
    today_pkgs = pd.to_numeric(df_ship_all[df_ship_all['pure_date'] == today]['quantity'], errors='coerce').sum() if not df_ship_all.empty else 0
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.markdown(f'<div class="metric-card"><div class="metric-label">今日出貨包裹</div><div class="metric-value">{int(today_pkgs)} 件</div></div>', unsafe_allow_html=True)
    with m3: st.markdown(f'<div class="metric-card"><div class="metric-label">今日明細筆數</div><div class="metric-value">{len(df_items_only)} 筆</div></div>', unsafe_allow_html=True)
    with m4: st.markdown(f'<div class="metric-card"><div class="metric-label">低庫存警戒</div><div class="metric-value" style="color:red">{len(df_p[pd.to_numeric(df_p["stock"], errors="coerce") < 10]) if not df_p.empty else 0} 項</div></div>', unsafe_allow_html=True)
    
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("#### 🚚 今日物流分佈")
        today_ship = df_ship_all[df_ship_all['pure_date'] == today] if not df_ship_all.empty else pd.DataFrame()
        if not today_ship.empty:
            st.dataframe(today_ship.groupby('logistics')['quantity'].sum().reset_index(), use_container_width=True, hide_index=True)
        else: st.info("無物流數據")
    with col_r:
        st.markdown("#### 📉 包裹趨勢圖")
        if not df_ship_all.empty:
            st.line_chart(df_ship_all.groupby('pure_date')['quantity'].sum(), use_container_width=True)

with tabs[1]:
    if not df_p.empty:
        sel_v = st.selectbox("🔍 供應商篩選", ["✨ 全部"] + sorted(list(df_p['vendor'].unique())))
        f_df_p = df_p if sel_v == "✨ 全部" else df_p[df_p['vendor'] == sel_v]
        st.dataframe(f_df_p[['name', 'stock', 'vendor']], use_container_width=True, hide_index=True)

with tabs[2]:
    if not df_o.empty:
        dr = st.date_input("📅 日期範圍", [date(2024, 3, 1), today])
        if len(dr) == 2:
            # 關鍵：使用 pd.to_datetime().dt.date 確保 pure_date 欄位 100% 都是日期物件
            df_o['pure_date'] = pd.to_datetime(df_o['pure_date'], errors='coerce').dt.date
            mask = (df_o['pure_date'].fillna(date.min) >= dr[0]) & (df_o['pure_date'].fillna(date.max) <= dr[1])
            mask &= (~df_o['p_name'].str.contains("物流|包裹", na=False))
            st.dataframe(df_o[mask].sort_values('tz_fixed', ascending=False)[['tz_fixed', 'p_name', 'quantity', 'mode', 'platform']], use_container_width=True, hide_index=True)

with tabs[3]:
    if not df_o.empty:
        l_dr = st.date_input("📅 物流日期", [date(2024, 3, 1), today])
        if len(l_dr) == 2:
            df_entry = df_o[df_o['p_name'].str.contains("物流|包裹", na=False)]
            df_entry['pure_date'] = pd.to_datetime(df_entry['pure_date'], errors='coerce').dt.date
            e_mask = (df_entry['pure_date'].fillna(date.min) >= l_dr[0]) & (df_entry['pure_date'].fillna(date.max) <= l_dr[1])
            st.dataframe(df_entry[e_mask][['tz_fixed', 'platform', 'logistics', 'quantity']], use_container_width=True, hide_index=True)

    if st.button("🔄 刷新數據", use_container_width=True): st.cache_data.clear(); st.rerun()
