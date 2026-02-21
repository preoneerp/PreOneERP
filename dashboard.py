import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 頁面配置 ---
st.set_page_config(page_title="ERP 雲端管理系統", layout="wide", initial_sidebar_state="expanded")

# 自定義 CSS 優化視覺
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stMetricValue"] { color: #2E86C1; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 初始化 Supabase ---
@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"連線失敗: {e}")
        return None

supabase = init_connection()

# --- 3. 登入邏輯 (優化欄位與圖片大小) ---
def check_password():
    if st.session_state.get("password_correct", False):
        return True

    # 登入區塊置中佈局
    _, col_mid, _ = st.columns([1.5, 1, 1.5])
    
    with col_mid:
        st.write("") # 增加上方間距
        try:
            # 調整圖片為合適的固定寬度
            st.image("mascot.jpg", width=180)
        except:
            st.markdown("<h1 style='text-align: center; color: #D32F2F;'>🧧 ERP 系統</h1>", unsafe_allow_html=True)
        
        with st.container(border=True):
            st.subheader("🔑 系統登入")
            u = st.text_input("帳號", key="login_u")
            p = st.text_input("密碼", type="password", key="login_p")
            
            def password_entered():
                auth = st.secrets.get("auth", {})
                if u in auth and str(p) == str(auth[u]["password"]):
                    st.session_state["password_correct"] = True
                    st.session_state["user_level"] = auth[u]["level"]
                    st.session_state["current_user"] = u
                else:
                    st.error("❌ 帳號或密碼錯誤")

            st.button("登入系統", on_click=password_entered, use_container_width=True)
    return False

if check_password():
    user_level = st.session_state["user_level"]
    
    # 側邊欄
    with st.sidebar:
        st.markdown(f"### 👤 使用者: {st.session_state['current_user']}")
        st.caption(f"權限層級: Level {user_level}")
        st.divider()
        if st.button("🚪 安全登出", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    # 定義分頁架構
    tab_list = ["📦 即時庫存概況"]
    if user_level >= 5: tab_list.append("🚚 歷史紀錄查詢")
    if user_level >= 9: tab_list.append("📊 報表匯出中心")
    tabs = st.tabs(tab_list)

    # --- TAB 1: 即時庫存 (視覺化指標 + 篩選) ---
    with tabs[0]:
        try:
            res_p = supabase.table("products").select("*").execute()
            if res_p.data:
                df_p = pd.DataFrame(res_p.data)
                df_p.columns = [c.lower() for c in df_p.columns]
                
                # 頂部視覺化指標卡片
                total_items = len(df_p)
                total_stock = df_p['stock'].sum()
                
                # 控制面板區
                with st.expander("🛠️ 數據篩選與安全設定", expanded=True):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        v_list = ["全部供應商"] + sorted([str(x) for x in df_p['v_name'].unique() if x])
                        sel_v = st.selectbox("🔍 選擇供應商", v_list)
                    with c2:
                        safe_stock_limit = st.number_input("🛡️ 安全庫存標準", min_value=0, value=10)
                
                # 執行篩選
                filtered_df_p = df_p if sel_v == "全部供應商" else df_p[df_p['v_name'] == sel_v]
                low_stock_df = filtered_df_p[filtered_df_p['stock'] < safe_stock_limit]
                
                # 顯示指標
                m1, m2, m3 = st.columns(3)
                m1.metric("品項總數", f"{total_items} 種")
                m2.metric("在庫總量", f"{int(total_stock)} 件")
                m3.metric("低庫存警示", f"{len(low_stock_df)} 筆", delta=f"-{len(low_stock_df)}" if len(low_stock_df)>0 else "正常", delta_color="inverse")

                if not low_stock_df.empty:
                    st.warning(f"🚨 以下商品庫存低於設定標準 ({safe_stock_limit})，請及時補貨！")

                # 顯示資料表
                rename_p = {'name': '商品名稱', 'stock': '在庫數量', 'v_name': '供應商'}
                display_p = filtered_df_p.rename(columns=rename_p)
                available_cols = [c for c in rename_p.values() if c in display_p.columns]
                st.dataframe(display_p[available_cols], use_container_width=True, hide_index=True, height=500)
            else:
                st.info("雲端目前無庫存資料。")
        except Exception as e:
            st.error(f"庫存讀取出錯: {e}")

    # --- TAB 2: 歷史紀錄 (視覺化篩選佈局) ---
    if user_level >= 5:
        with tabs[1]:
            st.subheader("🔎 變動紀錄追蹤")
            try:
                res_o = supabase.table("order_history").select("*").execute()
                if res_o.data:
                    df_o = pd.DataFrame(res_o.data)
                    df_o.columns = [c.lower() for c in df_o.columns]
                    df_o['timestamp'] = pd.to_datetime(df_o['timestamp'])
                    df_o['日期'] = df_o['timestamp'].dt.date

                    # 篩選區塊視覺化
                    with st.container(border=True):
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            d_range = st.date_input("📅 日期區間", [date.today() - timedelta(days=30), date.today()])
                        with c2:
                            platforms = ["全部"] + sorted([str(x) for x in df_o['platform'].unique() if x])
                            sel_plt = st.selectbox("📱 銷售平台", platforms)
                        with c3:
                            modes = ["全部"] + sorted([str(x) for x in df_o['mode'].unique() if x])
                            sel_mode = st.selectbox("🔄 變動模式", modes)

                    mask = (df_o['日期'] >= d_range[0]) & (df_o['日期'] <= d_range[1])
                    if sel_plt != "全部": mask &= (df_o['platform'] == sel_plt)
                    if sel_mode != "全部": mask &= (df_o['mode'] == sel_mode)
                    
                    filtered_df = df_o[mask].sort_values('timestamp', ascending=False)
                    
                    final_rename = {
                        'p_name': '商品名稱', 'quantity': '數量', 'mode': '變動模式',
                        'platform': '平台', 'logistics': '物流', 'timestamp': '紀錄時間'
                    }
                    show_df = filtered_df.rename(columns=final_rename)
                    display_cols = [c for c in final_rename.values() if c in show_df.columns]
                    st.dataframe(show_df[display_cols], use_container_width=True, hide_index=True)
                    st.session_state["filtered_report"] = show_df[display_cols]
                else:
                    st.warning("📭 雲端目前沒有歷史紀錄。")
            except Exception as e:
                st.error(f"紀錄讀取失敗: {e}")

    # --- TAB 3: 報表匯出 ---
    if user_level >= 9:
        with tabs[-1]:
            st.subheader("📥 數據報表導出")
            if "filtered_report" in st.session_state and not st.session_state["filtered_report"].empty:
                report_data = st.session_state["filtered_report"]
                st.info(f"📋 當前準備匯出的數據共計 **{len(report_data)}** 筆")
                csv = report_data.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="💾 點擊下載 CSV 報表",
                    data=csv,
                    file_name=f"ERP_Export_{date.today()}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    type="primary"
                )
            else:
                st.info("💡 請先到『歷史紀錄查詢』分頁進行數據篩選。")
