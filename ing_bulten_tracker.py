#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ING Aylık Ekonomi Bülteni Otomasyonu

Bu script:
1. ING Bankası'nın aylık ekonomi bülteni sayfasını kontrol eder
2. Yeni yayınlanan bültenleri tespit eder
3. PDF'leri indirir
4. Dropbox'a yükler
5. (İsteğe bağlı) E-posta bildirimi gönderir
"""

import os
import re
import json
import time
import requests
import smtplib
import datetime
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
from loguru import logger
from dotenv import load_dotenv
import dropbox

# .env dosyasını yükle
load_dotenv()

# Sabitler
ING_BULTEN_URL = "https://www.ing.com.tr/tr/ing/ekonomi-sayfasi/aylik-ekonomi-bulteni"
CACHE_FILE = "last_bulletins.json"

# Türkçe ay isimleri ve İngilizce karşılıkları
MONTH_MAPPING = {
    "Ocak": "January",
    "Şubat": "February",
    "Mart": "March",
    "Nisan": "April",
    "Mayıs": "May",
    "Haziran": "June",
    "Temmuz": "July",
    "Ağustos": "August",
    "Eylül": "September",
    "Ekim": "October",
    "Kasım": "November",
    "Aralık": "December"
}

# Çevre değişkenlerini al
DROPBOX_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = os.getenv("SMTP_PORT")
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "./downloads")
DROPBOX_UPLOAD_PATH = os.getenv("DROPBOX_UPLOAD_PATH", "/ING_Bultenler")

# Log ayarları
logger.add("ing_bulten_tracker.log", rotation="1 week")

class INGBultenTracker:
    def __init__(self):
        """Sınıfı başlat ve gerekli klasörleri oluştur."""
        self.download_dir = Path(DOWNLOAD_DIR)
        self.download_dir.mkdir(exist_ok=True)
        
        self.cache_file = Path(CACHE_FILE)
        
        # Dropbox istemcisini başlat (eğer token varsa)
        self.dbx = dropbox.Dropbox(DROPBOX_TOKEN) if DROPBOX_TOKEN else None
        
        # Son görülen bültenleri yükle
        self.last_bulletins = self._load_last_bulletins()

    def _load_last_bulletins(self):
        """Son görülen bültenleri cache dosyasından yükle."""
        if not self.cache_file.exists():
            return []
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Cache dosyası yüklenirken hata: {e}")
            return []
    
    def _save_last_bulletins(self, bulletins):
        """Son görülen bültenleri cache dosyasına kaydet."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(bulletins, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Cache dosyası kaydedilirken hata: {e}")
    
    def get_current_bulletins(self):
        """ING web sitesinden güncel bültenleri al."""
        try:
            response = requests.get(ING_BULTEN_URL)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            bulletins = []
            # Bülten içeriklerini içeren wrapper'lar
            wrappers = soup.select("div.wrapper-content")
            
            for wrapper in wrappers:
                # Bülten başlığını al
                title_elem = wrapper.select_one("strong")
                if not title_elem:
                    continue
                
                title = title_elem.text.strip()
                
                # PDF linkini al
                link_elem = wrapper.select_one("a[href$='.pdf']")
                if not link_elem:
                    continue
                
                pdf_url = link_elem['href']
                
                # URL'yi tam URL'ye dönüştür
                if pdf_url.startswith('/'):
                    pdf_url = f"https://www.ing.com.tr{pdf_url}"
                
                bulletins.append({
                    'title': title,
                    'url': pdf_url
                })
            
            return bulletins
            
        except Exception as e:
            logger.error(f"Web sitesinden bültenler alınırken hata: {e}")
            return []
    
    def find_new_bulletins(self, current_bulletins):
        """Yeni bültenleri belirle."""
        if not self.last_bulletins:
            logger.info("İlk çalıştırma - tüm bültenler yeni olarak işaretlenecek")
            return current_bulletins
        
        new_bulletins = []
        last_urls = [b['url'] for b in self.last_bulletins]
        
        for bulletin in current_bulletins:
            if bulletin['url'] not in last_urls:
                new_bulletins.append(bulletin)
        
        return new_bulletins
    
    def download_bulletin(self, bulletin):
        """Bülteni indir."""
        try:
            # PDF URL'sinden dosya adını çıkar
            filename = os.path.basename(bulletin['url'])
            file_path = self.download_dir / filename
            
            # PDF'i indir
            response = requests.get(bulletin['url'], stream=True)
            response.raise_for_status()
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Bülten indirildi: {filename}")
            
            return str(file_path)
        except Exception as e:
            logger.error(f"Bülten indirilirken hata: {e}")
            return None
    
    def upload_to_dropbox(self, file_path):
        """Dosyayı Dropbox'a yükle."""
        if not self.dbx:
            logger.warning("Dropbox token bulunamadı, yükleme atlanıyor")
            return False
        
        try:
            filename = os.path.basename(file_path)
            dropbox_path = f"{DROPBOX_UPLOAD_PATH}/{filename}"
            
            with open(file_path, 'rb') as f:
                self.dbx.files_upload(
                    f.read(),
                    dropbox_path,
                    mode=dropbox.files.WriteMode.overwrite
                )
            
            logger.info(f"Dosya Dropbox'a yüklendi: {dropbox_path}")
            return True
        except Exception as e:
            logger.error(f"Dropbox'a yüklerken hata: {e}")
            return False
    
    def send_notification(self, bulletin, file_path):
        """E-posta bildirimi gönder."""
        if not all([NOTIFY_EMAIL, SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD]):
            logger.warning("E-posta bilgileri eksik, bildirim atlanıyor")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = SMTP_USERNAME
            msg['To'] = NOTIFY_EMAIL
            msg['Subject'] = f"Yeni ING Bülteni: {bulletin['title']}"
            
            body = f"""
            <html>
            <body>
                <h2>Yeni ING Ekonomi Bülteni</h2>
                <p><strong>{bulletin['title']}</strong> yayınlandı ve Dropbox'a yüklendi.</p>
                <p>PDF URL: <a href="{bulletin['url']}">{bulletin['url']}</a></p>
                <p>İndirilen dosya: {os.path.basename(file_path)}</p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            with smtplib.SMTP(SMTP_SERVER, int(SMTP_PORT)) as server:
                server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Bildirim e-postası gönderildi: {NOTIFY_EMAIL}")
            return True
        except Exception as e:
            logger.error(f"E-posta gönderilirken hata: {e}")
            return False
    
    def check_expected_bulletin_for_current_month(self):
        """Mevcut ay için beklenen bültenin yayınlanıp yayınlanmadığını kontrol et."""
        current_date = datetime.datetime.now()
        current_month = current_date.month
        current_year = current_date.year
        
        # Eğer ay 1-5 arası değilse, gelecek ay için kontrol et
        if current_date.day > 5:
            logger.info("Ayın 5'inden sonra çalıştırıldı, gelecek ayın bülteni beklenmeyecek")
            return False
        
        # Türkçe ay adını bul
        month_name = list(MONTH_MAPPING.keys())[current_month - 1]
        expected_bulletin_title = f"Aylık Ekonomi Bülteni - {month_name} {current_year}"
        
        # Mevcut bültenleri al
        current_bulletins = self.get_current_bulletins()
        
        # Beklenen başlığı kontrol et
        for bulletin in current_bulletins:
            if expected_bulletin_title in bulletin['title']:
                logger.info(f"Beklenen bülten ({expected_bulletin_title}) bulundu")
                return True
        
        logger.warning(f"Beklenen bülten ({expected_bulletin_title}) henüz yayınlanmamış")
        return False
        
    def run(self):
        """Ana işlem akışını çalıştır."""
        logger.info("ING Bülten takipçisi başlatılıyor...")
        
        # Mevcut bültenleri al
        current_bulletins = self.get_current_bulletins()
        if not current_bulletins:
            logger.error("Bültenler alınamadı, işlem sonlandırılıyor")
            return
        
        logger.info(f"Toplam {len(current_bulletins)} bülten bulundu")
        
        # Mevcut ay için beklenen bülten kontrolü
        self.check_expected_bulletin_for_current_month()
        
        # Yeni bültenleri bul
        new_bulletins = self.find_new_bulletins(current_bulletins)
        logger.info(f"{len(new_bulletins)} yeni bülten bulundu")
        
        # Yeni bülten yoksa işlemi sonlandır
        if not new_bulletins:
            self._save_last_bulletins(current_bulletins)  # Son gördüğümüz bültenleri güncelle
            logger.info("Yeni bülten bulunamadı, işlem sonlandırılıyor")
            return
        
        # Her yeni bülten için işlem yap
        for bulletin in new_bulletins:
            logger.info(f"İşleniyor: {bulletin['title']}")
            
            # Bülteni indir
            file_path = self.download_bulletin(bulletin)
            if not file_path:
                continue
            
            # Dropbox'a yükle
            uploaded = self.upload_to_dropbox(file_path)
            
            # Bildirim gönder
            if uploaded and NOTIFY_EMAIL:
                self.send_notification(bulletin, file_path)
        
        # Son görülen bültenleri güncelle
        self._save_last_bulletins(current_bulletins)
        logger.info("İşlem tamamlandı")


if __name__ == "__main__":
    tracker = INGBultenTracker()
    tracker.run()
