# ING Ekonomi Bülteni Otomasyonu

Bu script, ING bankasının aylık ekonomi bültenlerini otomatik olarak kontrol eder, yeni yayınlanan bültenleri indirir ve Dropbox hesabınıza yükler.

## Kurulum

1. Gerekli paketleri yükleyin:

```bash
pip install -r requirements.txt
```

2. `.env.example` dosyasını `.env` olarak kopyalayın ve Dropbox API token'ınızı girin:

```bash
cp .env.example .env
```

3. Dosyayı düzenleyerek gerekli bilgileri ekleyin.

## Kullanım

Scripti çalıştırmak için:

```bash
python ing_bulten_tracker.py
```

Bu script'i bir cron job olarak ayarlayabilir ve her ay başında otomatik olarak çalıştırabilirsiniz:

```bash
# Crontab örneği (Her ayın 1, 2, 3, 4 ve 5. günlerinde saat 10:00'da çalıştır)
0 10 1-5 * * cd /path/to/ing-ekonomi-bulteni-automation && python ing_bulten_tracker.py
```

## Özellikler

- ING ekonomi bülteni sayfasını düzenli kontrol eder
- Yeni bültenleri tespit eder
- PDF'leri indirir
- Dropbox'a yükler
- Opsiyonel e-posta bildirimleri gönderir