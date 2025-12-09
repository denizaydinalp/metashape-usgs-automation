# ==============================================================================
# Metashape USGS Otomasyonu - v1.3.1 Safe Mode (Final Stabil Versiyon)
# DAA Mühendislik Bilişim - Deniz Aydınalp
# Güncelleme: 2025-12-09 | API Hatası Çözüldü & Log Seviyesi Hatası Giderildi
# ==============================================================================

import Metashape
import math
from datetime import datetime

# --- KRİTİK SABİT DEĞERLER (M3E ve USGS Standartları) ---
TIE_POINT_ACCURACY_START = 1.0  # Safe Mode başlangıç değeri (Overfitting'i önlemek için yüksek başlar)
TIE_POINT_ACCURACY_MIN = 0.3   # Ulaşılmak istenen en sıkı Tie Point değeri
TIE_POINT_REDUCTION_STEP = 0.2 # Her iterasyonda ne kadar azaltılacağı (Kademeli Sıkılaştırma)

CAMERA_ACCURACY_GCP_OVERRIDE = 10.0 # RTK/GCP çakışmasında GCP'ye güvenmek için (metre)
REPROJECTION_ERROR_TARGET = 0.3 # USGS Hedefi (piksel)
OPTIMIZATION_TOLERANCE = 0.0001 # Iterasyon durma eşiği (metre farkı)

def log_message(message, level=Metashape.Information): # DÜZELTME: Metashape.app.Information yerine Metashape.Information
    """Metashape konsoluna tarihli ve seviyeli log mesajı yazar."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Log seviyeleri (Information, Warning, Critical) doğrudan Metashape objesinden alınır.
    Metashape.app.log(f"{timestamp} | {message}", level)

def check_stop_criteria(prev_rmse):
    """
    USGS standardında optimizasyonun durma kriterini (Marker RMSE) kontrol eder.
    Metashape API v2.x uyumlu: m.residual.norm() kullanır.
    """
    chunk = Metashape.app.document.chunk
    
    total_error_sq = 0.0
    num_markers = 0
    
    for m in chunk.markers:
        # Yalnızca referansı etkin olan (GCP) noktaları kontrol et.
        if m.reference.enabled:
            try:
                # KRİTİK DÜZELTME: Marker'ın 3D kalıntı hatasının vektörel büyüklüğünü alıyoruz.
                error = m.residual.norm()
            except AttributeError:
                log_message("Hata: Metashape.Marker objesi 'residual' niteliğine sahip değil.", Metashape.Critical)
                return True # Hata durumunda döngüyü sonlandır
            
            total_error_sq += error ** 2
            num_markers += 1

    if num_markers == 0:
        log_message("Referansı etkin marker (GCP) bulunamadı. Durdurma kriteri uygulanamaz.", Metashape.Warning)
        return False
    
    # Marker'ların Toplam RMSE (metre cinsinden) hesaplama
    current_rmse = (total_error_sq / num_markers) ** 0.5 if num_markers > 0 else 0.0
    
    log_message(f"Optimizasyon Döngüsü - Güncel Marker RMSE (m): {current_rmse:.4f} m", Metashape.Information)
    
    # Durdurma Kriteri Mantığı: RMSE farkı eşikten küçükse durdur
    if abs(current_rmse - prev_rmse) < OPTIMIZATION_TOLERANCE:
        log_message(f"Durdurma Kriteri Sağlandı: RMSE farkı toleransın altında.", Metashape.Information)
        return True
    
    return current_rmse # Yeni RMSE değerini döndür

def usgs_professional_workflow():
    """
    USGS Standartlarına uygun Fotogrametrik İş Akışı (Optimize Cameras sonrası başlar)
    """
    
    if not Metashape.app.document.chunk:
        log_message("Hata: Aktif chunk (iş parçası) bulunamadı.", Metashape.Critical)
        return

    chunk = Metashape.app.document.chunk
    log_message("--- DAA Mühendislik Fotogrametri USGS Workflow v1.3.1 Başladı ---", Metashape.Information)

    # 1. USGS Step 11: Kamera Referans Ayarları (RTK/GCP Çakışması Kontrolü)
    log_message(f"--- Adım 11: Kamera Referans Ayarları (M3E) ---", Metashape.Information)
    
    # Kamera doğruluğunu GCP'ye mutlak güven duymak için 10m'ye ayarlama
    for camera in chunk.cameras:
        if camera.reference.enabled:
            camera.reference.accuracy = Metashape.Vector([CAMERA_ACCURACY_GCP_OVERRIDE, CAMERA_ACCURACY_GCP_OVERRIDE, CAMERA_ACCURACY_GCP_OVERRIDE])
    
    log_message(f"Kamera Doğruluğu (XYZ) {CAMERA_ACCURACY_GCP_OVERRIDE}m olarak ayarlandı.", Metashape.Information)

    # 2. USGS Step 12: Temel Kalibrasyon ve Optimizasyon Ayarları
    log_message(f"--- Adım 12: Kalibrasyon ve Optimasyon Ayarları ---", Metashape.Information)
    
    # Tie Point Accuracy başlangıç değerini ayarlama
    current_tie_point_accuracy = TIE_POINT_ACCURACY_START
    chunk.tiepoint_accuracy = current_tie_point_accuracy
    log_message(f"Tie Point Accuracy başlangıç değeri {current_tie_point_accuracy} px.", Metashape.Information)

    # Optimize edilecek kamera parametreleri: f, cx, cy, k1, k2, k3, p1, p2
    optimization_flags = Metashape.CalibrationGroup.Adjustment
    
    # İlk Optimizasyon
    if chunk.transform.matrix is None:
        chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True)
    else:
        chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True, transform_to_reference=True)
    log_message("İlk optimizasyon tamamlandı.", Metashape.Information)

    # 3. USGS Step 13: Reprojection Error ve Tie Point Düzeltme Döngüsü
    log_message(f"--- Adım 13: USGS Reprojection/Tie Point Döngüsü (Hedef: {REPROJECTION_ERROR_TARGET} px) ---", Metashape.Information)

    prev_rmse = float('inf')
    iter_count = 0
    max_iterations = 5 # Güvenlik için maksimum iterasyon sayısı

    while iter_count < max_iterations:
        iter_count += 1
        log_message(f"--- İterasyon {iter_count} Başladı ---", Metashape.Information)
        
        # 3.a Reprojection Error Hesaplama
        point_cloud = chunk.point_cloud
        max_reprojection_error = 0.0
        
        for point in point_cloud.points:
            if not point.valid: continue
            for proj in point.projections.values():
                error = proj.error
                if error > max_reprojection_error:
                    max_reprojection_error = error

        log_message(f"İterasyon {iter_count}: Max Reprojection Error = {max_reprojection_error:.4f} px", Metashape.Information)
        
        # 3.b USGS Kriteri Kontrolü ve Ayıklama
        if max_reprojection_error > REPROJECTION_ERROR_TARGET:
            
            # Reprojection Error eşiği aşan noktaları kaldır
            Metashape.PointCloud.selectByReprojection(chunk=chunk, error=REPROJECTION_ERROR_TARGET)
            chunk.point_cloud.removeSelectedPoints()
            log_message(f"Reprojection Error eşiği ({REPROJECTION_ERROR_TARGET} px) aşan noktalar silindi.", Metashape.Information)

            # Tie Point Accuracy'yi Sıkılaştırma (Kademeli Azaltma)
            if current_tie_point_accuracy > TIE_POINT_ACCURACY_MIN:
                current_tie_point_accuracy = max(TIE_POINT_ACCURACY_MIN, current_tie_point_accuracy - TIE_POINT_REDUCTION_STEP)
                chunk.tiepoint_accuracy = current_tie_point_accuracy
                log_message(f"Tie Point Accuracy sıkılaştırıldı: {current_tie_point_accuracy:.2f} px", Metashape.Warning)
            
            # Yeniden Optimizasyon
            chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True)
            log_message("Kameralar yeniden optimize edildi.", Metashape.Information)
            
            # 3.c Durdurma Kriteri Kontrolü (Marker RMSE'ye bak)
            current_rmse = check_stop_criteria(prev_rmse)

            if current_rmse is True: # Eğer Durdurma Kriteri sağlandıysa
                break
            
            if current_rmse is False:
                 log_message("Hata: Durdurma kriteri kontrolü başarısız.", Metashape.Critical)
                 break
                 
            prev_rmse = current_rmse # Yeni RMSE değerini bir sonraki iterasyon için sakla
            
        else:
            log_message(f"Max Reprojection Error hedefin altında. Döngü sonlandı.", Metashape.Information)
            break
        
    # 4. USGS Step 15: Temizleme ve Final Optimizasyonu
    log_message("--- Adım 15: Final Optimizasyon ve Kalibrasyon Kilitleme ---", Metashape.Information)
    
    # Final Optimizasyonu
    chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True)
    log_message("Final Optimizasyon tamamlandı.", Metashape.Information)
    
    log_message("--- USGS Workflow Başarıyla Tamamlandı ---", Metashape.Information)
    
# Çalıştırmak için:
# usgs_professional_workflow()
