# ALP Ziraat Proje Hafizasi

Son guncelleme: 21 Mayis 2026

Bu dosya projenin mevcut halini, yapilan degisiklikleri, testleri ve dagitim notlarini hatirlamak icin tutulur. Yeni bir isleme baslamadan once burayi oku.

## Proje Ozeti

ALP Ziraat Hayvan Takip uygulamasi, ciftliklerin suru kayitlarini yonetmesi icin yazilmis bir masaustu uygulamasidir.

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
- Kamera ile kupe numarasi tarama ve galeriden kupe okuma ileride Android tarafinda eklenecek.
- Mobilde hayvan sekmesinde tarama sonrasi direkt ilgili profile gitme isteniyor.

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
- Guncelleme popup'i GitHub release asset'leri icinden once `ALP_Ziraat_Hayvan_Takip_Setup.exe` dosyasini arar; yoksa `setup` iceren `.exe`, o da yoksa herhangi `.exe` asset'e duser.
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
- Hayvan profil header rozetleri ve profil kartlari responsive hale getirildi. Kucuk/orta pencerede fotograf, kimlik ve ozet kartlari alt satira akar; alt gecmis kartlari da gerekirse tek kolona duser.
- Hayvan profilindeki `Fotograf Ekle` artik kalan slot sayisi kadar coklu dosya secimi yapar; profil tarafinda da yeni kayit ekranindaki 3 fotograf mantigi korunur.
- Profil gecmis tablolarina yatay scrollbar eklendi. Ozellikle `Dogum ve Yavru Gecmisi` tablosunda `Not` kolonu genisletildi ve uzun notlar saga kaydirilarak okunabilir.
- `tools/smoke_update.py` icinde test ortamina sizabilecek `DATABASE_URL` temizlenir; update smoke test artik harici Supabase/Render baglantisi denemeden deterministik calisir.
- Son tam test: `python tools\run_smoke_tests.py` komutu 22 Mayis 2026 tarihinde gecti.

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
