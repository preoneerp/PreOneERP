import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 頁面配置與視覺設計 ---
st.set_page_config(page_title="培玩雲端 ERP WEB V0407.3", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stApp { background-color: #FDFBFA; }
    /* 指標卡片美化 */
    .metric-card {
        background: white; padding: 22px; border-radius: 18px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.06); border-left: 6px solid #E8A0BF;
        text-align: left; margin-bottom: 12px;
    }
    .total-card {
        background: linear-gradient(135deg, #E67E22 0%, #D35400 100%);
        color: white; padding: 25px; border-radius: 18px;
        text-align: center; margin-bottom: 25px; font-weight: bold;
        box-shadow: 0 4px 15px rgba(230, 126, 34, 0.3);
    }
    .metric-value { font-size: 2rem; font-weight: bold; color: #2C3E50; }
    .metric-label { color: #7F8C8D; font-size: 0.95rem; margin-bottom: 5px; }
    
    /* 商品標籤美化 */
    .product-tag {
        background: white; border: 1px solid #F0F0F0; border-radius: 15px;
        padding: 18px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.03);
    }
    .product-name {
        font-size: 1rem; color: #5D6D7E; margin-bottom: 8px; font-weight: 500;
        height: 2.8rem; display: flex; align-items: center; justify-content: center;
    }
    .product-qty { font-size: 2.4rem; font-weight: 800; color: #E67E22; }
    .product-unit { font-size: 0.9rem; color: #ABB2B9; margin-left: 4px; }
    
    /* 表格視覺優化 */
    .stDataFrame { border-radius: 12px; overflow: hidden; border: 1px solid #F0F0F0; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 初始化 ---
@st.cache_resource
def init_connection():
    try: return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except: return None

supabase = init_connection()

# --- 3. 數據處理核心 (V0407.3 鋼鐵邏輯) ---
def process_orders(df):
    std_cols = ['p_name', 'quantity', 'timestamp', 'platform', 'mode', 'logistics']
    if df is None or df.empty: return pd.DataFrame(columns=std_cols + ['date_str', 'dt_sort'])
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    r_map = {}
    for c in df.columns:
        if any(x in c for x in ['p_name', 'product', '品名', '商品']): r_map[c] = 'p_name'
        if any(x in c for x in ['qty', 'quantity', '數量', '件數']): r_map[c] = 'quantity'
        if any(x in c for x in ['timestamp', 'time', 'created']): r_map[c] = 'timestamp'
    df = df.rename(columns=r_map)
    
    for m in std_cols:
        if m not in df.columns: df[m] = "-"
    
    df['date_str'] = df['timestamp'].astype(str).str[:10]
    df['dt_sort'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
    return df

def process_products(df):
    if df is None or df.empty: return pd.DataFrame(columns=['name', 'stock', 'vendor'])
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    r_map = {}
    for c in df.columns:
        if any(x in c for x in ['name', 'product', '品名']): r_map[c] = 'name'
        if any(x in c for x in ['stock', '庫存', '在庫', 'qty']): r_map[c] = 'stock'
        if any(x in c for x in ['vendor', '供應', 'v_name']): r_map[c] = 'vendor'
    df = df.rename(columns=r_map)
    
    if 'name' not in df.columns and len(df.columns) > 0: df['name'] = df.iloc[:, 0]
    if 'stock' not in df.columns and len(df.columns) > 1: df['stock'] = df.iloc[:, 1]
    if 'vendor' not in df.columns and len(df.columns) > 2: df['vendor'] = df.iloc[:, 2]
    
    for col in ['name', 'stock', 'vendor']:
        if col not in df.columns: df[col] = "-"
    df['stock'] = pd.to_numeric(df['stock'], errors='coerce').fillna(0)
    return df[['name', 'stock', 'vendor']]

# --- 4. 登入系統 ---
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

if not st.session_state["password_correct"]:
    _, col_mid, _ = st.columns([1.2, 1, 1.2])
    with col_mid:
        st.write("<br><br>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; color: #E8A0BF;'>🎀 培玩雲端管理系統</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            u = st.text_input("帳號"); p = st.text_input("密碼", type="password")
            if st.button("進入系統", use_container_width=True):
                auth = st.secrets.get("auth", {})
                if u in auth and str(p) == str(auth[u]["password"]):
                    st.session_state.update({"password_correct": True})
                    st.rerun()
                else: st.error("🔒 密碼不正確")
    st.stop()

# --- 5. 數據抓取 ---
@st.cache_data(ttl=5)
def fetch_data():
    try:
        r1 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(0, 999).execute()
        r2 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(1000, 1999).execute()
        r3 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(2000, 2999).execute()
        raw_p = supabase.table("products").select("*").execute().data
        return pd.DataFrame(raw_p), pd.DataFrame(r1.data + r2.data + r3.data)
    except: return pd.DataFrame(), pd.DataFrame()

df_p_raw, df_o_raw = fetch_data()
df_p = process_products(df_p_raw)
df_o = process_orders(df_o_raw)

# --- 6. 主介面 ---
tabs = st.tabs(["📊 數據總覽", "☁️ 庫存狀態", "📦 出貨紀錄明細", "🚚 物流件數登記"])

# --- TAB 0: 數據總覽 ---
with tabs[0]:
    t_str = date.today().strftime("%Y-%m-%d")
    today_o = df_o[df_o['date_str'] == t_str] if not df_o.empty else pd.DataFrame(columns=df_o.columns)
    st.markdown(f"### 🎯 今日營運概況 ({t_str})")
    
    prods = [{"name": "專注力訓練機", "s": "舒爾特專注力訓練機"},{"name": "24點數感大作戰", "s": "24點數感邏輯大作戰"},{"name": "顯微鏡相機", "s": "顯微鏡相機"},{"name": "創意卷軸畫", "s": "滾動創意卷軸畫"},{"name": "攜行盒-藍", "s": "攜行盒-藍"},{"name": "攜行盒-粉", "s": "攜行盒-粉"}]
    p_cols = st.columns(6)
    df_items = today_o[~today_o['p_name'].str.contains("物流|包裹", na=False)] if not today_o.empty else pd.DataFrame(columns=df_o.columns)
    
    for i, item in enumerate(prods):
        with p_cols[i]:
            qty = int(df_items[df_items['p_name'].str.contains(item['s'], na=False)]['quantity'].sum()) if not df_items.empty else 0
            st.markdown(f'<div class="product-tag"><div class="product-name">{item["name"]}</div><div class="product-qty">{qty}<span class="product-unit">個</span></div></div>', unsafe_allow_html=True)
    
    st.write("<br>", unsafe_allow_html=True)
    col_m, col_logi = st.columns([1, 1.2])
    
    with col_m:
        st.markdown("#### 📈 今日核心指標")
        df_ship = df_o[df_o['p_name'].str.contains("物流|包裹", na=False)]
        pkg_cnt = int(df_ship[df_ship["date_str"]==t_str]["quantity"].sum()) if not df_ship.empty else 0
        
        m1, m2 = st.columns(2)
        m1.markdown(f'<div class="metric-card"><div class="metric-label">今日出貨包裹</div><div class="metric-value">{pkg_cnt} 件</div></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="metric-card"><div class="metric-label">今日訂單明細</div><div class="metric-value">{len(df_items)} 筆</div></div>', unsafe_allow_html=True)
        
        m3, m4 = st.columns(2)
        low_stock = len(df_p[df_p['stock'] < 10]) if not df_p.empty else 0
        m3.markdown(f'<div class="metric-card"><div class="metric-label">庫存警戒項目</div><div class="metric-value" style="color:red">{low_stock} 項</div></div>', unsafe_allow_html=True)
        m4.markdown(f'<div class="metric-card"><div class="metric-label">數據更新狀態</div><div class="metric-value" style="font-size:1.2rem; color:#27AE60;">V0407.3 鋼鐵版</div></div>', unsafe_allow_html=True)

    with col_logi:
        st.markdown("#### 🚚 當日物流統計表")
        today_ship = df_ship[df_ship['date_str'] == t_str] if not df_ship.empty else pd.DataFrame()
        if not today_ship.empty:
            logi_sum = today_ship.groupby('logistics')['quantity'].sum().reset_index()
            logi_sum.columns = ['物流渠道', '今日件數']
            st.dataframe(logi_sum.sort_values('今日件數', ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("今日尚無物流登記數據")

# --- TAB 1: 庫存狀態 ---
with tabs[1]:
    st.markdown("### ☁️ 現有庫存清單")
    if not df_p.empty:
        # 使用 V0407.3 原本穩定的顯示邏輯
        st.dataframe(df_p[['name', 'stock', 'vendor']].rename(columns={'name':'商品名稱','stock':'在庫數量','vendor':'供應商'}), use_container_width=True, hide_index=True)

# --- TAB 2: 出貨紀錄明細 ---
with tabs[2]:
    st.markdown("### 📦 出貨紀錄明細")
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        dr = c1.date_input("📅 日期範圍", [date(2026, 3, 2), date.today()], key="order_dr")
        plt_filter = ["全部平台"] + sorted(list(df_o['platform'].unique()))
        sel_plt = c2.selectbox("📱 銷售平台", plt_filter)
        mode_filter = ["全部模式"] + sorted(list(df_o['mode'].unique()))
        sel_mode = c3.selectbox("🔃 交易模式", mode_filter)

    if not df_o.empty and len(dr) == 2:
        mask = (~df_o['p_name'].str.contains("物流|包裹", na=False))
        mask &= (df_o['date_str'] >= dr[0].strftime("%Y-%m-%d")) & (df_o['date_str'] <= dr[1].strftime("%Y-%m-%d"))
        if sel_plt != "全部平台": mask &= (df_o['platform'] == sel_plt)
        if sel_mode != "全部模式": mask &= (df_o['mode'] == sel_mode)
        
        view_o = df_o[mask].sort_values('dt_sort', ascending=False)[['timestamp', 'p_name', 'quantity', 'mode', 'platform', 'logistics']]
        st.dataframe(view_o.rename(columns={
            'timestamp':'時間註記','p_name':'商品名稱','quantity':'數量','mode':'交易模式','platform':'銷售平台','logistics':'物流單號'
        }), use_container_width=True, hide_index=True)

# --- TAB 3: 物流件數登記 ---
with tabs[3]:
    st.markdown("### 🚚 物流件數登記")
    df_ent = df_o[df_o['p_name'].str.contains("物流|包裹", na=False)]
    with st.container(border=True):
        l1, l2 = st.columns(2)
        ldr = l1.date_input("📅 統計週期", [date(2026, 3, 2), date.today()], key="logi_dr")
        logi_filter = ["全部物流"] + sorted(list(df_ent['logistics'].unique()))
        sel_logi = l2.selectbox("🚚 物流商/渠道", logi_filter)

    if not df_ent.empty and len(ldr) == 2:
        e_mask = (df_ent['date_str'] >= ldr[0].strftime("%Y-%m-%d")) & (df_ent['date_str'] <= ldr[1].strftime("%Y-%m-%d"))
        if sel_logi != "全部物流": e_mask &= (df_ent['logistics'] == sel_logi)
        
        df_res = df_ent[e_mask].sort_values('dt_sort', ascending=False)
        total_qty = int(df_res['quantity'].sum())
        st.markdown(f'<div class="total-card"><div style="font-size:1.1rem; opacity:0.9;">週期件數總計 ({ldr[0]} ~ {ldr[1]})</div><div style="font-size:2.8rem;">{total_qty} <span style="font-size:1.1rem;">件</span></div></div>', unsafe_allow_html=True)
        st.dataframe(df_res[['timestamp', 'platform', 'logistics', 'quantity']].rename(columns={
            'timestamp':'時間註記','platform':'來源平台','logistics':'物流渠道','quantity':'件數'
        }), use_container_width=True, hide_index=True)

    if st.button("🔄 刷新雲端數據", use_container_width=True): st.cache_data.clear(); st.rerun()
