import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta

# --- 1. 初始化 ---
st.set_page_config(page_title="培玩雲端 ERP - 最終修復", layout="wide")

@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

# --- 2. 數據抓取 (關鍵：加入排序與提高上限) ---
@st.cache_data(ttl=10)
def fetch_all_data():
    try:
        # 【核心修正】：強制按 ID 倒序排列，並確保抓取最新的一萬筆資料
        # 這樣最新的 3559, 3566 絕對會排在最前面被抓進來
        res = supabase.table("order_history") \
            .select("*") \
            .order("id", desc=True) \
            .limit(10000) \
            .execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"資料抓取失敗: {e}")
        return pd.DataFrame()

# --- 3. 處理數據 ---
def smart_process(df):
    if df is None or df.empty: return pd.DataFrame()
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    # 僅做基礎轉換，不做任何過濾
    t_col = next((c for c in df.columns if any(k in c for k in ['timestamp', 'time', 'created_at'])), None)
    if t_col:
        df['tz_fixed'] = pd.to_datetime(df[t_col], utc=True).dt.tz_convert('Asia/Taipei').dt.tz_localize(None)
        df['pure_date'] = df['tz_fixed'].dt.date
    return df

raw_o = fetch_all_data()
df_o = smart_process(raw_o)

# --- 4. 介面呈現 ---
st.title("📦 出貨數據觀測")

if not df_o.empty:
    # 直接在最上方顯示一個「ID 搜尋」，測試 3559 是否存在於記憶體中
    search_id = st.text_input("🔍 輸入 ID 進行定位測試 (例如: 3559)", "")
    
    if search_id:
        # 強制轉字串比對 id 欄位
        test_res = df_o[df_o['id'].astype(str) == search_id]
        if not test_res.empty:
            st.success(f"✅ 找到 ID {search_id}！")
            st.write(test_res)
        else:
            st.error(f"❌ 記憶體中依然找不到 ID {search_id}")
            st.write("目前記憶體中最新的 5 筆 ID 為:", df_o['id'].head(5).tolist())

    st.write("---")
    
    # 原有的明細表
    today = date.today()
    sel_date = st.date_input("選擇日期範圍", [today, today])
    start_d, end_d = (sel_date[0], sel_date[1]) if len(sel_date) > 1 else (sel_date[0], sel_date[0])
    
    display_df = df_o[(df_o['pure_date'] >= start_d) & (df_o['pure_date'] <= end_d)]
    st.dataframe(display_df.sort_values('id', ascending=False), use_container_width=True)

else:
    st.warning("雲端無回傳任何資料。")

if st.button("🔄 強制刷新"):
    st.cache_data.clear()
    st.rerun()
