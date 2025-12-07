# ==============================================================================
# AGISOFT METASHAPE - USGS STANDARDI GRADUAL SELECTION OTOMASYONU
# ==============================================================================
# Referans: USGS Open-File Report 2021-1039
# İş Akışı: Adım 11 (Geometry), Adım 12 (Pixel Matching), Adım 13 (Reprojection)
#           ve Adım 15 (Tie Point Accuracy Sıkılaştırma)
#
# ÖNEMLİ: Bu scripti çalıştırmadan önce lütfen şunları kontrol edin:
# 1. Align Photos aşamasında "Tie point limit" 0 (sıfır) olarak ayarlanmış olmalı.
# 2. GCP (Yer Kontrol Noktaları) işaretlenmiş ve aktif (tikli) olmalı.
# 3. Reference Settings kısmında "Marker Accuracy" (örn: 0.02m) doğru girilmeli.
# 4. İşleme başlamadan önce Chunk üzerinde sağ tık -> "Duplicate" ile yedek alınız.
# ==============================================================================

import Metashape
import math

def usgs_professional_workflow():
    print(">>> USGS Standartlarında Gradual Selection İş Akışı Başlatılıyor...")
    
    doc = Metashape.app.document
    chunk = doc.chunk
    
    if not chunk:
        print("HATA: Lütfen projenizi açın.")
        return

    # --- AYARLAR VE LİMİTLER ---
    
    # Başlangıç Nokta Sayısı (Güvenlik kilidi için referans)
    INITIAL_POINTS = len(chunk.point_cloud.points)
    MIN_POINT_LIMIT = INITIAL_POINTS * 0.10  # Orijinal verinin %10'u kalırsa DUR
    
    print(f"Başlangıç Bağlantı Noktası (Tie Points): {INITIAL_POINTS}")
    print(f"Güvenlik Limiti (Minimum): {int(MIN_POINT_LIMIT)} nokta")

    # Kamera Optimizasyon Parametreleri (USGS Tablo Adım 11 & 14 uyarınca)
    # Adaptive fitting: Tie point covariance matrisi için önemlidir.
    opt_params = dict(fit_f=True, fit_cx=True, fit_cy=True, 
                      fit_k1=True, fit_k2=True, fit_k3=True, 
                      fit_p1=True, fit_p2=True, 
                      fit_b1=False, fit_b2=False, # b1, b2 kapalı (USGS standardı)
                      adaptive_fitting=True)

    # --- YARDIMCI FONKSİYONLAR ---

    def check_stop_criteria(current_rmse, prev_rmse):
        """
        İşlemi ne zaman durdurmalıyız?
        1. Nokta sayısı %10'un altına düştüyse.
        2. RMSE hatası düşeceğine artmaya başladıysa.
        3. GCP Hataları (Error), belirlenen Doğruluğu (Accuracy) geçtiyse.
        """
        current_points = len(chunk.point_cloud.points)
        
        # Kriter 1: Nokta Sayısı
        if current_points < MIN_POINT_LIMIT:
            print(f"   DURDURMA SEBEBİ: Nokta sayısı kritik seviyenin altında ({current_points})")
            return True

        # Kriter 2: RMSE Artışı (Toleranslı Kontrol)
        if prev_rmse is not None and current_rmse > (prev_rmse * 1.01):
            print(f"   DURDURMA SEBEBİ: RMSE artmaya başladı! ({prev_rmse:.3f} -> {current_rmse:.3f})")
            return True

        # Kriter 3: GCP (Referans) Sağlığı
        markers = [m for m in chunk.markers if m.enabled and m.type == Metashape.Marker.Type.Regular]
        for m in markers:
            if m.error and m.reference.accuracy:
                acc = m.reference.accuracy
                # Accuracy vektör ise normunu al, float ise direkt kullan
                acc_val = acc.norm() if isinstance(acc, Metashape.Vector) else acc
                
                if m.error.norm() > acc_val:
                    print(f"   DURDURMA SEBEBİ: {m.label} hatası ({m.error.norm():.3f}m), limiti ({acc_val:.3f}m) aştı.")
                    return True
        return False

    def safe_filter_execution(name, criterion, target_level, safety_percent=50):
        """
        Adım 11 ve 12 için Güvenli Filtreleme.
        Hedef değer noktaların %50'sinden fazlasını siliyorsa, limiti otomatik esnetir.
        """
        print(f"\n--- {name} (Hedef Değer: {target_level}) ---")
        f = Metashape.PointCloud.Filter()
        f.init(chunk, criterion=criterion)
        values = f.values
        values.sort()
        
        # Hedef değerin üzerindeki nokta sayısı (kötü noktalar)
        to_delete_count = len([v for v in values if v > target_level])
        ratio = (to_delete_count / len(values)) * 100
        
        threshold = target_level
        
        if ratio > safety_percent:
            print(f"   UYARI: Hedef değer noktaların %{ratio:.1f}'ini siliyor. Güvenlik kilidi devrede.")
            # Güvenli eşiği bul (%50'ye denk gelen değer)
            safe_index = int(len(values) * (1 - safety_percent/100))
            threshold = values[safe_index]
            print(f"   Revize Edilen Eşik: {threshold:.2f}")
        
        f.selectPoints(threshold)
        n_removed = len([p for p in chunk.point_cloud.points if p.selected])
        chunk.point_cloud.removeSelectedPoints()
        print(f"   Silinen Nokta: {n_removed}")
        
        chunk.optimizeCameras(**opt_params)

    # =========================================================
    # ADIM 11: Reconstruction Uncertainty (Geometri Kontrolü)
    # =========================================================
    safe_filter_execution("Adım 11: Reconstruction Uncertainty", 
                          Metashape.PointCloud.Filter.ReconstructionUncertainty, 
                          10.0)

    # =========================================================
    # ADIM 12: Projection Accuracy (Piksel Eşleşme Kontrolü)
    # =========================================================
    safe_filter_execution("Adım 12: Projection Accuracy", 
                          Metashape.PointCloud.Filter.ProjectionAccuracy, 
                          3.0)

    # =========================================================
    # ADIM 13: Reprojection Error - Faz 1 (Kaba Temizlik)
    # =========================================================
    print("\n--- Adım 13: Reprojection Error (Hedef: 0.3 piksel) ---")
    TARGET_RE_PHASE_1 = 0.3
    prev_rmse = None

    while True:
        f = Metashape.PointCloud.Filter()
        f.init(chunk, criterion=Metashape.PointCloud.Filter.ReprojectionError)
        values = f.values
        values.sort()
        current_max = values[-1]
        
        if current_max <= TARGET_RE_PHASE_1:
            print(f"   Faz 1 Tamamlandı (Max Hata: {current_max:.3f})")
            break
            
        if check_stop_criteria(current_max, prev_rmse):
            break
        
        prev_rmse = current_max

        # %10 Kuralı: Her turda sadece en kötü %10 silinir
        limit_index = int(len(values) * 0.90) 
        threshold_10_percent = values[limit_index]
        
        apply_threshold = max(threshold_10_percent, TARGET_RE_PHASE_1)
        
        print(f"   Max Hata: {current_max:.3f} -> Eşik: {apply_threshold:.3f}")
        
        f.selectPoints(apply_threshold)
        chunk.point_cloud.removeSelectedPoints()
        chunk.optimizeCameras(**opt_params)

    # =========================================================
    # ADIM 15: Hassasiyeti Sıkılaştırma & Final Temizlik
    # =========================================================
    print("\n--- Adım 15: Tie Point Accuracy Ayarı ve Final Temizlik ---")
    
    # 1. Tie Point Accuracy Ayarını Değiştir (1 px -> 0.1 px)
    # Bu işlem yazılımı GCP'lere daha sıkı tutunmaya zorlar.
    print("   Ayarlar Güncelleniyor: Tie Point Accuracy 1 -> 0.1")
    chunk.tiepoint_accuracy = 0.1
    chunk.optimizeCameras(**opt_params)
    
    # 2. Yeni Hedef: RMSE <= 0.18 (USGS Final Standardı)
    print("   Yeni Hedef: RMSE <= 0.18 piksel")
    TARGET_RE_PHASE_2 = 0.18
    
    while True:
        f = Metashape.PointCloud.Filter()
        f.init(chunk, criterion=Metashape.PointCloud.Filter.ReprojectionError)
        values = f.values
        values.sort()
        current_max = values[-1]
        
        # Gerçek RMSE değerini al (API sürümüne göre)
        try:
            real_rmse = chunk.rms_reprojection_error
        except:
            real_rmse = current_max 

        print(f"   Durum -> Max Hata: {current_max:.3f} | Global RMSE: {real_rmse:.3f}")

        if real_rmse <= TARGET_RE_PHASE_2:
            print("   BAŞARI: Nihai USGS hedefine (RMSE <= 0.18) ulaşıldı.")
            break
            
        if check_stop_criteria(real_rmse, prev_rmse):
            break
            
        prev_rmse = real_rmse
        
        # Yine %10 kuralı ile hassas temizlik
        limit_index = int(len(values) * 0.90)
        threshold_10_percent = values[limit_index]
        apply_threshold = threshold_10_percent # Hedefe zorluyoruz
        
        f.selectPoints(apply_threshold)
        n_selected = len([p for p in chunk.point_cloud.points if p.selected])
        
        if n_selected == 0:
            print("   Seçilecek nokta kalmadı.")
            break
            
        chunk.point_cloud.removeSelectedPoints()
        chunk.optimizeCameras(**opt_params)

    print("\n>>> USGS İş Akışı Başarıyla Tamamlandı.")
    print(f"Kalan Nokta Sayısı: {len(chunk.point_cloud.points)}")
    if hasattr(chunk, 'rms_reprojection_error'):
        print(f"Son RMSE: {chunk.rms_reprojection_error:.4f}")

# Scripti Çalıştır
usgs_professional_workflow()