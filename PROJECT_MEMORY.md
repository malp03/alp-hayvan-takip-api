# ALP Ziraat Proje Hafizasi

Son guncelleme: 21 Mayis 2026

Bu dosya projenin mevcut halini, yapilan degisiklikleri, testleri ve dagitim notlarini hatirlamak icin tutulur. Yeni bir isleme baslamadan once burayi oku.

## Proje Ozeti

Alp Ziraat Suru Takip uygulamasi, ciftliklerin suru kayitlarini yonetmesi icin yazilmis bir masaustu uygulamasidir.

- Masaustu uygulamasi: `alp_ziraat_hayvan_takip.py`
- Arayuz: Tkinter tabanli koyu dashboard tasarimi
- Online API: FastAPI
- Online veritabani: Render uzerinde calisan API'nin baglandigi online database
- Yerel veri: Windows `APPDATA/ALP Ziraat/HayvanTakip` altinda cache, offline oturum, bekleyen senkron, islem gecmisi ve ayarlar
- Hedef: Desktop tarafini stabil hale getirip Android uygulamaya ayni API ile gecmek

## Ana Dosyalar

- `alp_ziraat_hayvan_takip.py`: Desktop uygulamanin ana dosyasi. UI, login, offline mod, senkron, admin paneli, hayvan kayitlari burada.
- `api.py`: Lokal/API kaynak dosyasi.
- `api_deploy/`: Render'a deploy edilecek API dosyalari.
- `models.py`, `schemas.py`, `database.py`, `init_db.py`: API model, schema, database ve baslangic islemleri.
- `alp_ziraat_export.py`: Excel/PDF export yardimcilari.
- `alp_ziraat_is_kurallari.py`: Hayvan durum/uyari gibi ortak is kurallari.
- `installer/`: Kurulum dosyasi uretimi ve install/uninstall scriptleri.
- `tools/`: Smoke testler, API testleri, server backup araclari.
- `.github/workflows/daily-api-backup.yml`: Gunluk API yedegi alan GitHub Actions workflow'u.
- `ANDROID_API_CONTRACT.md`: Android tarafina geciste API kontrati.
- `SERVER_BACKUPS.md`: Sunucu yedek sistemi notlari.
- `DEPLOY_RENDER.md`: Render deploy talimatlari.

## Kullanici ve Ciftlik Modeli

- Admin kullanici tum ciftlikleri, kullanicilari ve kayitlari gorebilir/duzenleyebilir.
- Normal kullanici sadece kendi ciftliginin suru kayitlarini gorebilir/duzenleyebilir.
- Admin panelinde ciftlik yonetimi, kullanici yonetimi, yeni kullanici olusturma, islem gecmisi, online yedek indirme, sifre degistirme ve senkron islemleri vardir.
- Ciftlik silinirse o ciftlige ait hayvanlar da databaseden tamamen silinir; bu yuzden silme isleminde onay uyarisi vardir.
- Kullanici silme ve ciftlik silme admin yetkisi ister.
- Hassas bilgi: Admin sifresi gibi bilgiler repo notlarina yazilmamalidir.

## Online API ve Database

- Desktop ve ileride Android ayni API'ye baglanacak.
- API adresi su an Render uzerinden kullaniliyor: `https://alp-hayvan-takip-api.onrender.com`
- Database online oldugu icin baska bilgisayar veya Android tarafinda yapilan degisiklikler ayni merkezi kaynaga gider.
- API degisirse Render redeploy gerekir.
- Sadece desktop UI degisirse Render redeploy gerekmez; yeni EXE/setup uretmek yeterlidir.

## Offline ve Senkron Mantigi

- Internet yokken uygulama son basarili kullanici oturumuyla offline acilabilir.
- Offline durumda hayvan ekleme, duzenleme ve silme yerel bekleyen senkron kuyruguna alinir.
- Internet geri geldiginde `Senkronize` ile bekleyen degisiklikler API'ye gonderilir.
- Otomatik baglanti kontrolu eklendi; uygulama periyodik olarak API health kontrol eder.
- Degisikliklerde `updated_at` mantigi kullanilir: online ve offline farkli cihazlarda degisiklik varsa daha yeni degistirilme tarihi kazanmalidir.
- Offline modda ciftlik/kullanici/sifre/online gecmis gibi guvenlik ve merkezi veri isteyen islemler kapali tutulur.

## Islem Gecmisi

- Islem gecmisi kullanici bazli degil, ayni ciftlik icindeki herkesin ortak gorebilecegi sekilde tasarlandi.
- Adminin o ciftlikte yaptigi degisiklikler de ilgili ciftligin gecmisinde gorunur.
- Iki normal kullanici ayni ciftlikteyse birbirlerinin yaptigi islemleri ayni gecmiste gorebilir.
- Admin tum ciftliklerin gecmisini filtreleyebilir.

## UI / UX Degisiklikleri

- Eski koyu yesil/klasik gorunum yerine modern koyu dashboard tasarimina gecildi.
- Beyaz tema ve tema degistirme butonu kaldirildi; uygulama sabit koyu tema ile calisir.
- Header sade hale getirildi: istatistik, Online/Offline durumu ve ana aksiyonlar.
- API adresi normal ciftlik ekraninda gereksiz gorunmesin diye sade durum metnine indirildi.
- `Senkronize` ve baglanti yenileme mantigi birlestirildi.
- Header butonlari responsive hale getirildi; dar ekranda alt satira duser.
- Admin paneline scroll eklendi; kucuk pencerede alttaki butonlara erisilebilir.
- Admin panelinde ciftlik listesine cift tiklayinca ilgili ciftlige girme eklendi.
- Login ekranina logo eklendi, butonlar `Giris` ve `Cikis` olarak duzenlendi.
- Pencere ve kisayol ikonlari logo bozulmasin diye iyilestirildi.
- Hayvan duzenleme popup'inda kaydet butonu daha uygun konuma alindi.
- Popup pencerelerin modern koyu tema ile uyumlu olmasi icin duzenlemeler yapildi.

## Hayvan Kayit ve Profil Ozellikleri

- Hayvan kaydi: resmi kupe no, ciftlik kupe no, dogum tarihi, cins, anne kupe no.
- Hayvan listesi filtreleri: aktif, arsivli vb.
- Arsivli hayvani arsivden cikarma eklendi.
- Hayvan profilini zenginlestirme yapildi: kimlik/durum, ozet, tohumlama gecmisi, dogum-yavru gecmisi, asi/prosedur gecmisi.
- Hayvan profilinin ust kismi kompakt hale getirildi: buyuk bos header kaldirildi, profil basligi/rozetler/aksiyon bar ayrildi.
- Hayvan profilinde fotograf ekleme butonu sadece fotograf kartinda tutulur; ust aksiyon barinda tekrar edilmez.
- Hayvan profilinden `Tohumla` akisi eklendi: hayvan profilindeyken tohumlama ekranina gidip hayvan otomatik secili gelir.
- Tohumlanamayacak hayvanlarda, ornegin dana/erkek gibi uygun olmayan cinslerde, sag tik menude tohumlama secenegi cikmamali.
- Hayvanlara fotograf ekleme destegi eklendi.
- Yeni hayvan kaydederken de 3 fotograf slotu desteklenir; kayit sirasinda secilen fotograflar `foto_datas` listesine yazilir.
- Yeni hayvan kaydinda fotograf secimi toplu yapilabilir. Buton metni `Fotoğraf Ekle`dir. Onizlemeler sabit boyutlu slot/canvas yapisindadir, fotograflar slotu cover/crop mantigiyla doldurur; her slotun sag ustundeki `X` ile istenen fotograf kaldirilir.
- Onceden fotograf eklenmeyen hayvanlarin profilinden sonradan fotograf eklenebilir.
- Hayvan fotograflari profil ekraninda gosterilmelidir.
- Hayvan basina en fazla 3 fotograf desteklenir. Eski `foto_data` alanı korunur, yeni coklu alan `foto_datas` listesidir. Ilk fotograf geriye donuk uyumluluk icin `foto_data` olarak da tutulur.
- Profildeki kucuk fotografa tiklaninca buyuk onizleme penceresi acilir.

## Dogum ve Yavru Akisi

- Yeni dogum kaydinda yavru bilgileri alinirken yeni kupe numarasi degisikliklerinin sorulmasi gerekiyor.
- Dogum/yavru popup butonlari gorunur ve modern olmalidir.
- Bu alan Android tarafina gecmeden once tekrar test edilmesi gereken onemli akislar arasinda.

## Login ve Donma Duzeltmeleri

Son kritik duzeltme login ekranindaki `Yanit Vermiyor` problemiydi.

Yapilanlar:

- Login sirasindaki API istegi ana Tkinter thread'inden ayrildi.
- Login islemi arka planda `threading.Thread` ile calisir.
- Worker thread sonucu dogrudan Tkinter'a yazmaz; `queue.Queue` ile UI thread'e aktarir.
- UI thread `after` ile kuyrugu kontrol eder ve sonucu ekrana yansitir.
- Giris sirasinda inputlar ve giris butonu kilitlenir, pencere yine yanit vermeye devam eder.
- Buton animasyonundaki timer bug'i duzeltildi. `_animate_canvas_bg` icinde `after` yanlislikla buton parcalari kadar kez planlaniyordu; artik frame basina tek kez planlanir.
- `Bu bilgisayari tani` otomatik giris denemelerindeki timeoutlar kisaltildi.
- `tools/smoke_login_responsive.py` eklendi. Bu test login istegini bilerek geciktirir ve pencerenin yanit vermeye devam ettigini dogrular.

## Testler

Tam test komutu:

```powershell
python tools\run_smoke_tests.py
```

Bu komut sunlari calistirir:

- Python syntax check
- Pyflakes static check
- Desktop UI smoke
- Admin popup UI smoke
- Login UI smoke
- Login responsiveness smoke
- API HTTP smoke

Son bilinen durum: 21 Mayis 2026 tarihinde tum smoke testler gecti.

Tekil testler:

```powershell
python tools\smoke_ui.py
python tools\smoke_admin_popups.py
python tools\smoke_login.py
python tools\smoke_login_responsive.py
python tools\smoke_api.py
```

## Build ve Kurulum

EXE uretimi:

```powershell
python -m PyInstaller alp_ziraat_hayvan_takip.spec --noconfirm
```

Kurulum paketi uretimi:

```powershell
powershell -ExecutionPolicy Bypass -File installer\make_installer.ps1
```

Son uretilen dosyalar:

- `dist/ALP_Ziraat_Hayvan_Takip.exe`
- `dist/ALP_Ziraat_Hayvan_Takip_Setup.exe`
- `dist/ALP_Ziraat_Hayvan_Takip_Kurulum.zip`

Kullanici masaustu kisayolundan eski kurulu EXE'yi calistiriyorsa eski hatalari gormeye devam edebilir. Yeni duzeltmelerin kullanilmasi icin yeni `Setup.exe` ile tekrar kurulum yapilmalidir.

## GitHub ve Release Notlari

Bu bilgisayarda `git` komutu kurulu gorunmeyebilir; bu bir kod sorunu degildir. GitHub'a dosyalar web arayuzunden yuklenebilir veya bilgisayara Git kurulabilir.

Desktop degisikligi varsa genelde push edilecek dosyalar:

- `alp_ziraat_hayvan_takip.py`
- Degisen `tools/*.py` dosyalari
- Degisen `installer/*` dosyalari
- Degisen dokumanlar

API degisikligi varsa ayrica:

- `api.py`
- `api_deploy/`
- `models.py`
- `schemas.py`
- `database.py`
- `init_db.py`
- `requirements-api.txt`
- `render.yaml`

Release icin GitHub Releases'a genelde sunlar yuklenir:

- `dist/ALP_Ziraat_Hayvan_Takip_Setup.exe`
- Istege bagli: `dist/ALP_Ziraat_Hayvan_Takip_Kurulum.zip`

Yeni API kodu push edildiyse Render'da:

```text
Manual Deploy > Deploy latest commit
```

Sonra kontrol:

```text
https://alp-hayvan-takip-api.onrender.com/api/health
```

## Android Hazirlik

Android uygulama desktop ile ayni merkezi API'yi kullanacak.

Android icin onemli hazirliklar:

- API kontrati `ANDROID_API_CONTRACT.md` icinde tutulur.
- Mobil login ayni kullanici/ciftlik/admin modelini kullanmali.
- Hayvan listesi, profil, fotograf ve tohumlama akislarinda desktop davranisi referans alinmali.

### Android Kamera ile Kupe Tarama (Kritik Ozellik)

Bu ozellik Android uygulamasinin temel ayirt edici ozelligi olup mutlaka implemente edilmeli:

- Hayvan listesi ekraninda bir `Tara` butonu bulunur.
- Butona basildiginda kamera acilir; kullanici hayvana takilmis kupedeki numarayi kameraya gosterir.
- Tarama ML Kit (Google) veya ZXing kutuphanesi ile yapilabilir. Kupe numaralari genellikle sade rakam/harf dizisidir; OCR veya barkod/QR destegi gerekmez; elle yazilmis/baski duz metin icin kamera ile metin okuma (MLKit TextRecognition) kullanilmali.
- Tarama tamamlaninca okunan metin once `resmi_kupe_no` veya `ciftlik_kupe_no` alaninda `GET /api/hayvanlar/{ref}` ile sorgulanir.
- **Hayvan bulunursa:** Hayvan listesi ekranini atla, direkt o hayvani profil ekrani ac.
- **Hayvan bulunamazsa:** Yeni hayvan kayit ekrani ac, okunan kupe numarasini `ciftlik_kupe_no` alanina otomatik doldur.
- Galeri uzerinden de foto/tarama secimi desteklenebilir (ileride).
- Tarama sonucu bos veya okunamaz ise kullaniciya uyari goster ve tekrar deneme imkani ver.
- API arama hem `resmi_kupe_no` hem `ciftlik_kupe_no` uzerinden calisir; `hayvan_bul` endpoint zaten her ikisinde de arama yapabiliyor (`GET /api/hayvanlar/{ref}`).
- Offline modda kupe sorgusu yerel SQLite cache uzerinden yapilir.

### Android Is Akisi (Kamera Dahil)

1. Login ekrani
2. Token guvenli saklama (Android KeyStore)
3. Kullanici rolune gore yonlendirme (admin → ciftlik sec, normal → direkt suru)
4. Hayvan listesi ekrani + ust kisimda `Tara` ikonu/butonu
5. Tara basilinca kamera ac → kupe metni oku
6. Kupe API'de bulunursa → Hayvan Profil Ekrani
7. Kupe bulunamazsa → Yeni Hayvan Kayit Ekrani (kupe alani dolu gelir)
8. Hayvan ekle/duzenle/tohumla/asi/dogum akislari
9. Offline kuyruk ve otomatik senkron

### Hayvan Profil Ekrani (Android)

Desktop profil ile ayni sekmeleri icermeli:
- Kimlik & Durum
- Ozet (yas, gebe mi, son islem)
- Tohumlama gecmisi
- Dogum & Yavru gecmisi
- Asi / Prosedur gecmisi
- Fotograflar (kameradan ekleme destegi)

### Teknik Notlar

- Arama: `GET /api/hayvanlar/{ref}` — ref hem ID hem resmi_kupe_no hem ciftlik_kupe_no kabul eder.
- Kupe numarasi buyuk harf normalize edilmeli (API zaten upper yapiyor ama client da yapsin).
- Tarama ekrani tam ekran kamera preview olmali; iptal icin geri butonu yeterlii.
- Tarama basarili sesi veya titresim geribildirim onerilir.

## 21 Mayis 2026 UI Notlari

- Yeni hayvan kaydinda fotograf alani 3 sabit slottur; `Fotoğraf Ekle` coklu dosya secimi yapar.
- Fotograf slotlarinda sag ustteki kirmizi `X`, sadece ilgili fotografi kaldirir.
- Fotograf onizleme siyah bosluk birakmamali: `foto_slot_canvas_ciz` slotun gercek canvas boyutunu kullanir ve `<Configure>`/`after_idle` ile yeniden cizer.
- Raporlama ekrani sabit matplotlib canvas yerine uygulama ici responsive donut kartlari kullanir. Kucuk pencerede tek/iki kolona, genis pencerede uc kolona akar.
- Raporlama sekmesi `kaydirilabilir_sayfa` icinde acilir; kucuk pencerede asagi kaydirma olmalidir.
- Asi/Prosedur sekmesi de `kaydirilabilir_sayfa` kullanir ve ana prosedur tablosunda dikey/yatay scrollbar vardir.
- Matplotlib bagimliligi kaldirildi; raporlar Tkinter canvas ile cizilir ve matplotlib yoksa da calisir.
- Admin/login ekraninda kullaniciya gorunen ASCII metinler Turkcelestirildi.
- Sag tik hayvan menüsündeki islevsiz `Iptal` satiri kaldirildi.
- Ana sekme barinda buton genisligi canvas `width` degerinden hesaplanir; 1280 genislikte sekmeler sagdan tasmamali.
- `tools/smoke_ui.py` fotograf slot doluluk kontrolunu, 3 fotograf kaydini, profil fotograf buyutmeyi, rapor kartlarini ve sekme tasmasini test eder.

## 21 Mayis 2026 Son Paket Notlari

- Admin `Çiftlik Yönetimi` ve `Kullanıcı Yönetimi` popuplari yeniden duzenlendi: baslik/aciklama alani, kartli liste/form yapisi, tablo scrollbarlari, responsive yerlesim ve modern buton gruplari eklendi.
- Admin popup icinde Tkinter `pack/grid` karisimi ve tuple `pady` hatalari yakalanip duzeltildi. Bu hatalar popup acilisinda runtime crash yaratabiliyordu.
- Dashboard guclendirildi: kompakt responsive metrik kartlari, `Yaklaşan İşler`, `Son İşlemler`, calisilan ciftlik/baglanti/senkron ve kritik durum icin `Oncelik Ozeti` eklendi. Onceki buyuk `Hizli Islemler` blogu kaldirildi.
- Ana sekme butonlari `tab=True` boyutu ile biraz buyutuldu; kucuk aksiyon butonlari ayni kalir.
- Rapor grafik kartlarinda halka grafik solda, aciklama/legend yazilari sagda kalir; legend genisligi sabitlenip yazilar wraplength ile kirpilmeyecek sekilde ayarlandi.
- Excel/PDF export sistemi profesyonellestirildi: marka basligi, alt aciklama, tarih/kayit sayisi/metadata, zebra tablo, wrap text, Excel filtre/freeze pane/table ve PDF sayfa altligi eklendi.
- Hayvan listesi export'unda gizli `ID` kolonu artik cikmaz; sadece kullanicinin gordugu temiz kolonlar export edilir.
- Ana ekrandaki `Yedekten Yukle` butonu kaldirildi. O JSON'lar kullanicinin disari aktardigi dosyalar degil, yerel modda veri kaydindan once uygulamanin kendi aldigi otomatik kurtarma yedekleridir.
- `tools/smoke_exports.py` eklendi ve `tools/run_smoke_tests.py` icine baglandi; Excel/PDF export dosyasi uretimi smoke test ile kontrol edilir.

## 22 Mayis 2026 Zorunlu Guncelleme Akisi

- Desktop uygulama surumu `alp_ziraat_hayvan_takip.py` icindeki `APP_VERSION` sabitinden okunur. Yeni release cikarken bu deger GitHub tag'iyle ayni olmalidir, ornek: `APP_VERSION = "1.9.0"` ve release tag `v1.9.0`.
- Kurulu EXE calistiginda login tamamlanip ana ekran acildiktan sonra GitHub latest release kontrol edilir. Kaynak koddan/testten calisirken kontrol varsayilan olarak kapali; EXE icinde aktiftir. Test icin `ALP_FORCE_UPDATE_CHECK=1`, kapatmak icin `ALP_SKIP_UPDATE_CHECK=1` kullanilir.
- Latest release mevcut surumden yeniyse modal popup acilir: kullanici uygulamayi kullanmadan once `Guncelle`ye basmak zorundadir veya uygulamadan cikar.
- Guncelleme popup'i GitHub release asset'leri icinden once `ALP_Ziraat_Suru_Takip_Setup.exe` dosyasini arar; geriye donuk uyumluluk icin `ALP_Ziraat_Hayvan_Takip_Setup.exe` asset'ini de kabul eder. Bunlar yoksa `setup` iceren `.exe`, o da yoksa herhangi `.exe` asset'e duser.
- Uygulama setup dosyasini temp klasore indirir, release notlarini `bekleyen_guncelleme_notu.json` olarak AppData'ya yazar, setup'i `--launch --wait-pid <pid>` ile calistirir ve kapanir.
- `installer/setup_installer.py` `--wait-pid` gelirse eski uygulama kapanana kadar bekler, EXE'yi kurar, `--launch` gelirse yeni uygulamayi tekrar baslatir.
- Yeni surum acildiginda AppData'daki bekleyen release notu, `APP_VERSION` ile eslesiyorsa kullaniciya `Uygulama Guncellendi` penceresi olarak gosterilir ve sonra dosya temizlenir.
- `tools/smoke_update.py` eklendi ve `tools/run_smoke_tests.py` icine baglandi; surum karsilastirma, asset secimi ve release notu kaydet/yukle akisi test edilir.
- Hayvan Listesi filtre/arama alani sabit yukseklikten cikarildi; dar/orta genislikte butonlar alt satira akar. `Temizle` ve `Yenile` butonlari gorunur kalacak sekilde yerlestirildi.
- Ana sekme butonlari kompakt hale getirildi; 1280 genislikte sekmeler sagdan tasmamali.
- Kullanilmayan eski `hayvan_detay_penceresi_eski` blogu ve islevsiz `combo_secimi` callback'i kaldirildi.
- `tools/smoke_api.py` genisletildi: kullanici silme, silinen kullanicinin login olamamasi, ciftlik silinince bagli kullanici/hayvan/yavru kayitlarinin kalkmasi lokal gecici veritabaninda test edilir.
- `tools/smoke_admin_popups.py` eklendi ve `tools/run_smoke_tests.py` icine baglandi; admin popup acilis hatalari artik otomatik yakalanir.
- Son tam test: `python tools\run_smoke_tests.py` komutu 21 Mayis 2026 tarihinde gecti.
- Son uretilen paketler: `ALP_Ziraat_Hayvan_Takip.exe` 39.8 MB, `ALP_Ziraat_Hayvan_Takip_Setup.exe` 47.5 MB, kurulum ZIP'i 39.4 MB.

## 22 Mayis 2026 GitHub Actions Yedek Duzeltmesi

- GitHub Actions `Daily API Backup` job'unda `The read operation timed out` hatasi goruldu. Sebep buyuk olasilikla Render API'nin uyku modundan yavas uyanmasi veya `/api/yedek` cevabinin 30 sn icinde donmemesiydi.
- `tools/server_backup.py` guncellendi: once `/api/health` ile API uyandirilir, login timeout 90 sn, yedek indirme timeout 180 sn oldu ve istekler 5 kez retry/backoff ile denenir.
- `.github/workflows/daily-api-backup.yml` guncellendi: job timeout 12 dakika, retry/timeout env degerleri eklendi.
- Lokal backup smoke test basarili calisti; gecici lokal API'den yedek JSON dosyasi indirildi.

## 22 Mayis 2026 Final Desktop QA Notlari

- Son auditte artik kullanilmayan yerel `Yedekten Yukle` popup kodu ve eski tema degistirme yardimci metodlari kaldirildi. UI'da bu butonlar zaten yoktu; kod tarafindaki karisikligi da temizlendi.
- Orta genislikte ust islem butonlari kaybolmasin diye header esigi guncellendi; 1680 px altinda butonlar alt satira akar.
- Dashboard metrik kartlari artik genis ekranda gereksiz esneyip sagdan kesilmez; kompakt sabit kartlar halinde satir kirar.
- Raporlama ekrani sonradan fazla kompakt gorundugu icin onceki genis kartli duzene geri alindi: genis ekranda ozet kartlari satira yayilir, grafik kartlari genis kolonlarda kalir, butonlar sagda durur.
- Raporlama aksiyon butonlari sag tarafta garip kirildigi icin baslik altinda tek satir toolbar'a alindi. Tam ekran genisliginde grafik kartlari 3 kolon yan yana kalacak sekilde min genislik ayarlandi.
- Hayvan kaydi ekraninda `HAYVANI KAYDET` butonu formun altindan kart basliginin sagina alindi; tam ekranda buton gorunur kalir, dar ekranda sayfa kaydirma davranisi korunur.
- Ust global aksiyon butonlari icin genis ekran esigi 1450 px yapildi; Windows'ta maksimize pencerede piksel olceklemesine bakmadan butonlar sag ustte kalir, daha dar pencerede ikinci satira responsive olarak duser.
- Hayvan profil header rozetleri ve profil kartlari responsive hale getirildi. Kucuk/orta pencerede fotograf, kimlik ve ozet kartlari alt satira akar; alt gecmis kartlari da gerekirse tek kolona duser.
- Hayvan profilindeki `Fotograf Ekle` artik kalan slot sayisi kadar coklu dosya secimi yapar; profil tarafinda da yeni kayit ekranindaki 3 fotograf mantigi korunur.
- Profil gecmis tablolarina yatay scrollbar eklendi. Ozellikle `Dogum ve Yavru Gecmisi` tablosunda `Not` kolonu genisletildi ve uzun notlar saga kaydirilarak okunabilir.
- `tools/smoke_update.py` icinde test ortamina sizabilecek `DATABASE_URL` temizlenir; update smoke test artik harici Supabase/Render baglantisi denemeden deterministik calisir.
- Son tam test: `python tools\run_smoke_tests.py` komutu 22 Mayis 2026 tarihinde gecti.
- 23 Mayis 2026: Hayvan kaydi ve tohumlama tarih alanlarindaki popup modern tarih seciciye cevrildi. Ay secimi, yil spinbox'i, bugun/temizle/kapat aksiyonlari ve gun seciminin alana yazilmasini dogrulayan smoke test eklendi.
- 23 Mayis 2026: Tarih secici popup'inda eski duzende oldugu gibi yazili ay/yil bandi geri eklendi; ayni bantta secili tarih de gorunur. Bu ortak popup hayvan kaydi ve tohumlama tarih alanlarinda kullanilir.
- 23 Mayis 2026: Tarih seciminde asil beklenen davranis netlesti: kullanici `Takvim` butonundan gun secince tarih popup icinde degil, formdaki `Takvim` butonunun yanindaki tarih kutusunda gorunmelidir. Hayvan kaydi ve tohumlama tarih alanlari bunun icin gorunur `tk.Entry` kutusuna cevrildi; smoke test artik alanin degerini, ekranda gorunmesini ve yeterli genisligini birlikte kontrol eder.
- 23 Mayis 2026: GitHub latest release `1.9.2` oldugu icin yeni canli dagitim/updater testi icin desktop `APP_VERSION` `1.9.3` yapildi. Yeni release tag'i ayni formatta `1.9.3` olmali; asset adi yine `ALP_Ziraat_Hayvan_Takip_Setup.exe` kalmali.
- 24 Mayis 2026: Android kamera/normal arama hazirligi eklendi. Desktop liste aramasi artik resmi kupe, ciftlik kupe, ciftlik son 6 hane ve resmi kupe kisaltmasini destekler. API'ye `/api/hayvanlar/bul?ref=...&kaynak=normal|kamera` eklendi; `kaynak=kamera` resmi kupede tam eslesme, ciftlik kupede son 6 hane kullanir ve kisaltmalari kullanmaz. Desktop `APP_VERSION` `1.9.4` yapildi.
- 24 Mayis 2026: Fotograflari veritabanini sisirmeden saklamak icin API Storage hazirligi eklendi. `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` ve `ALP_PHOTO_BUCKET` varsa API base64 `foto_datas` alanlarini Supabase Storage'a yukleyip `foto_urls` olarak dondurur. Storage yoksa eski base64 alanlariyla calismaya devam eder. Admin paneline `Sistem durumu` ekrani eklendi; database boyutu, Storage aktifligi, kayit sayilari ve fotograf istatistikleri gorulur. Desktop `APP_VERSION` `1.9.5` yapildi.
- 24 Mayis 2026: Fotoğraflı yeni hayvan kaydında görülen `API 404: Hayvan bulunamadı` hatasının asıl sebebi maskelenmiş POST hatasıydı. Desktop yeni kayıt gönderirken artık her 400/404/409 hatasında PATCH'e düşmez; sadece aynı `id` gerçekten sunucuda varsa PATCH dener. API tarafında da tarih kontrolleri `ALP_TIMEZONE` varsayılanı `Europe/Istanbul` ile yapılır; Render UTC saatinde bir gün gerideyken Türkiye'de bugünün tarihi yanlışlıkla gelecekte sayılmaz. Desktop `APP_VERSION` `1.9.6` yapıldı.
- 24 Mayis 2026: Storage temizlik sistemi eklendi. Hayvan/fotoğraf/çiftlik silindiğinde API Supabase Storage object'lerini de silmeyi dener; DB silme işlemi Storage temizliği başarısız olsa bile bozulmaz. Android hazırlığı için `POST /api/hayvanlar/{hayvan_ref}/fotograflar` multipart upload ve `DELETE /api/hayvanlar/{hayvan_ref}/fotograflar/{foto_index}` endpoint'leri eklendi. Admin test temizliği için `POST /api/admin/test-verilerini-sifirla` eklendi; admin hesapları kalır, test çiftlik/kullanıcı/hayvan/geçmiş verileri temizlenir. Render cold start için GitHub Actions `Render Keepalive` workflow'u eklendi ve desktop login/device-login timeoutları artırıldı. Desktop `APP_VERSION` `1.9.7` yapıldı.
- 24 Mayis 2026: Hayvan fotograflari private Storage modeline gecirildi. API artik veritabaninda public URL yerine `foto_paths` saklar; istemciye sadece oturumlu isteklerde gecici signed `foto_urls` dondurur. Render icin `ALP_PHOTO_BUCKET_PUBLIC=false` ve `ALP_PHOTO_SIGNED_URL_TTL_SECONDS` dokumante edildi. Desktop signed URL'lerden Storage path'i geri okuyarak foto silme/guncelleme islemlerinde eski path'leri korumaz. Desktop `APP_VERSION` `1.9.8` yapildi.
- 24 Mayis 2026: Hayvan profili fotograf acilis performansi iyilestirildi. Profil penceresi artik signed URL fotograflari beklemeden acilir; fotograflar arka planda indirilir, AppData `foto_onbellek` cache'ine yazilir ve sonraki acilislarda hizli gosterilir. Buyuk fotograf penceresi de gerekirse `Yukleniyor...` durumuyla arka planda yukler. Desktop `APP_VERSION` `1.9.9` yapildi.
- Son tam test: `python tools\run_smoke_tests.py` komutu 24 Mayis 2026 tarihinde gecti. Ardindan `pyinstaller alp_ziraat_hayvan_takip.spec --noconfirm` ve `powershell -ExecutionPolicy Bypass -File installer\make_installer.ps1` ile EXE/kurulum paketleri yeniden uretildi.
- 25 Mayis 2026: Hayvan kaydi performansi iyilestirildi. API modunda yeni hayvan kaydi artik UI'yi kilitlemeden arka planda calisir; buton `KAYDEDILIYOR...` durumuna gecer ve tamamlaninca form temizlenir. `veri_kaydet(kupe_no=...)` yolu gercek tekil API kaydina baglandi; yeni/degisen hayvan icin tum suru tekrar gonderilmez. `Senkronize Et` ve liste yenileme hala tam API yenilemesi yapar. Desktop `APP_VERSION` `1.9.10` yapildi. Son tam test: `python tools\run_smoke_tests.py` gecti.
- 25 Mayis 2026: Logo gorunumu yenilendi. Beyaz logo zeminleri login ve ana header alanindan kaldirildi; transparent LED vurgulu `alp_ziraat_logo_led.png`, `alp_ziraat_icon_led.png` ve `alp_ziraat_logo_led.ico` eklendi. Uygulama, pencere ve kisayol ikonlari LED ikonla paketlenir; eski logo dosyalari geriye donuk yedek olarak kalir. Desktop `APP_VERSION` `1.9.11` yapildi.
- 25 Mayis 2026: Kurulum ve kisayol gorunumu modernlestirildi. Hem ZIP icindeki `install.ps1` hem de tek tik `Setup.exe`, LED `alp_ziraat_logo_led.ico` dosyasini kurulum klasorune kopyalar ve Masaustu/Baslat menusu kisayollarinda dogrudan bu ikonu kullanir. Kisa yollara aciklama metni de eklendi. Desktop `APP_VERSION` `1.9.12` yapildi.
- 25 Mayis 2026: Kucuk Windows kisayolu icin denenen monogram tasarim kullanilmadi; resmi sirket logosu korunacak sekilde geri donuldu. `alp_ziraat_logo_led.png` mevcut resmi `alp_ziraat_logo.png` dosyasindan sadece yuksek cozunurluklu/upscale uretildi, tasarim/renk/kompozisyon degistirilmedi. Kisa yol cache sorununu kirmak icin resmi kare ikon yeni `alp_ziraat_shortcut_led.ico` adiyla paketlenir. Header logo gosterimi biraz buyutuldu. Desktop `APP_VERSION` `1.9.14` yapildi.
- 25 Mayis 2026: Logo varliklari kullanicinin verdigi `C:\Users\mehme\Desktop\alpziraatwebsite\logo.pdf` dosyasindan yeniden uretildi. PDF kaynakli logo yuksek cozunurlukte render edildi, beyaz PDF zemini kaldirildi ve logonun sekli/yazi tipi/yerlesimi korunarak sadece arka parilti katmani eklendi. `alp_ziraat_logo_led.png`, `alp_ziraat_icon_led.png`, `alp_ziraat_logo_led.ico` ve `alp_ziraat_shortcut_led.ico` PDF kalitesine gore guncellendi. Desktop `APP_VERSION` `1.9.15` yapildi.
- 25 Mayis 2026: Baslik cubugu/titlebar ikonu da PDF kaynakli dark ICO'ya baglandi. Uygulama artik Windows tarafinda `iconbitmap` ile `alp_ziraat_shortcut_led.ico` dosyasini, Tk tarafinda `iconphoto` ile `alp_ziraat_icon_led.png` dosyasini birlikte uygular. Modern popup ve alt pencereler ayni ikon yardimcisini kullanir. Desktop `APP_VERSION` `1.9.16` yapildi.
- 25 Mayis 2026: Windows icon cache eski beyaz kisayol ikonunu gosterebildigi icin PDF kaynakli dark ikon yeni `alp_ziraat_pdf_dark.ico` dosya adiyla uretildi ve EXE, setup, install scriptleri ve titlebar ikon yolu buna baglandi. Login ekranindaki tekrar eden `ALP Ziraat` metni kaldirildi; ana header alt basligi `Hayvan Yonetim Platformu` olarak sadelestirildi. Desktop `APP_VERSION` `1.9.17` yapildi.
- 25 Mayis 2026: Dagitim/kurulum adi `Alp Ziraat Suru Takip` olarak guncellendi. Yeni EXE `ALP_Ziraat_Suru_Takip.exe`, setup asset'i `ALP_Ziraat_Suru_Takip_Setup.exe`, ZIP `ALP_Ziraat_Suru_Takip_Kurulum.zip` olarak uretilir; updater eski `ALP_Ziraat_Hayvan_Takip_Setup.exe` asset'ini de yedek olarak kabul eder. Installer eski `ALP Ziraat Hayvan Takip` kisayollarini ve eski kurulum klasorunu temizler. `Anne Ciftlik Kupe No` gorunen etiketleri `Anne Resmi Kupe No` olarak duzeltildi. Desktop `APP_VERSION` `1.9.18` yapildi.
- 25 Mayis 2026: Hayvan listesi secim kutulari, secili hayvanlarin yas ortalamasi, ciftlik kolonu kaldirma, ust durum alaninda `Ciftlik - Online/Offline`, hayvan profilinde `Satildi` islemi ve `Satildi` filtresi eklendi. Satilan hayvanlar aktif suru sayimindan dusurulur. API tarafinda `satildi`, `satis_tarihi`, `satis_bilgisi` alanlari ve storage/default ciftlik temizlikleri guclendirildi. Desktop `APP_VERSION` `1.9.20` yapildi; release tag'i `v1.9.20` olmalidir.

## 22 Mayis 2026 v1.9.1 Release Notu

- GitHub latest release zaten `v1.9.0` oldugu icin updater'in tetiklenmesi adina desktop `APP_VERSION` `1.9.1` yapildi.
- Bu release tag'i `v1.9.1` olmali; asset adi mutlaka `ALP_Ziraat_Hayvan_Takip_Setup.exe` kalmali.
- Eski `v1.9.0` kurulu kullanici login olduktan sonra GitHub latest release `v1.9.1` oldugunu gorurse zorunlu guncelleme popup'i acilir.

## 22 Mayis 2026 v1.9.2 Login/Logout Duzeltmeleri

- Desktop `APP_VERSION` `1.9.2` yapildi; release tag'i `v1.9.2` olmali.
- `Bu bilgisayari tani` ile giris yapildiktan sonra normal ekrandan veya Admin Merkezi'nden `Cikis Yap` denince taninan bilgisayar kaydi temizlenir ve otomatik giris o turda atlanir.
- Offline login daha dayanikli hale getirildi: API istegi beklenmeyen ag hatalariyla kesilirse de `ApiHatasi` uzerinden offline oturum fallback'i denenir.
- Offline oturum API URL karsilastirmasi normalize edildi; trailing slash farklari offline girisi bozmaz.
- Regression testleri eklendi: `tools/smoke_offline_login.py`, `tools/smoke_remember_logout.py`, `tools/smoke_admin_panel_logout.py`.
- Hayvan kaydi ve tohumlama tarih alanlarina takvim popup'i eklendi; hayvan kaydina/duzenlemeye `Irk` alani eklendi ve profil kimlik kartinda gosteriliyor.
- `tools/smoke_ui.py` tarih popup'i, `Irk` kaydi ve profilde gorunme akisini test edecek sekilde guncellendi.
- Render/Supabase API ve Android kontrati icin `irk` alani `schemas.py`, `api_deploy/schemas.py`, `api.py`, `api_deploy/api.py` ve `ANDROID_API_CONTRACT.md` icinde acik hale getirildi. Supabase'de ayri kolon gerekmiyor; tam hayvan payload'i `hayvanlar.veri_json` icinde saklaniyor.

## Bilinen Oncelikler / Sonraki Iyilestirmeler

- Raporlara tarih araligi, ciftlik karsilastirma ve PDF/Excel icinde daha detayli grafik verisi eklemek.
- Islem gecmisini daha detayli ve kullanisli yapmak.
- Dogum/yavru popup akislarini tekrar test edip guzellestirmek.
- Fotograf ekleme/profilde gosterme akisini gercek kullanici senaryosuyla tekrar test etmek.
- Android'e gecmeden once API kontratini son kez sabitlemek.
- EXE kurulum sonrasi masaustu kisayolu ve ikon davranisini tekrar smoke test etmek.

## Hata Ararken Ilk Bakilacak Yerler

- Login donuyorsa: `api_giris_penceresi`, `api_giris_yap`, `taninan_bilgisayar_giris_dene`, `tools/smoke_login_responsive.py`
- Sekmeler alta kaciyorsa: `ana_interface_olustur`, `custom_tab_bar`, `notebook.pack`
- API yavas/cevap vermiyorsa: Render health endpoint ve `api_istek`
- Offline/senkron sorunlari: `bekleyen_senkron_*`, `api_senkronize_et_ui`, `otomatik_baglanti_kontrol`
- Admin paneli sorunlari: `admin_yonetim_merkezi`, ciftlik/kullanici yonetim popup'lari
- Fotograf sorunlari: `foto_data_olustur`, `foto_data_to_image`, hayvan profil penceresi
