import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta
from PIL import Image

# --- 頁面配置 ---
st.set_page_config(page_title="ERP 雲端戰情室", layout="wide")

# --- 1. 登入邏輯 (包含圖片顯示) ---
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
            # --- 補回圖片顯示 ---
            try:
                img = Image.open("mascot.jpg") # ⬅️ 請確保 logo.png 在 Streamlit 根目錄
                st.image(img, width=200)
            except:
                st.write("🧧") # 若無圖片則顯示圖示
            
            st.markdown("<h2 style='color: #D32F2F;'>🧧 招財進寶 ERP 系統</h2>", unsafe_allow_html=True)
            
            with st.container(border=True):
                st.text_input("帳號", key="username")
                st.text_input("密碼", type="password", key="password")
                st.button("登入系統", on_click=password_entered, use_container_width=True)
        return False
    return st.session_state["password_correct"]

if check_password():
    # --- 2. 初始化 Supabase ---
    @st.cache_resource
    def init_connection():
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    
    supabase = init_connection()
    user_level = st.session_state["user_level"]

    st.title("📊 ERP 雲端戰情室")
    
    # 權限分頁
    tab_list = ["📦 即時庫存概況"]
    if user_level >= 5: tab_list.append("🚚 歷史紀錄查詢")
    tabs = st.tabs(tab_list)

    # --- TAB 1: 庫存概況 ---
    with tabs[0]:
        st.subheader("📋 商品在庫明細")
        res_p = supabase.table("products").select("name, stock, v_name").execute()
        if res_p.data:
            df_p = pd.DataFrame(res_p.data)
            df_p.columns = ['商品名稱', '在庫數量', '供應商']
            st.dataframe(df_p, use_container_width=True, hide_index=True)
        else:
            st.info("雲端目前無庫存資料。")

    # --- TAB 2: 歷史紀錄查詢 (修正篩選功能與資料顯示) ---
    if user_level >= 5:
        with tabs[1]:
            st.subheader("🔎 進出貨歷史明細")
            
            # 抓取雲端歷史資料
            res_o = supabase.table("order_history").select("*").execute()
            if res_o.data:
                df_o = pd.DataFrame(res_o.data)
                
                # 預處理時間
                df_o['timestamp'] = pd.to_datetime(df_o['timestamp'])
                df_o['日期'] = df_o['timestamp'].dt.date
                
                # --- 篩選介面區 ---
                c1, c2, c3 = st.columns(3)
                with c1:
                    date_range = st.date_input(
                        "選擇日期區間", 
                        value=(date.today() - timedelta(days=30), date.today())
                    )
                with c2:
                    # 處理平台清單 (過濾 None/空值)
                    plt_list = ["全部"] + sorted([str(x) for x in df_o['platform'].unique() if x and str(x).strip()])
                    sel_plt = st.selectbox("篩選平台", plt_list)
                with c3:
                    mode_list = ["全部"] + sorted([str(x) for x in df_o['mode'].unique() if x])
                    sel_mode = st.selectbox("篩選模式", mode_list)

                # --- 執行篩選邏輯 ---
                f_df = df_o.copy()
                
                # 日期篩選
                if isinstance(date_range, tuple) and len(date_range) == 2:
                    f_df = f_df[(f_df['日期'] >= date_range[0]) & (f_df['日期'] <= date_range[1])]
                
                # 平台篩選
                if sel_plt != "全部":
                    f_df = f_df[f_df['platform'] == sel_plt]
                
                # 模式篩選
                if sel_mode != "全部":
                    f_df = f_df[f_df['mode'] == sel_mode]

                # --- 顯示結果 ---
                # 重新整理顯示欄位名
                display_df = f_df[['p_name', 'quantity', 'mode', 'platform', 'logistics', 'timestamp']].copy()
                display_df.columns = ['商品', '數量', '模式', '平台', '物流', '紀錄時間']
                
                st.dataframe(display_df.sort_values('紀錄時間', ascending=False), use_container_width=True, hide_index=True)
                
                # 匯出按鈕
                csv = display_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 下載篩選紀錄 (CSV)", csv, "erp_history.csv", "text/csv")
            else:
                st.warning("雲端資料庫中沒有歷史紀錄。請確認 GUI 端是否已執行『數據搬家』。")
