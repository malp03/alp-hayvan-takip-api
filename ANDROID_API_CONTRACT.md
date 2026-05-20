# Android API Contract

Android uygulamasi masaustu uygulamayla ayni online API'yi kullanacak. Bir cihazda yapilan degisiklik API'ye gidince diger masaustu ve Android istemcileri ayni veriyi gormeli.

## Temel URL

Production:

`https://alp-hayvan-takip-api.onrender.com`

## Kimlik Dogrulama

1. `POST /api/auth/login`
2. Donen `access_token` guvenli alanda saklanir.
3. Sonraki isteklerde header gonderilir:

```http
Authorization: Bearer <token>
```

Oturum kontrolu:

- `GET /api/auth/me`
- `POST /api/auth/change-password`
- `POST /api/auth/device-token`: "bu cihazi tani" icin uzun sureli cihaz tokeni uretir.
- `POST /api/auth/device-login`: cihaz tokeninden yeni `access_token` alir.

Cihaz tokeni Android'de KeyStore, Windows'ta yerel uygulama verisi icinde saklanir. Kullanici cikis yaparsa bu yerel kayit silinmelidir.

## Roller ve Yetki

- `admin`: tum ciftlikleri, kullanicilari, hayvanlari, yedekleri ve islem gecmisini yonetebilir.
- `ciftlik`: sadece kendi ciftligindeki hayvanlari yonetir; ayni ciftlikteki admin ve kullanici islemlerini ortak gecmiste gorur.

Admin girisi Android'de once bir yonetim ekrani acmali: ciftlik sec, tum suruyu gor, kullanici/ciftlik yonet, islem gecmisi, yedek.

Normal kullanici girisi kendi ciftliginin suru ekranina direkt gecmeli.

## Ana Endpointler

Saglik:

- `GET /api/health`

Ciftlik:

- `GET /api/ciftlikler?aktif_dahil=true`
- `POST /api/ciftlikler`
- `PATCH /api/ciftlikler/{ciftlik_id}`
- `DELETE /api/ciftlikler/{ciftlik_id}`

Kullanici:

- `GET /api/kullanicilar`
- `POST /api/kullanicilar`
- `PATCH /api/kullanicilar/{kullanici_id}`
- `POST /api/kullanicilar/{kullanici_id}/sifre-sifirla`
- `DELETE /api/kullanicilar/{kullanici_id}`

Hayvan:

- `GET /api/hayvanlar?arsiv_dahil=true`
- `GET /api/hayvanlar/{hayvan_ref}`
- `POST /api/hayvanlar`
- `PATCH /api/hayvanlar/{hayvan_ref}`
- `DELETE /api/hayvanlar/{hayvan_ref}?kalici=true&degisiklik_zamani=GG/AA/YYYY%20SS:DD:SS`

Hayvan payload ek alanlari:

- `resmi_kupe_no`
- `ciftlik_kupe_no`
- `foto_data`: masaustu ve mobil icin kucultulmus JPEG data URI. Ilk surumde API JSON icinde tasinir.
- `foto_url`: ileride dosya depolama/S3 benzeri sistem gelirse kullanilacak URL alani.

Alt kayitlar:

- `POST /api/hayvanlar/{hayvan_ref}/tohumlamalar`
- `PATCH /api/hayvanlar/{hayvan_ref}/tohumlamalar/{tohumlama_ref}`
- `DELETE /api/hayvanlar/{hayvan_ref}/tohumlamalar/{tohumlama_ref}`
- `POST /api/hayvanlar/{hayvan_ref}/asi-prosedurler`
- `PATCH /api/hayvanlar/{hayvan_ref}/asi-prosedurler/{asi_ref}`
- `DELETE /api/hayvanlar/{hayvan_ref}/asi-prosedurler/{asi_ref}`
- `POST /api/hayvanlar/{hayvan_ref}/dogumlar`
- `PATCH /api/hayvanlar/{hayvan_ref}/dogumlar/{dogum_ref}`
- `DELETE /api/hayvanlar/{hayvan_ref}/dogumlar/{dogum_ref}`

Dogum `yavrular` icinde her yavru icin:

- `cins`
- `resmi_kupe_no`
- `ciftlik_kupe_no`
- `kupe`: geriye donuk uyumluluk icin gorunen/ana kupe.

Android kamera/galeri kupesi okudugunda sonuc once `resmi_kupe_no` veya `ciftlik_kupe_no` alanina yazilmali. Tarama sonucunda hayvan bulunursa direkt profil acilir; bulunamazsa yeni kayit ekrani o kupeyle doldurulur.

Rapor, uyari, gecmis, yedek:

- `GET /api/uyarilar`
- `GET /api/raporlar/ozet`
- `GET /api/islem-gecmisi`
- `GET /api/yedek`

## Offline Senkron Kurali

Her hayvan kaydinda `son_guncelleme` vardir. Offline silmede `degisiklik_zamani` gonderilir.

Kural: en yeni degisiklik kazanir.

- Merkezdeki `son_guncelleme` daha yeniyse eski offline kayit uygulanmaz.
- Offline kaydin `son_guncelleme` zamani daha yeniyse merkezdeki kaydin uzerine yazilir.
- Offline silme de `degisiklik_zamani` ile karsilastirilir.
- Eski offline silme, merkezde daha yeni degisen kaydi silemez.
- Android saati yanlis olabilir; senkron ekraninda bekleyen kuyruk ve son deneme zamani gosterilmeli.

## Android Yerel Tablolar

Minimum yerel tablolar:

- `session`: token, kullanici, rol, ciftlik, api_url
- `farms_cache`: admin ciftlik listesi
- `animals`: son bilinen hayvan verisi
- `pending_sync`: offline ekle/guncelle/sil kuyrugu
- `audit_cache`: son islem gecmisi

`pending_sync` alanlari:

- `id`
- `operation`: `upsert` veya `delete`
- `animal_id`
- `payload_json`
- `changed_at`
- `retry_count`
- `last_error`

## Ilk Android Is Akisi

1. Login ekrani
2. Token'i guvenli saklama
3. Kullanici rolune gore yonlendirme
4. Admin icin ciftlik secme/yonetim ekrani
5. Normal kullanici icin direkt suru ekranina gecis
6. Hayvan liste/kayit/duzenleme/tohumlama/asi/dogum ekranlari
7. Offline kuyruk ve otomatik baglanti kontrolu
8. Internet gelince otomatik senkron ve manuel `Senkronize` butonu
