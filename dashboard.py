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
    /* 基礎指標卡片 */
    .metric-card {
        background: white; padding: 20px; border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05); border-left: 5px solid #E8A0BF;
        text-align: left; margin-bottom: 10px;
    }
    .metric-value { font-size: 1.8rem; font-weight: bold; color: #2C3E50; }
    .metric-label { color: #7F8C8D; font-size: 0.9rem; }
    
    /* 商品標籤卡片式設計 */
    .product-tag {
        background: #ffffff;
        border: 1px solid #eee;
        border-radius: 12px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .product-name {
        font-size: 1rem;
        color: #5D6D7E;
        margin-bottom: 5px;
        font-weight: 500;
        height: 2.5rem; 
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .product-qty {
        font-size: 2rem;
        font-weight: 800;
        color: #E67E22;
    }
    .product-unit {
        font-size: 0.8rem;
        color: #ABB2B9;
        margin-left: 3px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 初始化 Supabase ---
@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"連線失敗: {e}")
        return None

supabase = init_connection()

# --- 3. 數據自動處理工具 (強化去空格邏輯) ---
def smart_process(df):
    if df is None or df.empty: return pd.DataFrame()
    
    # 1. 欄位名稱標準化
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    # 2. 【核心修復】自動修剪所有文字內容的前後空格
    # 解決 "官網 " (多空格) 與 "官網" (篩選器) 不匹配的問題
    for col in df.select_dtypes(['object']).columns:
        df[col] = df[col].astype(str).str.strip()
    
    # 3. 處理時間欄位
    t_col = next((c for c in df.columns if any(keyword in c for keyword in ['timestamp', 'time', 'created_at'])), None)
    if t_col:
        # 強制轉為台北時間並移除時區屬性，確保篩選正確
        df['tz_fixed'] = pd.to_datetime(df[t_col], utc=True).dt.tz_convert('Asia/Taipei').dt.tz_localize(None)
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

# --- 5. 數據抓取 ---
@st.cache_data(ttl=60) 
def fetch_all_data():
    try:
        res_p = supabase.table("products").select("*").execute()
        res_o = supabase.table("order_history").select("*").execute()
        return pd.DataFrame(res_p.data), pd.DataFrame(res_o.data)
    except:
        return pd.DataFrame(), pd.DataFrame()

raw_p, raw_o = fetch_all_data()
df_p = smart_process(raw_p)
df_o = smart_process(raw_o)

# --- 6. 主介面設計 ---
tabs = st.tabs(["📊 數據總覽", "☁️ 庫存狀態", "📦 出貨紀錄明細", "🚚 物流件數登記"])

# --- TAB 0: 數據總覽 ---
with tabs[0]:
    today = date.today()
    this_month = today.replace(day=1)
    
    # 數據預處理
    today_o = df_o[df_o['pure_date'] == today]
    df_ship_entry = df_o[df_o['p_name'].str.contains("物流登記", na=False)]
    today_ship_all = df_ship_entry[df_ship_entry['pure_date'] == today]
    
    st.markdown(f"### 🎯 今日純出貨數量統計 ({today})")
    
    # 定義精確搜尋標籤
    target_prods = [
        {"name": "專注力訓練機", "search": "舒爾特專注力訓練機Ⅱ"},
        {"name": "24點數感大作戰", "search": "24點數感邏輯大作戰"},
        {"name": "顯微鏡相機", "search": "顯微鏡相機"},
        {"name": "創意卷軸畫", "search": "滾動創意卷軸畫(主機+空白卷)"},
        {"name": "攜行盒-藍", "search": "攜行盒-藍(直接出貨)"},
        {"name": "攜行盒-粉", "search": "攜行盒-粉(直接出貨)"}
    ]
    
    prod_cols = st.columns(6)
    # 僅統計 mode 為 '出貨' 的紀錄
    df_only_out = today_o[today_o['mode'] == '出貨']
    
    for i, item in enumerate(target_prods):
        with prod_cols[i]:
            # 精確比對內容
            p_mask = (df_only_out['p_name'] == item['search'])
            qty = int(df_only_out[p_mask]['quantity'].sum())
            
            st.markdown(f"""
                <div class="product-tag">
                    <div class="product-name">{item['name']}</div>
                    <div class="product-qty">{qty}<span class="product-unit">個</span></div>
                </div>
            """, unsafe_allow_html=True)

    st.write("<br>", unsafe_allow_html=True)
    st.markdown("### 📈 營運關鍵指標")
    
    m1, m2, m3, m4 = st.columns(4)
    today_total_pkgs = today_ship_all['quantity'].sum()
    month_total_pkgs = df_ship_entry[df_ship_entry['pure_date'] >= this_month]['quantity'].sum()
    
    with m1: st.markdown(f'<div class="metric-card"><div class="metric-label">今日出貨包裹</div><div class="metric-value">{int(today_total_pkgs)} 件</div></div>', unsafe_allow_html=True)
    with m2: st.markdown(f'<div class="metric-card"><div class="metric-label">本月累計包裹</div><div class="metric-value">{int(month_total_pkgs)} 件</div></div>', unsafe_allow_html=True)
    with m3: st.markdown(f'<div class="metric-card"><div class="metric-label">今日訂單品項筆數</div><div class="metric-value">{len(today_o[~today_o["p_name"].str.contains("物流登記", na=False)])} 筆</div></div>', unsafe_allow_html=True)
    with m4: st.markdown(f'<div class="metric-card"><div class="metric-label">低庫存警戒</div><div class="metric-value" style="color:red">{len(df_p[df_p["stock"] < 10])} 項</div></div>', unsafe_allow_html=True)

    st.write("<br>", unsafe_allow_html=True)
    
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("#### 🚚 今日各物流統計")
        if not today_ship_all.empty:
            logi_stats = today_ship_all.groupby('logistics')['quantity'].sum().reset_index()
            logi_stats.columns = ['物流方式', '件數']
            st.dataframe(logi_stats, use_container_width=True, hide_index=True)
        else:
            st.info("今日尚無物流登記數據")
            
    with col_r:
        st.markdown("#### 📉 包裹趨勢圖")
        trend_data = df_ship_entry.groupby('pure_date')['quantity'].sum().reset_index()
        if not trend_data.empty:
            trend_data = trend_data.set_index('pure_date')
            st.line_chart(trend_data, use_container_width=True)

# --- TAB 1: 庫存狀態 ---
with tabs[1]:
    with st.container(border=True):
        c1, c2 = st.columns([2, 1])
        v_col = 'v_name' if 'v_name' in df_p.columns else 'vendor' if 'vendor' in df_p.columns else df_p.columns[-1]
        sel_v = c1.selectbox("🔍 供應商篩選", ["✨ 全部"] + sorted(list(df_p[v_col].unique())))
        safe_limit = c2.number_input("🛡️ 預警數量設定", min_value=0, value=10)
    
    f_df_p = df_p if sel_v == "✨ 全部" else df_p[df_p[v_col] == sel_v]
    f_df_p['狀態'] = f_df_p['stock'].apply(lambda x: '❗ 補貨' if x < safe_limit else '✅ 正常')
    st.dataframe(f_df_p[['狀態', 'name', 'stock', v_col]].rename(columns={'name':'商品名稱','stock':'在庫數量',v_col:'供應商'}), use_container_width=True, hide_index=True)

# --- TAB 2: 出貨紀錄明細 ---
with tabs[2]:
    with st.container(border=True):
        cc1, cc2, cc3 = st.columns(3)
        dr = cc1.date_input("📅 日期範圍", [today - timedelta(days=7), today])
        # 這裡的下拉選單會因為 smart_process 自動去空格，保證能選到正確資料
        sel_plt = cc2.selectbox("📱 平台", ["全部"] + sorted([str(x) for x in df_o['platform'].unique() if x]))
        sel_mode = cc3.selectbox("🔃 模式", ["全部"] + sorted([str(x) for x in df_o['mode'].unique() if x]))

    start_d, end_d = (dr[0], dr[1]) if len(dr) > 1 else (dr[0], dr[0])
    mask = (df_o['pure_date'] >= start_d) & (df_o['pure_date'] <= end_d)
    mask &= (~df_o['p_name'].str.contains("物流登記", na=False))
    if sel_plt != "全部": mask &= (df_o['platform'] == sel_plt)
    if sel_mode != "全部": mask &= (df_o['mode'] == sel_mode)
    
    final_o = df_o[mask].sort_values('tz_fixed', ascending=False)
    final_o['時間'] = final_o['tz_fixed'].dt.strftime('%Y-%m-%d %H:%M')
    st.dataframe(final_o[['時間', 'p_name', 'quantity', 'mode', 'platform', 'logistics']].rename(columns={'p_name':'商品','quantity':'數量'}), use_container_width=True, hide_index=True)

# --- TAB 3: 物流件數登記 ---
with tabs[3]:
    with st.container(border=True):
        lc1, lc2, lc3 = st.columns(3)
        l_dr = lc1.date_input("📅 物流日期", [today - timedelta(days=7), today])
        sel_l_plt = lc2.selectbox("平台 ", ["全部"] + sorted([str(x) for x in df_o['platform'].unique() if x]))
        sel_l_logi = lc3.selectbox("物流 ", ["全部"] + sorted([str(x) for x in df_o['logistics'].unique() if x]))

    l_start, l_end = (l_dr[0], l_dr[1]) if len(l_dr) > 1 else (l_dr[0], l_dr[0])
    df_entry = df_o[df_o['p_name'].str.contains("物流登記", na=False)].copy()
    e_mask = (df_entry['pure_date'] >= l_start) & (df_entry['pure_date'] <= l_end)
    if sel_l_plt != "全部": e_mask &= (df_entry['platform'] == sel_l_plt)
    if sel_l_logi != "全部": e_mask &= (df_entry['logistics'] == sel_l_logi)
    df_entry = df_entry[e_mask]

    st.markdown(f"""<div style="background:#E67E22; color:white; padding:15px; border-radius:15px; text-align:center; margin-bottom:20px">
        <div style="font-size:0.9rem">🚚 篩選區間總包裹數</div>
        <div style="font-size:2.2rem; font-weight:bold">{int(df_entry['quantity'].sum())} 件</div>
    </div>""", unsafe_allow_html=True)
    
    df_entry['時間顯示'] = df_entry['tz_fixed'].dt.strftime('%m/%d %H:%M')
    st.dataframe(df_entry[['時間顯示', 'platform', 'logistics', 'quantity']].rename(columns={'platform':'平台','logistics':'物流','quantity':'件數'}), use_container_width=True, hide_index=True)

    if st.button("🔄 刷新雲端數據", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
