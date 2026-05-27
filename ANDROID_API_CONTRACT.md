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
- `GET /api/hayvanlar/bul?ref={okunan_metin}&kaynak=normal|kamera`
- `GET /api/hayvanlar/{hayvan_ref}`
- `POST /api/hayvanlar`
- `PATCH /api/hayvanlar/{hayvan_ref}`
- `DELETE /api/hayvanlar/{hayvan_ref}?kalici=true&degisiklik_zamani=GG/AA/YYYY%20SS:DD:SS`

Hayvan payload ek alanlari:

- `resmi_kupe_no`
- `ciftlik_kupe_no`
- `irk`: Simental, Holstein vb. serbest metin/opsiyonel irk bilgisi. Desktop, Android ve API yanitlarinda ayni alan adi kullanilir.
- `foto_datas`: geriye donuk uyumluluk icin max 3 kucultulmus JPEG data URI. Storage aktif degilse kullanilir.
- `foto_data`: ilk fotograf icin eski tekil alan; yeni istemciler `foto_datas` / `foto_urls` kullanmali.
- `foto_paths`: Storage aktifken max 3 private dosya yolu. API/veritabani icin kalici alan budur.
- `foto_path`: ilk private dosya yolu icin eski tekil alan.
- `foto_urls`: Storage aktifken API tarafindan uretilen gecici signed URL listesi. Ekranda gostermek icin kullanilir, kalici kayit gibi saklanmamali.
- `foto_url`: ilk gecici signed URL icin eski tekil URL alani.

Foto notu:
- API'de Supabase Storage ayarlari varsa (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ALP_PHOTO_BUCKET`) istemci base64 `foto_datas` gonderse bile API bunu private Storage'a yukler, DB'de `foto_paths` saklar ve cevapta oturumlu kullanici icin gecici `foto_urls` dondurur.
- Supabase bucket canli kullanimda private olmali. Signed URL suresi `ALP_PHOTO_SIGNED_URL_TTL_SECONDS` ile belirlenir; varsayilan 7 gundur.
- Android tarafinda yeni foto eklerken desktop ile ayni sekilde kucultulmus data URI gonderilebilir; daha verimli yol multipart endpoint'idir. Signed URL 401/403 verirse hayvan profilini API'den tekrar cekip yeni URL alin.

Alt kayitlar:

- `POST /api/hayvanlar/{hayvan_ref}/fotograflar`
  - `multipart/form-data`
  - alanlar: `fotograflar` (1-3 adet image dosyasi), `replace` (opsiyonel boolean)
  - Android kamera/galeri yuklemelerinde base64 yerine bu endpoint tercih edilmeli. Storage aktifse cevapta `foto_paths` ve gecici `foto_urls` doner.
- `DELETE /api/hayvanlar/{hayvan_ref}/fotograflar/{foto_index}`
  - `foto_index` 1 tabanlidir.
  - Storage aktifse silinen dosya Supabase Storage'dan da temizlenir.
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

### Kamera ile Kupe Tarama (Android'e Ozel Kritik Akis)

Android kamera veya galeriden kupe okudugunda:

1. Okunan metin buyuk harfe normalize edilir (`trim().uppercase()`), kullanici isterse duzeltir.
2. Kamera/galeri akisi `GET /api/hayvanlar/bul?ref={metin}&kaynak=kamera` sorgusunu kullanir.
   - `resmi_kupe_no`: okunan temiz metnin tamamiyla eslesir.
   - `ciftlik_kupe_no`: okunan metindeki rakamlarin son 6 hanesiyle eslesir.
   - Resmi kupe kisaltmalari kamera modunda kullanilmaz.
3. **tekil=true donerse:** `hayvanlar[0]` ile Hayvan Profil Ekrani acilir (liste ekranini atla).
4. **eslesme_sayisi > 1 donerse:** ayni son 6 haneyi tasiyan hayvanlar icin secim listesi gosterilir.
5. **eslesme_sayisi = 0 donerse:** Yeni hayvan kayit ekrani acilir, uygun alan okunan metinle doldurulur.
6. **Offline ise:** Yerel `animals` tablosunda ayni kurallar uygulanir.
   - `kaynak=kamera`: resmi kupe tam eslesme, ciftlik kupe son 6 hane.
   - `kaynak=normal`: resmi kupe, ciftlik kupe, ciftlik son 6 hane ve resmi kupe kisaltmasi.

Normal elle arama:
- `GET /api/hayvanlar?q={arama}` liste aramasidir.
- Resmi kupe ve ciftlik kupe icinde arar.
- Ciftlik kupe numarasinin son 6 hanesini kabul eder.
- Resmi kupe kisaltmasini kabul eder: ilk iki harf + bosluk + resmi kupe icindeki ard arda gelen 4 veya 5 rakam. Ornek: `TR 1234`, `TR 56789`.

Tarama kutuphanesi:
- Oncelikli secim: **ML Kit TextRecognition** (on-device, internet gerektirmez).
- Alternatif: **ZXing** (barkod/QR destegi de isteniyor ise).
- Kupe numaralari standart barkod icermeyebilir; sade basili/el yazisi rakam-harf icin OCR tercih edilmeli.

UX:
- Tarama ekrani tam ekran kamera preview olmali.
- Basarili okuma sesli/titresim geribildirim verir.
- Kullanici okunan metni onaylar veya duzeltir, sonra "Ara" tusuna basar (yanlis okuma toleransi).
- Iptal icin Android geri butonu veya ust sol X yeterli.

Rapor, uyari, gecmis, yedek:

- `GET /api/uyarilar`
- `GET /api/raporlar/ozet`
- `GET /api/islem-gecmisi`
- `GET /api/yedek`
- `GET /api/sistem-durumu` (admin): database boyutu, Storage aktifligi, kayit sayilari ve fotograf istatistikleri.
- `POST /api/admin/test-verilerini-sifirla` (admin): gercek kullanima gecmeden once test ciftlik/kullanici/hayvan/gecmis verilerini temizler, admin hesaplarini korur.

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
2. Token'i guvenli saklama (Android KeyStore)
3. Kullanici rolune gore yonlendirme:
   - `admin` -> ciftlik sec / yonetim ekrani
   - `ciftlik` -> direkt suru listesi
4. Hayvan listesi ekraninda **Tara butonu** (ust kisim)
5. Tara basilinca tam ekran kamera preview acilir
6. Kupe okunur -> kullanici onaylar/duzeltir -> Ara
7. Kupe bulunursa -> Hayvan Profil Ekrani
8. Kupe bulunamazsa -> Yeni Hayvan Kayit Ekrani (kupe dolu)
9. Hayvan ekle / duzenle / tohumla / asi / dogum akislari
10. Offline kuyruk ve otomatik baglanti kontrolu
11. Internet gelince otomatik senkron ve manuel Senkronize butonu

Ek not: Tara akisinda arama icin `/api/hayvanlar/bul?ref={metin}&kaynak=kamera` kullanilir. Tekil eslesme profil ekranina, coklu eslesme secim listesine, sifir eslesme yeni kayit ekranina gider.

## Hayvan Profil Sekmeler (Android)

Desktop profiliyle esdeger, sekme tabanli:

1. **Kimlik & Durum:** resmi/ciftlik kupe, cins, irk, yas, durum rozeti
2. **Ozet:** gebe mi, son tohumlama, yaklasan dogum
3. **Tohumlama Gecmisi:** liste + yeni tohumlama ekle
4. **Dogum & Yavru Gecmisi:** liste + yeni dogum kaydi
5. **Asi / Prosedur:** liste + yeni asi ekle
6. **Fotograflar:** max 3 fotograf, kameradan veya galeriden ekleme
