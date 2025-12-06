import streamlit as st
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Sayfa Ayarları ---
st.set_page_config(page_title="Kişisel Finans Asistanım", layout="wide", page_icon="💰")

# --- Google Sheets Bağlantısı ---
def get_google_sheet():
    email = st.secrets["gcp_service_account"]["client_email"]
    private_key = st.secrets["gcp_service_account"]["private_key"].replace("\\n", "\n")

    creds_dict = {
        "type": "service_account",
        "project_id": "finans-app",
        "private_key_id": "ba456",
        "private_key": private_key,
        "client_email": email,
        "client_id": "123",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/example"
    }

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("FinansVerim").sheet1

# --- Başlık ---
st.title("📊 Kişisel Varlık ve Bütçe Yönetimi")

# --- Yan Menü ---
menu = ["Genel Bakış", "İşlem Ekle", "Portföy & Varlıklar", "İşlem Geçmişi"]
secim = st.sidebar.selectbox("Menü", menu)

# --- VERİLERİ GÜVENLİ ÇEKME (Hata Önleyici Modül) ---
sheet = None
df = pd.DataFrame()

try:
    sheet = get_google_sheet()
    data = sheet.get_all_records()
    
    # Eğer veri varsa DataFrame oluştur
    if data:
        df = pd.DataFrame(data)
        
        # Sütun isimlerini kontrol et (Tip sütunu var mı?)
        if "Tip" not in df.columns:
            st.error("⚠️ Hata: Google Tablo'da 'Tip' sütunu bulunamadı. Lütfen 1. satırdaki başlıkları kontrol et.")
            st.stop()
            
        # Sayısal dönüşümler
        cols = ['Tutar', 'Adet', 'Birim_Fiyat']
        for col in cols:
            if col in df.columns:
                 df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    else:
        # Veri yoksa bile boş ama doğru sütunlu bir tablo oluştur
        df = pd.DataFrame(columns=["Tarih", "Tip", "Kategori", "Tutar", "Aciklama", "Adet", "Birim_Fiyat", "Guncel_Deger"])

except Exception as e:
    st.error(f"Veri çekilirken hata oluştu: {e}")
    df = pd.DataFrame() # Hata durumunda boş tablo ile devam et


# --- 1. İŞLEM EKLEME ---
if secim == "İşlem Ekle":
    st.header("Yeni İşlem Ekle")
    
    with st.form("islem_formu"):
        col1, col2 = st.columns(2)
        tarih = col1.date_input("Tarih", datetime.date.today())
        tur = col2.selectbox("İşlem Türü", ["Gider", "Gelir", "Yatırım (Alış)", "Yatırım (Satış)"])
        
        if "Yatırım" in tur:
            kategori = st.selectbox("Enstrüman Adı (Fon Kodu/Hisse)", ["TTE", "IPB", "NNF", "THYAO", "ALTIN", "Diğer"])
        else:
            kategori = st.selectbox("Kategori", ["Market", "Fatura", "Kira", "Maaş", "Yeme-İçme", "Eğlence", "Diğer"])

        col3, col4 = st.columns(2)
        adet = 0.0
        birim_fiyat = 0.0
        tutar = 0.0

        if "Yatırım" in tur:
            st.info("👇 Yatırım Detaylarını Girin")
            adet = col3.number_input("Adet (Lot/Pay)", min_value=0.0, format="%.2f")
            birim_fiyat = col4.number_input("Birim Fiyat (₺)", min_value=0.0, format="%.4f")
            tutar = adet * birim_fiyat
            st.write(f"**Toplam Tutar:** {tutar:,.2f} ₺")
        else:
            tutar = st.number_input("Tutar (₺)", min_value=0.0, format="%.2f")
            
        aciklama = st.text_input("Açıklama (Opsiyonel)")
        
        kaydet = st.form_submit_button("Kaydet")
        
        if kaydet:
            if sheet is None:
                st.error("Veritabanı bağlantısı yok, kayıt yapılamadı.")
            else:
                tarih_str = tarih.strftime("%Y-%m-%d")
                yeni_satir = [tarih_str, tur, kategori, tutar, aciklama, adet, birim_fiyat, 0]
                sheet.append_row(yeni_satir)
                st.success(f"✅ {tur} işlemi kaydedildi!")
                st.rerun()

# --- 2. PORTFÖY & VARLIKLAR ---
elif secim == "Portföy & Varlıklar":
    st.header("📈 Yatırım Portföyüm")
    
    if not df.empty and "Tip" in df.columns:
        yatirim_df = df[df["Tip"].astype(str).str.contains("Yatırım")].copy()
        
        if not yatirim_df.empty:
            portfoy = yatirim_df.groupby("Kategori").agg({
                'Adet': 'sum',
                'Tutar': 'sum'
            }).reset_index()
            
            portfoy["Ort. Maliyet"] = portfoy["Tutar"] / portfoy["Adet"]
            portfoy["Güncel Fiyat (Tahmini)"] = portfoy["Ort. Maliyet"] * 1.10 
            portfoy["Toplam Değer"] = portfoy["Adet"] * portfoy["Güncel Fiyat (Tahmini)"]
            portfoy["Kâr/Zarar (₺)"] = portfoy["Toplam Değer"] - portfoy["Tutar"]
            portfoy["Kâr Oranı (%)"] = (portfoy["Kâr/Zarar (₺)"] / portfoy["Tutar"]) * 100
            
            st.dataframe(portfoy.style.format({
                "Tutar": "{:,.2f} ₺",
                "Ort. Maliyet": "{:,.4f} ₺",
                "Güncel Fiyat (Tahmini)": "{:,.4f} ₺",
                "Toplam Değer": "{:,.2f} ₺",
                "Kâr/Zarar (₺)": "{:,.2f} ₺",
                "Kâr Oranı (%)": "%{:,.2f}"
            }), use_container_width=True)
        else:
            st.info("Henüz yatırım kaydı yok.")
    else:
        st.write("Veri yok veya tablo başlıkları hatalı.")

# --- 3. GENEL BAKIŞ ---
elif secim == "Genel Bakış":
    st.header("Durum Özeti")
    if not df.empty and "Tip" in df.columns:
        # Tip sütununu string yap ki hata vermesin
        df["Tip"] = df["Tip"].astype(str)
        
        gelir = df[df["Tip"] == "Gelir"]["Tutar"].sum()
        gider = df[df["Tip"] == "Gider"]["Tutar"].sum()
        yatirim = df[df["Tip"].str.contains("Yatırım")]["Tutar"].sum()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Toplam Gelir", f"{gelir:,.2f} ₺")
        col2.metric("Toplam Gider", f"{gider:,.2f} ₺", delta_color="inverse")
        col3.metric("Yatırıma Giden", f"{yatirim:,.2f} ₺")
    else:
        st.info("Henüz veri yok.")

# --- 4. GEÇMİŞ ---
elif secim == "İşlem Geçmişi":
    st.header("Tüm Kayıtlar")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.write("Veri yok.")
