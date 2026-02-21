import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta
from PIL import Image

# --- 1. 頁面配置與樣式 ---
st.set_page_config(page_title="ERP 雲端管理系統 v22.9", layout="wide")

# 自定義 CSS 讓警告更明顯
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; border: 1px solid #f0f2f6; padding: 10px; border-radius: 10px; }
    .low-stock { color: #E74C3C; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 登入邏輯 (含圖片與權限) ---
def check_password():
    def password_entered():
        auth_data = st.secrets.get("auth", {})
        u_name = st.session_state.get("username", "")
        u_pw = st.session_state.get("password", "")
        if u_name in auth_data and str(u_pw) == str(auth_data[u_name]["password"]):
            st.session_state["password_correct"] = True
            st.session_state["current_user"] = u_name
            st.session_state["user_level"] = auth_data[u_name]["level"]
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        _, center_col, _ = st.columns([1, 2, 1])
        with center_col:
            # 補回 LOGIN 圖片
            try:
                img = Image.open("mascot.jpg")
                st.image(img, width=220)
            except:
                st.markdown("### 🧧 招財進寶 ERP")
            
            with st.container(border=True):
                st.subheader("系統登入")
                st.text_input("帳號", key="username")
                st.text_input("密碼", type="password", key="password")
                st.button("登入系統", on_click=password_entered, use_container_width=True)
                if st.session_state.get("password_correct") == False:
                    st.error("❌ 帳號或密碼錯誤")
        return False
    return st.session_state["password_correct"]

if check_password():
    # --- 3. 初始化 Supabase ---
    @st.cache_resource
    def init_connection():
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    
    supabase = init_connection()
    user_level = st.session_state["user_level"]

    # --- 4. 側邊欄權限資訊 ---
    with st.sidebar:
        st.title("👤 使用者資訊")
        st.write(f"當前用戶: **{st.session_state['current_user']}**")
        st.write(f"權限等級: `Level {user_level}`")
        if st.button("🚪 登出系統"):
            st.session_state.clear()
            st.rerun()

    # --- 5. 主分頁架構 (根據權限顯示) ---
    tabs_labels = ["📦 即時庫存概況"]
    if user_level >= 5:
        tabs_labels.append("🚚 歷史紀錄查詢")
    if user_level >= 9:
        tabs_labels.append("📊 報表匯出中心")
    
    tabs = st.tabs(tabs_labels)

    # --- 分頁：庫存概況 (含庫存警示) ---
    with tabs[0]:
        st.subheader("📢 庫存警示與監控")
        res_p = supabase.table("products").select("name, stock, v_name").execute()
        if res_p.data:
            df_p = pd.DataFrame(res_p.data)
            df_p.columns = ['商品名稱', '在庫數量', '供應商']
            
            # 庫存警示邏輯 (低於 10)
            low_stock_df = df_p[df_p['在庫數量'] < 10]
            if not low_stock_df.empty:
                st.error(f"⚠️ 警告：有 {len(low_stock_df)} 項商品庫存不足！")
                st.dataframe(low_stock_df, hide_index=True, use_container_width=True)
            else:
                st.success("✅ 目前所有商品庫存充足")
            
            st.divider()
            st.subheader("📋 所有庫存清單")
            st.dataframe(df_p, use_container_width=True, hide_index=True)
        else:
            st.info("尚無庫存資料。")

    # --- 分頁：歷史紀錄 (含完整篩選) ---
    if user_level >= 5:
        with tabs[1]:
            st.subheader("🔎 歷史紀錄查詢")
            res_o = supabase.table("order_history").select("*").execute()
            if res_o.data:
                df_o = pd.DataFrame(res_o.data)
                df_o['timestamp'] = pd.to_datetime(df_o['timestamp'])
                df_o['日期'] = df_o['timestamp'].dt.date
                
                # 篩選器
                c1, c2, c3 = st.columns(3)
                with c1:
                    d_range = st.date_input("日期區間", value=(date.today() - timedelta(days=30), date.today()))
                with c2:
                    plt_list = ["全部"] + sorted([str(x) for x in df_o['platform'].unique() if x])
                    sel_plt = st.selectbox("平台篩選", plt_list)
                with c3:
                    mode_list = ["全部"] + sorted([str(x) for x in df_o['mode'].unique() if x])
                    sel_mode = st.selectbox("模式篩選", mode_list)

                # 應用篩選
                f_df = df_o.copy()
                if len(d_range) == 2:
                    f_df = f_df[(f_df['日期'] >= d_range[0]) & (f_df['日期'] <= d_range[1])]
                if sel_plt != "全部": f_df = f_df[f_df['platform'] == sel_plt]
                if sel_mode != "全部": f_df = f_df[f_df['mode'] == sel_mode]

                # 顯示歷史表格
                display_df = f_df[['p_name', 'quantity', 'mode', 'platform', 'logistics', 'timestamp']].copy()
                display_df.columns = ['商品名稱', '數量', '變動模式', '平台', '物流', '紀錄時間']
                st.dataframe(display_df.sort_values('紀錄時間', ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("目前雲端無歷史紀錄。")

    # --- 分頁：報表匯出 (Level 9 專屬) ---
    if user_level >= 9:
        with tabs[-1]:
            st.subheader("📥 報表導出中心")
            if 'display_df' in locals() and not display_df.empty:
                st.write(f"準備導出共 {len(display_df)} 筆紀錄")
                csv = display_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="💾 點擊下載完整報表 (CSV)",
                    data=csv,
                    file_name=f"ERP_Report_{date.today()}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
                st.divider()
                st.write("📈 快速統計")
                st.bar_chart(display_df['變動模式'].value_counts())
            else:
                st.warning("無資料可供匯出。")
