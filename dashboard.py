import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 頁面配置與進階視覺設計 ---
st.set_page_config(page_title="ERP 雲端管理中心", layout="wide", initial_sidebar_state="expanded")

# 自定義高級感 UI CSS
st.markdown("""
    <style>
    .stApp { background-color: #FDFBFA; }
    
    /* 自定義卡片容器 */
    .dashboard-container {
        display: flex;
        gap: 20px;
        margin-bottom: 25px;
    }
    
    .status-card {
        flex: 1;
        background: white;
        padding: 25px;
        border-radius: 20px;
        box-shadow: 0 10px 25px rgba(232, 160, 191, 0.1);
        border: 1px solid #FADBD8;
        text-align: center;
        transition: transform 0.3s ease;
    }
    
    .status-card:hover { transform: translateY(-5px); }
    
    .card-title { color: #888; font-size: 0.9rem; margin-bottom: 10px; }
    .card-value { font-size: 1.8rem; font-weight: bold; color: #444; }
    
    /* 不同的卡片強調色 (柔和莫蘭迪) */
    .card-1 { border-top: 5px solid #E8A0BF; } /* 霧粉 */
    .card-2 { border-top: 5px solid #BA94D1; } /* 柔紫 */
    .card-3 { border-top: 5px solid #FF9EAA; } /* 亮粉 */
    
    .stButton>button { border-radius: 20px; border: none; background-color: #E8A0BF; color: white; }
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

# --- 3. 登入邏輯 ---
def check_password():
    if st.session_state.get("password_correct", False):
        return True

    _, col_mid, _ = st.columns([1.2, 1, 1.2])
    with col_mid:
        st.write("<br><br>", unsafe_allow_html=True)
        try:
            st.image("mascot.jpg", width=160)
        except:
            st.markdown("<h2 style='text-align: center; color: #E8A0BF;'>🎀 雲端管理系統</h2>", unsafe_allow_html=True)
        
        with st.container(border=True):
            u = st.text_input("帳號", placeholder="Username")
            p = st.text_input("密碼", type="password", placeholder="Password")
            
            def password_entered():
                auth = st.secrets.get("auth", {})
                if u in auth and str(p) == str(auth[u]["password"]):
                    st.session_state["password_correct"] = True
                    st.session_state["user_level"] = auth[u]["level"]
                    st.session_state["current_user"] = u
                else: st.error("🔒 密碼不正確")

            st.button("登入系統", on_click=password_entered, use_container_width=True)
    return False

if check_password():
    user_level = st.session_state["user_level"]
    
    with st.sidebar:
        st.markdown(f"### 🌸 你好，{st.session_state['current_user']}")
        st.caption(f"權限層級：Level {user_level}")
        st.divider()
        if st.button("🚪 安全登出", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    tabs = st.tabs(["☁️ 庫存清單", "📔 變動紀錄", "💾 數據匯出"])

    # --- TAB 1: 即時庫存 (自定義卡片呈現) ---
    with tabs[0]:
        try:
            res_p = supabase.table("products").select("*").execute()
            if res_p.data:
                df_p = pd.DataFrame(res_p.data)
                df_p.columns = [c.lower() for c in df_p.columns]
                
                # 篩選區
                with st.container(border=True):
                    c1, c2 = st.columns([2, 1])
                    sel_v = c1.selectbox("🔍 篩選供應商", ["✨ 全部供應商"] + sorted([str(x) for x in df_p['v_name'].unique() if x]))
                    safe_limit = c2.number_input("🛡️ 警示額度", min_value=0, value=10)
                
                filtered_df = df_p if sel_v == "✨ 全部供應商" else df_p[df_p['v_name'] == sel_v]
                low_count = len(filtered_df[filtered_df['stock'] < safe_limit])
                total_stock = int(filtered_df['stock'].sum())

                # --- 🎨 全新卡片式呈現 (取代 st.metric) ---
                st.markdown(f"""
                    <div class="dashboard-container">
                        <div class="status-card card-1">
                            <div class="card-title">📦 總產品項</div>
                            <div class="card-value">{len(filtered_df)} <span style="font-size:1rem;">種</span></div>
                        </div>
                        <div class="status-card card-2">
                            <div class="card-title">💎 在庫總量</div>
                            <div class="card-value">{total_stock} <span style="font-size:1rem;">件</span></div>
                        </div>
                        <div class="status-card card-3">
                            <div class="card-title">⚠️ 需補貨品項</div>
                            <div class="card-value" style="color: {'#FF9EAA' if low_count > 0 else '#444'};">
                                {low_count} <span style="font-size:1rem;">筆</span>
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                if low_count > 0:
                    st.toast(f"提醒：有 {low_count} 項商品庫存偏低！", icon="🎀")

                # 表格顯示
                display_df = filtered_df.copy()
                display_df['狀態'] = display_df['stock'].apply(lambda x: '❗ 補貨' if x < safe_limit else '✅ 正常')
                final_df = display_df.rename(columns={'name':'商品名稱','stock':'數量','v_name':'供應商','狀態':'庫存狀態'})
                st.dataframe(final_df[['庫存狀態', '商品名稱', '數量', '供應商']], 
                             use_container_width=True, hide_index=True, height=500)
                
            else: st.info("雲端目前無庫存資料。")
        except Exception as e: st.error(f"錯誤: {e}")

    # --- TAB 2 & 3 ---
    with tabs[1]:
        if user_level >= 5:
            # 歷史紀錄邏輯 (簡化版呈現)
            st.subheader("📔 歷史變動追蹤")
            try:
                res_o = supabase.table("order_history").select("*").execute()
                if res_o.data:
                    df_o = pd.DataFrame(res_o.data); df_o.columns = [c.lower() for c in df_o.columns]
                    df_o['timestamp'] = pd.to_datetime(df_o['timestamp'])
                    final_o = df_o.sort_values('timestamp', ascending=False).rename(columns={'p_name':'商品','quantity':'數量','mode':'模式','timestamp':'時間'})
                    st.dataframe(final_o[['時間','商品','數量','模式']], use_container_width=True, hide_index=True)
                    st.session_state["filtered_report"] = final_o
            except: pass
        else: st.warning("權限不足")

    with tabs[2]:
        if user_level >= 9:
            st.subheader("💾 報表儲存")
            if "filtered_report" in st.session_state:
                csv = st.session_state["filtered_report"].to_csv(index=False).encode('utf-8-sig')
                st.download_button(label="📥 下載 CSV", data=csv, file_name=f"Report_{date.today()}.csv", use_container_width=True)
