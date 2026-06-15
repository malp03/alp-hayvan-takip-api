# Render Deploy

Bu proje icin online API deploy hedefi Render Web Service.

## Ayarlar

- Build Command: `pip install -r requirements-api.txt`
- Start Command: `uvicorn api:app --host 0.0.0.0 --port $PORT`
- Health Check Path: `/api/health`

## Environment Variables

Render servisinde su degiskenleri ayarla:

- `DATABASE_URL`: Supabase Transaction Pooler PostgreSQL URL
- `ALP_AUTH_SECRET`: Kullanici tokenlari icin guclu ve gizli anahtar
- `ALP_API_CORS_ORIGINS`: `*` simdilik yeterli; Android yayina cikinca daha daraltabiliriz.
- `SUPABASE_URL`: Supabase project URL. Fotograf Storage icin gerekli.
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role key. Sadece Render secret olarak saklanmali.
- `ALP_PHOTO_BUCKET`: Fotograf bucket adi. Varsayilan: `animal-photos`
- `ALP_PHOTO_BUCKET_PUBLIC`: Fotograflar herkese acik URL ile servis edilsin mi. Canli kullanim icin `false` olmali.
- `ALP_PHOTO_SIGNED_URL_TTL_SECONDS`: Private fotograflar icin gecici goruntuleme linki suresi. Varsayilan `604800` (7 gun).
- `ALP_STORAGE_QUOTA_MB`: Storage kota takibi icin bilgi amacli limit. Supabase Free icin `1024`.
- `ALP_DB_QUOTA_MB`: Database kota takibi icin bilgi amacli limit. Supabase Free icin `500`.

`DATABASE_URL`, `ALP_AUTH_SECRET` ve `SUPABASE_SERVICE_ROLE_KEY` dosyaya yazilmamali ve GitHub'a gonderilmemeli.

## Private Fotograf Storage

Supabase Storage'da `animal-photos` adli bucket olustur. Canli kullanimda bucket `Private` olmali; public bucket kullanilacaksa sadece test icin `ALP_PHOTO_BUCKET_PUBLIC=true` ayarla. Bucket adi farkli olacaksa Render'da `ALP_PHOTO_BUCKET` ayni ada ayarlanmali.

API yeni hayvan fotograflarini once kucultulmus base64 olarak alabilir; Storage ayarlari varsa otomatik olarak bucket'a yukler ve veritabaninda kalici public URL yerine `foto_paths` saklar. API cevap verirken oturumlu istek icin gecici `foto_urls` signed URL'leri uretir. Storage ayarlari yoksa eski `foto_datas` alanlariyla calismaya devam eder.

Android icin daha verimli yol `POST /api/hayvanlar/{hayvan_ref}/fotograflar` multipart endpoint'idir. Bu endpoint kamera/galeri dosyalarini dogrudan alir, Storage aktifse private path'e cevirir ve cevapta gecici goruntuleme URL'si dondurur. Hayvan veya fotograf silindiginde Storage'daki ilgili dosyalar da temizlenir.

## Render Cold Start

Render Free servisleri uykuya gecebilir. GitHub Actions icindeki `Render Keepalive` workflow'u `/api/health` adresini 10 dakikada bir pingler. `ALP_API_URL` secret'i tanimliysa onu, tanimli degilse canli Render API adresini kullanir. Workflow basarisiz olursa hata gizlenmez ve Actions ekraninda gorunur.

## Yedekleme

Online verinin geri donusu icin iki yedek katmani kullan:

- PostgreSQL/Supabase otomatik yedekleri
- `tools/server_backup.py` ile gunluk `/api/yedek` JSON yedegi

Detayli kurulum icin `SERVER_BACKUPS.md` dosyasina bak.

## Android Hazirligi

Android uygulamasi ayni API'yi kullanacak. Endpointler, offline senkron kurali ve yerel tablo onerileri `ANDROID_API_CONTRACT.md` dosyasinda tutuluyor.
