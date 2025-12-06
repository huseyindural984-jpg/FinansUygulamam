import streamlit as st
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import yfinance as yf

# --- AYAR: https://docs.google.com/spreadsheets/d/1YSgaT62o3j59LLoi28bjwGtRJh8_74alFzglAsDYMcA/edit?gid=0#gid=0 ---
# (Kendi Google Sheet linkini tırnak içine yapıştır)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1YSgaT62o3j59LLoi28bjwGtRJh8_74alFzglAsDYMcA/edit?gid=0#gid=0" 

# --- Sayfa Ayarları ---
st.set_page_config(page_title="Servet Yönetim İstasyonu", layout="wide", page_icon="💎")

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

# --- CANLI FİYAT MOTORU ---
@st.cache_data(ttl=3600)
def get_tefas_price(fon_kodu):
    try:
        url = f"https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod={fon_kodu}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            content = response.text
            start = content.find('<span id="MainContent_PanelInfo_LabelPrice">')
            if start != -1:
                sub = content[start:]
                end = sub.find('</span>')
                return float(sub[44:end].replace(',', '.'))
    except:
        pass
    return None

@st.cache_data(ttl=3600)
def get_gold_usd_price():
    try:
        usd_try = yf.Ticker("TRY=X").history(period="1d")['Close'].iloc[-1]
        ons = yf.Ticker("GC=F").history(period="1d")['Close'].iloc[-1]
        gram_altin_tl = (ons * usd_try) / 31.1035
        return {"Dolar": usd_try, "Gram Altın": gram_altin_tl}
    except:
        return {"Dolar": 0, "Gram Altın": 0}

# --- Başlık ---
st.title("💎 Servet Yönetim İstasyonu")

# --- Yan Menü ---
menu = ["Genel Bakış", "İşlem Ekle", "CANLI PORTFÖY", "İşlem Geçmişi & DÜZELTME"]
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
    st.error(f"Bağlantı Hatası: {e}")

# --- 1. İŞLEM EKLEME ---
if secim == "İşlem Ekle":
    st.header("Yeni İşlem Ekle")
    tur_listesi = ["Gider", "Gelir", "Yatırım (Alış)", "Yatırım (Satış)", "BES (Bireysel Emeklilik)"]
    tur_secimi = st.radio("İşlem Türü:", tur_listesi, horizontal=True)
    st.divider()

    kategori_adi = "" 
    with st.container():
        if "Yatırım" in tur_secimi:
            liste = ["Fiziki Altın (Gr)", "KHA", "RIK", "TZL", "DİĞER"]
            secilen = st.selectbox("Yatırım Aracı:", liste)
            kategori_adi = st.text_input("Kod:") if secilen == "DİĞER" else secilen
        elif "BES" in tur_secimi:
            liste = ["NHN", "EİH", "FEİ", "DİĞER"]
            secilen = st.selectbox("BES Fonu:", liste)
            kategori_adi = st.text_input("BES Fonu:") if secilen == "DİĞER" else secilen
        elif tur_secimi == "Gelir":
            liste = ["Maaş", "Ek Ders", "DİĞER"]
            secilen = st.selectbox("Gelir Kaynağı:", liste)
            kategori_adi = st.text_input("Gelir Adı:") if secilen == "DİĞER" else secilen
        else:
            liste = ["Market", "Fatura", "Kira", "Yeme-İçme", "Eğlence", "Ulaşım", "DİĞER"]
            secilen = st.selectbox("Gider Kategorisi:", liste)
            kategori_adi = st.text_input("Gider Adı:") if secilen == "DİĞER" else secilen

    with st.form("islem_formu"):
        col1, col2 = st.columns(2)
        tarih = col1.date_input("Tarih", datetime.date.today())
        aciklama = st.text_input("Açıklama")
        
        adet = 0.0
        birim_fiyat = 0.0
        tutar = 0.0

        if "Yatırım" in tur_secimi or "BES" in tur_secimi:
            c1, c2 = st.columns(2)
            adet = c1.number_input("Adet (Lot/Gr)", min_value=0.0, format="%.2f")
            etiket = "Alış Fiyatı (₺)" if "Satış" not in tur_secimi else "Satış Fiyatı (₺)"
            birim_fiyat = c2.number_input(etiket, min_value=0.0, format="%.4f")
            tutar = adet * birim_fiyat
            st.info(f"Tutar: {tutar:,.2f} ₺")
        else:
            tutar = st.number_input("Tutar (₺)", min_value=0.0, format="%.2f")

        if st.form_submit_button("KAYDET"):
            if sheet:
                hesaplanan_tutar = - (adet * birim_fiyat) if "Satış" in tur_secimi else (adet * birim_fiyat if "Yatırım" in tur_secimi or "BES" in tur_secimi else tutar)
                kayit_adet = -adet if "Satış" in tur_secimi else adet
                
                # Eğer Kategori boşsa uyar
                final_kategori = kategori_adi if kategori_adi else "Belirtilmedi"
                
                sheet.append_row([tarih.strftime("%Y-%m-%d"), tur_secimi, final_kategori, hesaplanan_tutar, aciklama, kayit_adet, birim_fiyat, 0])
                st.success("✅ Kaydedildi!")
                st.rerun()

# --- 2. CANLI PORTFÖY ---
elif secim == "CANLI PORTFÖY":
    st.header("📈 Canlı Varlık Analizi")
    if not df.empty and "Tip" in df.columns:
        varlik_df = df[df["Tip"].astype(str).str.contains("Yatırım|BES", regex=True)].copy()
        if not varlik_df.empty:
            portfoy = varlik_df.groupby(["Tip", "Kategori"]).agg({'Adet': 'sum', 'Tutar': 'sum'}).reset_index()
            portfoy = portfoy[portfoy['Adet'] > 0]
            portfoy["Ort. Maliyet"] = portfoy["Tutar"] / portfoy["Adet"]
            
            market_data = get_gold_usd_price()
            guncel_fiyatlar = []
            
            my_bar = st.progress(0, text="Veriler çekiliyor...")
            for index, row in portfoy.iterrows():
                kod = row['Kategori']
                fiyat = row['Ort. Maliyet']
                if len(kod) == 3 and kod.isupper() and "BES" not in row["Tip"]:
                    val = get_tefas_price(kod)
                    if val: fiyat = val
                elif "Altın" in kod:
                    fiyat = market_data["Gram Altın"]
                guncel_fiyatlar.append(fiyat)
                my_bar.progress((index + 1) / len(portfoy))
            my_bar.empty()
            
            portfoy["Canlı Fiyat"] = guncel_fiyatlar
            portfoy["Güncel Değer"] = portfoy["Adet"] * portfoy["Canlı Fiyat"]
            portfoy["Kâr (₺)"] = portfoy["Güncel Değer"] - portfoy["Tutar"]
            portfoy["Getiri (%)"] = (portfoy["Kâr (₺)"] / portfoy["Tutar"]) * 100
            
            def color_profit(val): return f'color: {"green" if val > 0 else "red"}'
            st.dataframe(portfoy.style.format({"Tutar": "{:,.2f}","Ort. Maliyet": "{:,.4f}","Canlı Fiyat": "{:,.4f}","Güncel Değer": "{:,.2f}","Kâr (₺)": "{:,.2f}","Getiri (%)": "%{:,.2f}"}).applymap(color_profit, subset=['Kâr (₺)', 'Getiri (%)']), use_container_width=True)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Toplam Maliyet", f"{portfoy['Tutar'].sum():,.2f} ₺")
            c2.metric("Güncel Değer", f"{portfoy['Güncel Değer'].sum():,.2f} ₺")
            k = portfoy['Güncel Değer'].sum() - portfoy['Tutar'].sum()
            c3.metric("Kâr/Zarar", f"{k:,.2f} ₺")
        else: st.info("Portföy boş.")

# --- 3. GENEL BAKIŞ ---
elif secim == "Genel Bakış":
    st.header("💰 Nakit Akışı")
    if not df.empty and "Tip" in df.columns:
        gelir = df[df["Tip"] == "Gelir"]["Tutar"].sum()
        gider = df[df["Tip"] == "Gider"]["Tutar"].sum()
        yatirim = df[df["Tip"].str.contains("Yatırım|BES", regex=True)]["Tutar"].sum()
        col1, col2, col3 = st.columns(3)
        col1.metric("Gelirler", f"{gelir:,.2f} ₺")
        col2.metric("Giderler", f"{gider:,.2f} ₺", delta_color="inverse")
        col3.metric("Net Yatırım", f"{yatirim:,.2f} ₺")
        st.write(f"**Kalan Nakit:** {gelir - gider - yatirim:,.2f} ₺")

# --- 4. GEÇMİŞ & DÜZELTME (YENİLENDİ) ---
elif secim == "İşlem Geçmişi & DÜZELTME":
    st.header("Kayıt Defteri ve Düzenleme")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info("💡 Hata yaptıysan **'Son İşlemi Sil'** butonunu kullan. Daha eski hatalar için **'Tabloyu Düzenle'** diyerek Excel moduna geç.")
    with col2:
        # Excel Link Butonu
        if "http" in SHEET_URL:
            st.link_button("📂 Tabloyu Aç (Düzenle)", SHEET_URL)
        else:
            st.warning("Tablo Linki Girilmemiş!")

    # Tabloyu Göster
    if not df.empty:
        # Son eklenen en üstte görünsün diye ters çeviriyoruz
        st.dataframe(df.iloc[::-1], use_container_width=True)
        
        st.divider()
        st.subheader("⚠️ Tehlikeli Bölge")
        
        # SİLME BUTONU
        if st.button("Son Girilen Satırı Sil (Geri Al)", type="primary"):
            if sheet:
                # Toplam satır sayısını bul (Header dahil)
                total_rows = len(sheet.get_all_values())
                if total_rows > 1: # Başlığı silmeyelim
                    sheet.delete_rows(total_rows)
                    st.success("Son işlem veritabanından silindi!")
                    st.rerun()
                else:
                    st.warning("Silinecek veri yok.")
    else:
        st.write("Henüz veri yok.")
