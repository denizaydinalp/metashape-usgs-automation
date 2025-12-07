# USGS Standartlarında Agisoft Metashape Otomasyonu (Python Script)

Bu proje, **Agisoft Metashape** yazılımında fotogrametrik nirengi ve dengeleme işlemlerini **USGS (Amerika Birleşik Devletleri Jeoloji Araştırmaları Kurumu)** 2021 standartlarına göre tam otomatik hale getiren bir Python betiğidir.

Manuel olarak yapıldığında saatler süren ve insan hatasına açık olan "Gradual Selection" (Aşamalı Seçim) sürecini, matematiksel hassasiyetle ve optimize edilmiş bir algoritma ile gerçekleştirir.

## Temel Özellikler

* **Tam Otomasyon:** Geometry (Reconstruction Uncertainty), Pixel Matching (Projection Accuracy) ve Reprojection Error adımlarını sırasıyla uygular.
* **Akıllı Güvenlik Kilitleri:**
    * **%50 Kuralı:** İlk aşamalarda veri kaybını önlemek için otomatik eşik (threshold) kontrolü yapar.
    * **%10 İterasyon Döngüsü:** Reprojection Error temizliğinde her seferinde nokta bulutunun sadece en kötü %10'unu silerek hedefe (RMSE 0.3 -> 0.18) güvenle ilerler.
* **15. Adım Entegrasyonu:** Çoğu kullanıcının gözden kaçırdığı "Tie Point Accuracy" sıkılaştırma (0.1px) işlemini otomatik yaparak modelin doğruluğunu maksimize eder.
* **Referans Kontrolü:** İşlem boyunca GCP (Yer Kontrol Noktası) hatalarını izler; model araziden koparsa işlemi otomatik durdurur.

## Kurulum ve Kullanım

Bu scripti çalıştırmak için ekstra bir kütüphane kurmanıza gerek yoktur. Agisoft Metashape Pro içerisindeki Python konsolu yeterlidir.

### Ön Hazırlık (Kritik!)
Scripti çalıştırmadan önce projenizde şu adımların tamamlandığından emin olun:
1.  **Align Photos:** İşlemi yaparken `Tie point limit` değerini **0 (Sıfır)** olarak ayarlayın.
2.  **GCP İşaretleme:** Yer kontrol noktalarınızın işaretlenmiş ve aktif (tikli) olduğundan emin olun.
3.  **Hassasiyet Ayarı:** Reference panelindeki `Settings` kısmından `Marker accuracy` değerini (örn: 0.02m) doğru girin.
4.  **Yedekleme:** İşleme başlamadan önce Chunk'ı **Duplicate** (Kopyala) yaparak yedeğini alın.

### Çalıştırma
1.  `usgs_workflow.py` dosyasını indirin.
2.  Metashape içerisinde **Tools > Run Script** menüsüne gidin.
3.  İndirdiğiniz dosyayı seçin ve çalıştırın.
4.  Arkanıza yaslanın ve `Console` ekranından işlemleri izleyin. ☕

## Neden Bu Script?

Fotogrametrik projelerde en büyük hata kaynağı, gürültülü (noise) noktaların yanlış temizlenmesi veya aşırı temizlik sonucu modelin deforme olmasıdır. Bu script:
* Subjektif kararları ortadan kaldırır.
* Her projede standart ve tekrarlanabilir kalite sağlar.
* Modelin RMSE (Karesel Ortalama Hata) değerini USGS standartlarına (<= 0.18 piksel) çeker.

## Yazar Hakkında

**Deniz Aydınalp**
*Jeodezi ve Fotogrametri Mühendisi*

Fotogrametrik veri üretimi, mühendislik ölçmeleri ve Python tabanlı CBS otomasyonları üzerine profesyonel çözümler geliştiriyorum.

**Web Sitesi:** www.daaeng.com
**LinkedIn:** https://www.linkedin.com/in/denizaydinalp/

---
**Sorumluluk Reddi:** Bu script profesyonel kullanım için geliştirilmiştir ancak her proje verisi farklıdır. Lütfen her zaman verilerinizi yedekleyerek çalışın.*
