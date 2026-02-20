import streamlit as st
import pandas as pd
from supabase import create_client

# --- 頁面基本配置 ---
st.set_page_config(page_title="ERP 權限管理系統", layout="wide")

# --- 1. 登入與等級檢查邏輯 ---
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
        # --- 登入視覺設計 ---
        # 建立三個欄位，讓圖片置中
        _, center_col, _ = st.columns([1, 2, 1])
        
        with center_col:
            # 這裡建議把圖片放在 GitHub 根目錄命名為 mascot.jpg
            # 如果還沒上傳，可以暫時用下方註解掉的網路範例連結測試
            try:
                st.image("mascot.jpg", use_container_width=True)
            except:
                st.warning("請將吉祥物圖片命名為 mascot.jpg 並上傳至 GitHub 倉庫。")
                
            st.markdown("<h2 style='text-align: center; color: #D32F2F;'>🧧 招財進寶 ERP 系統</h2>", unsafe_allow_html=True)
            
            # 登入框放在圖片下方
            with st.container(border=True):
                st.text_input("帳號 (Username)", key="username")
                st.text_input("密碼 (Password)", type="password", key="password")
                st.button("確認登入", on_click=password_entered, use_container_width=True)
        return False
        
    elif not st.session_state["password_correct"]:
        st.error("❌ 帳號或密碼錯誤，請重新輸入。")
        # 登入失敗時也維持圖片顯示
        st.rerun()
    return True

# --- 2. 核心主程式 (驗證通過後執行) ---
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
                df_p = pd.json_normalize(res_p.data)
                df_p.columns = ['商品名稱', '庫存數量', '供應商']
                
                v_list = ["全部"] + sorted(df_p['供應商'].unique().tolist())
                sel_v = st.sidebar.selectbox("📦 篩選供應商", v_list)
                if sel_v != "全部":
                    df_p = df_p[df_p['供應商'] == sel_v]
                
                st.dataframe(df_p, use_container_width=True, hide_index=True)

                if user_level >= 9:
                    st.divider()
                    st.subheader("🛠️ 管理員快速校正")
                    with st.expander("展開校正表單"):
                        target = st.selectbox("選擇商品", df_p['商品名稱'].tolist())
                        new_val = st.number_input("修正數量", min_value=0, step=1)
                        if st.button("確認提交"):
                            supabase.table("products").update({"stock": new_val}).eq("name", target).execute()
                            st.success("數據已更新")
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
                st.warning("訂單表讀取失敗。")

    # --- TAB 3: 管理 (Level 9) ---
    if user_level >= 9:
        with tabs[-1]:
            st.header("🔑 系統管理員控制台")
            st.button("📥 下載全庫存備份 (CSV)")
