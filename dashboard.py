import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 頁面配置與柔和風格定義 ---
st.set_page_config(page_title="ERP 雲端管理中心", layout="wide", initial_sidebar_state="expanded")

# 自定義柔和風格 CSS
st.markdown("""
    <style>
    /* 全域背景 */
    .stApp { background-color: #FDFBFA; font-family: 'Segoe UI', 'PingFang TC', sans-serif; }
    
    /* 讓 stMetric 的容器大小一致 */
    div[data-testid="stMetric"] {
        background-color: white; 
        padding: 20px; 
        border-radius: 15px; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.03); 
        border: 1px solid #FADBD8;
        min-height: 120px; /* 確保高度一致 */
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    /* 側邊欄與按鈕樣式 */
    .stButton>button { border-radius: 20px; border: none; background-color: #E8A0BF; color: white; transition: 0.3s; }
    .stButton>button:hover { background-color: #BA94D1; transform: scale(1.02); }
    section[data-testid="stSidebar"] { background-color: #F9F3EE; border-right: 1px solid #F2E9E1; }
    
    /* 標籤視覺 */
    .warning-tag { background-color: #FF9EAA; color: white; padding: 2px 10px; border-radius: 10px; font-size: 0.8rem; font-weight: bold; }
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

# --- 3. 登入邏輯 (維持柔和視覺) ---
def check_password():
    if st.session_state.get("password_correct", False):
        return True

    _, col_mid, _ = st.columns([1.2, 1, 1.2])
    with col_mid:
        st.write("<br><br>", unsafe_allow_html=True)
        try:
            st.image("mascot.jpg", width=160)
        except:
            st.markdown("<h2 style='text-align: center; color: #E8A0BF;'>🎀 雲端管理系統</h2>", unsafe_allow_html=True)
        
        with st.container(border=True):
            st.markdown("<p style='text-align: center; color: #888;'>歡迎回來，請輸入帳號密碼</p>", unsafe_allow_html=True)
            u = st.text_input("帳號", placeholder="請輸入使用者名稱")
            p = st.text_input("密碼", type="password", placeholder="請輸入密碼")
            
            def password_entered():
                auth = st.secrets.get("auth", {})
                if u in auth and str(p) == str(auth[u]["password"]):
                    st.session_state["password_correct"] = True
                    st.session_state["user_level"] = auth[u]["level"]
                    st.session_state["current_user"] = u
                else:
                    st.error("🔒 密碼不正確，請再試一次")

            st.button("開啟美力系統", on_click=password_entered, use_container_width=True)
    return False

if check_password():
    user_level = st.session_state["user_level"]
    
    with st.sidebar:
        st.markdown(f"### 🌸 你好，{st.session_state['current_user']}")
        st.write(f"系統權限：Level {user_level}")
        st.divider()
        if st.button("🚪 安全登出", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    tab_list = ["☁️ 庫存清單"]
    if user_level >= 5: tab_list.append("📔 變動紀錄")
    if user_level >= 9: tab_list.append("💾 數據匯出")
    tabs = st.tabs(tab_list)

    # --- TAB 1: 即時庫存 (調整指標方塊大小一致) ---
    with tabs[0]:
        try:
            res_p = supabase.table("products").select("*").execute()
            if res_p.data:
                df_p = pd.DataFrame(res_p.data)
                df_p.columns = [c.lower() for c in df_p.columns]
                
                # 指標數據計算
                v_list = ["✨ 全部供應商"] + sorted([str(x) for x in df_p['v_name'].unique() if x])
                
                # 控制面板
                with st.container(border=True):
                    c_s1, c_s2, c_s3 = st.columns([1.5, 1, 1])
                    with c_s1:
                        sel_v = st.selectbox("選擇篩選供應商", v_list)
                    with c_s2:
                        safe_limit = st.number_input("🛡️ 設定警示庫存額度", min_value=0, value=10)
                
                filtered_df = df_p if sel_v == "✨ 全部供應商" else df_p[df_p['v_name'] == sel_v]
                low_count = len(filtered_df[filtered_df['stock'] < safe_limit])

                # --- 核心優化：等寬等高的指標方塊 ---
                m_col1, m_col2, m_col3 = st.columns(3)
                with m_col1:
                    st.metric("總產品項", f"{len(filtered_df)} 種")
                with m_col2:
                    st.metric("在庫件數", f"{int(filtered_df['stock'].sum())}")
                with m_col3:
                    # 讓補貨 Delta 呈現更溫柔
                    st.metric("需補貨品項", f"{low_count} 筆", 
                              delta=f"{low_count}" if low_count > 0 else None, 
                              delta_color="inverse")

                # 低庫存警示 Banner
                if low_count > 0:
                    st.markdown(f"""
                        <div style="background-color: #FFF0F0; padding: 15px; border-radius: 12px; border-left: 5px solid #FF9EAA; margin-bottom: 20px;">
                            <span style="color: #D32F2F; font-weight: bold;">📢 補貨提醒：</span>
                            目前有 {low_count} 項商品低於安全標準，請留意下方狀態。
                        </div>
                    """, unsafe_allow_html=True)

                # 表格顯示
                display_df = filtered_df.copy()
                display_df['狀態'] = display_df['stock'].apply(lambda x: '❗ 補貨' if x < safe_limit else '✅ 正常')
                rename_map = {'name': '商品名稱', 'stock': '在庫數量', 'v_name': '供應商', '狀態': '庫存狀態'}
                final_df = display_df.rename(columns=rename_map)
                
                st.dataframe(final_df[['庫存狀態', '商品名稱', '在庫數量', '供應商']], 
                             use_container_width=True, hide_index=True, height=450)
                
            else:
                st.info("雲端目前無庫存資料。")
        except Exception as e:
            st.error(f"讀取出錯: {e}")

    # --- TAB 2 & 3 (保持邏輯一致) ---
    if user_level >= 5:
        with tabs[1]:
            st.subheader("📔 歷史變動追蹤")
            # ... (歷史紀錄邏輯與前版本一致)
            try:
                res_o = supabase.table("order_history").select("*").execute()
                if res_o.data:
                    df_o = pd.DataFrame(res_o.data); df_o.columns = [c.lower() for c in df_o.columns]
                    df_o['timestamp'] = pd.to_datetime(df_o['timestamp'])
                    with st.container(border=True):
                        c1, c2, c3 = st.columns(3)
                        d_range = c1.date_input("📅 日期範圍", [date.today() - timedelta(days=30), date.today()])
                        sel_plt = c2.selectbox("平台篩選", ["全部"] + sorted([str(x) for x in df_o['platform'].unique() if x]))
                        sel_mode = c3.selectbox("類型篩選", ["全部"] + sorted([str(x) for x in df_o['mode'].unique() if x]))
                    
                    mask = (df_o['timestamp'].dt.date >= d_range[0]) & (df_o['timestamp'].dt.date <= d_range[1])
                    if sel_plt != "全部": mask &= (df_o['platform'] == sel_plt)
                    if sel_mode != "全部": mask &= (df_o['mode'] == sel_mode)
                    
                    final_o = df_o[mask].sort_values('timestamp', ascending=False).rename(columns={'p_name':'商品','quantity':'數量','mode':'模式','platform':'平台','logistics':'物流','timestamp':'時間'})
                    st.dataframe(final_o[['時間','商品','數量','模式','平台','物流']], use_container_width=True, hide_index=True)
                    st.session_state["filtered_report"] = final_o
            except: pass

    if user_level >= 9:
        with tabs[-1]:
            st.subheader("💾 報表儲存")
            if "filtered_report" in st.session_state and not st.session_state["filtered_report"].empty:
                csv = st.session_state["filtered_report"].to_csv(index=False).encode('utf-8-sig')
                st.download_button(label="📥 匯出 CSV 報表檔", data=csv, file_name=f"ERP_Report_{date.today()}.csv", use_container_width=True)
