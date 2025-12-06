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
st.title("📊 Kişisel Varlık Yönetimi")

# --- Yan Menü ---
menu = ["Genel Bakış", "İşlem Ekle", "Portföy (Yatırım & BES)", "İşlem Geçmişi"]
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
    pass

# --- 1. İŞLEM EKLEME (GÜNCELLENDİ) ---
if secim == "İşlem Ekle":
    st.header("Yeni İşlem Ekle")

    # 1. ADIM: İşlem Türü Seçimi
    tur_listesi = ["Gider", "Gelir", "Yatırım (Normal)", "BES (Bireysel Emeklilik)"]
    tur_secimi = st.radio("İşlem Türü Seçiniz:", tur_listesi, horizontal=True)
    
    st.divider()

    # 2. ADIM: Dinamik Kategori Seçimi (Form DIŞINDA)
    kategori_adi = "" 
    
    col_secim, col_bos = st.columns([1, 1])
    
    with col_secim:
        # --- A. YATIRIM SEÇİLİRSE ---
        if tur_secimi == "Yatırım (Normal)":
            liste = ["Fiziki Altın (Gr)", "KHA Fonu", "RIK Fonu", "TZL Fonu", "DİĞER / ELLE GİRİŞ"]
            secilen = st.selectbox("Yatırım Aracı:", liste)
            
            if secilen == "DİĞER / ELLE GİRİŞ":
                kategori_adi = st.text_input("Yatırım Adını Buraya Yazın (Örn: THYAO):")
            else:
                kategori_adi = secilen

        # --- B. BES SEÇİLİRSE ---
        elif tur_secimi == "BES (Bireysel Emeklilik)":
            liste = ["NHN Fonu", "EİH Fonu", "FEİ Fonu", "DİĞER / ELLE GİRİŞ"]
            secilen = st.selectbox("BES Fonu:", liste)
            
            if secilen == "DİĞER / ELLE GİRİŞ":
                kategori_adi = st.text_input("BES Fon Adını Yazın:")
            else:
                kategori_adi = secilen
        
        # --- C. GELİR SEÇİLİRSE (YENİ) ---
        elif tur_secimi == "Gelir":
            # Sadece gelir kalemleri
            liste = ["Maaş", "Ek Ders", "DİĞER / ELLE GİRİŞ"]
            secilen = st.selectbox("Gelir Kaynağı:", liste)
            
            if secilen == "DİĞER / ELLE GİRİŞ":
                kategori_adi = st.text_input("Gelir Adını Yazın (Örn: Prim, Satış):")
            else:
                kategori_adi = secilen

        # --- D. GİDER SEÇİLİRSE ---
        else:
            # Sadece gider kalemleri
            liste = ["Market", "Fatura", "Kira", "Yeme-İçme", "Eğlence", "Ulaşım", "DİĞER / ELLE GİRİŞ"]
            secilen = st.selectbox("Gider Kategorisi:", liste)
            
            if secilen == "DİĞER / ELLE GİRİŞ":
                kategori_adi = st.text_input("Gider Adını Yazın:")
            else:
                kategori_adi = secilen

    # 3. ADIM: Detaylar ve Kaydetme (Form İÇİNDE)
    with st.form("islem_formu"):
        st.write(f"**Seçilen:** {tur_secimi} > {kategori_adi}")
        
        col1, col2 = st.columns(2)
        tarih = col1.date_input("Tarih", datetime.date.today())
        aciklama = st.text_input("Açıklama (Opsiyonel)")

        adet = 0.0
        birim_fiyat = 0.0
        tutar = 0.0
        
        # Eğer Yatırım veya BES ise Adet/Fiyat sor
        if "Yatırım" in tur_secimi or "BES" in tur_secimi:
            c1, c2 = st.columns(2)
            adet = c1.number_input("Adet (Lot/Pay/Gram)", min_value=0.0, format="%.2f")
            birim_fiyat = c2.number_input("Birim Fiyat (₺)", min_value=0.0, format="%.4f")
            tutar = adet * birim_fiyat
            st.info(f"💰 Toplam Tutar: {tutar:,.2f} ₺ (Otomatik Hesaplanacak)")
        else:
            # Gelir veya Gider ise sadece Tutar sor
            tutar = st.number_input("Tutar (₺)", min_value=0.0, format="%.2f")

        kaydet = st.form_submit_button("KAYDET")
        
        if kaydet:
            if sheet is None:
                st.error("Veritabanı bağlantısı yok.")
            elif kategori_adi == "":
                st.warning("Lütfen bir isim/kategori giriniz.")
            else:
                if "Yatırım" in tur_secimi or "BES" in tur_secimi:
                    hesaplanan_tutar = adet * birim_fiyat
                else:
                    hesaplanan_tutar = tutar

                tarih_str = tarih.strftime("%Y-%m-%d")
                yeni_satir = [tarih_str, tur_secimi, kategori_adi, hesaplanan_tutar, aciklama, adet, birim_fiyat, 0]
                
                sheet.append_row(yeni_satir)
                st.success(f"✅ İşlem başarıyla kaydedildi!")
                st.rerun()

# --- 2. PORTFÖY (YATIRIM & BES) ---
elif secim == "Portföy (Yatırım & BES)":
    st.header("📈 Varlıklarım")
    
    if not df.empty and "Tip" in df.columns:
        varlik_df = df[df["Tip"].astype(str).str.contains("Yatırım|BES", regex=True)].copy()
        
        if not varlik_df.empty:
            portfoy = varlik_df.groupby(["Tip", "Kategori"]).agg({
                'Adet': 'sum',
                'Tutar': 'sum'
            }).reset_index()
            
            portfoy = portfoy[portfoy['Adet'] > 0]
            portfoy["Ort. Maliyet"] = portfoy["Tutar"] / portfoy["Adet"]
            
            # Basit Simülasyon
            portfoy["Güncel Fiyat (Tahmini)"] = portfoy["Ort. Maliyet"] * 1.10 
            portfoy["Toplam Değer"] = portfoy["Adet"] * portfoy["Güncel Fiyat (Tahmini)"]
            portfoy["Kâr/Zarar (₺)"] = portfoy["Toplam Değer"] - portfoy["Tutar"]
            
            st.dataframe(portfoy.style.format({
                "Tutar": "{:,.2f} ₺",
                "Ort. Maliyet": "{:,.4f} ₺",
                "Güncel Fiyat (Tahmini)": "{:,.4f} ₺",
                "Toplam Değer": "{:,.2f} ₺",
                "Kâr/Zarar (₺)": "{:,.2f} ₺"
            }), use_container_width=True)
            
            toplam_bes = portfoy[portfoy["Tip"].str.contains("BES")]["Toplam Değer"].sum()
            toplam_yatirim = portfoy[portfoy["Tip"].str.contains("Yatırım")]["Toplam Değer"].sum()
            
            c1, c2 = st.columns(2)
            c1.metric("Toplam Normal Yatırım", f"{toplam_yatirim:,.2f} ₺")
            c2.metric("Toplam BES Birikimi", f"{toplam_bes:,.2f} ₺")
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
        yatirim_giden = df[df["Tip"].str.contains("Yatırım|BES", regex=True)]["Tutar"].sum()
        kalan = gelir - gider - yatirim_giden # Nakit akışı
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Toplam Gelir", f"{gelir:,.2f} ₺")
        col2.metric("Toplam Gider", f"{gider:,.2f} ₺", delta_color="inverse")
        col3.metric("Yatırım+BES", f"{yatirim_giden:,.2f} ₺")
        col4.metric("Kalan Nakit", f"{kalan:,.2f} ₺")
    else:
        st.info("Veri girişi bekleniyor...")

# --- 4. GEÇMİŞ ---
elif secim == "İşlem Geçmişi":
    st.header("Tüm Kayıtlar")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.write("Veri yok.")
