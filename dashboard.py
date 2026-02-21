import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta
from PIL import Image

# --- 1. 頁面配置 ---
st.set_page_config(page_title="ERP 雲端管理系統 v22.9", layout="wide")

# --- 2. 初始化 Supabase (放在最前面確保連線) ---
@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"連線設定錯誤: {e}")
        return None

supabase = init_connection()

# --- 3. 登入邏輯 (修復刷新問題並保留 Logo) ---
def check_password():
    # 如果 Session 中已經紀錄為 True，直接通過
    if st.session_state.get("password_correct", False):
        return True

    def password_entered():
        auth_data = st.secrets.get("auth", {})
        u_name = st.session_state.get("username", "")
        u_pw = str(st.session_state.get("password", ""))
        
        if u_name in auth_data and u_pw == str(auth_data[u_name]["password"]):
            st.session_state["password_correct"] = True
            st.session_state["current_user"] = u_name
            st.session_state["user_level"] = auth_data[u_name]["level"]
            # 清除暫存密碼防止外洩
            del st.session_state["password"]
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False
            st.error("❌ 帳號或密碼錯誤")

    # 登入介面
    _, center_col, _ = st.columns([1, 2, 1])
    with center_col:
        try:
            img = Image.open("mascot.jpg")
            st.image(img, width=220)
        except:
            st.markdown("### 🧧 招財進寶 ERP")
        
        with st.container(border=True):
            st.subheader("系統登入")
            st.text_input("帳號", key="username")
            st.text_input("密碼", type="password", key="password")
            st.button("登入系統", on_click=password_entered, use_container_width=True)
    return False

# --- 執行登入檢查 ---
if check_password():
    user_level = st.session_state["user_level"]

    # 側邊欄
    with st.sidebar:
        st.title("👤 使用者資訊")
        st.write(f"當前用戶: **{st.session_state['current_user']}**")
        st.write(f"權限等級: `Level {user_level}`")
        if st.button("🚪 登出系統"):
            st.session_state.clear()
            st.rerun()

    # --- 4. 資料抓取函數 (強化防錯機制) ---
    def fetch_data(table_name):
        try:
            res = supabase.table(table_name).select("*").execute()
            if res.data:
                return pd.DataFrame(res.data)
            return pd.DataFrame()
        except Exception as e:
            st.error(f"讀取 {table_name} 失敗: {e}")
            return pd.DataFrame()

    # --- 5. 主分頁區 ---
    tab_list = ["📦 即時庫存概況"]
    if user_level >= 5: tab_list.append("🚚 歷史紀錄查詢")
    if user_level >= 9: tab_list.append("📊 報表匯出中心")
    tabs = st.tabs(tab_list)

    # --- TAB 1: 庫存概況 (含低庫存警示) ---
    with tabs[0]:
        st.subheader("📋 商品在庫明細")
        df_p = fetch_data("products")
        if not df_p.empty:
            # 兼容不同大小寫欄位
            df_p.columns = [c.lower() for c in df_p.columns]
            # 欄位映射
            col_map = {'name': '商品名稱', 'stock': '在庫數量', 'v_name': '供應商'}
            df_display = df_p.rename(columns=col_map)[list(col_map.values())]
            
            # 庫存警示
            low_stock = df_display[df_display['在庫數量'] < 10]
            if not low_stock.empty:
                st.error(f"⚠️ 警報：有 {len(low_stock)} 項商品庫存不足 10 件！")
                st.dataframe(low_stock, hide_index=True, use_container_width=True)
            
            st.divider()
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.info("雲端目前無庫存資料，請由 GUI 端上傳。")

    # --- TAB 2: 歷史紀錄 (修正不顯示問題) ---
    if user_level >= 5:
        with tabs[1]:
            st.subheader("🔎 進出貨歷史明細")
            df_o = fetch_data("order_history")
            
            if not df_o.empty:
                # 統一欄位為小寫
                df_o.columns = [c.lower() for c in df_o.columns]
                
                # 確保時間格式正確
                df_o['timestamp'] = pd.to_datetime(df_o['timestamp'])
                df_o['日期'] = df_o['timestamp'].dt.date
                
                # 篩選區
                c1, c2, c3 = st.columns(3)
                with c1:
                    d_range = st.date_input("日期區間", value=(date.today() - timedelta(days=30), date.today()))
                with c2:
                    plt_list = ["全部"] + sorted([str(x) for x in df_o['platform'].unique() if x])
                    sel_plt = st.selectbox("平台篩選", plt_list)
                with c3:
                    mode_list = ["全部"] + sorted([str(x) for x in df_o['mode'].unique() if x])
                    sel_mode = st.selectbox("模式篩選", mode_list)

                # 應用篩選邏輯
                f_df = df_o.copy()
                if len(d_range) == 2:
                    f_df = f_df[(f_df['日期'] >= d_range[0]) & (f_df['日期'] <= d_range[1])]
                if sel_plt != "全部": f_df = f_df[f_df['platform'] == sel_plt]
                if sel_mode != "全部": f_df = f_df[f_df['mode'] == sel_mode]

                # 準備最終顯示
                final_cols = {'p_name': '商品', 'quantity': '數量', 'mode': '模式', 'platform': '平台', 'logistics': '物流', 'timestamp': '紀錄時間'}
                history_display = f_df.rename(columns=final_cols)[list(final_cols.values())]
                
                st.dataframe(history_display.sort_values('紀錄時間', ascending=False), use_container_width=True, hide_index=True)
                
                # 將結果存在 Session State 供 TAB 3 使用
                st.session_state["history_data"] = history_display
            else:
                st.warning("⚠️ 讀取紀錄失敗或雲端目前無資料。請確認：\n1. GUI 端是否點擊『數據重整』。\n2. Supabase 欄位名稱是否為 p_name, quantity, mode, platform, logistics, timestamp。")

    # --- TAB 3: 報表匯出 (修正沒內容問題) ---
    if user_level >= 9:
        with tabs[-1]:
            st.subheader("📥 報表導出中心")
            # 嘗試從 Session 獲取剛才篩選後的資料
            export_df = st.session_state.get("history_data", pd.DataFrame())
            
            if not export_df.empty:
                st.write(f"✅ 準備就緒！共有 {len(export_df)} 筆篩選紀錄。")
                csv = export_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="💾 點擊下載報表 (CSV)",
                    data=csv,
                    file_name=f"ERP_Export_{date.today()}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
                # 簡易統計圖表 (增加視覺化)
                st.divider()
                st.subheader("📊 快速統計")
                st.bar_chart(export_df['模式'].value_counts())
            else:
                st.error("❌ 無資料可匯出。請先前往『歷史紀錄查詢』分頁確保資料已成功讀取。")
