import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(page_title="排查 1：基礎抓取", layout="wide")
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

@st.cache_data(ttl=5)
def fetch_data():
    # 測試是否能穿透 1000 筆
    r1 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(0, 999).execute()
    r2 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(1000, 1999).execute()
    r3 = supabase.table("order_history").select("*").order("timestamp", desc=True).range(2000, 2999).execute()
    return pd.DataFrame(r1.data + r2.data + r3.data)

df = fetch_data()
st.write(f"當前抓取總筆數：{len(df)}")
st.dataframe(df) # 檢查這裡是否有 3/31 以前的資料
