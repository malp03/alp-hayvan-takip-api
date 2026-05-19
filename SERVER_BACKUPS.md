# Sunucu Yedekleri

Bu proje icin online verinin ana kaynagi Render uzerindeki API ve PostgreSQL veritabanidir. Guvenli yedek stratejisi iki katmanli olmalidir:

1. PostgreSQL saglayicisinin otomatik yedegi
2. API yedek endpointinden gunluk JSON dis aktarim

## Render/Supabase tarafinda

- PostgreSQL/Supabase panelinde otomatik yedekleri etkin tut.
- En az 7 gunluk geri donus penceresi hedefle.
- `DATABASE_URL`, `ALP_AUTH_SECRET` ve admin sifresi GitHub'a yazilmaz.

## Gunluk JSON yedek

`tools/server_backup.py` scripti API'ye admin kullanici ile girer ve `/api/yedek` sonucunu JSON dosyasi olarak kaydeder.

Ornek:

```powershell
$env:ALP_API_URL="https://alp-hayvan-takip-api.onrender.com"
$env:ALP_BACKUP_USERNAME="admin"
$env:ALP_BACKUP_PASSWORD="admin1234"
python tools/server_backup.py
```

Varsayilan cikti klasoru:

`backups/server`

## GitHub Actions ile otomatik calistirma

`.github/workflows/daily-api-backup.yml` dosyasi gunluk yedek icin hazirlandi.

GitHub repo ayarlarinda su secrets degerlerini ekle:

- `ALP_API_URL`
- `ALP_BACKUP_USERNAME`
- `ALP_BACKUP_PASSWORD`

Workflow calisinca yedek JSON dosyasini GitHub Actions artifact olarak saklar.

Not: Artifact uzun sureli arsiv degildir. Kritik veri icin ayrica Supabase/PostgreSQL otomatik yedegini mutlaka acik tut.
