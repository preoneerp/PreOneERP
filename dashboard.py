import streamlit as st
import pandas as pd
from supabase import create_client

# --- 頁面基本配置 ---
st.set_page_config(page_title="ERP 權限管理系統", layout="wide")

# --- 1. 登入與等級檢查邏輯 ---
def check_password():
    def password_entered():
        # 安全讀取 secrets
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
        st.title("🔐 ERP 系統登入")
        col_l, _ = st.columns([1, 1])
        with col_l:
            st.text_input("帳號 (Username)", key="username")
            st.text_input("密碼 (Password)", type="password", key="password")
            st.button("登入系統", on_click=password_entered)
        return False
    elif not st.session_state["password_correct"]:
        st.title("🔐 ERP 系統登入")
        st.error("❌ 帳號或密碼錯誤")
        st.text_input("帳號 (Username)", key="username")
        st.text_input("密碼 (Password)", type="password", key="password")
        st.button("登入系統", on_click=password_entered)
        return False
    return True

# --- 2. 核心主程式 ---
if check_password():
    user_level = st.session_state["user_level"]
    current_user = st.session_state["current_user"]

    @st.cache_resource
    def init_connection():
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    
    supabase = init_connection()

    # 側邊欄狀態
    st.sidebar.markdown(f"### 👤 使用者：{current_user}")
    st.sidebar.markdown(f"🛡️ 權限等級：**Level {user_level}**")
    if st.sidebar.button("登出系統"):
        st.session_state.clear()
        st.rerun()

    st.title("📊 ERP 雲端戰情室")
    st.divider()

    # 動態分頁
    tab_titles = ["📦 即時庫存概況"]
    if user_level >= 5: tab_titles.append("🚚 已出貨訂單")
    if user_level >= 9: tab_titles.append("⚙️ 系統管理")
    
    tabs = st.tabs(tab_titles)

    # --- TAB 1: 庫存 (所有等級) ---
    with tabs[0]:
        st.header("庫存概況")
        try:
            res_p = supabase.table("products").select("name, stock, vendors(name)").execute()
            if res_p.data:
                # 修正後的 json_normalize 寫法
                df_p = pd.json_normalize(res_p.data)
                df_p.columns = ['商品名稱', '庫存數量', '供應商']
                
                # 篩選
                v_list = ["全部"] + sorted(df_p['供應商'].unique().tolist())
                sel_v = st.sidebar.selectbox("📦 篩選供應商", v_list)
                if sel_v != "全部":
                    df_p = df_p[df_p['供應商'] == sel_v]
                
                st.dataframe(df_p, use_container_width=True, hide_index=True)

                # Level 9 管理功能
                if user_level >= 9:
                    st.divider()
                    st.subheader("🛠️ 管理員快速校正")
                    with st.expander("展開校正表單"):
                        target = st.selectbox("選擇商品", df_p['商品名稱'].tolist())
                        new_val = st.number_input("修正數量", min_value=0, step=1)
                        if st.button("確認提交"):
                            supabase.table("products").update({"stock": new_val}).eq("name", target).execute()
                            st.success("已更新，請稍候...")
                            st.cache_resource.clear()
                            st.rerun()
            else:
                st.info("尚無庫存資料。")
        except Exception as e:
            st.error(f"連線異常: {e}")

    # --- TAB 2: 訂單 (Level 5+) ---
    if user_level >= 5:
        with tabs[1]:
            st.header("訂單追蹤紀錄")
            try:
                res_o = supabase.table("orders").select("order_number, customer_name, quantity, platform, logistics, shipped_at, products(name)").execute()
                if res_o.data:
                    df_o = pd.json_normalize(res_o.data)
                    df_o.columns = ['訂單編號', '客戶', '數量', '平台', '物流', '時間', '商品']
                    st.dataframe(df_o, use_container_width=True, hide_index=True)
                else:
                    st.info("尚無訂單紀錄。")
            except:
                st.warning("訂單表讀取失敗，請確認資料表是否存在。")

    # --- TAB 3: 管理 (Level 9) ---
    if user_level >= 9:
        with tabs[-1]:
            st.header("🔑 系統管理員控制台")
            st.write("此區域僅等級 9 帳號可見。")
            st.button("📥 下載全庫存備份 (CSV)")
