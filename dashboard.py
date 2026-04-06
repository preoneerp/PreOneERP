import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import date

st.set_page_config(page_title="排查 4：日期篩選")
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
df = pd.DataFrame(supabase.table("order_history").select("*").order("timestamp", desc=True).range(0, 2000).execute().data)
df.columns = [str(c).lower().strip() for c in df.columns]
df['pure_date'] = pd.to_datetime(df['timestamp']).dt.date

# 模擬介面篩選
dr = st.date_input("選擇範圍", [date(2026, 3, 1), date.today()])
if len(dr) == 2:
    mask = (df['pure_date'] >= dr[0]) & (df['pure_date'] <= dr[1])
    df_final = df[mask]
    st.write(f"篩選範圍 {dr[0]} ~ {dr[1]} 內的筆數：{len(df_final)}")
    st.dataframe(df_final)
