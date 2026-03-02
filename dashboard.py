import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 頁面配置 ---
st.set_page_config(page_title="ERP 雲端中心 v2.2", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #FDFBFA; }
    .status-card { background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 初始化 Supabase ---
@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except: return None

supabase = init_connection()

# --- 3. 數據救援工具 (核心修正) ---
def smart_process(df):
    if df.empty: return df
    # 移除所有欄位的空格並轉小寫
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    # 時間戳救援
    t_col = next((c for c in df.columns if 'time' in c), None)
    if t_col:
        df[t_col] = pd.to_datetime(df[t_col], errors='coerce')
        df = df.dropna(subset=[t_col])
        if df[t_col].dt.tz is None:
            df[t_col] = df[t_col].dt.tz_localize('UTC')
        df['timestamp_fixed'] = df[t_col].dt.tz_convert('Asia/Taipei').dt.tz_localize(None)
    return df

# --- 4. 登入邏輯 (簡化) ---
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

if not st.session_state["password_correct"]:
    _, col_mid, _ = st.columns([1.2, 1, 1.2])
    with col_mid:
        st.markdown("## 🎀 系統登入")
        u = st.text_input("帳號")
        p = st.text_input("密碼", type="password")
        if st.button("登入", use_container_width=True):
            auth = st.secrets.get("auth", {})
            if u in auth and str(p) == str(auth[u]["password"]):
                st.session_state.update({"password_correct": True, "user_level": auth[u]["level"], "current_user": u})
                st.rerun()
            else: st.error("登入失敗")
    st.stop()

# --- 5. 主介面 ---
curr_user = st.session_state["current_user"]
user_level = st.session_state["user_level"]

with st.sidebar:
    st.title(f"🌸 {curr_user}")
    if st.button("🚪 登出"):
        st.session_state.clear()
        st.rerun()

tabs = st.tabs(["☁️ 庫存清單", "📦 出貨紀錄", "🚚 物流件數"])

# --- TAB 1: 庫存清單 ---
with tabs[0]:
    res_p = supabase.table("products").select("*").execute()
    if res_p.data:
        df_p = smart_process(pd.DataFrame(res_p.data))
        # 截圖 [image_5fae78.png] 顯示有 v_name 欄位，這裡做動態偵測
        v_col = next((c for c in df_p.columns if 'v_name' in c or 'v_id' in c), df_p.columns[-1])
        n_col = next((c for c in df_p.columns if 'name' in c), df_p.columns[1])
        
        st.dataframe(df_p[[n_col, 'stock', v_col]].rename(columns={n_col:'商品','stock':'庫存',v_col:'供應商'}), 
                     use_container_width=True, hide_index=True)

# --- TAB 2: 出貨紀錄 (徹底修正日期與欄位問題) ---
with tabs[1]:
    res_o = supabase.table("order_history").select("*").execute()
    if res_o.data:
        df_o = smart_process(pd.DataFrame(res_o.data))
        df_o['pure_date'] = df_o['timestamp_fixed'].dt.date
        
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            # 修正日期：預設為「月初到今天」，確保不會因為當天沒資料而顯示 empty
            dr = c1.date_input("📅 日期範圍", [date.today().replace(day=1), date.today()])
            
            # 修正平台偵測：截圖 [image_0a4b9b.png] 顯示有「酷彭」
            p_col = next((c for c in df_o.columns if 'platform' in c or 'plt' in c), 'platform')
            plts = ["全部"] + sorted([str(x) for x in df_o[p_col].unique() if x])
            sel_plt = c2.selectbox("平台", plts)
            
            m_col = 'mode' if 'mode' in df_o.columns else df_o.columns[-1]
            modes = ["全部"] + sorted([str(x) for x in df_o[m_col].unique() if x])
            sel_mode = c3.selectbox("模式", modes)

        # 篩選邏輯
        start_d = dr[0]
        end_d = dr[1] if len(dr) > 1 else dr[0]
        mask = (df_o['pure_date'] >= start_d) & (df_o['pure_date'] <= end_d)
        
        if sel_plt != "全部": mask &= (df_o[p_col] == sel_plt)
        if sel_mode != "全部": mask &= (df_o[m_col] == sel_mode)
        
        final_o = df_o[mask].sort_values('timestamp_fixed', ascending=False)
        
        if not final_o.empty:
            # 救援商品名稱欄位 (p_name 或 name)
            item_col = next((c for c in final_o.columns if 'p_name' in c or 'item' in c or 'name' in c), final_o.columns[1])
            final_o['時間'] = final_o['timestamp_fixed'].dt.strftime('%m/%d %H:%M')
            
            show_cols = ['時間', item_col, 'quantity', m_col, p_col]
            # 確保欄位存在於顯示清單中
            show_cols = [c for c in show_cols if c in final_o.columns]
            
            st.dataframe(final_o[show_cols], use_container_width=True, hide_index=True)
        else:
            st.warning(f"💡 範圍 {start_d} ~ {end_d} 內無匹配數據。雲端現有筆數：{len(df_o)}")
            if st.checkbox("偵錯模式：顯示雲端原始資料前 5 筆"):
                st.write(df_o.head(5))
    else:
        st.info("雲端目前無任何出貨數據。")

# --- TAB 3: 物流件數 ---
with tabs[2]:
    res_l = supabase.table("shipping_log").select("*").execute()
    if res_l.data:
        df_l = smart_process(pd.DataFrame(res_l.data))
        st.write("🚚 最近物流紀錄")
        st.dataframe(df_l.sort_values('timestamp_fixed', ascending=False), use_container_width=True, hide_index=True)
