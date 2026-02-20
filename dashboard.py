import streamlit as st
import pandas as pd
from supabase import create_client

# --- 頁面配置 ---
st.set_page_config(page_title="ERP 雲端管理系統", layout="wide")

# --- 1. 多帳號驗證邏輯 ---
def check_password():
    def password_entered():
        # 從 Secrets 讀取所有帳號清單
        users_dict = st.secrets["auth"]
        
        # 檢查帳號是否存在且密碼正確
        input_user = st.session_state["username"]
        input_pw = st.session_state["password"]
        
        if input_user in users_dict and input_pw == users_dict[input_user]:
            st.session_state["password_correct"] = True
            st.session_state["current_user"] = input_user  # 紀錄當前使用者
            del st.session_state["password"]  # 安全考量：刪除 session 中的密碼
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # 初次訪問顯示登入介面
        st.title("🔐 ERP 系統登入")
        st.text_input("帳號 (Username)", key="username")
        st.text_input("密碼 (Password)", type="password", key="password")
        st.button("登入", on_click=password_entered)
        return False
    elif not st.session_state["password_correct"]:
        # 登入失敗顯示
        st.title("🔐 ERP 系統登入")
        st.text_input("帳號 (Username)", key="username")
        st.text_input("密碼 (Password)", type="password", key="password")
        st.button("登入", on_click=password_entered)
        st.error("❌ 帳號或密碼錯誤，請重新輸入。")
        return False
    else:
        return True

# --- 2. 驗證通過後的介面 ---
if check_password():
    # 側邊欄顯示狀態與登出
    current_user = st.session_state["current_user"]
    st.sidebar.info(f"👤 當前使用者: {current_user}")
    
    if st.sidebar.button("登出系統"):
        st.session_state["password_correct"] = False
        st.rerun()

    # --- 3. 權限分流範例 ---
    # 你可以根據 current_user 來決定顯示內容
    st.title(f"📊 ERP 雲端戰情室")
    
    tab1, tab2, tab3 = st.tabs(["📦 即時庫存概況", "🚚 已出貨訂單", "⚙️ 管理員專區"])

    with tab1:
        st.header("庫存概況")
        # (原本抓取 Supabase 庫存的程式碼...)
        st.write("這裡是所有人都能看到的庫存資訊")

    with tab2:
        st.header("已出貨訂單")
        # (原本抓取 Supabase 訂單的程式碼...)
        st.write("這裡是所有人都能看到的訂單資訊")

    with tab3:
        if current_user == "admin":
            st.header("🔑 管理員控制台")
            st.write("此區域僅管理員(admin)可見")
            # 可以在這裡放「刪除資料」、「修改價格」或「下載成本報表」的功能
            st.button("導出年度財務報表 (CSV)")
        else:
            st.warning("🔒 權限不足：此區塊僅限管理員帳號存取。")
