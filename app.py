import streamlit as st
import pandas as pd
import datetime

st.set_page_config(page_title="Kişisel Finans Asistanım", layout="wide", page_icon="💰")
st.title("📊 Kişisel Varlık ve Bütçe Yönetimi")

menu = ["Genel Bakış", "Gelir/Gider Ekle", "Varlıklarım", "Fon Analizi"]
secim = st.sidebar.selectbox("Menü", menu)

if secim == "Genel Bakış":
    st.header("Varlık Durumu")
    st.write("Uygulaman çalışıyor! Burası senin paneli olacak.")
    col1, col2 = st.columns(2)
    col1.metric("Toplam Varlık", "0 ₺")
    col2.metric("Bu Ay Gider", "0 ₺")

elif secim == "Gelir/Gider Ekle":
    st.header("İşlem Ekle")
    st.write("Buradan harcamalarını gireceksin.")

elif secim == "Varlıklarım":
    st.header("Portföy")
    st.write("Yatırımların burada listelenecek.")

elif secim == "Fon Analizi":
    st.header("Fon Analizi")
    st.write("Fonlarının içindeki hisseleri burada göreceksin.")