import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 頁面配置與視覺設計 (維持 V0407.4 原版) ---
st.set_page_config(page_title="培玩雲端 ERP WEB V0407.41", layout="wide", initial_sidebar_state="expanded")

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
        box-shadow: 0 4px 15px rgba(230, 126, 34, 0.3);
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
    .product-unit { font-size: 0.9rem; color: #ABB2B9; margin-left: 4px; }
    .stDataFrame { border-radius: 12px; overflow: hidden; border: 1px solid #F0F0F0; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 初始化 ---
@st.cache_resource
def init_connection():
    try: return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except: return None

supabase = init_connection()

# --- 3. 數據抓取 ---
@st.cache_data(ttl=5)
def fetch_raw_data():
    try:
        # 維持 3000 筆物理抓取
        r1 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(0, 999).execute()
        r2 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(1000, 1999).execute()
        r3 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(2000, 2999).execute()
        raw_p = supabase.table("products").select("*").execute().data
        return pd.DataFrame(raw_p), pd.DataFrame(r1.data + r2.data + r3.data)
    except: return pd.DataFrame(), pd.DataFrame()

df_p_raw, df_o_raw = fetch_raw_data()

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

# --- 5. 主介面 ---
tabs = st.tabs(["📊 數據總覽", "☁️ 庫存狀態", "📦 出貨紀錄明細", "🚚 物流件數登記"])

# --- TAB 0: 數據總覽 ---
with tabs[0]:
    # 訂單數據處理
    df_o_tab0 = df_o_raw.copy()
    df_o_tab0.columns = [str(c).lower().strip() for c in df_o_tab0.columns]
    
    # 模糊對齊
    r_map = {'p_name':['p_name','product','品名','商品'], 'quantity':['qty','quantity','數量','件數']}
    for target, keys in r_map.items():
        found = next((c for c in df_o_tab0.columns if any(k in c for k in keys)), None)
        if found: df_o_tab0 = df_o_tab0.rename(columns={found: target})

    # 時間註記 (字串切片降噪)
    ts_str = df_o_tab0['timestamp'].astype(str).str.replace('T', ' ').str.replace('Z', '')
    df_o_tab0['date_str'] = ts_str.str[:10]
    df_o_tab0['quantity'] = pd.to_numeric(df_o_tab0['quantity'], errors='coerce').fillna(0)

    t_str = date.today().strftime("%Y-%m-%d")
    today_o = df_o_tab0[df_o_tab0['date_str'] == t_str]
    st.markdown(f"### 🎯 今日營運概況 ({t_str})")
    
    prods = [{"name": "專注力訓練機", "s": "專注力訓練機"},{"name": "24點數感大作戰", "s": "24點數感"},{"name": "顯微鏡相機", "s": "顯微鏡相機"},{"name": "創意卷軸畫", "s": "卷軸畫"},{"name": "攜行盒-藍", "s": "攜行盒-藍"},{"name": "攜行盒-粉", "s": "攜行盒-粉"}]
    p_cols = st.columns(6)
    df_items = today_o[~today_o['p_name'].astype(str).str.contains("物流|包裹", na=False)] if not today_o.empty else pd.DataFrame()
    
    for i, item in enumerate(prods):
        with p_cols[i]:
            qty = int(df_items[df_items['p_name'].astype(str).str.contains(item['s'], na=False)]['quantity'].sum()) if not df_items.empty else 0
            st.markdown(f'<div class="product-tag"><div class="product-name">{item["name"]}</div><div class="product-qty">{qty}<span class="product-unit"> 個</span></div></div>', unsafe_allow_html=True)
    
    st.write("<br>", unsafe_allow_html=True)
    col_m, col_logi = st.columns([1, 1.2])
    with col_m:
        st.markdown("#### 📈 今日核心指標")
        df_ship_all = df_o_tab0[df_o_tab0['p_name'].astype(str).str.contains("物流|包裹", na=False)]
        pkg_cnt = int(df_ship_all[df_ship_all["date_str"]==t_str]["quantity"].sum()) if not df_ship_all.empty else 0
        m1, m2 = st.columns(2); m3, m4 = st.columns(2)
        m1.markdown(f'<div class="metric-card"><div class="metric-label">今日出貨包裹</div><div class="metric-value">{pkg_cnt} 件</div></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="metric-card"><div class="metric-label">今日訂單明細</div><div class="metric-value">{len(df_items)} 筆</div></div>', unsafe_allow_html=True)
        # 低庫存統計
        df_p_tab0 = df_p_raw.copy()
        df_p_tab0.columns = [str(c).lower().strip() for c in df_p_tab0.columns]
        stock_col = next((c for c in df_p_tab0.columns if any(k in c for k in ['stock','庫存','在庫','qty'])), df_p_tab0.columns[1])
        low_stock = len(df_p_tab0[pd.to_numeric(df_p_tab0[stock_col], errors='coerce') < 10])
        m3.markdown(f'<div class="metric-card"><div class="metric-label">庫存警戒項目</div><div class="metric-value" style="color:red">{low_stock} 項</div></div>', unsafe_allow_html=True)
        m4.markdown(f'<div class="metric-card"><div class="metric-label">更新狀態</div><div class="metric-value" style="font-size:1.1rem; color:#27AE60;">V0407.41 已優化</div></div>', unsafe_allow_html=True)

    with col_logi:
        st.markdown("#### 🚚 當日物流分佈")
        today_ship = df_ship_all[df_ship_all['date_str'] == t_str] if not df_ship_all.empty else pd.DataFrame()
        if not today_ship.empty:
            # 模糊對齊物流商欄位
            l_col = next((c for c in today_ship.columns if any(k in c for k in ['logistics','物流'])), 'logistics')
            logi_sum = today_ship.groupby(l_col)['quantity'].sum().reset_index()
            st.dataframe(logi_sum.rename(columns={l_col:'渠道','quantity':'件數'}), use_container_width=True, hide_index=True)
        else: st.info("今日尚無物流登記數據")

# --- TAB 1: 庫存狀態 (獨立邏輯) ---
with tabs[1]:
    st.markdown("### ☁️ 現有庫存清單")
    df_p_tab1 = df_p_raw.copy()
    df_p_tab1.columns = [str(c).lower().strip() for c in df_p_tab1.columns]
    
    # 模糊對齊
    r_map_p = {'name':['name','product','品名'], 'stock':['stock','庫存','在庫','qty'], 'vendor':['vendor','供應','v_name']}
    for target, keys in r_map_p.items():
        found = next((c for c in df_p_tab1.columns if any(k in c for k in keys)), None)
        if found: df_p_tab1 = df_p_tab1.rename(columns={found: target})
    
    # 保底 iloc
    if 'name' not in df_p_tab1.columns: df_p_tab1['name'] = df_p_tab1.iloc[:, 0]
    if 'stock' not in df_p_tab1.columns: df_p_tab1['stock'] = df_p_tab1.iloc[:, 1]
    if 'vendor' not in df_p_tab1.columns: df_p_tab1['vendor'] = df_p_tab1.iloc[:, 2]

    sel_v = st.selectbox("🔍 依供應商篩選", ["全部供應商"] + sorted(list(df_p_tab1['vendor'].unique())))
    f_p = df_p_tab1 if sel_v == "全部供應商" else df_p_tab1[df_p_tab1['vendor'] == sel_v]
    st.dataframe(f_p[['name', 'stock', 'vendor']].rename(columns={'name':'商品名稱','stock':'在庫數量','vendor':'供應商'}), use_container_width=True, hide_index=True)

# --- TAB 2: 出貨紀錄明細 (獨立篩選 + 字串降噪) ---
with tabs[2]:
    st.markdown("### 📦 出貨紀錄明細")
    df_o_tab2 = df_o_raw.copy()
    df_o_tab2.columns = [str(c).lower().strip() for c in df_o_tab2.columns]
    
    # 模糊對齊關鍵欄位
    r_map2 = {'p_name':['p_name','product','品名','商品'], 'mode':['mode','模式'], 'platform':['platform','平台']}
    for target, keys in r_map2.items():
        found = next((c for c in df_o_tab2.columns if any(k in c for k in keys)), None)
        if found: df_o_tab2 = df_o_tab2.rename(columns={found: target})

    # 時間註記 (字串降噪：不經過 to_datetime 避免資料消失)
    ts_str2 = df_o_tab2['timestamp'].astype(str).str.replace('T', ' ').str.replace('Z', '')
    df_o_tab2['display_time'] = ts_str2.str[:16] # 顯示用
    df_o_tab2['date_str'] = ts_str2.str[:10]     # 篩選用
    df_o_tab2['dt_sort'] = pd.to_datetime(df_o_tab2['timestamp'], errors='coerce') # 排序用

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        dr = c1.date_input("📅 日期範圍", [date(2026, 3, 2), date.today()], key="dr_tab2")
        plt_f = ["全部平台"] + sorted(list(df_o_tab2['platform'].unique()))
        sel_plt = c2.selectbox("📱 銷售平台", plt_f, key="plt_tab2")
        mod_f = ["全部模式"] + sorted(list(df_o_tab2['mode'].unique()))
        sel_mod = c3.selectbox("🔃 交易模式", mod_f, key="mod_tab2")

    if not df_o_tab2.empty and len(dr) == 2:
        mask = (~df_o_tab2['p_name'].astype(str).str.contains("物流|包裹", na=False))
        mask &= (df_o_tab2['date_str'] >= dr[0].strftime("%Y-%m-%d")) & (df_o_tab2['date_str'] <= dr[1].strftime("%Y-%m-%d"))
        if sel_plt != "全部平台": mask &= (df_o_tab2['platform'] == sel_plt)
        if sel_mod != "全部模式": mask &= (df_o_tab2['mode'] == sel_mod)
        
        view_o = df_o_tab2[mask].sort_values('dt_sort', ascending=False)
        st.dataframe(view_o[['display_time', 'p_name', 'quantity', 'mode', 'platform', 'logistics']].rename(columns={
            'display_time':'時間註記','p_name':'商品名稱','quantity':'數量','mode':'交易模式','platform':'銷售平台','logistics':'物流單號'
        }), use_container_width=True, hide_index=True)

# --- TAB 3: 物流件數登記 (獨立統計 + 字串降噪) ---
with tabs[3]:
    st.markdown("### 🚚 物流件數登記")
    df_o_tab3 = df_o_raw.copy()
    df_o_tab3.columns = [str(c).lower().strip() for c in df_o_tab3.columns]
    
    # 模糊對齊
    r_map3 = {'p_name':['p_name','product','品名','商品'], 'logistics':['logistics','物流']}
    for target, keys in r_map3.items():
        found = next((c for c in df_o_tab3.columns if any(k in c for k in keys)), None)
        if found: df_o_tab3 = df_o_tab3.rename(columns={found: target})

    ts_str3 = df_o_tab3['timestamp'].astype(str).str.replace('T', ' ').str.replace('Z', '')
    df_o_tab3['display_time'] = ts_str3.str[:16]
    df_o_tab3['date_str'] = ts_str3.str[:10]
    df_o_tab3['dt_sort'] = pd.to_datetime(df_o_tab3['timestamp'], errors='coerce')
    df_o_tab3['quantity'] = pd.to_numeric(df_o_tab3['quantity'], errors='coerce').fillna(0)

    df_ent = df_o_tab3[df_o_tab3['p_name'].astype(str).str.contains("物流|包裹", na=False)]
    
    with st.container(border=True):
        l1, l2 = st.columns(2)
        ldr = l1.date_input("📅 統計週期", [date(2026, 3, 2), date.today()], key="dr_tab3")
        logi_f = ["全部物流"] + sorted(list(df_ent['logistics'].unique()))
        sel_logi = l2.selectbox("🚚 物流商/渠道", logi_f, key="logi_tab3")

    if not df_ent.empty and len(ldr) == 2:
        e_mask = (df_ent['date_str'] >= ldr[0].strftime("%Y-%m-%d")) & (df_ent['date_str'] <= ldr[1].strftime("%Y-%m-%d"))
        if sel_logi != "全部物流": e_mask &= (df_ent['logistics'] == sel_logi)
        
        df_res = df_ent[e_mask].sort_values('dt_sort', ascending=False)
        total_q = int(df_res['quantity'].sum())
        st.markdown(f'<div class="total-card"><div style="font-size:1.1rem; opacity:0.9;">週期件數總計 ({ldr[0]} ~ {ldr[1]})</div><div style="font-size:2.8rem;">{total_q} <span style="font-size:1.1rem;">件</span></div></div>', unsafe_allow_html=True)
        st.dataframe(df_res[['display_time', 'platform', 'logistics', 'quantity']].rename(columns={
            'display_time':'時間註記','platform':'來源平台','logistics':'物流渠道','quantity':'件數'
        }), use_container_width=True, hide_index=True)

if st.button("🔄 刷新雲端數據", use_container_width=True): st.cache_data.clear(); st.rerun()
