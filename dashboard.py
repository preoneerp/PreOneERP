import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta
import io

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

    # --- TAB 2: 已出貨訂單 ---
    if user_level >= 5:
        with tabs[1]:
            st.header("歷史出貨紀錄")
            try:
                res_o = supabase.table("orders").select("order_number, customer_name, quantity, platform, logistics, shipped_at, products(name)").execute()
                if res_o.data:
                    df_o = pd.json_normalize(res_o.data)
                    df_o.columns = ['訂單編號', '客戶', '數量', '平台', '物流', '時間', '商品名稱']
                    df_o['時間'] = pd.to_datetime(df_o['時間'])
                    df_o['日期'] = df_o['時間'].dt.date
                    
                    st.write("🔍 **進階篩選查詢**")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        date_range = st.date_input("日期區間", value=(date.today() - timedelta(days=30), date.today()))
                    with c2:
                        sel_p = st.selectbox("🛒 平台", ["全部"] + sorted(df_o['平台'].unique().astype(str).tolist()))
                    with c3:
                        sel_l = st.selectbox("🚛 物流", ["全部"] + sorted(df_o['物流'].unique().astype(str).tolist()))

                    f_df = df_o.copy()
                    if len(date_range) == 2:
                        f_df = f_df[(f_df['日期'] >= date_range[0]) & (f_df['日期'] <= date_range[1])]
                    if sel_p != "全部": f_df = f_df[f_df['平台'] == sel_p]
                    if sel_l != "全部": f_df = f_df[f_df['物流'] == sel_l]

                    st.markdown(f"共找到 **{len(f_df)}** 筆訂單")
                    display_df = f_df.drop(columns=['日期'])
                    display_df['時間'] = display_df['時間'].dt.strftime('%Y-%m-%d %H:%M')
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    
                    csv_o = display_df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 下載篩選後結果 (CSV)", csv_o, "filtered_orders.csv", "text/csv")
                else:
                    st.info("尚無訂單紀錄。")
            except Exception as e:
                st.warning(f"訂單讀取異常: {e}")

    # --- TAB 3: 報表導出 (正式啟用功能) ---
    if user_level >= 9:
        with tabs[-1]:
            st.header("⚙️ 系統報表導出中心")
            st.write("點擊下方按鈕以生成並下載最新營運數據。")
            st.divider()

            col_a, col_b = st.columns(2)

            with col_a:
                st.subheader("📦 全系統庫存總結")
                st.write("包含所有商品名稱、目前庫存以及供應商。")
                try:
                    res_p_full = supabase.table("products").select("name, stock, vendors(name)").execute()
                    if res_p_full.data:
                        df_full_p = pd.json_normalize(res_p_full.data)
                        df_full_p.columns = ['商品名稱', '庫存數量', '供應商']
                        csv_p = df_full_p.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="🚀 導出全系統庫存總結 (CSV)",
                            data=csv_p,
                            file_name=f"Inventory_Full_Report_{date.today()}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                except:
                    st.error("無法抓取庫存資料")

            with col_b:
                st.subheader("📈 年度銷售統計報表")
                st.write("依據訂單時間，自動按月份統計銷售總數量。")
                try:
                    res_o_full = supabase.table("orders").select("quantity, platform, shipped_at").execute()
                    if res_o_full.data:
                        df_full_o = pd.json_normalize(res_o_full.data)
                        df_full_o['shipped_at'] = pd.to_datetime(df_full_o['shipped_at'])
                        df_full_o['月份'] = df_full_o['shipped_at'].dt.strftime('%Y-%m')
                        
                        # 製作樞紐分析表：按月份統計銷售數量
                        pivot_df = df_full_o.groupby(['月份', 'platform'])['quantity'].sum().reset_index()
                        pivot_df.columns = ['銷售月份', '出貨平台', '總銷售數量']
                        
                        csv_s = pivot_df.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="🚀 導出年度銷售統計報表 (CSV)",
                            data=csv_s,
                            file_name=f"Sales_Analysis_{date.today()}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    else:
                        st.info("目前無訂單數據可供統計。")
                except Exception as e:
                    st.error(f"報表生成失敗: {e}")
