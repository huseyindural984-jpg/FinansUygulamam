import streamlit as st
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import yfinance as yf
from bs4 import BeautifulSoup

# --- AYAR: https://docs.google.com/spreadsheets/d/1YSgaT62o3j59LLoi28bjwGtRJh8_74alFzglAsDYMcA/edit?gid=0#gid=0 ---
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

# --- PROFESYONEL VERİ MOTORU ---
@st.cache_data(ttl=600) # 10 dakikada bir güncelle
def get_market_data():
    """Dolar ve Gram Altın fiyatını çeker"""
    try:
        # Dolar Kuru (Yahoo Finance)
        usd_try = yf.Ticker("TRY=X").history(period="1d")['Close'].iloc[-1]
        
        # Ons Altın (Yahoo Finance)
        ons = yf.Ticker("GC=F").history(period="1d")['Close'].iloc[-1]
        
        # Gram Altın Hesabı: (Ons * Dolar) / 31.1035
        gram_altin_tl = (ons * usd_try) / 31.1035
        
        return float(usd_try), float(gram_altin_tl)
    except Exception as e:
        st.error(f"Piyasa verisi çekilemedi: {e}")
        return 1.0, 0.0 # Hata olursa doları 1 al ki bölme hatası olmasın

@st.cache_data(ttl=600)
def get_tefas_price(fon_kodu):
    """TEFAS'tan BeautifulSoup ile güvenli veri çeker"""
    try:
        url = f"https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod={fon_kodu}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            # TEFAS'taki Fiyat Etiketi ID'si: MainContent_PanelInfo_LabelPrice
            price_span = soup.find("span", {"id": "MainContent_PanelInfo_LabelPrice"})
            
            if price_span:
                price_str = price_span.text.strip().replace(',', '.')
                return float(price_str)
    except:
        pass
    return None

# --- BAŞLANGIÇ AYARLARI ---
st.title("💎 Servet Yönetim İstasyonu")

# --- GLOBAL DOLAR KURU ---
dolar_kuru, gram_altin_kuru = get_market_data()

# --- YAN MENÜ ---
st.sidebar.header("Ayarlar")
# Dolar Şalteri
show_usd = st.sidebar.toggle("💲 Dolar Bazlı Göster", value=False)

# Kura göre sembol ve bölen belirle
para_birimi = "$" if show_usd else "₺"
bolen = dolar_kuru if show_usd else 1.0

# Kur Bilgisi Göster
st.sidebar.info(f"🇺🇸 Dolar: {dolar_kuru:.2f} ₺\n🟡 Gram Altın: {gram_altin_kuru:.2f} ₺")

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
    pass # Sessiz kal

# --- 1. İŞLEM EKLEME ---
if secim == "İşlem Ekle":
    st.header("Yeni İşlem Ekle")
    st.caption(f"Veri girişi her zaman **TL** olarak yapılır. Analiz kısmında Dolar'a çevrilir.")
    
    tur_listesi = ["Gider", "Gelir", "Yatırım (Alış)", "Yatırım (Satış)", "BES (Bireysel Emeklilik)"]
    tur_secimi = st.radio("İşlem Türü:", tur_listesi, horizontal=True)
    st.divider()

    kategori_adi = "" 
    with st.container():
        if "Yatırım" in tur_secimi:
            liste = ["Fiziki Altın (Gr)", "KHA", "RIK", "TZL", "DİĞER"]
            secilen = st.selectbox("Yatırım Aracı:", liste)
            kategori_adi = st.text_input("Kod (Örn: THYAO):") if secilen == "DİĞER" else secilen
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
            etiket = "Alış Fiyatı (TL)" if "Satış" not in tur_secimi else "Satış Fiyatı (TL)"
            birim_fiyat = c2.number_input(etiket, min_value=0.0, format="%.4f")
            tutar = adet * birim_fiyat
            st.info(f"İşlem Tutarı: {tutar:,.2f} ₺")
        else:
            tutar = st.number_input("Tutar (TL)", min_value=0.0, format="%.2f")

        if st.form_submit_button("KAYDET"):
            if sheet:
                # Satış ise eksiye çevir
                hesaplanan_tutar = - (adet * birim_fiyat) if "Satış" in tur_secimi else (adet * birim_fiyat if "Yatırım" in tur_secimi or "BES" in tur_secimi else tutar)
                kayit_adet = -adet if "Satış" in tur_secimi else adet
                final_kategori = kategori_adi if kategori_adi else "Belirtilmedi"
                
                sheet.append_row([tarih.strftime("%Y-%m-%d"), tur_secimi, final_kategori, hesaplanan_tutar, aciklama, kayit_adet, birim_fiyat, 0])
                st.success("✅ Kaydedildi!")
                st.rerun()

# --- 2. CANLI PORTFÖY (DOLAR DESTEKLİ) ---
elif secim == "CANLI PORTFÖY":
    st.header(f"📈 Canlı Varlık Analizi ({para_birimi})")
    
    if not df.empty and "Tip" in df.columns:
        varlik_df = df[df["Tip"].astype(str).str.contains("Yatırım|BES", regex=True)].copy()
        
        if not varlik_df.empty:
            portfoy = varlik_df.groupby(["Tip", "Kategori"]).agg({'Adet': 'sum', 'Tutar': 'sum'}).reset_index()
            portfoy = portfoy[portfoy['Adet'] > 0]
            
            # Maliyet Hesabı
            portfoy["Ort. Maliyet (TL)"] = portfoy["Tutar"] / portfoy["Adet"]
            
            # CANLI FİYAT ÇEKME DÖNGÜSÜ
            guncel_fiyatlar_tl = []
            
            progress_text = "Piyasa verileri çekiliyor..."
            my_bar = st.progress(0, text=progress_text)
            
            for index, row in portfoy.iterrows():
                kod = row['Kategori'].upper()
                fiyat = row['Ort. Maliyet (TL)'] # Varsayılan: Maliyet
                
                # A. FON KONTROLÜ
                if len(kod) == 3 and "BES" not in row["Tip"]:
                    val = get_tefas_price(kod)
                    if val: fiyat = val
                
                # B. ALTIN KONTROLÜ
                elif "ALTIN" in kod or "GOLD" in kod:
                    fiyat = gram_altin_kuru
                
                # C. HİSSE SENEDİ (Opsiyonel: İleride BIST eklenirse buraya)
                
                guncel_fiyatlar_tl.append(fiyat)
                my_bar.progress((index + 1) / len(portfoy))
            
            my_bar.empty()
            
            # HESAPLAMALAR (Önce TL)
            portfoy["Canlı Fiyat (TL)"] = guncel_fiyatlar_tl
            portfoy["Güncel Değer (TL)"] = portfoy["Adet"] * portfoy["Canlı Fiyat (TL)"]
            portfoy["Kâr (TL)"] = portfoy["Güncel Değer (TL)"] - portfoy["Tutar"]
            portfoy["Getiri (%)"] = (portfoy["Kâr (TL)"] / portfoy["Tutar"]) * 100
            
            # EĞER DOLAR SEÇİLDİYSE GÖRÜNTÜYÜ DÖNÜŞTÜR
            if show_usd:
                portfoy["Maliyet ($)"] = portfoy["Tutar"] / bolen
                portfoy["Güncel Değer ($)"] = portfoy["Güncel Değer (TL)"] / bolen
                portfoy["Kâr ($)"] = portfoy["Kâr (TL)"] / bolen
                
                # Tablo için sadeleştirilmiş görünüm
                gosterim_df = portfoy[["Kategori", "Adet", "Maliyet ($)", "Güncel Değer ($)", "Kâr ($)", "Getiri (%)"]]
                
                # Format
                format_dict = {
                    "Maliyet ($)": "${:,.2f}",
                    "Güncel Değer ($)": "${:,.2f}",
                    "Kâr ($)": "${:,.2f}",
                    "Getiri (%)": "%{:,.2f}"
                }
            else:
                # TL Görünümü
                gosterim_df = portfoy[["Kategori", "Adet", "Ort. Maliyet (TL)", "Canlı Fiyat (TL)", "Güncel Değer (TL)", "Kâr (TL)", "Getiri (%)"]]
                format_dict = {
                    "Ort. Maliyet (TL)": "{:,.2f} ₺",
                    "Canlı Fiyat (TL)": "{:,.2f} ₺",
                    "Güncel Değer (TL)": "{:,.2f} ₺",
                    "Kâr (TL)": "{:,.2f} ₺",
                    "Getiri (%)": "%{:,.2f}"
                }

            # RENKLENDİRME VE GÖSTERİM
            def color_profit(val):
                color = 'green' if val > 0 else 'red'
                return f'color: {color}'

            col_subset = ['Kâr ($)', 'Getiri (%)'] if show_usd else ['Kâr (TL)', 'Getiri (%)']
            st.dataframe(gosterim_df.style.format(format_dict).applymap(color_profit, subset=col_subset), use_container_width=True)
            
            # KARTLAR
            toplam_deger = portfoy["Güncel Değer (TL)"].sum() / bolen
            toplam_maliyet = portfoy["Tutar"].sum() / bolen
            toplam_kar = toplam_deger - toplam_maliyet
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Toplam Portföy Değeri", f"{para_birimi}{toplam_deger:,.2f}")
            c2.metric("Toplam Maliyet", f"{para_birimi}{toplam_maliyet:,.2f}")
            c3.metric("Toplam Kâr/Zarar", f"{para_birimi}{toplam_kar:,.2f}", delta=f"%{(toplam_kar/toplam_maliyet)*100:.2f}")

        else:
            st.info("Portföy boş.")

# --- 3. GENEL BAKIŞ (DOLAR DESTEKLİ) ---
elif secim == "Genel Bakış":
    st.header(f"💰 Nakit Akışı ve Bütçe ({para_birimi})")
    
    if not df.empty and "Tip" in df.columns:
        # TL Olarak Hesapla
        gelir_tl = df[df["Tip"] == "Gelir"]["Tutar"].sum()
        gider_tl = df[df["Tip"] == "Gider"]["Tutar"].sum()
        yatirim_net_tl = df[df["Tip"].str.contains("Yatırım|BES", regex=True)]["Tutar"].sum()
        kalan_tl = gelir_tl - gider_tl - yatirim_net_tl
        
        # Gösterim için Çevir
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Toplam Gelir", f"{para_birimi}{gelir_tl / bolen:,.2f}")
        col2.metric("Toplam Gider", f"{para_birimi}{gider_tl / bolen:,.2f}", delta_color="inverse")
        col3.metric("Yatırıma Giden", f"{para_birimi}{yatirim_net_tl / bolen:,.2f}")
        col4.metric("Kalan Nakit", f"{para_birimi}{kalan_tl / bolen:,.2f}")
        
        st.divider()
        
        # Detaylı Gelir/Gider Tablosu (Opsiyonel)
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Gider Dağılımı")
            gider_df = df[df["Tip"] == "Gider"].groupby("Kategori")["Tutar"].sum().reset_index()
            if not gider_df.empty:
                gider_df["Tutar"] = gider_df["Tutar"] / bolen # Dönüştür
                st.dataframe(gider_df.style.format({"Tutar": f"{para_birimi}{{:,.2f}}"}))
        
        with c2:
            st.subheader("Gelir Dağılımı")
            gelir_df = df[df["Tip"] == "Gelir"].groupby("Kategori")["Tutar"].sum().reset_index()
            if not gelir_df.empty:
                gelir_df["Tutar"] = gelir_df["Tutar"] / bolen
                st.dataframe(gelir_df.style.format({"Tutar": f"{para_birimi}{{:,.2f}}"}))

# --- 4. GEÇMİŞ & DÜZELTME ---
elif secim == "İşlem Geçmişi & DÜZELTME":
    st.header("Kayıt Defteri")
    
    if "http" in SHEET_URL:
        st.link_button("📂 Tabloyu Aç (Düzenle)", SHEET_URL)

    if not df.empty:
        # Tabloyu da Dolar göstermek ister misin? Genelde kayıtlar orijinal kalmalı.
        # Ama bilgilendirme yapalım.
        st.info(f"Aşağıdaki tablo veritabanındaki **orijinal TL** kayıtlarıdır. Dolar dönüşümü sadece analiz sayfalarında yapılır.")
        st.dataframe(df.iloc[::-1], use_container_width=True)
        
        if st.button("Son Girilen Satırı Sil (Geri Al)", type="primary"):
            if sheet:
                total_rows = len(sheet.get_all_values())
                if total_rows > 1:
                    sheet.delete_rows(total_rows)
                    st.success("Silindi!")
                    st.rerun()
