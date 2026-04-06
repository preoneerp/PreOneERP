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

# --- 3. 數據預處理 (字串首位偵測邏輯) ---
def smart_process(df):
    if df is None or df.empty: return pd.DataFrame()
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # 確保 timestamp 存在且為字串
    if 'timestamp' in df.columns:
        df['timestamp_str'] = df['timestamp'].astype(str)
        # 關鍵：直接取字串前 10 位 (YYYY-MM-DD)
        df['date_str'] = df['timestamp_str'].str[:10]
        # 為了排序，我們還是嘗試轉一次 dt，但如果不成也不會崩潰
        df['dt_sort'] = pd.to_datetime(df['timestamp'], errors='coerce')
    
    # 欄位對齊與補位
    for col in ['p_name', 'quantity', 'mode', 'platform', 'logistics', 'vendor']:
        if col not in df.columns: df[col] = "-"
        df[col] = df[col].astype(str).replace(['nan', 'None', ''], '-')
        
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

# --- 5. 數據抓取 (維持 3000 筆物理量) ---
@st.cache_data(ttl=5)
def fetch_all_data():
    try:
        r1 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(0, 999).execute()
        r2 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(1000, 1999).execute()
        r3 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(2000, 2999).execute()
        raw_o = r1.data + r2.data + r3.data
        raw_p = supabase.table("products").select("*").execute().data
        return pd.DataFrame(raw_p), pd.DataFrame(raw_o)
    except: return pd.DataFrame(), pd.DataFrame()

df_p_raw, df_o_raw = fetch_all_data()
df_p, df_o = smart_process(df_p_raw), smart_process(df_o_raw)

# --- 6. 主介面 ---
tabs = st.tabs(["📊 數據總覽", "☁️ 庫存狀態", "📦 出貨紀錄明細", "🚚 物流件數登記"])

with tabs[0]:
    today_str = date.today().strftime("%Y-%m-%d")
    today_o = df_o[df_o['date_str'] == today_str] if not df_o.empty else pd.DataFrame()
    st.markdown(f"### 🎯 今日統計 ({today_str})")
    
    target_prods = [{"name": "專注力訓練機", "search": "舒爾特專注力訓練機"},{"name": "24點數感大作戰", "search": "24點數感邏輯大作戰"},{"name": "顯微鏡相機", "search": "顯微鏡相機"},{"name": "創意卷軸畫", "search": "滾動創意卷軸畫"},{"name": "攜行盒-藍", "search": "攜行盒-藍"},{"name": "攜行盒-粉", "search": "攜行盒-粉"}]
    prod_cols = st.columns(6)
    
    # 排除物流登記
    df_items_only = today_o[~today_o['p_name'].str.contains("物流|包裹", na=False)] if not today_o.empty else pd.DataFrame()
    for i, item in enumerate(target_prods):
        with prod_cols[i]:
            qty = int(pd.to_numeric(df_items_only[df_items_only['p_name'].str.contains(item['search'], na=False)]['quantity'], errors='coerce').sum())
            st.markdown(f'<div class="product-tag"><div class="product-name">{item["name"]}</div><div class="product-qty">{qty}<span class="product-unit">個</span></div></div>', unsafe_allow_html=True)
    
    st.write("<br>", unsafe_allow_html=True)
    df_ship_all = df_o[df_o['p_name'].str.contains("物流|包裹", na=False)]
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.markdown(f'<div class="metric-card"><div class="metric-label">今日出貨包裹</div><div class="metric-value">{int(pd.to_numeric(df_ship_all[df_ship_all["date_str"]==today_str]["quantity"], errors="coerce").sum())} 件</div></div>', unsafe_allow_html=True)
    with m2: st.metric("總資料筆數", f"{len(df_o)} 筆")
    with m3: st.markdown(f'<div class="metric-card"><div class="metric-label">今日明細筆數</div><div class="metric-value">{len(df_items_only)} 筆</div></div>', unsafe_allow_html=True)
    with m4: st.markdown(f'<div class="metric-card"><div class="metric-label">在庫商品項數</div><div class="metric-value">{len(df_p)} 項</div></div>', unsafe_allow_html=True)

with tabs[1]:
    if not df_p.empty:
        st.dataframe(df_p[['name', 'stock', 'vendor']].rename(columns={'name':'商品','stock':'庫存','vendor':'供應商'}), use_container_width=True, hide_index=True)

with tabs[2]:
    if not df_o.empty:
        # 日期範圍篩選
        dr = st.date_input("📅 選擇日期區間", [date(2026, 3, 2), date.today()])
        mask = (~df_o['p_name'].str.contains("物流|包裹", na=False))
        if len(dr) == 2:
            start_s, end_s = dr[0].strftime("%Y-%m-%d"), dr[1].strftime("%Y-%m-%d")
            # 字串範圍比較 (YYYY-MM-DD 字串可以直接比大小)
            mask &= (df_o['date_str'] >= start_s) & (df_o['date_str'] <= end_s)
        
        st.dataframe(df_o[mask].sort_values('dt_sort', ascending=False)[['timestamp', 'p_name', 'quantity', 'mode', 'platform']], use_container_width=True, hide_index=True)

with tabs[3]:
    if not df_o.empty:
        df_entry = df_o[df_o['p_name'].str.contains("物流|包裹", na=False)]
        l_dr = st.date_input("📅 物流日期篩選", [date(2026, 3, 2), date.today()])
        if len(l_dr) == 2:
            l_start, l_end = l_dr[0].strftime("%Y-%m-%d"), l_dr[1].strftime("%Y-%m-%d")
            e_mask = (df_entry['date_str'] >= l_start) & (df_entry['date_str'] <= l_end)
            st.dataframe(df_entry[e_mask][['timestamp', 'platform', 'logistics', 'quantity']], use_container_width=True, hide_index=True)

    if st.button("🔄 刷新雲端數據", use_container_width=True): st.cache_data.clear(); st.rerun()
