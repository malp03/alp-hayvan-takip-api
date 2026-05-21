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

`DATABASE_URL` ve `ALP_AUTH_SECRET` dosyaya yazilmamali ve GitHub'a gonderilmemeli.

## Yedekleme

Online verinin geri donusu icin iki yedek katmani kullan:

- PostgreSQL/Supabase otomatik yedekleri
- `tools/server_backup.py` ile gunluk `/api/yedek` JSON yedegi

Detayli kurulum icin `SERVER_BACKUPS.md` dosyasina bak.

## Android Hazirligi

Android uygulamasi ayni API'yi kullanacak. Endpointler, offline senkron kurali ve yerel tablo onerileri `ANDROID_API_CONTRACT.md` dosyasinda tutuluyor.
