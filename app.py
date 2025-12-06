import streamlit as st
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# --- Sayfa Ayarları ---
st.set_page_config(page_title="Kişisel Finans Asistanım", layout="wide", page_icon="💰")

# --- Google Sheets Bağlantısı (Ayarlar) ---
def get_google_sheet():
    # Streamlit Secrets'tan anahtarı alıyoruz
    key_dict = json.loads(st.secrets["gcp_service_account"]["api_key"])
    
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    
    # Tabloyu aç (İsmi 'FinansVerim' olmalı)
    sheet = client.open("FinansVerim").sheet1 
    return sheet

# --- Başlık ---
st.title("📊 Kişisel Varlık ve Bütçe Yönetimi")

try:
    sheet = get_google_sheet()
    st.success("✅ Veritabanı Bağlantısı Başarılı!")
except Exception as e:
    st.error(f"❌ Bağlantı Hatası: {e}")
    st.stop()

# --- Yan Menü ---
menu = ["Genel Bakış", "İşlem Ekle (Gelir/Gider)", "İşlem Geçmişi"]
secim = st.sidebar.selectbox("Menü", menu)

# --- VERİLERİ ÇEKME ---
# Google Sheets'ten tüm veriyi alıp Pandas tablosuna çeviriyoruz
data = sheet.get_all_records()
df = pd.DataFrame(data)

# --- 1. İŞLEM EKLEME ---
if secim == "İşlem Ekle (Gelir/Gider)":
    st.header("Yeni İşlem Ekle")
    
    with st.form("islem_formu"):
        col1, col2 = st.columns(2)
        tarih = col1.date_input("Tarih", datetime.date.today())
        tur = col2.selectbox("İşlem Türü", ["Gider", "Gelir", "Yatırım"])
        
        kategori = st.selectbox("Kategori", ["Market", "Fatura", "Kira", "Maaş", "Yeme-İçme", "Fon Alımı", "Hisse Alımı", "Diğer"])
        tutar = st.number_input("Tutar (₺)", min_value=0.0, format="%.2f")
        aciklama = st.text_input("Açıklama (Opsiyonel)")
        
        kaydet = st.form_submit_button("Kaydet")
        
        if kaydet:
            # Tarihi string formatına çevir
            tarih_str = tarih.strftime("%Y-%m-%d")
            # Yeni satırı hazırla
            yeni_satir = [tarih_str, tur, kategori, tutar, aciklama]
            
            # Google Sheet'e ekle
            sheet.append_row(yeni_satir)
            st.success(f"✅ İşlem başarıyla kaydedildi: {tutar} ₺")
            st.rerun() # Sayfayı yenile ki tablo güncellensin

# --- 2. GENEL BAKIŞ (DASHBOARD) ---
elif secim == "Genel Bakış":
    st.header("Durum Özeti")
    
    if not df.empty:
        # Gelir ve Giderleri Hesapla
        toplam_gelir = df[df["Tip"] == "Gelir"]["Tutar"].sum()
        toplam_gider = df[df["Tip"] == "Gider"]["Tutar"].sum()
        kalan = toplam_gelir - toplam_gider
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Toplam Gelir", f"{toplam_gelir:,.2f} ₺")
        col2.metric("Toplam Gider", f"{toplam_gider:,.2f} ₺", delta_color="inverse")
        col3.metric("Net Durum (Kalan)", f"{kalan:,.2f} ₺")
        
        st.subheader("Harcama Dağılımı")
        gider_df = df[df["Tip"] == "Gider"]
        if not gider_df.empty:
            st.bar_chart(gider_df.groupby("Kategori")["Tutar"].sum())
        else:
            st.info("Henüz gider kaydı yok.")
            
    else:
        st.warning("Henüz hiç veri girişi yapılmamış.")

# --- 3. İŞLEM GEÇMİŞİ ---
elif secim == "İşlem Geçmişi":
    st.header("Tüm Kayıtlar")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.write("Veri yok.")
