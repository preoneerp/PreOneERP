import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 頁面配置與視覺設計 ---
st.set_page_config(page_title="ERP 雲端管理中心 v2.1", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #FDFBFA; }
    .status-card {
        background: white; padding: 20px; border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #FADBD8;
        text-align: center; margin-bottom: 20px;
    }
    .card-title { color: #888; font-size: 0.8rem; }
    .card-value { font-size: 1.5rem; font-weight: bold; color: #E8A0BF; }
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

# --- 3. 強化版數據處理函數 ---
def process_data(df):
    if df.empty: return df
    # 1. 統一轉小寫欄位
    df.columns = [c.lower() for c in df.columns]
    # 2. 處理時間戳 (轉換失敗的會變為 NaT)
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df = df.dropna(subset=['timestamp'])
        # 轉台北時間
        if df['timestamp'].dt.tz is None:
            df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
        df['timestamp'] = df['timestamp'].dt.tz_convert('Asia/Taipei').dt.tz_localize(None)
    return df

# --- 4. 登入邏輯 ---
def check_password():
    if st.session_state.get("password_correct", False): return True
    _, col_mid, _ = st.columns([1.2, 1, 1.2])
    with col_mid:
        st.markdown("<h2 style='text-align: center; color: #E8A0BF;'>🎀 雲端管理系統</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            u = st.text_input("帳號")
            p = st.text_input("密碼", type="password")
            if st.button("登入系統", use_container_width=True):
                auth = st.secrets.get("auth", {})
                if u in auth and str(p) == str(auth[u]["password"]):
                    st.session_state.update({"password_correct": True, "user_level": auth[u]["level"], "current_user": u})
                    st.rerun()
                else:
                    try:
                        res = supabase.table("users").select("*").eq("username", u).eq("password", p).execute()
                        if res.data:
                            st.session_state.update({"password_correct": True, "user_level": 9 if res.data[0]['role'] == 'admin' else 5, "current_user": u})
                            st.rerun()
                        else: st.error("🔒 帳號或密碼錯誤")
                    except: st.error("連線超時")
    return False

if check_password():
    user_level, curr_user = st.session_state["user_level"], st.session_state["current_user"]
    
    with st.sidebar:
        st.markdown(f"### 🌸 你好，{curr_user}")
        if st.button("🚪 安全登出", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    tabs = st.tabs(["☁️ 庫存清單", "📦 出貨紀錄", "🚚 物流件數", "💾 數據匯出"])

    # --- TAB 1: 庫存清單 ---
    with tabs[0]:
        res_p = supabase.table("products").select("*").execute()
        if res_p.data:
            df_p = process_data(pd.DataFrame(res_p.data))
            # 自動找供應商欄位
            v_col = 'v_name' if 'v_name' in df_p.columns else ('v_id' if 'v_id' in df_p.columns else None)
            sel_v = st.selectbox("🔍 供應商過濾", ["全部"] + sorted(list(df_p[v_col].unique()))) if v_col else "全部"
            f_df = df_p if sel_v == "全部" else df_p[df_p[v_col] == sel_v]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("品項數", len(f_df))
            c2.metric("總庫存", int(f_df['stock'].sum()))
            c3.metric("低庫存警示", len(f_df[f_df['stock'] < 10]))
            
            # 動態匹配商品名稱欄位
            name_col = 'name' if 'name' in f_df.columns else ('p_name' if 'p_name' in f_df.columns else f_df.columns[0])
            st.dataframe(f_df[[name_col, 'stock', v_col]].rename(columns={name_col:'商品','stock':'數量', v_col:'供應商'}), use_container_width=True, hide_index=True)

    # --- TAB 2: 出貨紀錄 (修正重點) ---
    with tabs[1]:
        res_o = supabase.table("order_history").select("*").execute()
        if res_o.data:
            df_o = process_data(pd.DataFrame(res_o.data))
            df_o['日期'] = df_o['timestamp'].dt.date
            
            with st.container(border=True):
                c1, c2, c3 = st.columns(3)
                # 預設範圍拉長到 30 天，避免看不到數據
                dr = c1.date_input("📅 範圍", [date.today() - timedelta(days=30), date.today()])
                
                # 容錯處理下拉選單
                plts = ["全部"] + sorted([str(x) for x in df_o['platform'].unique() if x])
                sel_plt = c2.selectbox("平台", plts)
                
                modes = ["全部"] + sorted([str(x) for x in df_o['mode'].unique() if x])
                sel_mode = c3.selectbox("模式", modes)
            
            # 安全篩選
            start_d = dr[0]
            end_d = dr[1] if len(dr) > 1 else dr[0]
            mask = (df_o['日期'] >= start_d) & (df_o['日期'] <= end_d)
            if sel_plt != "全部": mask &= (df_o['platform'] == sel_plt)
            if sel_mode != "全部": mask &= (df_o['mode'] == sel_mode)
            
            final_o = df_o[mask].sort_values('timestamp', ascending=False)
            
            if not final_o.empty:
                # 自動匹配 p_name 或 name
                p_col = 'p_name' if 'p_name' in final_o.columns else ('name' if 'name' in final_o.columns else final_o.columns[0])
                final_o['時間'] = final_o['timestamp'].dt.strftime('%m/%d %H:%M')
                st.dataframe(final_o[['時間', p_col, 'quantity', 'mode', 'platform', 'logistics']].rename(columns={p_col:'商品','quantity':'數量'}), use_container_width=True, hide_index=True)
                st.session_state["filtered_report"] = final_o
            else:
                st.info(f"💡 範圍 {start_d} ~ {end_d} 內無數據。雲端總共有 {len(df_o)} 筆歷史資料。")
        else:
            st.warning("雲端無歷史紀錄數據。")

    # --- TAB 3: 物流件數 ---
    with tabs[2]:
        res_l = supabase.table("shipping_log").select("*").execute()
        if res_l.data:
            df_l = process_data(pd.DataFrame(res_l.data))
            q_col = 'count' if 'count' in df_l.columns else ('quantity' if 'quantity' in df_l.columns else None)
            if q_col:
                st.metric("累計包裹總數", f"{int(df_l[q_col].sum())} 件")
                st.dataframe(df_l.sort_values('timestamp', ascending=False)[['platform','logistics', q_col, 'timestamp']], use_container_width=True, hide_index=True)

    # --- TAB 4: 數據匯出 ---
    with tabs[3]:
        if "filtered_report" in st.session_state:
            csv = st.session_state["filtered_report"].to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下載篩選報表 (CSV)", csv, f"Report_{date.today()}.csv", "text/csv", use_container_width=True)
