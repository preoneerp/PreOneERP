import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta
import pytz

# --- 1. 頁面配置與視覺設計 (莫蘭迪柔和色系) ---
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
    except Exception as e:
        st.error(f"連線失敗: {e}")
        return None

supabase = init_connection()

# --- 3. 時間轉換工具 (UTC -> Asia/Taipei) ---
def to_taipei_time(df, col='timestamp'):
    if df.empty or col not in df.columns:
        return df
    df[col] = pd.to_datetime(df[col])
    # 如果沒有時區資訊，先設定為 UTC，再轉換為台北
    if df[col].dt.tz is None:
        df[col] = df[col].dt.tz_localize('UTC')
    df[col] = df[col].dt.tz_convert('Asia/Taipei').dt.tz_localize(None)
    return df

# --- 4. 登入邏輯 ---
def check_password():
    if st.session_state.get("password_correct", False):
        return True

    _, col_mid, _ = st.columns([1.2, 1, 1.2])
    with col_mid:
        st.write("<br><br>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; color: #E8A0BF;'>🎀 雲端管理系統</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            u = st.text_input("帳號", placeholder="Username")
            p = st.text_input("密碼", type="password", placeholder="Password")
            
            def password_entered():
                auth = st.secrets.get("auth", {})
                if u in auth and str(p) == str(auth[u]["password"]):
                    st.session_state["password_correct"], st.session_state["user_level"], st.session_state["current_user"] = True, auth[u]["level"], u
                else:
                    try:
                        res = supabase.table("users").select("*").eq("username", u).eq("password", p).execute()
                        if res.data:
                            st.session_state["password_correct"] = True
                            st.session_state["user_level"] = 9 if res.data[0]['role'] == 'admin' else 5
                            st.session_state["current_user"] = u
                        else: st.error("🔒 帳號或密碼不正確")
                    except: st.error("🔒 驗證服務暫時不可用")
            st.button("登入系統", on_click=password_entered, use_container_width=True)
    return False

if check_password():
    user_level = st.session_state["user_level"]
    curr_user = st.session_state["current_user"]
    
    with st.sidebar:
        st.markdown(f"### 🌸 你好，{curr_user}")
        with st.expander("🔑 變更密碼"):
            new_p = st.text_input("新密碼", type="password")
            if st.button("更新密碼"):
                if new_p:
                    supabase.table("users").update({"password": new_p}).eq("username", curr_user).execute()
                    st.success("密碼已修改！")
                else: st.warning("不可為空")
        st.divider()
        if st.button("🚪 安全登出", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    tab_list = ["☁️ 庫存清單"]
    if user_level >= 5: tab_list.extend(["📦 出貨紀錄", "🚚 物流件數"])
    if user_level >= 9: tab_list.append("💾 數據匯出")
    tabs = st.tabs(tab_list)

    # --- TAB 1: 即時庫存 ---
    with tabs[0]:
        res_p = supabase.table("products").select("*").execute()
        if res_p.data:
            df_p = pd.DataFrame(res_p.data)
            df_p.columns = [c.lower() for c in df_p.columns]
            with st.container(border=True):
                c1, c2 = st.columns([2, 1])
                sel_v = c1.selectbox("🔍 供應商", ["✨ 全部"] + sorted(list(df_p['v_name'].unique())))
                safe_limit = c2.number_input("🛡️ 警示額度", min_value=0, value=10)
            
            f_df = df_p if sel_v == "✨ 全部" else df_p[df_p['v_name'] == sel_v]
            st.markdown(f"""<div class="dashboard-container">
                <div class="status-card card-1"><div class="card-title">📦 品項</div><div class="card-value">{len(f_df)}</div></div>
                <div class="status-card card-2"><div class="card-title">💎 在庫</div><div class="card-value">{int(f_df['stock'].sum())}</div></div>
                <div class="status-card card-3"><div class="card-title">⚠️ 低庫存</div><div class="card-value">{len(f_df[f_df['stock'] < safe_limit])}</div></div>
            </div>""", unsafe_allow_html=True)
            st.dataframe(f_df.assign(狀態=f_df['stock'].apply(lambda x: '❗ 補貨' if x < safe_limit else '✅ 正常'))
                         [['狀態', 'name', 'stock', 'v_name']].rename(columns={'name':'商品','stock':'數量','v_name':'供應商'}), 
                         use_container_width=True, hide_index=True, height=450)

    # --- TAB 2: 出貨紀錄 (台北時間) ---
    if user_level >= 5:
        with tabs[1]:
            res_o = supabase.table("order_history").select("*").neq("mode", "物流統計").execute()
            if res_o.data:
                df_o = to_taipei_time(pd.DataFrame(res_o.data))
                df_o.columns = [c.lower() for c in df_o.columns]
                df_o['日期'] = df_o['timestamp'].dt.date
                with st.container(border=True):
                    c1, c2, c3 = st.columns(3)
                    dr = c1.date_input("📅 範圍", [date.today() - timedelta(days=7), date.today()])
                    sel_plt = c2.selectbox("平台", ["全部"] + list(df_o['platform'].unique()))
                    sel_mode = c3.selectbox("模式", ["全部"] + list(df_o['mode'].unique()))
                
                mask = (df_o['日期'] >= dr[0]) & (df_o['日期'] <= (dr[1] if len(dr)>1 else dr[0]))
                if sel_plt != "全部": mask &= (df_o['platform'] == sel_plt)
                if sel_mode != "全部": mask &= (df_o['mode'] == sel_mode)
                
                final_o = df_o[mask].sort_values('timestamp', ascending=False)
                final_o['時間'] = final_o['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
                st.dataframe(final_o[['時間','p_name','quantity','mode','platform','logistics']].rename(columns={'p_name':'商品','quantity':'數量'}), use_container_width=True, hide_index=True)
                st.session_state["filtered_report"] = final_o

    # --- TAB 3: 物流件數 (台北時間) ---
    if user_level >= 5:
        with tabs[2]:
            res_l = supabase.table("order_history").select("*").eq("mode", "物流統計").execute()
            if res_l.data:
                df_l = to_taipei_time(pd.DataFrame(res_l.data))
                df_l.columns = [c.lower() for c in df_l.columns]
                st.markdown(f"""<div class="dashboard-container"><div class="status-card card-logistics">
                    <div class="card-title">🚚 台北時間累計包裹總數</div><div class="card-value">{int(df_l['quantity'].sum())} 件</div>
                </div></div>""", unsafe_allow_html=True)
                c1, c2 = st.columns([1, 2])
                c1.write("各平台統計")
                c1.dataframe(df_l.groupby('platform')['quantity'].sum().reset_index().rename(columns={'platform':'平台','quantity':'件數'}), hide_index=True)
                df_l['時間'] = df_l['timestamp'].dt.strftime('%m/%d %H:%M')
                c2.write("最近登打紀錄 (台北時間)")
                c2.dataframe(df_l.sort_values('timestamp', ascending=False)[['時間','platform','logistics','quantity']], use_container_width=True, hide_index=True)

    # --- TAB 4: 數據匯出 ---
    if user_level >= 9:
        with tabs[-1]:
            if "filtered_report" in st.session_state:
                csv = st.session_state["filtered_report"].to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 下載篩選報表 (CSV)", csv, f"Report_{date.today()}.csv", "text/csv", use_container_width=True)
