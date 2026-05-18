# Render Deploy

Bu proje icin online API deploy hedefi Render Web Service.

## Ayarlar

- Build Command: `pip install -r requirements-api.txt`
- Start Command: `uvicorn api:app --host 0.0.0.0 --port $PORT`
- Health Check Path: `/api/health`

## Environment Variables

Render servisinde su degiskenleri ayarla:

- `DATABASE_URL`: Supabase Transaction Pooler PostgreSQL URL
- `ALP_API_CORS_ORIGINS`: `*` simdilik yeterli; Android yayina cikinca daha daraltabiliriz.

`DATABASE_URL` dosyaya yazilmamali ve GitHub'a gonderilmemeli.
