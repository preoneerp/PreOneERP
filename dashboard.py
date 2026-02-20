import streamlit as st
import pandas as pd
from supabase import create_client

# --- 頁面基本配置 ---
st.set_page_config(page_title="ERP 雲端管理系統", layout="wide")

# --- 1. 登入驗證邏輯 ---
def check_password():
    """檢查登入狀態，回傳 True 則顯示主程式"""
    
    def password_entered():
        if "auth" not in st.secrets:
            st.error("❌ 系統設定錯誤：請在 Secrets 中新增 [auth] 區塊。")
            return
            
        users_dict = st.secrets["auth"]
        u_name = st.session_state["username"]
        u_pw = st.session_state["password"]
        
        if u_name in users_dict and str(u_pw) == str(users_dict[u_name]):
            st.session_state["password_correct"] = True
            st.session_state["current_user"] = u_name
            del st.session_state["password"] # 清除敏感資訊
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # 登入介面
        st.title("🔐 ERP 系統登入")
        col_l, col_r = st.columns([1, 1])
        with col_l:
            st.text_input("帳號 (Username)", key="username")
            st.text_input("密碼 (Password)", type="password", key="password")
            st.button("確認登入", on_click=password_entered)
        return False
    
    elif not st.session_state["password_correct"]:
        # 登入失敗
        st.title("🔐 ERP 系統登入")
        st.text_input("帳號 (Username)", key="username")
        st.text_input("密碼 (Password)", type="password", key="password")
        st.button("確認登入", on_click=password_entered)
        st.error("❌ 帳號或密碼錯誤，請重新輸入。")
        return False
    else:
        return True

# --- 2. 核心主程式 (驗證通過後執行) ---
if check_password():
    
    # 初始化 Supabase 連線
    @st.cache_resource
    def init_connection():
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

    supabase = init_connection()
    current_user = st.session_state["current_user"]

    # 側邊欄：顯示身份與登出
    st.sidebar.markdown(f"### 👤 目前登入：**{current_user}**")
    if st.sidebar.button("登出系統"):
        st.session_state["password_correct"] = False
        st.rerun()

    st.title("🚀 ERP 雲端戰情室")
    st.divider()

    # 定義分頁
    tab1, tab2, tab3 = st.tabs(["📦 即時庫存概況", "🚚 已出貨訂單", "🔑 管理員專區"])

    # --- TAB 1: 即時庫存概況 ---
    with tab1:
        st.header("庫存概況")
        try:
            res_p = supabase.table("products").select("name, stock, vendors(name)").execute()
            if res_p.data:
                df_p = pd.json_normalize(res_p.data)
                df_p.columns = ['商品名稱', '庫存數量', '供應商']
                
                # 篩選器
                v_list = ["全部"] + sorted(df_p['供應商'].unique().tolist())
                sel_v = st.sidebar.selectbox("📦 篩選供應商", v_list)
                threshold = st.sidebar.slider("⚠️ 低庫存提醒門檻", 0, 50, 10)
                
                if sel_v != "全部":
                    df_p = df_p[df_p['供應商'] == sel_v]
                
                # 指標顯示
                low_stock_df = df_p[df_p['庫存數量'] <= threshold]
                c1, c2 = st.columns(2)
                c1.metric("品項總數", len(df_p))
                c2.metric("低庫存預警", len(low_stock_df), delta_color="inverse")

                if not low_stock_df.empty:
                    st.warning(f"🚨 以下商品庫存低於 {threshold} 件，請注意補貨！")
                    st.dataframe(low_stock_df, use_container_width=True, hide_index=True)
                
                st.subheader("完整庫存清單")
                st.dataframe(df_p.style.highlight_between(left=0, right=threshold, subset=['庫存數量'], color='#FFEBEE'), use_container_width=True, hide_index=True)
            else:
                st.info("資料庫中尚無庫存資料。")
        except Exception as e:
            st.error(f"讀取庫存失敗：{e}")

    # --- TAB 2: 已出貨訂單 ---
    with tab2:
        st.header("訂單追蹤")
        try:
            # 抓取包含平台與物流的訂單資料
            res_o = supabase.table("orders").select("order_number, customer_name, quantity, platform, logistics, shipped_at, products(name)").execute()
            if res_o.data:
                df_o = pd.json_normalize(res_o.data)
                df_o.columns = ['訂單編號', '客戶名稱', '數量', '平台', '物流', '時間', '商品名稱']
                
                # 篩選器
                f1, f2 = st.columns(2)
                p_list = ["全部"] + sorted(df_o['平台'].unique().astype(str).tolist())
                l_list = ["全部"] + sorted(df_o['物流'].unique().astype(str).tolist())
                
                with f1: sel_p = st.selectbox("🛒 篩選平台", p_list)
                with f2: sel_l = st.selectbox("🚛 篩選物流", l_list)
                
                if sel_p != "全部": df_o = df_o[df_o['平台'] == sel_p]
                if sel_l != "全部": df_o = df_o[df_o['物流'] == sel_l]
                
                st.dataframe(df_o, use_container_width=True, hide_index=True)
            else:
                st.info("目前尚無出貨訂單紀錄。")
        except Exception as e:
            st.error(f"讀取訂單失敗：{e}")

    # --- TAB 3: 管理員專區 ---
    with tab3:
        if current_user == "admin":
            st.header("🔑 管理員控制台")
            st.success("您具備最高管理權限")
            
            st.subheader("系統管理功能")
            c_a, c_b = st.columns(2)
            with c_a:
                st.button("📥 導出全系統備份 (CSV)")
            with c_b:
                st.button("🧹 清理過期日誌")
            
            st.info("提示：未來您可以在此處新增『修改價格』或『刪除訂單』的功能。")
        else:
            st.error("🔒 權限不足：此區塊僅限管理員(admin)存取。")
            st.image("https://img.icons8.com/color/96/000000/lock-landscape.png")
