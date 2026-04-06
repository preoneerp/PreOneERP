import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(page_title="排查 3：品名過濾")
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
df = pd.DataFrame(supabase.table("order_history").select("*").order("timestamp", desc=True).range(0, 2000).execute().data)
df.columns = [str(c).lower().strip() for c in df.columns]

# 測試：排除物流後的資料
# 原本寫法：df[~df['p_name'].str.contains("物流|包裹")]
# 修正寫法：加入 na=False
df_filtered = df[~df['p_name'].str.contains("物流|包裹", na=False)]

st.write(f"原始筆數：{len(df)}，過濾後筆數：{len(df_filtered)}")
st.dataframe(df_filtered)
