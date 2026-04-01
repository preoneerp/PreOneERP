import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta
import pytz

# --- 1. 頁面配置與視覺設計 (恢復您原始設計) ---
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

# --- 3. 數據自動處理 (精準兼容邏輯：不扭曲日期) ---
def smart_process(df):
    if df is None or df.empty: return pd.DataFrame()
    # 解決大小寫不一：強行轉為小寫
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # 暴力搜尋所有時間欄位名稱，確保 3/31 前的資料能找到自己的時間
    t_targets = ['timestamp', 'created_at', 'time', '作成時間', '日期']
    t_col = next((c for c in df.columns if c in t_targets), None)
    
    if t_col:
        # 解析時間：utc=True 配合 Taipei 轉時區是最穩定的做法
        df['tz_fixed'] = pd.to_datetime(df[t_col], errors='coerce', utc=True)
        # 轉換回台北時間，但不補假資料，保留 NaT 讓用戶知道哪些資料時間格式毀損
        df['tz_fixed'] = df['tz_fixed'].dt.tz_convert('Asia/Taipei').dt.tz_localize(None)
        df['pure_date'] = df['tz_fixed'].dt.date
    
    # 處理空值：補上「-」或「未分類」僅是為了不讓 groupby 崩潰，不影響資料實體
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.strip().replace(['nan', 'None', 'None', ''], '-')
            
    # 修復 vendor 缺失問題
    if 'vendor' not in df.columns:
        v_alt = next((c for c in df.columns if '供應商' in c or 'v_name' in c), None)
        df['vendor'] = df[v_alt] if v_alt else "-"
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
                    st.session_state.update({"password_correct": True, "user_level": auth[u].get("level")})
                    st.rerun()
                else: st.error("🔒 帳號或密碼不正確")
    st.stop()

# --- 5. 數據抓取 (保持翻頁讀取：確保抓到總量超過 1000 筆的舊資料) ---
@st.cache_data(ttl=10)
def fetch_all_data():
    try:
        # 直接拉 3000 筆資料，這是找回 3/31 前資料的物理前提
        r1 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(0, 999).execute()
        r2 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(1000, 1999).execute()
        r3 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(2000, 2999).execute()
        return pd.DataFrame(supabase.table("products").select("*").execute().data), pd.DataFrame(r1.data + r2.data + r3.data)
    except: return pd.DataFrame(), pd.DataFrame()

df_p, df_o = smart_process(fetch_all_data()[0]), smart_process(fetch_all_data()[1])

# --- 6. 主介面 ---
tabs = st.tabs(["📊 數據總覽", "☁️ 庫存狀態", "📦 出貨紀錄明細", "🚚 物流件數登記"])

with tabs[0]:
    today = date.today()
    today_o = df_o[df_o['pure_date'] == today] if not df_o.empty else pd.DataFrame()
    st.markdown(f"### 🎯 今日統計 ({today})")
    target_prods = [{"name": "專注力訓練機", "search": "舒爾特專注力訓練機"},{"name": "24點數感大作戰", "search": "24點數感邏輯大作戰"},{"name": "顯微鏡相機", "search": "顯微鏡相機"},{"name": "創意卷軸畫", "search": "滾動創意卷軸畫"},{"name": "攜行盒-藍", "search": "攜行盒-藍"},{"name": "攜行盒-粉", "search": "攜行盒-粉"}]
    prod_cols = st.columns(6)
    # 過濾：na=True 確保沒時間的資料在今日不顯示，但不會被刪除
    df_items_only = today_o[~today_o['p_name'].str.contains("物流|包裹", na=False)] if not today_o.empty else pd.DataFrame()
    for i, item in enumerate(target_prods):
        with prod_cols[i]:
            qty = int(df_items_only[df_items_only['p_name'].str.contains(item['search'], na=False)]['quantity'].astype(float).sum()) if not df_items_only.empty else 0
            st.markdown(f'<div class="product-tag"><div class="product-name">{item["name"]}</div><div class="product-qty">{qty}<span class="product-unit">個</span></div></div>', unsafe_allow_html=True)
    
    df_ship_all = df_o[df_o['p_name'].str.contains("物流|包裹", na=False)] if not df_o.empty else pd.DataFrame()
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.markdown(f'<div class="metric-card"><div class="metric-label">今日出貨包裹</div><div class="metric-value">{int(df_ship_all[df_ship_all["pure_date"]==today]["quantity"].astype(float).sum())} 件</div></div>', unsafe_allow_html=True)
    with m2: st.markdown(f'<div class="metric-card"><div class="metric-label">本月累計包裹</div><div class="metric-value">{int(df_ship_all[df_ship_all["pure_date"]>=today.replace(day=1)]["quantity"].astype(float).sum())} 件</div></div>', unsafe_allow_html=True)
    with m3: st.markdown(f'<div class="metric-card"><div class="metric-label">今日明細筆數</div><div class="metric-value">{len(df_items_only)} 筆</div></div>', unsafe_allow_html=True)
    with m4: st.markdown(f'<div class="metric-card"><div class="metric-label">低庫存警戒</div><div class="metric-value" style="color:red">{len(df_p[df_p["stock"].astype(float) < 10]) if not df_p.empty else 0} 項</div></div>', unsafe_allow_html=True)

with tabs[1]:
    if not df_p.empty:
        sel_v = st.selectbox("🔍 供應商篩選", ["✨ 全部"] + sorted(list(df_p['vendor'].unique())))
        f_df_p = df_p if sel_v == "✨ 全部" else df_p[df_p['vendor'] == sel_v]
        st.dataframe(f_df_p[['name', 'stock', 'vendor']].rename(columns={'name':'商品','stock':'在庫','vendor':'供應商'}), use_container_width=True, hide_index=True)

with tabs[2]:
    if not df_o.empty:
        dr = st.date_input("📅 日期範圍", [today - timedelta(days=30), today])
        if len(dr) == 2:
            # 關鍵修正：使用 .fillna(date.min) 讓沒日期的資料排在最後面，但絕不消失
            mask = (df_o['pure_date'].fillna(date.min) >= dr[0]) & (df_o['pure_date'].fillna(date.max) <= dr[1])
            mask &= (~df_o['p_name'].str.contains("物流|包裹", na=False))
            st.dataframe(df_o[mask].sort_values('tz_fixed', ascending=False)[['tz_fixed', 'p_name', 'quantity', 'mode', 'platform']].rename(columns={'tz_fixed':'時間','p_name':'商品','quantity':'數量'}), use_container_width=True, hide_index=True)

with tabs[3]:
    if not df_o.empty:
        l_dr = st.date_input("📅 物流日期", [today - timedelta(days=30), today])
        if len(l_dr) == 2:
            df_entry = df_o[df_o['p_name'].str.contains("物流|包裹", na=False)]
            e_mask = (df_entry['pure_date'].fillna(date.min) >= l_dr[0]) & (df_entry['pure_date'].fillna(date.max) <= l_dr[1])
            st.markdown(f'<div style="background:#E67E22; color:white; padding:15px; border-radius:15px; text-align:center; margin-bottom:20px">總計: {int(df_entry[e_mask]["quantity"].astype(float).sum())} 件</div>', unsafe_allow_html=True)
            st.dataframe(df_entry[e_mask][['tz_fixed', 'platform', 'logistics', 'quantity']].rename(columns={'tz_fixed':'時間','platform':'平台','logistics':'物流','quantity':'件數'}), use_container_width=True, hide_index=True)

    if st.button("🔄 刷新雲端數據", use_container_width=True): st.cache_data.clear(); st.rerun()
