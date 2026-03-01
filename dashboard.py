import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 頁面配置與進階視覺設計 ---
st.set_page_config(page_title="ERP 雲端管理中心", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .stApp { background-color: #FDFBFA; }
    
    /* 自定義卡片容器 */
    .dashboard-container {
        display: flex;
        gap: 20px;
        margin-bottom: 25px;
    }
    
    .status-card {
        flex: 1;
        background: white;
        padding: 25px;
        border-radius: 20px;
        box-shadow: 0 10px 25px rgba(232, 160, 191, 0.1);
        border: 1px solid #FADBD8;
        text-align: center;
        transition: transform 0.3s ease;
    }
    
    .status-card:hover { transform: translateY(-5px); }
    
    .card-title { color: #888; font-size: 0.9rem; margin-bottom: 10px; }
    .card-value { font-size: 1.8rem; font-weight: bold; color: #444; }
    
    /* 莫蘭迪色系裝飾條 */
    .card-1 { border-top: 5px solid #E8A0BF; } 
    .card-2 { border-top: 5px solid #BA94D1; } 
    .card-3 { border-top: 5px solid #FF9EAA; } 
    .card-logistics { border-top: 5px solid #E67E22; } /* 物流專用色 */
    
    .stButton>button { border-radius: 20px; border: none; background-color: #E8A0BF; color: white; }
    .stButton>button:hover { background-color: #BA94D1; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 初始化 Supabase ---
@st.cache_resource
def init_connection():
    try:
        # 優先從 secrets 讀取，若無則手動填入（建議維持 secrets 安全性）
        url = st.secrets.get("SUPABASE_URL", "https://rpxhuseeabuwujokdvfp.supabase.co")
        key = st.secrets.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...") 
        return create_client(url, key)
    except Exception as e:
        st.error(f"連線失敗: {e}")
        return None

supabase = init_connection()

# --- 3. 登入邏輯 (支援資料庫驗證) ---
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
                # 優先比對 Secrets 中的管理員，其次可比對資料庫 users 表
                auth = st.secrets.get("auth", {})
                if u in auth and str(p) == str(auth[u]["password"]):
                    st.session_state["password_correct"] = True
                    st.session_state["user_level"] = auth[u]["level"]
                    st.session_state["current_user"] = u
                else:
                    # 嘗試從 Supabase users 表驗證
                    try:
                        res = supabase.table("users").select("*").eq("username", u).eq("password", p).execute()
                        if res.data:
                            st.session_state["password_correct"] = True
                            st.session_state["user_level"] = 9 if res.data[0]['role'] == 'admin' else 5
                            st.session_state["current_user"] = u
                        else: st.error("🔒 帳號或密碼不正確")
                    except: st.error("🔒 登入驗證失敗")

            st.button("登入系統", on_click=password_entered, use_container_width=True)
    return False

if check_password():
    user_level = st.session_state["user_level"]
    current_user = st.session_state["current_user"]
    
    with st.sidebar:
        st.markdown(f"### 🌸 你好，{current_user}")
        
        # --- 新增：密碼變更功能 ---
        with st.expander("🔑 變更個人密碼"):
            new_pw = st.text_input("新密碼", type="password")
            if st.button("確認修改"):
                if new_pw:
                    try:
                        supabase.table("users").update({"password": new_pw}).eq("username", current_user).execute()
                        st.success("密碼已更新！")
                    except: st.error("更新失敗")
                else: st.warning("請輸入密碼")

        st.divider()
        if st.button("🚪 安全登出", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    # --- 分頁管理 ---
    tab_list = ["☁️ 庫存清單"]
    if user_level >= 5: tab_list.extend(["📦 出貨紀錄", "🚚 物流件數"])
    if user_level >= 9: tab_list.append("💾 數據匯出")
    tabs = st.tabs(tab_list)

    # --- TAB 1: 即時庫存 (排除物流統計項) ---
    with tabs[0]:
        try:
            res_p = supabase.table("products").select("*").execute()
            if res_p.data:
                df_p = pd.DataFrame(res_p.data)
                df_p.columns = [c.lower() for c in df_p.columns]
                
                with st.container(border=True):
                    c1, c2 = st.columns([2, 1])
                    v_list = ["✨ 全部供應商"] + sorted([str(x) for x in df_p['v_name'].unique() if x])
                    sel_v = c1.selectbox("🔍 篩選供應商", v_list)
                    safe_limit = c2.number_input("🛡️ 警示額度", min_value=0, value=10)
                
                filtered_df = df_p if sel_v == "✨ 全部供應商" else df_p[df_p['v_name'] == sel_v]
                low_count = len(filtered_df[filtered_df['stock'] < safe_limit])
                total_stock = int(filtered_df['stock'].sum())

                st.markdown(f"""
                    <div class="dashboard-container">
                        <div class="status-card card-1">
                            <div class="card-title">📦 總產品項</div>
                            <div class="card-value">{len(filtered_df)} <span style="font-size:1rem;">種</span></div>
                        </div>
                        <div class="status-card card-2">
                            <div class="card-title">💎 在庫總量</div>
                            <div class="card-value">{total_stock} <span style="font-size:1rem;">件</span></div>
                        </div>
                        <div class="status-card card-3">
                            <div class="card-title">⚠️ 需補貨品項</div>
                            <div class="card-value" style="color: {'#FF9EAA' if low_count > 0 else '#444'};">
                                {low_count} <span style="font-size:1rem;">筆</span>
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                display_df = filtered_df.copy()
                display_df['狀態'] = display_df['stock'].apply(lambda x: '❗ 補貨' if x < safe_limit else '✅ 正常')
                final_df = display_df.rename(columns={'name':'商品名稱','stock':'數量','v_name':'供應商','狀態':'庫存狀態'})
                st.dataframe(final_df[['庫存狀態', '商品名稱', '數量', '供應商']], 
                             use_container_width=True, hide_index=True, height=500)
        except Exception as e: st.error(f"庫存讀取失敗: {e}")

    # --- TAB 2: 出貨紀錄 (排除物流統計項，避免干擾報表) ---
    if user_level >= 5:
        with tabs[1]:
            st.subheader("📦 出貨歷史追蹤")
            try:
                # 核心修正：neq('mode', '物流統計') 確保這分頁只看商品異動
                res_o = supabase.table("order_history").select("*").neq("mode", "物流統計").execute()
                if res_o.data:
                    df_o = pd.DataFrame(res_o.data)
                    df_o.columns = [c.lower() for c in df_o.columns]
                    df_o['timestamp'] = pd.to_datetime(df_o['timestamp'])
                    df_o['日期'] = df_o['timestamp'].dt.date

                    with st.container(border=True):
                        c1, c2, c3 = st.columns(3)
                        d_range = c1.date_input("📅 日期範圍", [date.today() - timedelta(days=30), date.today()], key="date_inv")
                        platforms = ["全部"] + sorted([str(x) for x in df_o['platform'].unique() if x])
                        sel_plt = c2.selectbox("平台篩選", platforms)
                        modes = ["全部"] + sorted([str(x) for x in df_o['mode'].unique() if x])
                        sel_mode = c3.selectbox("出貨類型", modes)

                    mask = (df_o['日期'] >= d_range[0]) & (df_o['日期'] <= (d_range[1] if len(d_range)>1 else d_range[0]))
                    if sel_plt != "全部": mask &= (df_o['platform'] == sel_plt)
                    if sel_mode != "全部": mask &= (df_o['mode'] == sel_mode)
                    
                    show_o = df_o[mask].sort_values('timestamp', ascending=False)
                    st.dataframe(show_o.rename(columns={'p_name':'商品','quantity':'數量','mode':'模式','platform':'平台','logistics':'物流','timestamp':'時間'})
                                 [['時間','商品','數量','模式','平台','物流']], use_container_width=True, hide_index=True)
                    st.session_state["filtered_report"] = show_o
                else: st.warning("無商品出貨紀錄。")
            except Exception as e: st.error(f"讀取失敗: {e}")

    # --- TAB 3: 物流件數 (對應桌面版 Page 4) ---
    if user_level >= 5:
        with tabs[2]:
            st.subheader("🚚 平台物流包裹總計")
            try:
                # 核心修正：只讀取 mode='物流統計'
                res_l = supabase.table("order_history").select("*").eq("mode", "物流統計").execute()
                if res_l.data:
                    df_l = pd.DataFrame(res_l.data)
                    df_l.columns = [c.lower() for c in df_l.columns]
                    df_l['timestamp'] = pd.to_datetime(df_l['timestamp'])
                    
                    # 統計小卡
                    total_pkg = int(df_l['quantity'].sum())
                    plt_pkg = df_l.groupby('platform')['quantity'].sum().to_dict()
                    
                    st.markdown(f"""
                        <div class="dashboard-container">
                            <div class="status-card card-logistics">
                                <div class="card-title">📦 累計包裹總數</div>
                                <div class="card-value">{total_pkg} <span style="font-size:1rem;">件</span></div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.write("各平台佔比")
                        st.dataframe(pd.DataFrame(plt_pkg.items(), columns=['平台', '總件數']), hide_index=True)
                    with c2:
                        st.write("詳細登打紀錄")
                        st.dataframe(df_l.sort_values('timestamp', ascending=False)[['timestamp', 'platform', 'logistics', 'quantity']], 
                                     use_container_width=True, hide_index=True)
                else: st.info("目前無物流統計數據。")
            except Exception as e: st.error(f"物流讀取失敗: {e}")

    # --- TAB 4: 報表匯出 ---
    if user_level >= 9:
        with tabs[-1]:
            st.subheader("💾 數據匯出中心")
            if "filtered_report" in st.session_state and not st.session_state["filtered_report"].empty:
                csv = st.session_state["filtered_report"].to_csv(index=False).encode('utf-8-sig')
                st.download_button(label="📥 下載已篩選的出貨報表 (CSV)", data=csv, file_name=f"ERP_Report_{date.today()}.csv", use_container_width=True)
            else: st.info("💡 請先到『出貨紀錄』分頁進行篩選。")
