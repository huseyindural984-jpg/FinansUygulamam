import streamlit as st
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import yfinance as yf

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

# --- CANLI FİYAT MOTORU (Robots) ---
@st.cache_data(ttl=3600) # Verileri 1 saat hafızada tut, sürekli istek atma
def get_tefas_price(fon_kodu):
    """TEFAS'tan fon fiyatını çeker"""
    try:
        url = f"https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod={fon_kodu}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            # Basit string parse işlemi (HTML parse yerine daha hızlı)
            content = response.text
            start = content.find('<span id="MainContent_PanelInfo_LabelPrice">')
            if start != -1:
                sub = content[start:]
                end = sub.find('</span>')
                price_str = sub[44:end].replace(',', '.')
                return float(price_str)
    except:
        pass
    return None

@st.cache_data(ttl=3600)
def get_gold_usd_price():
    """Altın ve Dolar fiyatını yfinance'den çeker"""
    try:
        # Gram Altın (Ons * Dolar / 31.10) yaklaşık hesabı yerine
        # Direkt veri çekmeyi deneyelim veya sabit kuralım.
        # Yahoo Finance'de Gram Altın TRY kodu: 'GLD' tam karşılamaz.
        # Dolar Kuru:
        usd_try = yf.Ticker("TRY=X").history(period="1d")['Close'].iloc[-1]
        
        # Ons Altın:
        ons = yf.Ticker("GC=F").history(period="1d")['Close'].iloc[-1]
        
        gram_altin_tl = (ons * usd_try) / 31.1035
        return {"Dolar": usd_try, "Gram Altın": gram_altin_tl}
    except:
        return {"Dolar": 0, "Gram Altın": 0}

# --- Başlık ---
st.title("💎 Servet Yönetim İstasyonu")

# --- Yan Menü ---
menu = ["Genel Bakış", "İşlem Ekle", "CANLI PORTFÖY", "İşlem Geçmişi"]
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

# --- 1. İŞLEM EKLEME ---
if secim == "İşlem Ekle":
    st.header("Yeni İşlem Ekle")

    tur_listesi = ["Gider", "Gelir", "Yatırım (Normal)", "BES (Bireysel Emeklilik)"]
    tur_secimi = st.radio("İşlem Türü:", tur_listesi, horizontal=True)
    st.divider()

    kategori_adi = "" 
    col_secim, col_bos = st.columns([1, 1])
    
    with col_secim:
        if tur_secimi == "Yatırım (Normal)":
            # Listeyi senin verdiğin fonlara göre güncelledim
            liste = ["Fiziki Altın (Gr)", "KHA", "RIK", "TZL", "DİĞER"]
            secilen = st.selectbox("Yatırım Aracı:", liste)
            kategori_adi = st.text_input("Kod (Örn: THYAO)") if secilen == "DİĞER" else secilen

        elif tur_secimi == "BES (Bireysel Emeklilik)":
            liste = ["NHN", "EİH", "FEİ", "DİĞER"]
            secilen = st.selectbox("BES Fonu:", liste)
            kategori_adi = st.text_input("BES Fon Kodu:") if secilen == "DİĞER" else secilen
        
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
            adet = c1.number_input("Adet/Lot", min_value=0.0, format="%.2f")
            birim_fiyat = c2.number_input("Alış Fiyatı (₺)", min_value=0.0, format="%.4f")
            tutar = adet * birim_fiyat
            st.info(f"Maliyet: {tutar:,.2f} ₺")
        else:
            tutar = st.number_input("Tutar (₺)", min_value=0.0, format="%.2f")

        if st.form_submit_button("KAYDET"):
            if sheet:
                hesaplanan_tutar = adet * birim_fiyat if ("Yatırım" in tur_secimi or "BES" in tur_secimi) else tutar
                yeni_satir = [tarih.strftime("%Y-%m-%d"), tur_secimi, kategori_adi, hesaplanan_tutar, aciklama, adet, birim_fiyat, 0]
                sheet.append_row(yeni_satir)
                st.success("✅ Kaydedildi!")
                st.rerun()

# --- 2. CANLI PORTFÖY (EN BÜYÜK YENİLİK) ---
elif secim == "CANLI PORTFÖY":
    st.header("📈 Canlı Varlık Analizi")
    
    if not df.empty and "Tip" in df.columns:
        # Sadece Yatırım ve BES satırlarını al
        varlik_df = df[df["Tip"].astype(str).str.contains("Yatırım|BES", regex=True)].copy()
        
        if not varlik_df.empty:
            # 1. Elimizdeki toplam adetleri bulalım
            portfoy = varlik_df.groupby(["Tip", "Kategori"]).agg({
                'Adet': 'sum',
                'Tutar': 'sum' # Bu toplam ödenen para (Maliyet)
            }).reset_index()
            
            # Adeti 0 olanları çıkar (Satılmışsa)
            portfoy = portfoy[portfoy['Adet'] > 0]
            portfoy["Ort. Maliyet"] = portfoy["Tutar"] / portfoy["Adet"]
            
            # 2. CANLI FİYATLARI ÇEKELİM
            market_data = get_gold_usd_price() # Dolar ve Altın'ı bir kere çek
            
            guncel_fiyatlar = []
            
            progress_text = "Piyasa verileri çekiliyor..."
            my_bar = st.progress(0, text=progress_text)
            
            total_items = len(portfoy)
            
            for index, row in portfoy.iterrows():
                kod = row['Kategori']
                fiyat = 0
                
                # A. Fon Kontrolü (3 harfli ve büyükse genelde fondur)
                if len(kod) == 3 and kod.isupper() and kod not in ["BES", "USD", "EUR"]:
                    tefas_fiyat = get_tefas_price(kod)
                    if tefas_fiyat:
                        fiyat = tefas_fiyat
                    else:
                        fiyat = row['Ort. Maliyet'] # Bulamazsa maliyeti yaz
                
                # B. Altın Kontrolü
                elif "Altın" in kod:
                    fiyat = market_data["Gram Altın"]
                
                # C. Diğerleri için şimdilik maliyeti kullan
                else:
                    fiyat = row['Ort. Maliyet']
                
                guncel_fiyatlar.append(fiyat)
                my_bar.progress((index + 1) / total_items)
            
            my_bar.empty() # Yükleme çubuğunu kaldır
            
            # 3. Hesaplamalar
            portfoy["Canlı Fiyat"] = guncel_fiyatlar
            portfoy["Güncel Değer"] = portfoy["Adet"] * portfoy["Canlı Fiyat"]
            portfoy["Net Kâr (₺)"] = portfoy["Güncel Değer"] - portfoy["Tutar"]
            portfoy["Getiri (%)"] = (portfoy["Net Kâr (₺)"] / portfoy["Tutar"]) * 100
            
            # 4. Tabloyu Renklendir ve Göster
            st.write("### 🧩 Varlık Detayı")
            
            # Fonksiyon: Kâr ise yeşil, Zarar ise kırmızı yaz
            def color_profit(val):
                color = 'green' if val > 0 else 'red'
                return f'color: {color}'

            st.dataframe(portfoy.style.format({
                "Tutar": "{:,.2f} ₺",
                "Ort. Maliyet": "{:,.4f}",
                "Canlı Fiyat": "{:,.4f}",
                "Güncel Değer": "{:,.2f} ₺",
                "Net Kâr (₺)": "{:,.2f} ₺",
                "Getiri (%)": "%{:,.2f}"
            }).applymap(color_profit, subset=['Net Kâr (₺)', 'Getiri (%)']), use_container_width=True)
            
            # 5. Büyük Özet Kartları
            toplam_yatirilan = portfoy["Tutar"].sum()
            toplam_guncel = portfoy["Güncel Değer"].sum()
            toplam_kar = toplam_guncel - toplam_yatirilan
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Toplam Yatırılan", f"{toplam_yatirilan:,.2f} ₺")
            c2.metric("Anlık Toplam Değer", f"{toplam_guncel:,.2f} ₺")
            c3.metric("Toplam Kâr/Zarar", f"{toplam_kar:,.2f} ₺", delta=f"%{(toplam_kar/toplam_yatirilan)*100:.2f}")
            
        else:
            st.info("Portföy boş.")

# --- 3. GENEL BAKIŞ ---
elif secim == "Genel Bakış":
    st.header("💰 Nakit Akışı")
    if not df.empty and "Tip" in df.columns:
        df["Tip"] = df["Tip"].astype(str)
        gelir = df[df["Tip"] == "Gelir"]["Tutar"].sum()
        gider = df[df["Tip"] == "Gider"]["Tutar"].sum()
        yatirim_harcama = df[df["Tip"].str.contains("Yatırım|BES", regex=True)]["Tutar"].sum()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Gelirler", f"{gelir:,.2f} ₺")
        col2.metric("Giderler", f"{gider:,.2f} ₺", delta_color="inverse")
        col3.metric("Yatırıma Aktarılan", f"{yatirim_harcama:,.2f} ₺")
        
        st.subheader("Bütçe Durumu")
        kalan = gelir - gider - yatirim_harcama
        st.write(f"Cepte Kalan Nakit: **{kalan:,.2f} ₺**")
    else:
        st.info("Veri yok.")

elif secim == "İşlem Geçmişi":
    st.header("Kayıt Defteri")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
