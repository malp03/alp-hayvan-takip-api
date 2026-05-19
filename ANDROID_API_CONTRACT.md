# Android Hazirlik Notlari

Android uygulamasi masaustu uygulamayla ayni online API'yi kullanmali. Boylece bir sistemde degisen veri diger sistemlerde de gorunur.

## Temel URL

Production:

`https://alp-hayvan-takip-api.onrender.com`

## Kimlik dogrulama

1. `POST /api/auth/login`
2. Donen `access_token` saklanir.
3. Sonraki isteklerde header:

```http
Authorization: Bearer <token>
```

## Roller

- `admin`: tum ciftlikleri, kullanicilari ve hayvanlari yonetebilir.
- `ciftlik`: sadece kendi ciftliginin hayvanlarini ve ortak islem gecmisini gorur.

## Ana endpointler

- `GET /api/health`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/ciftlikler`
- `GET /api/kullanicilar`
- `GET /api/hayvanlar?arsiv_dahil=true`
- `POST /api/hayvanlar`
- `PATCH /api/hayvanlar/{id}`
- `DELETE /api/hayvanlar/{id}?kalici=true&degisiklik_zamani=GG/AA/YYYY%20SS:DD:SS`
- `GET /api/islem-gecmisi`
- `GET /api/yedek`

## Offline senkron kurali

Her hayvan kaydinda `son_guncelleme` alanı vardir.

Kural:

- Merkezdeki `son_guncelleme` daha yeniyse eski offline kayit uygulanmaz.
- Offline kaydin `son_guncelleme` zamani daha yeniyse merkezdeki kaydin uzerine yazilir.
- Offline silme de `degisiklik_zamani` ile gonderilir.
- Eski offline silme, merkezde daha yeni degisen kaydi silemez.

Android de ayni kurala uymali.

## Android lokal tablolar

Minimum yerel tablolar:

- `users/session`
- `farms_cache`
- `animals`
- `pending_sync`
- `audit_cache`

`pending_sync` alanlari:

- `id`
- `operation`: `upsert` veya `delete`
- `animal_id`
- `payload_json`
- `changed_at`
- `retry_count`

## Ilk Android is akisi

1. Login ekrani
2. Token saklama
3. Ciftlik kullanicisiysa direkt kendi surusunu acma
4. Admin ise ciftlik secme ekrani
5. Hayvan liste/kayit/duzenleme
6. Offline kuyruk
7. Internet gelince otomatik senkron
