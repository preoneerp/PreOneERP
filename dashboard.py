import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta
import pytz

# --- 1. 頁面配置 ---
st.set_page_config(page_title="培玩雲端 ERP", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stApp { background-color: #FDFBFA; }
    .metric-card {
        background: white; padding: 20px; border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05); border-left: 5px solid #E8A0BF;
    }
    .metric-value { font-size: 1.8rem; font-weight: bold; color: #2C3E50; }
    .metric-label { color: #7F8C8D; font-size: 0.9rem; }
    .product-tag {
        background: #ffffff; border: 1px solid #eee; border-radius: 12px;
        padding: 15px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .product-name { font-size: 0.9rem; color: #5D6D7E; height: 2.5rem; display: flex; align-items: center; justify-content: center; }
    .product-qty { font-size: 1.8rem; font-weight: 800; color: #E67E22; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 初始化 ---
@st.cache_resource
def init_connection():
    try: return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except: return None

supabase = init_connection()

# --- 3. 數據處理 ---
def smart_process(df):
    if df is None or df.empty: return pd.DataFrame()
    df.columns = [str(c).strip().lower() for c in df.columns]
    for col in df.select_dtypes(['object']).columns:
        df[col] = df[col].astype(str).str.strip()
    t_col = next((c for c in df.columns if any(k in c for keyword in ['timestamp', 'time', 'created_at'])), None)
    if t_col:
        df['tz_fixed'] = pd.to_datetime(df[t_col], utc=True).dt.tz_convert('Asia/Taipei').dt.tz_localize(None)
        df['pure_date'] = df['tz_fixed'].dt.date
    return df

# --- 4. 數據抓取 ---
@st.cache_data(ttl=30)
def fetch_all_data():
    try:
        res_p = supabase.table("products").select("*").execute()
        res_o = supabase.table("order_history").select("*").execute()
        return pd.DataFrame(res_p.data), pd.DataFrame(res_o.data)
    except: return pd.DataFrame(), pd.DataFrame()

raw_p, raw_o = fetch_all_data()
df_p = smart_process(raw_p)
df_o = smart_process(raw_o)

# --- 主介面 ---
tabs = st.tabs(["📊 數據總覽", "☁️ 庫存狀態", "📦 出貨紀錄明細", "🚚 物流件數登記"])

with tabs[0]:
    today = date.today()
    today_o = df_o[df_o['pure_date'] == today]
    
    st.markdown(f"### 🎯 今日純出貨統計 ({today})")
    target_prods = [
        {"name": "專注力訓練機", "search": "舒爾特專注力訓練機Ⅱ"},
        {"name": "24點數感大作戰", "search": "24點數感邏輯大作戰"},
        {"name": "顯微鏡相機", "search": "顯微鏡相機"},
        {"name": "創意卷軸畫", "search": "滾動創意卷軸畫(主機+空白卷)"},
        {"name": "攜行盒-藍", "search": "攜行盒-藍(直接出貨)"},
        {"name": "攜行盒-粉", "search": "攜行盒-粉(直接出貨)"}
    ]
    
    cols = st.columns(6)
    # 計算商品標籤：排除所有物流登記/統計相關的資料，只看純出貨
    df_only_item_out = today_o[(today_o['mode'] == '出貨') & (today_o['p_name'] != "物流登記")]
    for i, item in enumerate(target_prods):
        with cols[i]:
            qty = int(df_only_item_out[df_only_item_out['p_name'] == item['search']]['quantity'].sum())
            st.markdown(f'<div class="product-tag"><div class="product-name">{item["name"]}</div><div class="product-qty">{qty}</div></div>', unsafe_allow_html=True)

    st.write("---")
    
    # 包裹總量統計 (關鍵修復：同時採納物流登記名稱與物流統計模式)
    df_ship_summary = today_o[(today_o['p_name'] == "物流登記") | (today_o['mode'] == "物流統計")]
    today_total_pkgs = df_ship_summary['quantity'].sum()

    m1, m2, m3, m4 = st.columns(4)
    with m1: st.markdown(f'<div class="metric-card"><div class="metric-label">今日出貨包裹總量</div><div class="metric-value">{int(today_total_pkgs)} 件</div></div>', unsafe_allow_html=True)
    with m3: st.markdown(f'<div class="metric-card"><div class="metric-label">今日訂單品項筆數</div><div class="metric-value">{len(df_only_item_out)} 筆</div></div>', unsafe_allow_html=True)
    
    st.markdown("#### 🚚 今日物流分佈")
    if not df_ship_summary.empty:
        st.dataframe(df_ship_summary.groupby('logistics')['quantity'].sum().reset_index(name='件數'), use_container_width=True, hide_index=True)
    else: st.info("今日尚無物流登記資料")

with tabs[2]:
    cc1, cc2 = st.columns(2)
    dr = cc1.date_input("📅 日期範圍", [today, today])
    sel_plt = cc2.selectbox("📱 平台", ["全部"] + sorted([str(x) for x in df_o['platform'].unique() if x]))
    start_d, end_d = (dr[0], dr[1]) if len(dr) > 1 else (dr[0], dr[0])
    
    # 明細表過濾：絕對排除物流相關統計，保留純商品
    mask = (df_o['pure_date'] >= start_d) & (df_o['pure_date'] <= end_d)
    mask &= (df_o['p_name'] != "物流登記")
    mask &= (df_o['mode'] != "物流統計")
    if sel_plt != "全部": mask &= (df_o['platform'] == sel_plt)
    
    st.dataframe(df_o[mask].sort_values('tz_fixed', ascending=False)[['tz_fixed', 'p_name', 'quantity', 'mode', 'platform', 'logistics']], use_container_width=True, hide_index=True)

with tabs[3]:
    st.info("🚚 包裹總數登記歷史")
    df_l = df_o[(df_o['p_name'] == "物流登記") | (df_o['mode'] == "物流統計")].copy()
    st.dataframe(df_l.sort_values('tz_fixed', ascending=False)[['tz_fixed', 'platform', 'logistics', 'quantity']], use_container_width=True, hide_index=True)
    if st.button("🔄 刷新雲端數據"):
        st.cache_data.clear()
        st.rerun()
