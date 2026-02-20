import streamlit as st
import pandas as pd
from supabase import create_client

# --- 頁面基本配置 ---
st.set_page_config(page_title="ERP 雲端數據中心", layout="wide")

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
        # 登入視覺設計
        _, center_col, _ = st.columns([1, 2, 1])
        with center_col:
            try:
                st.image("mascot.jpg", use_container_width=True)
            except:
                st.info("🧧 歡迎進入 ERP 數據中心")
                
            st.markdown("<h2 style='text-align: center; color: #D32F2F;'>🧧 招財進寶 ERP 系統</h2>", unsafe_allow_html=True)
            
            with st.container(border=True):
                st.text_input("帳號", key="username")
                st.text_input("密碼", type="password", key="password")
                st.button("登入系統", on_click=password_entered, use_container_width=True)
        return False
        
    elif not st.session_state["password_correct"]:
        st.error("❌ 帳號或密碼錯誤")
        return False
    return True

# --- 2. 核心主程式 (純觀看與輸出模式) ---
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
    if user_level >= 9: tab_titles.append("⚙️ 報表導出")
    
    tabs = st.tabs(tab_titles)

    # --- TAB 1: 庫存概況 (純觀看) ---
    with tabs[0]:
        st.header("庫存數據明細")
        try:
            res_p = supabase.table("products").select("name, stock, vendors(name)").execute()
            if res_p.data:
                df_p = pd.json_normalize(res_p.data)
                df_p.columns = ['商品名稱', '庫存數量', '供應商']
                
                # 篩選
                v_list = ["全部"] + sorted(df_p['供應商'].unique().tolist())
                sel_v = st.sidebar.selectbox("📦 篩選供應商", v_list)
                if sel_v != "全部":
                    df_p = df_p[df_p['供應商'] == sel_v]
                
                st.dataframe(df_p, use_container_width=True, hide_index=True)
                
                # 即使是 Level 1 也可以下載自己看到的視圖
                csv = df_p.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 下載當前庫存表 (CSV)", csv, "inventory.csv", "text/csv")
            else:
                st.info("尚無庫存資料。")
        except Exception as e:
            st.error(f"連線異常: {e}")

    # --- TAB 2: 已出貨訂單 (Level 5+ 純觀看) ---
    if user_level >= 5:
        with tabs[1]:
            st.header("歷史出貨紀錄")
            try:
                res_o = supabase.table("orders").select("order_number, customer_name, quantity, platform, logistics, shipped_at, products(name)").execute()
                if res_o.data:
                    df_o = pd.json_normalize(res_o.data)
                    df_o.columns = ['訂單編號', '客戶', '數量', '平台', '物流', '時間', '商品']
                    
                    st.dataframe(df_o, use_container_width=True, hide_index=True)
                    
                    csv_o = df_o.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 下載出貨清單 (CSV)", csv_o, "orders.csv", "text/csv")
                else:
                    st.info("尚無訂單紀錄。")
            except:
                st.warning("訂單讀取異常。")

    # --- TAB 3: 報表導出 (Level 9 專屬) ---
    if user_level >= 9:
        with tabs[-1]:
            st.header("⚙️ 系統報表導出中心")
            st.write("此處提供管理員進行全系統數據匯出。")
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("庫存總表")
                st.info("包含所有供應商之完整原始數據")
                # 這裡可以寫更複雜的 join 查詢用於導出
                st.button("🚀 產生年度庫存分析報表")
                
            with c2:
                st.subheader("物流與平台分析")
                st.info("針對各平台出貨佔比進行彙整")
                st.button("📈 產生銷售通路統計報表")
