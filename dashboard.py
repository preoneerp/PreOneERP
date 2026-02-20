import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(page_title="ERP 權限管理系統", layout="wide")

# --- 1. 登入與權限檢查邏輯 ---
def check_password():
    def password_entered():
        users_dict = st.secrets.get("auth", {})
        u_name = st.session_state["username"]
        u_pw = st.session_state["password"]
        
        if u_name in users_dict and str(u_pw) == str(users_dict[u_name]["password"]):
            st.session_state["password_correct"] = True
            st.session_state["current_user"] = u_name
            st.session_state["user_level"] = users_dict[u_name]["level"] # 儲存等級
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔐 ERP 系統登入")
        st.text_input("帳號", key="username")
        st.text_input("密碼", type="password", key="password")
        st.button("登入", on_click=password_entered)
        return False
    elif not st.session_state["password_correct"]:
        st.error("❌ 帳號或密碼錯誤")
        st.text_input("帳號", key="username")
        st.text_input("密碼", type="password", key="password")
        st.button("登入", on_click=password_entered)
        return False
    return True

# --- 2. 驗證通過後的主程式 ---
if check_password():
    user_level = st.session_state["user_level"]
    current_user = st.session_state["current_user"]

    # 側邊欄狀態
    st.sidebar.info(f"👤 使用者：{current_user} (等級：{user_level})")
    if st.sidebar.button("登出系統"):
        st.session_state["password_correct"] = False
        st.rerun()

    # --- 權限分流選單 ---
    # 根據等級決定分頁
    tabs_to_show = ["📦 即時庫存"]
    if user_level >= 5:
        tabs_to_show.append("🚚 已出貨訂單")
    if user_level >= 9:
        tabs_to_show.append("⚙️ 系統管理")
    
    tabs = st.tabs(tabs_to_show)

    # 初始化連線
    @st.cache_resource
    def init_connection():
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    supabase = init_connection()

    # --- 分頁 1: 庫存 (所有等級皆可見) ---
    with tabs[0]:
        st.header("庫存概況")
        res = supabase.table("products").select("name, stock, vendors(name)").execute()
        if res.data:
            df = pd.json_normalize(res.data)
            st.dataframe(df, use_container_width=True)
            
            # 只有 Level 9 可以看到編輯按鈕
            if user_level >= 9:
                st.divider()
                st.subheader("🛠️ 管理員快速校正")
                target = st.selectbox("選擇商品", df['name'].tolist())
                num = st.number_input("修正庫存數量", min_value=0)
                if st.button("確認修正"):
                    supabase.table("products").update({"stock": num}).eq("name", target).execute()
                    st.success("數據已更新")
                    st.rerun()

    # --- 分頁 2: 訂單 (Level 5 以上可見) ---
    if user_level >= 5:
        with tabs[1]:
            st.header("訂單追蹤")
            st.write("這裡是訂單明細...")
            # (放原本的訂單抓取程式碼)

    # --- 分頁 3: 系統管理 (僅 Level 9 可見) ---
    if user_level >= 9:
        with tabs[len(tabs)-1]:
            st.header("管理員最高限權區")
            st.warning("您可以進行刪除資料、導出報表等敏感操作。")
