import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

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

# --- 2. 核心主程式 ---
if check_password():
    user_level = st.session_state["user_level"]
    current_user = st.session_state["current_user"]

    @st.cache_resource
    def init_connection():
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    
    supabase = init_connection()

    # --- 側邊欄 ---
    st.sidebar.markdown(f"### 👤 使用者：{current_user}")
    st.sidebar.markdown(f"🛡️ 權限等級：**Level {user_level}**")
    
    low_stock_threshold = st.sidebar.slider("⚠️ 安全庫存預警門檻", 0, 100, 10)
    
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

    # --- TAB 1: 庫存概況 ---
    with tabs[0]:
        st.header("庫存數據明細")
        try:
            res_p = supabase.table("products").select("name, stock, vendors(name)").execute()
            if res_p.data:
                df_p = pd.json_normalize(res_p.data)
                df_p.columns = ['商品名稱', '庫存數量', '供應商']
                
                v_list = ["全部"] + sorted(df_p['供應商'].unique().tolist())
                sel_v = st.sidebar.selectbox("📦 篩選供應商", v_list)
                if sel_v != "全部":
                    df_p = df_p[df_p['供應商'] == sel_v]
                
                low_stock_items = df_p[df_p['庫存數量'] <= low_stock_threshold]
                if not low_stock_items.empty:
                    st.error(f"🚨 【預警】共有 {len(low_stock_items)} 項商品低於安全庫存！")
                
                def highlight_low_stock(s):
                    return ['background-color: #ffcccc' if s.name == '庫存數量' and v <= low_stock_threshold else '' for v in s]

                st.dataframe(df_p.style.apply(highlight_low_stock, axis=0), use_container_width=True, hide_index=True)
            else:
                st.info("尚無庫存資料。")
        except Exception as e:
            st.error(f"連線異常: {e}")

    # --- TAB 2: 已出貨訂單 (新增日期、平台、物流篩選) ---
    if user_level >= 5:
        with tabs[1]:
            st.header("歷史出貨紀錄")
            try:
                res_o = supabase.table("orders").select("order_number, customer_name, quantity, platform, logistics, shipped_at, products(name)").execute()
                if res_o.data:
                    df_o = pd.json_normalize(res_o.data)
                    df_o.columns = ['訂單編號', '客戶', '數量', '平台', '物流', '時間', '商品名稱']
                    
                    # 資料預處理：轉換時間格式
                    df_o['時間'] = pd.to_datetime(df_o['時間'])
                    df_o['日期'] = df_o['時間'].dt.date
                    
                    # --- 篩選介面佈局 ---
                    st.write("🔍 **篩選查詢**")
                    c1, c2, c3 = st.columns(3)
                    
                    with c1:
                        # 日期區間篩選
                        today = date.today()
                        last_month = today - timedelta(days=30)
                        date_range = st.date_input("選擇日期區間", value=(last_month, today))
                    
                    with c2:
                        p_list = ["全部"] + sorted(df_o['平台'].unique().astype(str).tolist())
                        sel_p = st.selectbox("🛒 篩選平台", p_list)
                    
                    with c3:
                        l_list = ["全部"] + sorted(df_o['物流'].unique().astype(str).tolist())
                        sel_l = st.selectbox("🚛 篩選物流", l_list)

                    # --- 執行過濾邏輯 ---
                    filtered_df = df_o.copy()
                    
                    # 1. 日期過濾 (判斷是否有選起始與結束)
                    if len(date_range) == 2:
                        start_date, end_date = date_range
                        filtered_df = filtered_df[(filtered_df['日期'] >= start_date) & (filtered_df['日期'] <= end_date)]
                    
                    # 2. 平台過濾
                    if sel_p != "全部":
                        filtered_df = filtered_df[filtered_df['平台'] == sel_p]
                    
                    # 3. 物流過濾
                    if sel_l != "全部":
                        filtered_df = filtered_df[filtered_df['物流'] == sel_l]

                    # --- 顯示結果 ---
                    st.write(f"📊 查詢結果：共 {len(filtered_df)} 筆訂單")
                    
                    # 整理顯示欄位（隱藏中間處理用的'日期'欄位）
                    display_df = filtered_df.drop(columns=['日期'])
                    # 將時間轉回字串顯示
                    display_df['時間'] = display_df['時間'].dt.strftime('%Y-%m-%d %H:%M')
                    
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    
                    # 下載功能
                    csv_o = display_df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 下載篩選後清單 (CSV)", csv_o, "filtered_orders.csv", "text/csv")
                else:
                    st.info("尚無訂單紀錄。")
            except Exception as e:
                st.warning(f"訂單讀取異常: {e}")

    # --- TAB 3: 報表導出 ---
    if user_level >= 9:
        with tabs[-1]:
            st.header("⚙️ 系統報表導出中心")
            st.button("🚀 產生年度分析報表")
