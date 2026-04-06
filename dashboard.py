import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 頁面配置 ---
st.set_page_config(page_title="培玩雲端 ERP WEB V0407.31", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stApp { background-color: #FDFBFA; }
    .metric-card {
        background: white; padding: 22px; border-radius: 18px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.06); border-left: 6px solid #E8A0BF;
        text-align: left; margin-bottom: 12px;
    }
    .total-card {
        background: linear-gradient(135deg, #E67E22 0%, #D35400 100%);
        color: white; padding: 25px; border-radius: 18px;
        text-align: center; margin-bottom: 25px; font-weight: bold;
    }
    .metric-value { font-size: 2rem; font-weight: bold; color: #2C3E50; }
    .product-tag {
        background: white; border: 1px solid #F0F0F0; border-radius: 15px;
        padding: 18px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.03);
    }
    .product-qty { font-size: 2.4rem; font-weight: 800; color: #E67E22; }
    .stDataFrame { border-radius: 12px; overflow: hidden; border: 1px solid #F0F0F0; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 初始化 ---
@st.cache_resource
def init_connection():
    try: return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except: return None

supabase = init_connection()

# --- 3. 數據處理核心 (字串切片降噪邏輯) ---
def process_orders(df):
    std_cols = ['p_name', 'quantity', 'timestamp', 'platform', 'mode', 'logistics']
    if df is None or df.empty: return pd.DataFrame(columns=std_cols + ['date_str', 'display_time', 'dt_sort'])
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    r_map = {}
    for c in df.columns:
        if any(x in c for x in ['p_name', 'product', '品名', '商品']): r_map[c] = 'p_name'
        if any(x in c for x in ['qty', 'quantity', '數量']): r_map[c] = 'quantity'
        if any(x in c for x in ['timestamp', 'time', 'created']): r_map[c] = 'timestamp'
    df = df.rename(columns=r_map)
    
    for m in std_cols:
        if m not in df.columns: df[m] = "-"
    
    # --- 視覺降噪核心：字串切片 (不使用 pd.to_datetime 避免消失) ---
    # 先將 T 和 Z 替換掉
    raw_ts = df['timestamp'].astype(str).str.replace('T', ' ').str.replace('Z', '')
    # 降噪：只取到 分鐘 (前 16 位)，例如 2026-03-02 14:30
    df['display_time'] = raw_ts.str[:16]
    # 篩選用：只取日期 (前 10 位)，例如 2026-03-02
    df['date_str'] = raw_ts.str[:10]
    
    # 排序保底：僅用於後台排序
    df['dt_sort'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
    return df

def process_products(df):
    if df is None or df.empty: return pd.DataFrame(columns=['name', 'stock', 'vendor'])
    df.columns = [str(c).lower().strip() for c in df.columns]
    r_map = {'name':['name','product','品名'], 'stock':['stock','庫存','在庫','qty'], 'vendor':['vendor','供應','v_name']}
    for target, keys in r_map.items():
        found = next((c for c in df.columns if any(k in c for k in keys)), None)
        if found: df = df.rename(columns={found: target})
    
    # iloc 保底
    if 'name' not in df.columns and len(df.columns) > 0: df['name'] = df.iloc[:, 0]
    if 'stock' not in df.columns and len(df.columns) > 1: df['stock'] = df.iloc[:, 1]
    if 'vendor' not in df.columns and len(df.columns) > 2: df['vendor'] = df.iloc[:, 2]
    
    df['stock'] = pd.to_numeric(df['stock'], errors='coerce').fillna(0)
    return df[['name', 'stock', 'vendor']]

# --- 4. 數據抓取 ---
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

# --- 5. 主介面 ---
tabs = st.tabs(["📊 數據總覽", "☁️ 庫存狀態", "📦 出貨紀錄明細", "🚚 物流件數登記"])

# --- TAB 0: 數據總覽 ---
with tabs[0]:
    t_str = date.today().strftime("%Y-%m-%d")
    today_o = df_o[df_o['date_str'] == t_str] if not df_o.empty else pd.DataFrame(columns=df_o.columns)
    st.markdown(f"### 🎯 今日營運概況 ({t_str})")
    
    prods = [{"name": "專注力訓練機", "s": "專注力訓練機"},{"name": "24點數感大作戰", "s": "24點數感"},{"name": "顯微鏡相機", "s": "顯微鏡相機"},{"name": "創意卷軸畫", "s": "卷軸畫"},{"name": "攜行盒-藍", "s": "攜行盒-藍"},{"name": "攜行盒-粉", "s": "攜行盒-粉"}]
    p_cols = st.columns(6)
    df_items = today_o[~today_o['p_name'].str.contains("物流|包裹", na=False)] if not today_o.empty else pd.DataFrame(columns=df_o.columns)
    
    for i, item in enumerate(prods):
        with p_cols[i]:
            qty = int(df_items[df_items['p_name'].str.contains(item['s'], na=False)]['quantity'].sum()) if not df_items.empty else 0
            st.markdown(f'<div class="product-tag"><div class="product-name">{item["name"]}</div><div class="product-qty">{qty}<span style="font-size:1rem;color:#999"> 個</span></div></div>', unsafe_allow_html=True)
    
    st.write("<br>", unsafe_allow_html=True)
    col_m, col_logi = st.columns([1, 1.2])
    with col_m:
        st.markdown("#### 📈 今日核心指標")
        df_ship = df_o[df_o['p_name'].str.contains("物流|包裹", na=False)]
        pkg_cnt = int(df_ship[df_ship["date_str"]==t_str]["quantity"].sum()) if not df_ship.empty else 0
        m1, m2 = st.columns(2); m3, m4 = st.columns(2)
        m1.markdown(f'<div class="metric-card"><div class="metric-label">今日出貨包裹</div><div class="metric-value">{pkg_cnt} 件</div></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="metric-card"><div class="metric-label">今日訂單明細</div><div class="metric-value">{len(df_items)} 筆</div></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="metric-card"><div class="metric-label">庫存警戒項目</div><div class="metric-value" style="color:red">{len(df_p[df_p["stock"] < 10])} 項</div></div>', unsafe_allow_html=True)
        m4.markdown(f'<div class="metric-card"><div class="metric-label">系統版本</div><div class="metric-value" style="font-size:1.1rem; color:#27AE60;">V0407.31 穩定版</div></div>', unsafe_allow_html=True)

    with col_logi:
        st.markdown("#### 🚚 當日物流統計")
        today_ship = df_ship[df_ship['date_str'] == t_str] if not df_ship.empty else pd.DataFrame()
        if not today_ship.empty:
            logi_sum = today_ship.groupby('logistics')['quantity'].sum().reset_index()
            st.dataframe(logi_sum.rename(columns={'logistics':'渠道','quantity':'件數'}), use_container_width=True, hide_index=True)
        else: st.info("今日尚無物流登記數據")

# --- TAB 2: 出貨紀錄明細 (修復點) ---
with tabs[2]:
    st.markdown("### 📦 出貨紀錄明細")
    dr = st.date_input("📅 日期篩選", [date(2026, 3, 2), date.today()], key="order_dr")
    if not df_o.empty and len(dr) == 2:
        mask = (~df_o['p_name'].str.contains("物流|包裹", na=False))
        # 關鍵：使用穩定的 date_str 比對字串日期
        mask &= (df_o['date_str'] >= dr[0].strftime("%Y-%m-%d")) & (df_o['date_str'] <= dr[1].strftime("%Y-%m-%d"))
        
        # 視覺降噪：顯示 display_time 而非原始 timestamp
        view_o = df_o[mask].sort_values('dt_sort', ascending=False)[['display_time', 'p_name', 'quantity', 'mode', 'platform', 'logistics']]
        st.dataframe(view_o.rename(columns={
            'display_time':'時間註記','p_name':'商品名稱','quantity':'數量','mode':'交易模式','platform':'銷售平台','logistics':'物流單號'
        }), use_container_width=True, hide_index=True)

with tabs[3]:
    st.markdown("### 🚚 物流件數登記")
    df_ent = df_o[df_o['p_name'].str.contains("物流|包裹", na=False)]
    ldr = st.date_input("📅 統計週期", [date(2026, 3, 2), date.today()], key="logi_dr")
    if not df_ent.empty and len(ldr) == 2:
        e_mask = (df_ent['date_str'] >= ldr[0].strftime("%Y-%m-%d")) & (df_ent['date_str'] <= ldr[1].strftime("%Y-%m-%d"))
        df_res = df_ent[e_mask]
        st.markdown(f'<div class="total-card"><div style="font-size:1.1rem; opacity:0.9;">週期件數總計</div><div style="font-size:2.8rem;">{int(df_res["quantity"].sum())} 件</div></div>', unsafe_allow_html=True)
        st.dataframe(df_res[['display_time', 'platform', 'logistics', 'quantity']].rename(columns={'display_time':'時間註記','platform':'來源平台','logistics':'物流渠道','quantity':'件數'}), use_container_width=True, hide_index=True)

if st.button("🔄 刷新雲端數據", use_container_width=True): st.cache_data.clear(); st.rerun()
