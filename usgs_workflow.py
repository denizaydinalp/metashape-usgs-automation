# ==============================================================================
# Metashape USGS Otomasyonu - v1.4.0 Stabil Safe Mode (v1.7.2 Garanti)
# DAA Mühendislik Bilişim - Deniz Aydınalp
# Güncelleme: 2025-12-09 | Log Seviyeleri Metashape.Level ile Uyumlu Hale Getirildi
# ==============================================================================

import Metashape
from datetime import datetime

# --- KRİTİK SABİT DEĞERLER ---
TIE_POINT_ACCURACY_START = 1.0  
TIE_POINT_ACCURACY_MIN = 0.3   
TIE_POINT_REDUCTION_STEP = 0.2 

CAMERA_ACCURACY_GCP_OVERRIDE = 10.0 
REPROJECTION_ERROR_TARGET = 0.3 
OPTIMIZATION_TOLERANCE = 0.0001 

# Log seviyesi sabitlerini Metashape.Level enum'ından alarak fonksiyonu tanımlıyoruz.
# Bu, v1.7.2 API'si için en doğru tanımlamadır.
def log_message(message, level): 
    """Metashape konsoluna tarihli ve seviyeli log mesajı yazar. V1.7.2 uyumludur."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    Metashape.app.log(f"{timestamp} | {message}", level)

def check_stop_criteria(prev_rmse):
    """
    USGS standardında optimizasyonun durma kriterini (Marker RMSE) kontrol eder.
    """
    chunk = Metashape.app.document.chunk
    total_error_sq = 0.0
    num_markers = 0
    
    for m in chunk.markers:
        if m.reference.enabled:
            try:
                # m.residual.norm() API v1.7.2'de çalışır.
                error = m.residual.norm()
            except AttributeError:
                log_message("Hata: Marker objesi 'residual' niteliğine sahip değil. Marker API sorunu.", Metashape.Level.Critical)
                return True 
            
            total_error_sq += error ** 2
            num_markers += 1

    if num_markers == 0:
        log_message("Referansı etkin marker (GCP) bulunamadı.", Metashape.Level.Warning)
        return False
    
    current_rmse = (total_error_sq / num_markers) ** 0.5 if num_markers > 0 else 0.0
    
    log_message(f"Optimizasyon Döngüsü - Güncel Marker RMSE (m): {current_rmse:.4f} m", Metashape.Level.Information)
    
    if abs(current_rmse - prev_rmse) < OPTIMIZATION_TOLERANCE:
        log_message(f"Durdurma Kriteri Sağlandı: RMSE farkı toleransın altında.", Metashape.Level.Information)
        return True
    
    return current_rmse

def usgs_professional_workflow():
    
    if not Metashape.app.document.chunk:
        log_message("Hata: Aktif chunk (iş parçası) bulunamadı.", Metashape.Level.Critical)
        return

    chunk = Metashape.app.document.chunk
    log_message("--- DAA Mühendislik Fotogrametri USGS Workflow v1.4.0 Başladı (v1.7.2 Garantili) ---", Metashape.Level.Information)

    # 1. USGS Step 11: Kamera Referans Ayarları (M3E)
    log_message(f"--- Adım 11: Kamera Referans Ayarları (M3E) ---", Metashape.Level.Information)
    
    for camera in chunk.cameras:
        if camera.reference.enabled:
            camera.reference.accuracy = Metashape.Vector([CAMERA_ACCURACY_GCP_OVERRIDE, CAMERA_ACCURACY_GCP_OVERRIDE, CAMERA_ACCURACY_GCP_OVERRIDE])
    
    log_message(f"Kamera Doğruluğu (XYZ) {CAMERA_ACCURACY_GCP_OVERRIDE}m olarak ayarlandı (GCP Güvencesi).", Metashape.Level.Information)

    # 2. USGS Step 12: Temel Kalibrasyon ve Optimizasyon Ayarları
    log_message(f"--- Adım 12: Kalibrasyon ve Optimasyon Ayarları ---", Metashape.Level.Information)
    
    current_tie_point_accuracy = TIE_POINT_ACCURACY_START
    chunk.tiepoint_accuracy = current_tie_point_accuracy
    log_message(f"Tie Point Accuracy başlangıç değeri {current_tie_point_accuracy} px.", Metashape.Level.Information)

    optimization_flags = Metashape.CalibrationGroup.Adjustment
    
    if chunk.transform.matrix is None:
        chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True)
    else:
        chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True, transform_to_reference=True)
    log_message("İlk optimizasyon tamamlandı.", Metashape.Level.Information)

    # 3. USGS Step 13: Reprojection Error ve Tie Point Düzeltme Döngüsü
    log_message(f"--- Adım 13: USGS Reprojection/Tie Point Döngüsü (Hedef: {REPROJECTION_ERROR_TARGET} px) ---", Metashape.Level.Information)

    prev_rmse = float('inf')
    iter_count = 0
    max_iterations = 5 

    while iter_count < max_iterations:
        iter_count += 1
        log_message(f"--- İterasyon {iter_count} Başladı ---", Metashape.Level.Information)
        
        # 3.a Reprojection Error Hesaplama
        point_cloud = chunk.point_cloud
        max_reprojection_error = 0.0
        
        for point in point_cloud.points:
            if not point.valid: continue
            for proj in point.projections.values():
                error = proj.error
                if error > max_reprojection_error:
                    max_reprojection_error = error

        log_message(f"İterasyon {iter_count}: Max Reprojection Error = {max_reprojection_error:.4f} px", Metashape.Level.Information)
        
        # 3.b USGS Kriteri Kontrolü ve Ayıklama
        if max_reprojection_error > REPROJECTION_ERROR_TARGET:
            
            # Ayıklama
            Metashape.PointCloud.selectByReprojection(chunk=chunk, error=REPROJECTION_ERROR_TARGET)
            chunk.point_cloud.removeSelectedPoints()
            log_message(f"Reprojection Error eşiği ({REPROJECTION_ERROR_TARGET} px) aşan noktalar silindi.", Metashape.Level.Information)

            # Tie Point Accuracy Sıkılaştırma
            if current_tie_point_accuracy > TIE_POINT_ACCURACY_MIN:
                current_tie_point_accuracy = max(TIE_POINT_ACCURACY_MIN, current_tie_point_accuracy - TIE_POINT_REDUCTION_STEP)
                chunk.tiepoint_accuracy = current_tie_point_accuracy
                log_message(f"Tie Point Accuracy sıkılaştırıldı: {current_tie_point_accuracy:.2f} px", Metashape.Level.Warning)
            
            # Yeniden Optimizasyon
            chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True)
            log_message("Kameralar yeniden optimize edildi.", Metashape.Level.Information)
            
            # 3.c Durdurma Kriteri Kontrolü (Marker RMSE)
            current_rmse = check_stop_criteria(prev_rmse)

            if current_rmse is True: 
                break
            
            if current_rmse is False:
                 log_message("Hata: Durdurma kriteri kontrolü başarısız.", Metashape.Level.Critical)
                 break
                 
            prev_rmse = current_rmse
            
        else:
            log_message(f"Max Reprojection Error hedefin altında. Döngü sonlandı.", Metashape.Level.Information)
            break
        
    # 4. USGS Step 15: Temizleme ve Final Optimizasyonu
    log_message("--- Adım 15: Final Optimizasyon ve Kalibrasyon Kilitleme ---", Metashape.Level.Information)
    
    chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True)
    log_message("Final Optimizasyon tamamlandı.", Metashape.Level.Information)
    
    log_message("--- USGS Workflow Başarıyla Tamamlandı ---", Metashape.Level.Information)
    
# usgs_professional_workflow()
