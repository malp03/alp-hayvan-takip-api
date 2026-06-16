# ALP Ziraat Proje Hafizasi

Son guncelleme: 14 Haziran 2026

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
- 26 Mayis 2026: Ortalama yas hesaplandiktan sonra hayvan listesi secim tikleri otomatik temizlenir. Tohumlama kaydi artik tum suruyu tekrar gondermek yerine tek hayvan API guncellemesiyle kaydedilir; bu kayit sirasinda UI cokmesi/agirlasmasi riski azaltildi. Hayvan profilindeki aksiyon butonlari biraz asagi alindi. Kalici hayvan silmede desktop API DELETE'i dogrudan cagirir; API kalici silmede foto paths hem response hem ham `veri_json` icinden toplanarak Storage temizligi guclendirildi. `tools/smoke_ui.py` icine gercek `tohumlama_kaydet()` regresyon testi eklendi. Desktop `APP_VERSION` `1.9.21` yapildi; release tag'i `v1.9.21` olmalidir.
- 26 Mayis 2026: Canli API'de Mahmut hayvanlari yanlislikla silinmis goruldu; `C:\Users\mehme\Desktop\hayvan listesi.xlsx` dosyasindan Mahmut ciftligi (`id=1`) altina 101 hayvan tekrar yuklendi. Bu kayitlar artik test degil, canli veri gibi korunacak. Smoke testlerin canli `ALP_API_URL`/`DATABASE_URL` ile calismamasi icin `tools/run_smoke_tests.py` ortam degiskenlerini temizler; tek tek calisan UI smoke scriptleri de `ALP_API_URL`'i kaldirir. Canli Render eski API kodunu calistiriyorsa ciftliksiz hayvan kaydinda `varsayilan-ciftlik` olusturabilir; guncel API kodu ciftliksiz kaydi 400 ile reddeder, bu yuzden Render redeploy sarttir.
- 26 Mayis 2026: Mahmut hayvanlarinda `Sa?mal ?nek` olarak gorunen bozuk Turkce veri canlida 101 kayit icin `Sağmal İnek` olarak duzeltildi; `bad_count=0` dogrulandi. API ve desktop normalize katmanina eski bozuk `?` karakterli cins/durum degerlerini otomatik dogru Turkceye ceviren koruma eklendi. Smoke scriptleri tek tek calistirilsa bile canli `ALP_API_URL`, `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ALP_PHOTO_BUCKET` ortam degiskenlerini temizler. Desktop `APP_VERSION` `1.9.22` yapildi; release tag'i `v1.9.22` olmalidir.

 - 26 Mayis 2026: Admin paneline okuma amacli `Veri Sagligi` ekrani eklendi. API endpoint: `GET /api/admin/veri-sagligi`. Bu kontrol veri silmez; varsayilan ciftlik kalintisi, ciftliksiz hayvan/kullanici, tekrar eden kupe, bozuk Turkce metin, gecersiz/gelecek tarih, sahipsiz alt kayit, durum celiskisi ve Storage/fotograf tutarsizliklarini raporlar. Desktop `APP_VERSION` `1.9.23` yapildi; release tag'i `v1.9.23` olmalidir.

- 27 Mayis 2026: `Geri Al` butonu tek tusla son snapshot'i yukleyip tum suruyu API'ye gondermek yerine secilebilir pencereye cevrildi. Pencere son 10 islemi gosterir; kullanici secili islemi geri alir. Kalici silme islemleri listede gorunse de `geri_alinabilir=False` olarak isaretlenir ve geri getirilemez. Geri alma sadece etkilenen kayitlari upsert/delete eder, bu yuzden buyuk surulerde donma riski azaltildi. Desktop `APP_VERSION` `1.9.24` yapildi; release tag'i `v1.9.24` olmalidir. `python tools\run_smoke_tests.py` gecti.

- 27 Mayis 2026: Android'e gecis oncesi paket surumu `1.9.25` yapildi. Bu surumde server tarafinda fotograf sikistirma icin `Pillow` gereksinimi, Excel export onarim uyarisini engelleyen tablo XML temizligi, Android API sozlesmesi duzeltmeleri ve onceki `1.9.23/1.9.24` veri sagligi/geri al iyilestirmeleri tek release altinda toplanacak. GitHub latest release kontrolunde canli son release `v1.9.22` oldugu goruldu; yeni release tag'i `v1.9.25` olmalidir ve asset adi `ALP_Ziraat_Suru_Takip_Setup.exe` kalmalidir.
- 28 Mayis 2026: Ust headerdaki Online/Offline durum kutusuna uygulama surumu eklendi. Artik kullanici baglanti durumunun hemen altinda `v{APP_VERSION}` bilgisini gorur. Android'e gecmeden once masaustu release paketi bu degisiklikten sonra yeniden uretilmelidir.

- 27 Mayis 2026: API tarafina sunucu tarafi fotograf sikistirma eklendi. Multipart veya base64 gelen fotograflar Storage/DB'ye yazilmadan once Pillow ile EXIF yonu duzeltilir, 900px maksimum kenara indirilir ve JPEG quality 82 ile kaydedilir. Varsayilan kaynak limit `ALP_PHOTO_MAX_SOURCE_MB=12`, cikti limit `ALP_PHOTO_MAX_OUTPUT_MB=3`; `requirements-api.txt` ve `api_deploy/requirements-api.txt` icine `Pillow>=10.0` eklendi. `tools/smoke_api.py` yeni sikistirma davranisina uygun guncellendi. `python tools\run_smoke_tests.py` gecti.

- 27 Mayis 2026: Excel ciktilarinda babanin gordugu `Excel okunamayan icerigi onardi / xl/tables/table1.xml` uyarisi icin export sistemi duzeltildi. `alp_ziraat_export.py` artik Excel structured table XML'i uretmez; ayni gorunumu hucre stilleri ve standart worksheet AutoFilter ile verir. `tools/smoke_exports.py` bundan sonra xlsx icinde `xl/tables/` ve `tableParts` olusmadigini kontrol eder. `python tools\run_smoke_tests.py` gecti.

- 28 Mayis 2026: Android/Flutter tarafi baslatildi. Mobil proje masaustu/API repo klasorunun disinda `C:\Users\mehme\Desktop\alp_ziraat_mobile` altinda olusturuldu. Flutter 3.44.0 ve Dart 3.12.0 aktif; Android toolchain temiz, Visual Studio uyarisi Android icin onemsiz. Ilk mobil iskelette canli API base URL'i, login, token saklama, "Bu cihazi tani" device-token akisi, rol/ciftlik bilgisine gore ana ekran ve ALP dark tema eklendi. Dogrulama: `flutter analyze`, `flutter test`, `flutter build apk --debug` gecti. Debug APK: `C:\Users\mehme\Desktop\alp_ziraat_mobile\build\app\outputs\flutter-apk\app-debug.apk`.
- 28 Mayis 2026: Android/Flutter tarafina ilk gercek suru akisi eklendi. `GET /api/hayvanlar` ile hayvan listesi, kupe/son 6/kisaltma aramasi, Aktif/Satildi/Arsiv/Tumu filtreleri ve `GET /api/hayvanlar/{id}` ile hayvan profil detayi calisiyor. Profilde resmi kupe, ciftlik kupesi, irk, cinsi, dogum tarihi, yas, anne resmi kupe, ureme/sagim ve fotograf bolumu gosteriliyor. Dogrulama: `flutter analyze`, `flutter test`, `flutter build apk --debug` gecti; debug APK emulator'e kuruldu ve admin oturumunda liste/profil/arama ekrani canli API ile goruldu.
- 28 Mayis 2026: Android/Flutter tarafina `Yeni Hayvan Kaydi` akisi eklendi. Farm kullanicisi kendi ciftligine, admin ise secilen ciftlige yeni hayvan kaydedebilir; resmi kupe/ciftlik kupe, cinsi, irk, dogum tarihi, anne resmi kupe ve not alanlari mobil formda yer alir. Ilk emulator kontrolunde form govdesini bos gosteren hata, satir icindeki `Takvim` butonunun sonsuz genislik istemesinden kaynaklandi; butona net minimum olcu verilerek duzeltildi. Yeni widget testi `test/new_animal_screen_test.dart` eklendi. Dogrulama: `flutter analyze`, `flutter test`, `flutter build apk --debug` gecti; APK emulator'e kuruldu, `Yeni Hayvan` ekrani ve bos kupe validasyonu gercek cihaz ekraninda dogrulandi.
- 28 Mayis 2026: Android/Flutter tarafinda admin ve tohumlama/raporlama akislari genisletildi. Admin ana ekranda artik dogrudan `Tum Suru`/`Yeni Hayvan` yok; admin `Ciftlikler` listesinden bir ciftlige girip o ciftlik calisma ekranindan `Hayvan Listesi`, `Yeni Hayvan Kaydi`, `Tohumlama`, `Raporlama` ve `Islem Gecmisi`ne ulasir. Farm kullanicisi ana ekranda hayvan listesi, yeni hayvan, tohumlama ve raporlama kartlarini gorur. Tohumlama mobilde masaustundeki merkezi API kurallarini kullanan `POST /api/hayvanlar/{id}/tohumlamalar` endpoint'ine baglandi; profil ekranina `Tohumla` butonu ve tohumlama gecmisi eklendi. Raporlama `GET /api/raporlar/ozet` ile suru ozetini ve hayvan listesinden tohumlama ozetini gosterir. Yeni testler: `test/home_admin_test.dart`, `test/insemination_screen_test.dart`. Dogrulama: `flutter analyze`, `flutter test`, `flutter build apk --debug` gecti; debug APK emulator'e kuruldu.
- 28 Mayis 2026: Android/Flutter PC eslestirmesi genisledi. Mobilde `Asi/Prosedur` ekrani `POST /api/hayvanlar/{id}/asi-prosedurler`, `Dogum Kaydi` ekrani `POST /api/hayvanlar/{id}/dogumlar` endpoint'lerine baglandi. Profil ekranina `Asi/Prosedur`, `Dogum`, `Satildi`, `Kesildi`, `Oldu` ve `Arsiv` aksiyonlari eklendi; bu aksiyonlar merkezi API'yi kullanir ve profil yenilenir. Admin ciftlik calisma ekraninda ve farm kullanici ana ekraninda bu yeni ekranlara gidis kartlari var. `OutlinedButton` temasi sonsuz genislik istemeyecek sekilde duzeltildi; bu, dogum ekranindaki responsive layout hatasini giderdi. Yeni testler: `test/procedure_screen_test.dart`, `test/birth_screen_test.dart`. Dogrulama: `flutter analyze`, `flutter test`, `flutter build apk --debug` gecti; debug APK emulator'e kuruldu.
- 28 Mayis 2026: Android/Flutter profil fotograf yonetimi eklendi. `image_picker` ile galeriden coklu secim ve kamerayla cekim desteklenir; mobil profil `POST /api/hayvanlar/{id}/fotograflar` multipart endpoint'ine yukler ve `DELETE /api/hayvanlar/{id}/fotograflar/{index}` ile tek tek siler. Profilde 3 fotograf limiti, yukleme durumu, buyuk fotograf goruntuleme ve signed URL gosterimi var. Android manifest'e kamera izni eklendi. Dogrulama: `flutter analyze`, `flutter test`, `flutter build apk --debug` gecti; debug APK emulator'e kuruldu. Build sirasinda `image_picker_android` icin ileri Flutter surumlerine yonelik Kotlin Gradle Plugin uyarisi goruldu; mevcut debug APK'yi bozmuyor.
- 28 Mayis 2026: Android/Flutter `Uyarilar` ekrani eklendi. `GET /api/uyarilar` ile gebelik kontrolu, dogum ve asi/prosedur uyarilari listelenir; uyarıya dokununca ilgili hayvan profili acilir. Farm kullanicisi ana ekrandan, admin ise ciftlik calisma ekranindan ilgili ciftligin uyarilarina girer. Yeni test: `test/alerts_screen_test.dart`. Dogrulama: `flutter analyze`, `flutter test`, `flutter build apk --debug` gecti; debug APK emulator'e kuruldu.

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

## 29 Mayis 2026 Android Mobil Notu

- Android/Flutter PC eslestirmesi icin ana akista tohumlama ve dogum kartlari kaldirildi; bu islemler artik hayvan profilinde uygun hayvanda gorunen butonlarla yapilir.
- Offline login son basarili oturumu ve parola hash'ini kullanarak internet yokken giris yapabilir; ilk kurulum veya hic basarili giris yoksa internet gerekir.
- Hayvan listesi PC filtreleriyle genisletildi: `Aktif`, `Tumu`, cins filtreleri, `Gebe`, `Olu`, `Kesildi`, `Satildi`, `Arsivli`; liste son dogum/dogum tarihi yeni olanlar ustte olacak sekilde siralanir.
- Kamera/galeri OCR ile kupe okuma ekrani eklendi; ciftlik kupesinde son 6 hane, resmi kupede tam numara/kisaltma aramasi API aramasina baglandi.
- Yeni hayvan kaydindaki `Not` alani kaldirildi, `Irk` serbest metin olarak kaldi.
- Mobil logo/splash/launcher ikonlari desktop LED logo varliklarindan yeniden uretildi.
- Dogrulama: `flutter analyze`, `flutter test`, `flutter build apk --debug` gecti.

## 29 Mayis 2026 Android Mobil Devam Notu

- Kullanici istegiyle kamera/galeri OCR aramasi sadeleştirildi: artik sadece ciftlik kupe numarasinin tamamini eslestirir ve tek sonuc bulursa dogrudan hayvan profilini acar. Resmi kupe, son 6 hane ve kisaltma mantigi kamera taramasinda kullanilmaz; normal hayvan listesi aramasi bundan bagimsiz kalir.
- Mobil yeni hayvan kaydindaki `Irk` alani Windows uygulamadaki listeye yaklastirildi: `Simental`, `Holstein`, `Montofon`, `Jersey`, `Angus`, `Hereford`, `Sarole`, `Limuzin`, `Yerli Kara`, `Boz Irk`, `Melez`, `Diger`.
- Dogrulama: `flutter analyze`, `flutter test`, `flutter build apk --debug` gecti; guncel `app-debug.apk` `emulator-5554` uzerine kuruldu ve uygulama baslatildi.
- Mobil raporlama ekrani yeniden duzenlendi: ust bilgi kartina yenile butonu eklendi, ozet metrikleri responsive hale getirildi, cinsiyet/tip/ozel durum dagilimlari okunur progress satirlariyla ayrildi ve tohumlama satirlari tasma yapmayacak kartlara cevrildi. Admin ana panelinde logo tek satira alindi; `Rol/Admin`, calisilan alan ve baglanti rozetleri logonun altina indirildi. Android launcher/app icon resmi sirket logosundan daha okunur dark ikon olarak yeniden uretildi ve tum mipmap boyutlari guncellendi. Dogrulama: `flutter analyze`, `flutter test`, `flutter build apk --debug` gecti; guncel debug APK emulator'e kuruldu.
- Mobil rapor dagilim kartlari sabit buyuk grid yuksekliginden cikarildi; artik icerik arttikca buyuyen Wrap tabanli kartlar kullanilir. Ciftlik calisma ekranina ve farm ana aksiyonlarina `Geri Al` eklendi. Mobil geri alma bu cihazdaki acik oturumda yapilan son 10 islemi tutar; hayvan olusturma, durum guncelleme, tohumlama, asi/prosedur ve dogum icin onceki hayvan snapshot'iyle geri doner. Dogum geri alinirken ayni islemde olusan yavru kayitlari da kalici silinmeye calisilir. Fotograf yukleme/silme storage dosyasi etkiledigi icin listede gorunur ama otomatik geri alinmaz. Dogrulama: `flutter analyze`, `flutter test`, `flutter build apk --debug` gecti; guncel debug APK emulator'e kuruldu ve app process calisti.
- Mobilde sadece ciftlik kullanicisi icin hizli giris eklendi: daha once basarili giris/cache varsa API uyanmasi beklenmeden uygulamaya girer, baglanti durumu `Baglaniyor/Online/Offline` olarak Home ekraninda guncellenir; admin bu hizli akisa sokulmaz. Hayvan listesi aramasi her tus vurusunda API'ye gitmek yerine yuklenen listeyi yerelde filtreler; ciftlik kupesi/resmi kupe/kupe alanlarinda rakam yazdikca anlik sonuc verir ve guclu eslesmeleri uste alir. Arsivli hayvan profilinde `Kalici Sil` butonu eklendi; onaydan sonra `DELETE /api/hayvanlar/{id}?kalici=true` ile hayvan ve bagli fotograflar sunucudan silinir. Dogrulama: `flutter analyze`, `flutter test`, `flutter build apk --debug` gecti; debug APK emulator'e kuruldu ve baslatildi.

## 30 Mayis 2026 Desktop Online Yedek Notu

- Admin panelindeki `Online yedek indir` butonu duzeltildi. Canli `/api/yedek` endpoint'i calisiyor fakat Render/cold start ve buyuk yedek nedeniyle ilk denemede yaklasik 53 saniye surebiliyor; eski desktop kodunda 45 saniye timeout oldugu icin buton hata veriyordu.
- Yeni akis once kayit dosyasini sordurur, sonra UI'yi kilitlemeden arka planda indirir. Kucuk bir ilerleme penceresi gosterir, once `/api/health` ile servisi uyandirir, `/api/yedek` icin 180 saniye timeout ve bir tekrar denemesi kullanir.
- Dogrulama: `python -m py_compile alp_ziraat_hayvan_takip.py api.py schemas.py api_deploy\api.py api_deploy\schemas.py` gecti. Canli API'de health ve yedek indirme test edildi; yedek 1 ciftlik, 2 kullanici, 103 hayvan ve 500 islem gecmisi ile basarili dondu.
- Yeni dagitim dosyalari uretildi: `dist\ALP_Ziraat_Suru_Takip.exe`, `dist\ALP_Ziraat_Suru_Takip_Setup.exe`, `dist\ALP_Ziraat_Suru_Takip_Kurulum.zip`.

## 3 Haziran 2026 Desktop v1.9.30 Notu

- Desktop `APP_VERSION` `1.9.30` yapildi. Yeni GitHub release tag'i `v1.9.30` olmali; updater'in kurulumdan sonra surumu dogru algilamasi icin EXE/Setup bu koddan yeniden uretilmelidir.
- Sagmal/Kuru inek kaydinda laktasyon numarasi ve son dogum tarihi artik bos birakilabilir; bilgi eksikse hayvan listesinde ve profilde eksik veri uyarisi gorunur.
- Hayvan duzenleme penceresindeki `Dogum/Laktasyon` sekmesine eksik laktasyon bilgisini sonradan tamamlama akisi eklendi.

## 3 Haziran 2026 Desktop v1.9.31 Notu

- Hayvan profili `Duzenle` penceresinin `Genel Bilgiler` sekmesine sagmal/kuru ineklerde dogrudan gorunen `Laktasyon Numarasi` ve `Son Dogum Tarihi` alanlari eklendi.
- Eksik laktasyon/son dogum uyarisi olan sagmal inekler artik genel duzenleme ekranindan tamamlanabilir; bilgiler kaydedildiginde `dogumlar` kaydi olusturulur ve eksik veri uyarisi kalkar.
- Desktop `APP_VERSION` `1.9.31` yapildi; release tag'i `v1.9.31` olmalidir.

## 3 Haziran 2026 Desktop/API v1.9.32 Notu

- Arsivli hayvan kalici silindiginde, silinen hayvana ait yavru referanslari annenin `dogumlar/yavrular` gecmisinden temizlenir.
- Hayvan sadece arsivdeyse anne dogum gecmisindeki baglanti korunur; temizlik yalnizca kalici silmede calisir.
- API `DELETE /api/hayvanlar/{ref}?kalici=true` ayni temizligi online veritabaninda da yapar. `api_deploy/api.py` kopyasi da guncellendi.
- Desktop `APP_VERSION` `1.9.32` yapildi; release tag'i `v1.9.32` olmalidir.

## 3 Haziran 2026 Desktop v1.9.33 Notu

- Hayvan profili `Duzenle > Genel Bilgiler` penceresi kaydirmali hale getirildi; laktasyon ve fotograf alanlari uzasa bile `GENEL BILGILERI KAYDET` butonu pencerenin altinda sabit gorunur.
- Pencereye minimum boyut verildi, kucuk ekranlarda kaydet butonunun alta kacmasi engellendi.
- Desktop `APP_VERSION` `1.9.33` yapildi; release tag'i `v1.9.33` olmalidir.

## 13 Haziran 2026 Desktop v1.9.34 Notu

- Tohumlama kaydi duzenlenirken de hayvanin tohumlama tarihinde en az 12 aylik olmasi zorunlu hale getirildi. Kontrol API, masaustu ve mobil katmanlarinda ayni sekilde uygulanir.
- API erkek hayvana dogum kaydi eklenmesini veya mevcut dogum kaydinin duzenlenmesini reddeder.
- Asi/prosedur kayitlarinda sonraki tarih uygulama tarihinden once olamaz. Kontrol API ve mobil ekleme/duzenleme ekranlarinda uygulanir; masaustu mevcut kontrolu korur.
- Desktop `APP_VERSION` `1.9.34` yapildi; release tag'i `v1.9.34` olmalidir. Mobil paket surumu `1.0.2+3` yapildi.

## 15 Haziran 2026 - Desktop v1.9.37 Render Uyku Dayanikliligi

- Render Free cold start durumu masaustunde ayri `checking`, `waking`, `online` ve `offline` durumlariyla izlenir.
- Manuel senkron, otomatik health kontrolu ve profil fotograf detayi ag beklerken Tk ana thread'ini bloklamaz.
- Masaustu acikken API `/api/health` adresine 8 dakikada bir istek atarak 15 dakikalik bosta uyumayi onler.
- GitHub `Render Keepalive`, `ALP_API_URL` secret'i yoksa canli API adresine fallback yapar ve basarisiz health sonucunu gizlemez.
- Beklenmeyen Tk ve worker hatalari AppData altindaki `logs/masaustu.log` dosyasina kaydedilir.
- Desktop `APP_VERSION` `1.9.37` yapildi; release tag'i `v1.9.37` olmalidir.

## 15 Haziran 2026 - Desktop v1.9.38 Oturum ve Senkron Cakisma Duzeltmeleri

- API 401 donerse masaustu tokeni temizleyip kayitli cihaz/yerel kimlik bilgisiyle oturumu bir kez yeniler ve basarisiz istegi tekrar dener.
- `timed out` ve benzeri cold-start timeout mesajlari Render uyandirma retry dongusune dahil edildi.
- Hayvan listesi `Yenile` butonu artik manuel senkron arka plan yolunu kullanir; ana UI thread'inde tam API yenilemesi yapmaz.
- Senkron/health kontrolu surerken yapilan hayvan degisiklikleri dogrudan API'ye gitmez, offline kuyruga alinir ve ayni senkron turunda tekrar kontrol edilir.
- `409 stale_update` alan eski offline kayitlar tum senkronu durdurmaz; ilgili kayit merkezden guncel haliyle uzlastirilir, kalan kuyruk devam eder.
- Tkinter'in pencere/zamanlayici temizligi sirasinda uretebildigi `deletecommand` kaynakli zararsiz `NoneType.remove` hatasi artik kullaniciya kritik hata penceresi olarak gosterilmez.
- Dogrulama: `python tools\run_smoke_tests.py` tum masaustu/API smoke testleriyle basarili.
- Desktop `APP_VERSION` `1.9.38` yapildi; release tag'i `v1.9.38` olmalidir.

## 16 Haziran 2026 - Desktop v1.9.39 Geri Al Senkron Kuyrugu Duzeltmesi

- Masaustu `Geri Al` akisi, geri alinan islem yeni kayit silmeyi gerektirdiginde ve API gecici olarak 503/uyaniyor gibi hata verdiginde silmeyi senkron kuyruguna alip islemi basarisiz sayiyordu. Kuyruk diske yazilabildiyse geri alma artik tamamlanmis kabul edilir; boylece hayvan yerelden kalkar, silme online olunca API'ye gonderilir ve undo kaydi tekrar listede kalmaz.
- Tohumlama gibi mevcut hayvan kaydini eski snapshot'a donduren geri alma islemlerinde eski snapshot'in `son_guncelleme` degeri API tarafindan `stale_update` olarak reddediliyordu. Geri yuklenen kayda artik geri alma aninin `son_guncelleme` degeri basilir; boylece islem merkezde yeni bir degisiklik olarak kabul edilir. Gercek stale/base cakismasi varsa degisiklik offline kuyruğa alinmaz, sunucudaki guncel kayit cekilir ve kullaniciya geri almanin uygulanmadigi soylenir.
- `tools/smoke_render_resilience.py` icine yeni kayit silme, tohumlama geri alma ve gercek stale_update uzlastirma regresyon testleri eklendi. `python tools\run_smoke_tests.py` gecti.
- Desktop `APP_VERSION` `1.9.39` yapildi; release tag'i `v1.9.39` olmalidir.

## Hata Ararken Ilk Bakilacak Yerler

- Login donuyorsa: `api_giris_penceresi`, `api_giris_yap`, `taninan_bilgisayar_giris_dene`, `tools/smoke_login_responsive.py`
- Sekmeler alta kaciyorsa: `ana_interface_olustur`, `custom_tab_bar`, `notebook.pack`
- API yavas/cevap vermiyorsa: Render health endpoint ve `api_istek`
- Offline/senkron sorunlari: `bekleyen_senkron_*`, `api_senkronize_et_ui`, `otomatik_baglanti_kontrol`
- Admin paneli sorunlari: `admin_yonetim_merkezi`, ciftlik/kullanici yonetim popup'lari
- Fotograf sorunlari: `foto_data_olustur`, `foto_data_to_image`, hayvan profil penceresi
# 14 Haziran 2026 - Senkron kuyruğu, güvenli fotoğraf silme ve health

- Mobil Senkronize ekranına bekleyen/başarısız işlemleri ayrıntılı gösteren yönetim alanı eklendi.
- Kullanıcı başarısız bir işlemi yeniden deneyebilir veya uyarı onayıyla kuyruktan kaldırabilir.
- Fotoğraf silme işlemi Storage sıra numarası yerine kalıcı `foto_path` ile çalışacak şekilde güncellendi; eski indeksli kuyruk kayıtları geriye uyumlu kaldı.
- Mobil hayvan modeli ve yerel önbellek `foto_paths` alanını koruyor.
- API `/api/health` artık gerçek `SELECT 1` sorgusuyla veritabanını kontrol ediyor.
- PostgreSQL üretiminde `ALP_AUTH_SECRET` eksik, varsayılan veya 32 karakterden kısaysa health 503 döndürüyor; anahtarın kendisi hiçbir yanıtta açığa çıkarılmıyor.
- API smoke testi path tabanlı fotoğraf silmeyi, gerçek DB health sonucunu ve auth secret yapılandırma durumunu doğruluyor.
# 14 Haziran 2026 - Masaüstü v1.9.35

- Senkron, health ve veri güvenliği düzeltmelerini içeren masaüstü dağıtımı için uygulama sürümü `1.9.35` yapıldı.
- Güncel EXE, Setup EXE ve kurulum ZIP paketi yeniden üretildi.

# 15 Haziran 2026 - API/Desktop/Mobil veri bütünlüğü

- API kullanıcı yönetiminde son aktif adminin pasifleştirilmesi, rolünün düşürülmesi veya silinmesi engellendi; mükerrer kullanıcı adı ve geçersiz çiftlik atamaları reddediliyor.
- Hayvan güncelleme/silme, fotoğraf ve alt kayıt işlemlerinde istemcinin okuduğu `son_guncelleme` sürümüyle çakışma kontrolü eklendi. Eski mobil/masaüstü veri yeni kaydı sessizce ezemiyor; 409 çakışma olarak bildiriliyor.
- Mobil senkron aynı anda tek çalışma kullanır; yeni hayvan ile mevcut hayvan ayrımı kuyrukta açık işaretle tutulur. Draft kimlikli fakat sunucuya kaydedilmiş hayvan artık yanlışlıkla yeniden POST edilmez.
- Mobil 401 durumunda saklanan oturum temizlenip giriş ekranına dönülür. Başarısız kuyruk kaydı kaldırılırken yerel veri sunucudan tekrar uzlaştırılır.
- Offline doğum yavru kimlikleri API tarafında korunur; fotoğraf işlemleri sonraki kuyruk işlemlerine yeni sunucu sürümünü aktarır. Tohumlama silme cevabı artık sahte hayvan olarak cache'e yazılmaz.
- Mobil profil yerel ve online fotoğrafları birlikte gösterir; fotoğraf sayısı doğru hesaplanır. Profilde laktasyon sayısı, son doğum, aktif ve toplam sağım günü özetleri eklendi.
- İşlem geçmişi gerçek tarih sırası ile döner. Health endpoint gerçek veritabanı sorgusu ve auth secret yapılandırmasını kontrol eder.
- Doğrulama: Python compile, API smoke, tüm desktop UI/login/offline/export/update smoke testleri, `flutter analyze`, 13 Flutter testi ve release APK build başarılı.

# 15 Haziran 2026 - Dağıtım sürümleri

- Masaüstü sürümü `1.9.36` olarak yükseltildi; GitHub release etiketi `v1.9.36` olmalıdır.
- Mobil paket sürümü `1.0.3+4` olarak yükseltildi.
- Güncel masaüstü EXE/Setup/ZIP ve Android release APK bu sürümlerle yeniden üretildi.
