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

# --- VERİLERİ ÇEKME ---
sheet = None
df = pd.DataFrame()

try:
    sheet = get_google_sheet()
    data = sheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        cols = ['Tutar', 'Adet', 'Birim_Fiyat']
        for col in cols:
            if col in df.columns:
                 df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    else:
        df = pd.DataFrame(columns=["Tarih", "Tip", "Kategori", "Tutar", "Aciklama", "Adet", "Birim_Fiyat", "Guncel_Deger"])
except Exception as e:
    # Sessizce devam et, hata mesajı basma
    pass

# --- 1. İŞLEM EKLEME (DÜZELTİLEN KISIM) ---
if secim == "İşlem Ekle":
    st.header("Yeni İşlem Ekle")

    # DİKKAT: Bu seçimi formun DIŞINA aldık ki anında güncellensin
    tur_secimi = st.radio("Önce İşlem Türünü Seçin:", ["Gider", "Gelir", "Yatırım (Alış)", "Yatırım (Satış)"], horizontal=True)
    
    st.divider() # Araya çizgi çek

    with st.form("islem_formu"):
        col1, col2 = st.columns(2)
        tarih = col1.date_input("Tarih", datetime.date.today())
        
        # Seçilen türe göre form içeriğini değiştiriyoruz
        if "Yatırım" in tur_secimi:
            kategori = col2.selectbox("Yatırım Aracı (Fon/Hisse)", ["TTE", "IPB", "NNF", "THYAO", "ALTIN", "Diğer"])
            
            st.info("👇 Yatırım Detayları")
            c1, c2 = st.columns(2)
            adet = c1.number_input("Adet (Lot/Pay)", min_value=0.0, format="%.2f")
            birim_fiyat = c2.number_input("Birim Fiyat (₺)", min_value=0.0, format="%.4f")
            
            # Form içinde anlık hesaplama yapılamaz ama kullanıcıya bilgi verebiliriz
            tutar = adet * birim_fiyat 
            st.write("*(Tutar kaydederken otomatik hesaplanacak)*")
            
        else:
            # Gelir veya Gider ise
            kategori = col2.selectbox("Kategori", ["Market", "Fatura", "Kira", "Maaş", "Yeme-İçme", "Eğlence", "Diğer"])
            tutar = st.number_input("Tutar (₺)", min_value=0.0, format="%.2f")
            # Yatırım olmadığı için adet ve fiyat 0
            adet = 0.0
            birim_fiyat = 0.0

        aciklama = st.text_input("Açıklama (Opsiyonel)")
        
        # Kaydet Butonu
        kaydet = st.form_submit_button("Kaydet")
        
        if kaydet:
            if sheet is None:
                st.error("Veritabanı bağlantısı yok.")
            else:
                # Eğer yatırım ise tutarı biz hesaplayalım
                if "Yatırım" in tur_secimi:
                    hesaplanan_tutar = adet * birim_fiyat
                else:
                    hesaplanan_tutar = tutar

                tarih_str = tarih.strftime("%Y-%m-%d")
                yeni_satir = [tarih_str, tur_secimi, kategori, hesaplanan_tutar, aciklama, adet, birim_fiyat, 0]
                
                sheet.append_row(yeni_satir)
                st.success(f"✅ {tur_secimi} işlemi kaydedildi!")
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
            
            # Sıfıra bölünme hatasını önle
            portfoy = portfoy[portfoy['Adet'] > 0]
            
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
            st.info("Henüz portföyünde aktif bir yatırım yok.")
    else:
        st.write("Veri yok.")

# --- 3. GENEL BAKIŞ ---
elif secim == "Genel Bakış":
    st.header("Durum Özeti")
    if not df.empty and "Tip" in df.columns:
        df["Tip"] = df["Tip"].astype(str)
        gelir = df[df["Tip"] == "Gelir"]["Tutar"].sum()
        gider = df[df["Tip"] == "Gider"]["Tutar"].sum()
        yatirim = df[df["Tip"].str.contains("Yatırım")]["Tutar"].sum()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Toplam Gelir", f"{gelir:,.2f} ₺")
        col2.metric("Toplam Gider", f"{gider:,.2f} ₺", delta_color="inverse")
        col3.metric("Yatırıma Giden", f"{yatirim:,.2f} ₺")
    else:
        st.info("Veri girişi bekleniyor...")

# --- 4. GEÇMİŞ ---
elif secim == "İşlem Geçmişi":
    st.header("Tüm Kayıtlar")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.write("Veri yok.")
