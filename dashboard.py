import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 頁面配置與視覺設計 ---
st.set_page_config(page_title="ERP 雲端管理中心", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stApp { background-color: #FDFBFA; }
    .dashboard-container { display: flex; gap: 20px; margin-bottom: 25px; flex-wrap: wrap; }
    .status-card {
        flex: 1; min-width: 200px; background: white; padding: 25px; border-radius: 20px;
        box-shadow: 0 10px 25px rgba(232, 160, 191, 0.1); border: 1px solid #FADBD8;
        text-align: center; transition: transform 0.3s ease;
    }
    .status-card:hover { transform: translateY(-5px); }
    .card-title { color: #888; font-size: 0.9rem; margin-bottom: 10px; }
    .card-value { font-size: 1.8rem; font-weight: bold; color: #444; }
    .card-1 { border-top: 5px solid #E8A0BF; } 
    .card-2 { border-top: 5px solid #BA94D1; } 
    .card-3 { border-top: 5px solid #FF9EAA; } 
    .card-logistics { border-top: 5px solid #E67E22; }
    .stButton>button { border-radius: 20px; border: none; background-color: #E8A0BF; color: white; }
    .stButton>button:hover { background-color: #BA94D1; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 初始化 Supabase ---
@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except: return None

supabase = init_connection()

# --- 3. 數據自動修復工具 (修復核心：相容 3/9 後的新舊格式) ---
def smart_process(df):
    if df is None or df.empty: return pd.DataFrame()
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    t_col = next((c for c in df.columns if any(keyword in c for keyword in ['timestamp', 'time', 'created_at'])), None)
    
    if t_col:
        # 1. 統一轉換為 datetime，不強制指定時區
        df[t_col] = pd.to_datetime(df[t_col], errors='coerce')
        df = df.dropna(subset=[t_col])
        
        # 2. 判斷格式：如果原本沒時區資訊，則視為 UTC 再轉台北；如果有時區(+08)，則保持不變
        def fix_timezone(dt):
            if dt.tzinfo is None:
                # 舊資料 (無時區) 視為 UTC 轉台北
                return dt.replace(tzinfo=pytz.UTC).astimezone(pytz.timezone('Asia/Taipei'))
            else:
                # 新資料 (已有時區) 直接轉為台北時間確保統一
                return dt.astimezone(pytz.timezone('Asia/Taipei'))

        import pytz
        # 這裡改用更簡單的邏輯：直接截取字串前 10 位作為 pure_date，最不受時區干擾
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
            u = st.text_input("帳號", placeholder="Username")
            p = st.text_input("密碼", type="password", placeholder="Password")
            if st.button("登入系統", use_container_width=True):
                auth = st.secrets.get("auth", {})
                if u in auth and str(p) == str(auth[u]["password"]):
                    st.session_state.update({"password_correct": True, "user_level": auth[u]["level"], "current_user": u})
                    st.rerun()
                else: st.error("🔒 帳號或密碼不正確")
    st.stop()

# --- 5. 主系統介面 ---
tabs = st.tabs(["☁️ 庫存清單", "📦 出貨紀錄", "🚚 物流件數", "💾 數據匯出"])

# --- TAB 1: 庫存清單 ---
with tabs[0]:
    res_p = supabase.table("products").select("*").execute()
    if res_p.data:
        df_p = smart_process(pd.DataFrame(res_p.data))
        v_col = 'v_name' if 'v_name' in df_p.columns else 'vendor' if 'vendor' in df_p.columns else df_p.columns[-1]
        
        with st.container(border=True):
            c1, c2 = st.columns([2, 1])
            sel_v = c1.selectbox("🔍 供應商", ["✨ 全部"] + sorted(list(df_p[v_col].unique())))
            safe_limit = c2.number_input("🛡️ 警示額度", min_value=0, value=10)
        
        f_df = df_p if sel_v == "✨ 全部" else df_p[df_p[v_col] == sel_v]
        
        st.markdown(f"""<div class="dashboard-container">
            <div class="status-card card-1"><div class="card-title">📦 品項</div><div class="card-value">{len(f_df)}</div></div>
            <div class="status-card card-2"><div class="card-title">💎 在庫</div><div class="card-value">{int(f_df['stock'].sum())}</div></div>
            <div class="status-card card-3"><div class="card-title">⚠️ 低庫存</div><div class="card-value">{len(f_df[f_df['stock'] < safe_limit])}</div></div>
        </div>""", unsafe_allow_html=True)
        
        f_df['狀態'] = f_df['stock'].apply(lambda x: '❗ 補貨' if x < safe_limit else '✅ 正常')
        name_col = 'name' if 'name' in f_df.columns else f_df.columns[1]
        st.dataframe(f_df[['狀態', name_col, 'stock', v_col]].rename(columns={name_col:'商品','stock':'數量', v_col:'供應商'}), 
                     use_container_width=True, hide_index=True, height=450)

# --- TAB 2: 出貨紀錄 ---
with tabs[1]:
    res_o = supabase.table("order_history").select("*").execute()
    if res_o.data:
        df_o = smart_process(pd.DataFrame(res_o.data))
        i_col = 'p_name' if 'p_name' in df_o.columns else 'name'
        p_col = 'platform' if 'platform' in df_o.columns else 'plt_name' if 'plt_name' in df_o.columns else 'platform'
        m_col = 'mode'
        
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns(4)
            dr = c1.date_input("📅 範圍", [date.today() - timedelta(days=7), date.today()], key="order_dr")
            sel_plt = c2.selectbox("平台", ["全部"] + sorted([str(x) for x in df_o[p_col].unique() if x]), key="order_plt")
            sel_mode = c3.selectbox("模式", ["全部"] + sorted([str(x) for x in df_o[m_col].unique() if x]) if m_col in df_o.columns else ["全部"], key="order_mode")
            items_list = sorted([str(x) for x in df_o[i_col].unique() if x and "物流登記" not in str(x)])
            sel_item = c4.selectbox("商品搜尋", ["全部"] + items_list)

        start_d, end_d = (dr[0], dr[1]) if len(dr) > 1 else (dr[0], dr[0])
        
        mask = (df_o['pure_date'] >= start_d) & (df_o['pure_date'] <= end_d)
        mask &= (~df_o[i_col].str.contains("物流登記", na=False))
        if sel_plt != "全部": mask &= (df_o[p_col] == sel_plt)
        if m_col in df_o.columns and sel_mode != "全部": mask &= (df_o[m_col] == sel_mode)
        if sel_item != "全部": mask &= (df_o[i_col] == sel_item)
        
        final_o = df_o[mask].sort_values('tz_fixed', ascending=False)
        if not final_o.empty:
            final_o['時間'] = final_o['tz_fixed'].dt.strftime('%Y-%m-%d %H:%M')
            cols_to_show = ['時間', i_col, 'quantity', p_col, 'logistics']
            if m_col in final_o.columns: cols_to_show.insert(3, m_col)
            st.dataframe(final_o[cols_to_show].rename(columns={i_col:'商品','quantity':'數量'}), use_container_width=True, hide_index=True)
            st.session_state["filtered_report"] = final_o
        else: st.info("💡 目前範圍內無出貨數據。")

# --- TAB 3: 物流件數 (修正 3/9 後不顯示件數的核心區塊) ---
with tabs[2]:
    # 同時讀取兩個表
    res_l = supabase.table("shipping_log").select("*").execute()
    res_o_log = supabase.table("order_history").select("*").execute()
    
    df_l = smart_process(pd.DataFrame(res_l.data))
    df_o_all = smart_process(pd.DataFrame(res_o_log.data))
    
    def get_col(df, options):
        if df.empty: return None
        for opt in options:
            if opt in df.columns: return opt
        return None

    o_name_col = get_col(df_o_all, ['p_name', 'name'])
    
    # 篩選出包含「物流登記」字眼的紀錄 (這通常是 3/9 之後新邏輯產生的)
    df_entry = pd.DataFrame()
    if not df_o_all.empty and o_name_col:
        df_entry = df_o_all[df_o_all[o_name_col].str.contains("物流登記", na=False)].copy()

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        l_dr = c1.date_input("📅 時間範圍", [date.today() - timedelta(days=7), date.today()], key="logi_dr")
        l_start, l_end = (l_dr[0], l_dr[1]) if len(l_dr) > 1 else (l_dr[0], l_dr[0])
        
        # 合併平台清單
        p_list = []
        if not df_l.empty: p_list += df_l['platform'].tolist()
        if not df_entry.empty: p_list += df_entry['platform'].tolist()
        sel_l_plt = c2.selectbox("平台篩選", ["全部"] + sorted([str(x) for x in set(p_list) if x]), key="logi_plt")
        
        # 合併物流清單
        lg_list = []
        if not df_l.empty: lg_list += df_l['logistics'].tolist()
        if not df_entry.empty: lg_list += df_entry['logistics'].tolist()
        sel_l_logi = c3.selectbox("物流方式", ["全部"] + sorted([str(x) for x in set(lg_list) if x]), key="logi_way")

    # 執行篩選
    if not df_entry.empty:
        e_mask = (df_entry['pure_date'] >= l_start) & (df_entry['pure_date'] <= l_end)
        if sel_l_plt != "全部": e_mask &= (df_entry['platform'] == sel_l_plt)
        if sel_l_logi != "全部": e_mask &= (df_entry['logistics'] == sel_l_logi)
        df_entry = df_entry[e_mask]

    if not df_l.empty:
        b_mask = (df_l['pure_date'] >= l_start) & (df_l['pure_date'] <= l_end)
        if sel_l_plt != "全部": b_mask &= (df_l['platform'] == sel_l_plt)
        if sel_l_logi != "全部": b_mask &= (df_l['logistics'] == sel_l_logi)
        df_l = df_l[b_mask]

    # 計算總件數
    total = (int(df_l['count'].sum()) if not df_l.empty else 0) + (int(df_entry['quantity'].sum()) if not df_entry.empty else 0)
    
    st.markdown(f"""<div class="dashboard-container"><div class="status-card card-logistics">
        <div class="card-title">🚚 篩選累計包裹總數</div><div class="card-value">{total} 件</div>
    </div></div>""", unsafe_allow_html=True)
    
    if not df_entry.empty:
        st.write("📋 3/10 之後新版物流紀錄 (來自 Order History)")
        df_entry['時間顯示'] = df_entry['tz_fixed'].dt.strftime('%m/%d %H:%M')
        st.dataframe(df_entry[['時間顯示', 'platform', 'logistics', 'quantity']].rename(columns={'quantity':'件數','platform':'平台','logistics':'物流'}), use_container_width=True, hide_index=True)

    if not df_l.empty:
        st.write("🚚 3/9 之前舊版物流紀錄 (來自 Shipping Log)")
        df_l['時間顯示'] = df_l['tz_fixed'].dt.strftime('%m/%d %H:%M')
        st.dataframe(df_l.sort_values('tz_fixed', ascending=False)[['時間顯示', 'platform', 'logistics', 'count']].rename(columns={'count':'件數','platform':'平台','logistics':'物流'}), use_container_width=True, hide_index=True)

# --- TAB 4: 數據匯出 ---
with tabs[3]:
    if "filtered_report" in st.session_state:
        csv = st.session_state["filtered_report"].to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載篩選報表", csv, f"Report_{date.today()}.csv", "text/csv", use_container_width=True)
