import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta
from PIL import Image

# --- 1. 頁面配置 ---
st.set_page_config(page_title="ERP 雲端系統", layout="wide")

# --- 2. 初始化 Supabase ---
@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"連線失敗: {e}")
        return None

supabase = init_connection()

# --- 3. 登入邏輯 (修復刷新問題) ---
def check_password():
    if st.session_state.get("password_correct", False):
        return True

    def password_entered():
        auth = st.secrets.get("auth", {})
        u = st.session_state.get("login_u", "")
        p = str(st.session_state.get("login_p", ""))
        if u in auth and p == str(auth[u]["password"]):
            st.session_state["password_correct"] = True
            st.session_state["user_level"] = auth[u]["level"]
            st.session_state["current_user"] = u
        else:
            st.error("❌ 帳號或密碼錯誤")

    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        try:
            st.image("mascot.jpg", width=200)
        except:
            st.title("🧧 ERP 系統")
        with st.container(border=True):
            st.text_input("帳號", key="login_u")
            st.text_input("密碼", type="password", key="login_p")
            st.button("登入系統", on_click=password_entered, use_container_width=True)
    return False

if check_password():
    user_level = st.session_state["user_level"]
    
    # 側邊欄
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state['current_user']}")
        st.info(f"權限: Level {user_level}")
        if st.button("🚪 登出"):
            st.session_state.clear()
            st.rerun()

    # 定義分頁架構
    tab_list = ["📦 即時庫存概況"]
    if user_level >= 5: tab_list.append("🚚 歷史紀錄查詢")
    if user_level >= 9: tab_list.append("📊 報表匯出中心")
    tabs = st.tabs(tab_list)

    # --- TAB 1: 即時庫存 (恢復單一清單狀態) ---
    with tabs[0]:
        st.subheader("📋 商品在庫明細")
        try:
            res_p = supabase.table("products").select("*").execute()
            if res_p.data:
                df_p = pd.DataFrame(res_p.data)
                
                # 自動對齊欄位 (兼容大小寫)
                df_p.columns = [c.lower() for c in df_p.columns]
                
                # 庫存警示 (僅顯示警示文字，不重複生成表格)
                low_stock_count = len(df_p[df_p['stock'] < 10])
                if low_stock_count > 0:
                    st.warning(f"🔔 注意：當前有 {low_stock_count} 項商品庫存低於 10！")

                # 只保留一個標準瀏覽清單
                rename_p = {'name': '商品名稱', 'stock': '在庫數量', 'v_name': '供應商'}
                # 篩選出需要的欄位並顯示
                display_p = df_p.rename(columns=rename_p)
                available_cols = [c for c in rename_p.values() if c in display_p.columns]
                st.dataframe(display_p[available_cols], use_container_width=True, hide_index=True)
            else:
                st.info("雲端目前無庫存資料。")
        except Exception as e:
            st.error(f"庫存讀取出錯: {e}")

    # --- TAB 2: 歷史紀錄 (修復無資料顯示) ---
    if user_level >= 5:
        with tabs[1]:
            st.subheader("🔎 歷史變動紀錄")
            try:
                res_o = supabase.table("order_history").select("*").execute()
                if res_o.data:
                    df_o = pd.DataFrame(res_o.data)
                    df_o.columns = [c.lower() for c in df_o.columns]
                    
                    # 統一處理時間
                    df_o['timestamp'] = pd.to_datetime(df_o['timestamp'])
                    df_o['日期'] = df_o['timestamp'].dt.date

                    # 篩選功能
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        d_range = st.date_input("日期區間", [date.today() - timedelta(days=30), date.today()])
                    with c2:
                        platforms = ["全部"] + sorted([str(x) for x in df_o['platform'].unique() if x])
                        sel_plt = st.selectbox("平台", platforms)
                    with c3:
                        modes = ["全部"] + sorted([str(x) for x in df_o['mode'].unique() if x])
                        sel_mode = st.selectbox("模式", modes)

                    # 篩選邏輯
                    mask = (df_o['日期'] >= d_range[0]) & (df_o['日期'] <= d_range[1])
                    if sel_plt != "全部": mask &= (df_o['platform'] == sel_plt)
                    if sel_mode != "全部": mask &= (df_o['mode'] == sel_mode)
                    
                    filtered_df = df_o[mask].sort_values('timestamp', ascending=False)
                    
                    # 重新命名欄位以便顯示
                    final_rename = {
                        'p_name': '商品名稱', 'quantity': '數量', 'mode': '變動模式',
                        'platform': '平台', 'logistics': '物流', 'timestamp': '紀錄時間'
                    }
                    show_df = filtered_df.rename(columns=final_rename)
                    display_cols = [c for c in final_rename.values() if c in show_df.columns]
                    st.dataframe(show_df[display_cols], use_container_width=True, hide_index=True)
                    
                    # 存入 Session 給報表分頁
                    st.session_state["filtered_report"] = show_df[display_cols]
                else:
                    st.warning("📭 雲端目前沒有歷史紀錄。請確保在 GUI 版本中點擊了「數據搬家」。")
            except Exception as e:
                st.error(f"紀錄讀取失敗: {e}")

    # --- TAB 3: 報表匯出 ---
    if user_level >= 9:
        with tabs[-1]:
            st.subheader("📥 數據報表導出")
            if "filtered_report" in st.session_state and not st.session_state["filtered_report"].empty:
                report_data = st.session_state["filtered_report"]
                st.write(f"📊 目前篩選筆數：{len(report_data)}")
                csv = report_data.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="💾 下載當前報表 (CSV)",
                    data=csv,
                    file_name=f"ERP_Export_{date.today()}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("請先到『歷史紀錄查詢』分頁進行篩選，再回來匯出報表。")
