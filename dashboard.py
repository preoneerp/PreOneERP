import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(page_title="排查 2：時間對齊")
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

df = pd.DataFrame(supabase.table("order_history").select("*").order("timestamp", desc=True).range(0, 2000).execute().data)

# 測試這段邏輯是否殺掉舊資料
df.columns = [str(c).lower().strip() for c in df.columns]
df['tz_fixed'] = pd.to_datetime(df['timestamp'], errors='coerce') # coerce 很重要
df['pure_date'] = df['tz_fixed'].dt.date

st.write("時間轉換後的資料：")
st.dataframe(df[['timestamp', 'pure_date']]) # 檢查 pure_date 是否有出現舊日期
