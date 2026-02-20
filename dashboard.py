import streamlit as st
import pandas as pd
from supabase import create_client

# --- 頁面基本配置 ---
st.set_page_config(page_title="ERP 權限管理系統", layout="wide")

# --- 1. 登入與等級檢查邏輯 ---
def check_password():
    """驗證帳號密碼，並將等級(level)存入 session"""
    def password_entered():
        users_dict = st.secrets.get("auth", {})
        u_name = st.session_state["username"]
        u_pw = st.session_state["password"]
        
        # 比對帳號是否存在於字典中，並檢查密碼與轉型為字串比對
        if u_name in users_dict and str(u_pw) == str(users_dict[u_name]["password"]):
            st.session_state["password_correct"] = True
            st.session_state["current_user"] = u_name
            st.session_state["user_level"] = users_dict[u_name]["level"]
            del st.session_state["password"]  # 安全考量刪除密碼紀錄
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # 初次訪問：顯示登入框
        st.title("🔐 ERP 系統登入")
        col_l, _ = st.columns([1, 1])
        with col_l:
            st.text_input("帳號 (Username)", key="username")
            st.text_input("密碼 (Password)", type="password", key="password")
            st.button("登入系統", on_click=password_entered)
        return False
    
    elif not st.session_state["password_correct"]:
        # 登入失敗：顯示錯誤並重新登入
        st.title("🔐 ERP 系統登入")
        st.error("❌ 帳號或密碼錯誤")
        st.text_input("帳號 (Username)", key="username")
        st.text_input("密碼 (Password)", type="password", key="password")
        st.button("登入系統", on_click=password_entered)
        return False
    else:
        return True

# --- 2. 核心主程式 (驗證通過後執行) ---
if check_password():
    # 讀取 Session 資訊
    user_level = st.session_state["user_level"]
    current_user = st.session_state["current_user"]

    # 初始化 Supabase 連線
    @st.cache_resource
    def init_connection():
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    
    supabase = init_connection()

    # 側邊欄：顯示用戶等級與登出
    st.sidebar.markdown(f"### 👤 使用者：{current_user}")
    st.sidebar.markdown(f"🛡️ 權限等級：**Level {user_level}**")
    if st.sidebar.button("登出系統"):
        st.session_state.clear() # 清空所有狀態
        st.rerun()

    st.title("📊 ERP 雲端戰情室")
    st.divider()

    # --- 權限分頁邏輯 ---
    # 根據等級決定要顯示的分頁標題
    tab_list = ["📦 即時庫存概況"]
    if user_level >= 5:
        tab_list.append("🚚 已出貨訂單")
    if user_level >= 9:
        tab_list.append("⚙️ 系統管理")
    
    tabs = st.tabs(tab_list)

    # --- TAB 1: 庫存概況 (全等級可見) ---
    with tabs[0]:
        st.header("庫存概況")
        try:
            res_p = supabase.table("products").select("name, stock, vendors(name)").execute()
            if res_p.data:
                df_p = pd.json_normalize(
