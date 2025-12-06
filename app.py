import streamlit as st
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Sayfa Ayarları ---
st.set_page_config(page_title="Kişisel Finans Asistanım", layout="wide", page_icon="💰")

# --- Google Sheets Bağlantısı (YENİ YÖNTEM) ---
def get_google_sheet():
    # Secrets'tan sadece email ve private_key alıyoruz
    email = st.secrets["gcp_service_account"]["client_email"]
    # Private key içindeki \n karakterlerini düzeltiyoruz
    private_key = st.secrets["gcp_service_account"]["private_key"].replace("\\n", "\n")

    # Robot kimliğini manuel oluşturuyoruz
    creds_dict = {
        "type": "service_account",
        "project_id": "finans-app", # Standart isim
        "private_key_id": "ba456", # Rastgele ID (Gspread kontrol etmez)
        "private_key": private_key,
        "client_email": email,
        "client_id": "123", # Rastgele ID
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/example"
    }

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # Tabloyu aç
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
try:
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
except:
    df = pd.DataFrame() # Boş tablo oluştur hata verme

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
            tarih_str = tarih.strftime("%Y-%m-%d")
            yeni_satir = [tarih_str, tur, kategori, tutar, aciklama]
            sheet.append_row(yeni_satir)
            st.success(f"✅ İşlem başarıyla kaydedildi: {tutar} ₺")
            st.rerun()

# --- 2. GENEL BAKIŞ ---
elif secim == "Genel Bakış":
    st.header("Durum Özeti")
    if not df.empty:
        # Tutar sütununu sayıya çevir (Hata önlemek için)
        df['Tutar'] = pd.to_numeric(df['Tutar'], errors='coerce').fillna(0)
        
        toplam_gelir = df[df["Tip"] == "Gelir"]["Tutar"].sum()
        toplam_gider = df[df["Tip"] == "Gider"]["Tutar"].sum()
        kalan = toplam_gelir - toplam_gider
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Toplam Gelir", f"{toplam_gelir:,.2f} ₺")
        col2.metric("Toplam Gider", f"{toplam_gider:,.2f} ₺", delta_color="inverse")
        col3.metric("Net Durum", f"{kalan:,.2f} ₺")
    else:
        st.info("Henüz veri yok.")

# --- 3. GEÇMİŞ ---
elif secim == "İşlem Geçmişi":
    st.header("Tüm Kayıtlar")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.write("Veri yok.")
