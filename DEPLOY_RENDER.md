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
- `ALP_STORAGE_QUOTA_MB`: Storage kota takibi icin bilgi amacli limit. Supabase Free icin `1024`.
- `ALP_DB_QUOTA_MB`: Database kota takibi icin bilgi amacli limit. Supabase Free icin `500`.

`DATABASE_URL`, `ALP_AUTH_SECRET` ve `SUPABASE_SERVICE_ROLE_KEY` dosyaya yazilmamali ve GitHub'a gonderilmemeli.

## Fotograf Storage

Supabase Storage'da `animal-photos` adli public bucket olustur. Bucket adi farkli olacaksa Render'da `ALP_PHOTO_BUCKET` ayni ada ayarlanmali.

API yeni hayvan fotograflarini once kucultulmus base64 olarak alabilir; Storage ayarlari varsa otomatik olarak bucket'a yukler ve kayda `foto_urls` olarak yazar. Storage ayarlari yoksa eski `foto_datas` alanlariyla calismaya devam eder.

## Yedekleme

Online verinin geri donusu icin iki yedek katmani kullan:

- PostgreSQL/Supabase otomatik yedekleri
- `tools/server_backup.py` ile gunluk `/api/yedek` JSON yedegi

Detayli kurulum icin `SERVER_BACKUPS.md` dosyasina bak.

## Android Hazirligi

Android uygulamasi ayni API'yi kullanacak. Endpointler, offline senkron kurali ve yerel tablo onerileri `ANDROID_API_CONTRACT.md` dosyasinda tutuluyor.
