import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 頁面配置 ---
st.set_page_config(page_title="培玩雲端 ERP WEB V0407.10", layout="wide", initial_sidebar_state="expanded")

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
    .metric-label { color: #7F8C8D; font-size: 0.95rem; margin-bottom: 5px; }
    .product-tag {
        background: white; border: 1px solid #F0F0F0; border-radius: 15px;
        padding: 18px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.03);
    }
    .product-name {
        font-size: 1rem; color: #5D6D7E; margin-bottom: 8px; font-weight: 500;
        height: 2.8rem; display: flex; align-items: center; justify-content: center;
    }
    .product-qty { font-size: 2.4rem; font-weight: 800; color: #E67E22; }
    .stDataFrame { border-radius: 12px; overflow: hidden; border: 1px solid #F0F0F0; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 初始化連線 ---
@st.cache_resource
def init_connection():
    try: return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except: return None

supabase = init_connection()

# --- 3. 獨立邏輯處理器 (分頁邏輯拆分) ---

def clean_order_data(df):
    """專門處理訂單與物流明細的邏輯"""
    if df is None or df.empty: return pd.DataFrame()
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # 訂單表專用模糊對齊
    r_map = {}
    for c in df.columns:
        if any(x in c for x in ['p_name', 'product', '品名', '商品']): r_map[c] = 'p_name'
        if any(x in c for x in ['qty', 'quantity', '數量']): r_map[c] = 'quantity'
        if any(x in c for x in ['timestamp', 'time', 'created']): r_map[c] = 'timestamp'
    df = df.rename(columns=r_map).loc[:, ~df.columns.duplicated()]

    # 時間格式優化 (使用者視角)
    ts_str = df['timestamp'].astype(str).str.replace('T', ' ').str.replace('Z', '')
    df['display_time'] = ts_str.str[:16] # 2026-03-02 14:30
    df['date_str'] = ts_str.str[:10]      # 2026-03-02
    df['dt_sort'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
    
    # 補齊必要欄位
    for col in ['p_name', 'platform', 'mode', 'logistics']:
        if col not in df.columns: df[col] = "-"
    return df

def clean_product_data(df):
    """專門處理庫存狀態的邏輯 (不與訂單表衝突)"""
    if df is None or df.empty: return pd.DataFrame()
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # 商品表專用對齊 (避免跟訂單表的 p_name 混淆)
    r_map = {}
    for c in df.columns:
        if any(x in c for x in ['name', 'product', '品名']): r_map[c] = 'prod_name'
        if any(x in c for x in ['stock', '庫存', '在庫', 'qty']): r_map[c] = 'stock_qty'
        if any(x in c for x in ['vendor', '供應']): r_map[c] = 'vendor_name'
    df = df.rename(columns=r_map).loc[:, ~df.columns.duplicated()]

    # 強制保底 (iloc 索引)
    if 'prod_name' not in df.columns: df['prod_name'] = df.iloc[:, 0]
    if 'stock_qty' not in df.columns: df['stock_qty'] = df.iloc[:, 1] if len(df.columns) > 1 else 0
    if 'vendor_name' not in df.columns: df['vendor_name'] = df.iloc[:, 2] if len(df.columns) > 2 else "-"
    
    df['stock_qty'] = pd.to_numeric(df['stock_qty'], errors='coerce').fillna(0)
    return df[['prod_name', 'stock_qty', 'vendor_name']]

# --- 4. 數據抓取 ---
@st.cache_data(ttl=5)
def fetch_all():
    try:
        r1 = supabase.table("order_history").select("*").range(0, 999).execute()
        r2 = supabase.table("order_history").select("*").range(1000, 1999).execute()
        r3 = supabase.table("order_history").select("*").range(2000, 2999).execute()
        raw_p = supabase.table("products").select("*").execute().data
        return pd.DataFrame(raw_p), pd.DataFrame(r1.data + r2.data + r3.data)
    except: return pd.DataFrame(), pd.DataFrame()

df_p_raw, df_o_raw = fetch_all()
df_o = clean_order_data(df_o_raw)
df_p = clean_product_data(df_p_raw)

# --- 5. 主介面 ---
tabs = st.tabs(["📊 數據總覽", "☁️ 庫存狀態", "📦 出貨紀錄明細", "🚚 物流件數登記"])

# --- TAB 0: 數據總覽 (獨立物流統計) ---
with tabs[0]:
    t_str = date.today().strftime("%Y-%m-%d")
    today_o = df_o[df_o['date_str'] == t_str] if not df_o.empty else pd.DataFrame()
    st.markdown(f"### 🎯 今日營運概況 ({t_str})")
    
    # 核心產品監控
    prods = [{"name": "專注力訓練機", "s": "專注力訓練機"},{"name": "24點數感大作戰", "s": "24點數感"},{"name": "顯微鏡相機", "s": "顯微鏡相機"},{"name": "創意卷軸畫", "s": "卷軸畫"},{"name": "攜行盒-藍", "s": "攜行盒-藍"},{"name": "攜行盒-粉", "s": "攜行盒-粉"}]
    p_cols = st.columns(6)
    df_items = today_o[~today_o['p_name'].astype(str).str.contains("物流|包裹", na=False)] if not today_o.empty else pd.DataFrame()
    
    for i, item in enumerate(prods):
        with p_cols[i]:
            qty = int(df_items[df_items['p_name'].astype(str).str.contains(item['s'], na=False)]['quantity'].sum()) if not df_items.empty else 0
            st.markdown(f'<div class="product-tag"><div class="product-name">{item["name"]}</div><div class="product-qty">{qty}<span style="font-size:1rem;color:#999"> 個</span></div></div>', unsafe_allow_html=True)

    st.write("<br>", unsafe_allow_html=True)
    col_left, col_right = st.columns([1, 1.2])
    with col_left:
        st.markdown("#### 📈 營運指標")
        df_ship_all = df_o[df_o['p_name'].astype(str).str.contains("物流|包裹", na=False)] if not df_o.empty else pd.DataFrame()
        pkg_today = int(df_ship_all[df_ship_all["date_str"]==t_str]["quantity"].sum()) if not df_ship_all.empty else 0
        st.markdown(f'<div class="metric-card"><div class="metric-label">今日出貨包裹</div><div class="metric-value">{pkg_today} 件</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-card"><div class="metric-label">庫存警戒項目</div><div class="metric-value" style="color:red">{len(df_p[df_p["stock_qty"] < 10])} 項</div></div>', unsafe_allow_html=True)

    with col_right:
        st.markdown("#### 🚚 當日物流分佈")
        today_ship = df_ship_all[df_ship_all['date_str'] == t_str] if not df_ship_all.empty else pd.DataFrame()
        if not today_ship.empty:
            st.dataframe(today_ship.groupby('logistics')['quantity'].sum().reset_index().rename(columns={'logistics':'物流渠道','quantity':'件數'}), use_container_width=True, hide_index=True)
        else: st.info("今日尚無物流登記數據")

# --- TAB 1: 庫存狀態 (完全獨立的供應商篩選) ---
with tabs[1]:
    st.markdown("### ☁️ 現有庫存清單")
    if not df_p.empty:
        sel_v = st.selectbox("🔍 依供應商篩選", ["全部供應商"] + sorted(list(df_p['vendor_name'].unique())))
        f_p = df_p if sel_v == "全部供應商" else df_p[df_p['vendor_name'] == sel_v]
        st.dataframe(f_p.rename(columns={'prod_name':'商品名稱','stock_qty':'在庫數量','vendor_name':'供應商'}), use_container_width=True, hide_index=True)

# --- TAB 2: 出貨明細 (獨立日期篩選) ---
with tabs[2]:
    st.markdown("### 📦 出貨紀錄明細")
    dr = st.date_input("📅 選擇日期", [date(2026, 3, 2), date.today()], key="tab2_dr")
    if not df_o.empty and len(dr) == 2:
        mask = (~df_o['p_name'].astype(str).str.contains("物流|包裹", na=False))
        mask &= (df_o['date_str'] >= dr[0].strftime("%Y-%m-%d")) & (df_o['date_str'] <= dr[1].strftime("%Y-%m-%d"))
        st.dataframe(df_o[mask].sort_values('dt_sort', ascending=False)[['display_time', 'p_name', 'quantity', 'mode', 'platform', 'logistics']].rename(columns={'display_time':'時間註記','p_name':'商品名稱','quantity':'數量','mode':'交易模式','platform':'銷售平台','logistics':'物流單號'}), use_container_width=True, hide_index=True)

# --- TAB 3: 物流登記 (獨立統計邏輯) ---
with tabs[3]:
    st.markdown("### 🚚 物流件數登記")
    df_ent = df_o[df_o['p_name'].astype(str).str.contains("物流|包裹", na=False)] if not df_o.empty else pd.DataFrame()
    ldr = st.date_input("📅 統計週期", [date(2026, 3, 2), date.today()], key="tab3_dr")
    if not df_ent.empty and len(ldr) == 2:
        e_mask = (df_ent['date_str'] >= ldr[0].strftime("%Y-%m-%d")) & (df_ent['date_str'] <= ldr[1].strftime("%Y-%m-%d"))
        df_res = df_ent[e_mask]
        st.markdown(f'<div class="total-card"><div style="font-size:1.1rem; opacity:0.9;">週期件數總計</div><div style="font-size:2.8rem;">{int(df_res["quantity"].sum())} 件</div></div>', unsafe_allow_html=True)
        st.dataframe(df_res[['display_time', 'platform', 'logistics', 'quantity']].rename(columns={'display_time':'時間註記','platform':'來源平台','logistics':'物流渠道','quantity':'件數'}), use_container_width=True, hide_index=True)

if st.button("🔄 刷新雲端數據", use_container_width=True): st.cache_data.clear(); st.rerun()
