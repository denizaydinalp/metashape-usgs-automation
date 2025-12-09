# ==============================================================================
# Metashape USGS Otomasyonu - v3.0.0 NİHAİ ÇEKİRDEK YAPI
# DAA Mühendislik Bilişim - Deniz Aydınalp
# Güncelleme: 2025-12-09 | Tüm Global Sabitler Kaldırıldı, Direkt Sayısal Loglama
# ==============================================================================

import Metashape
from datetime import datetime

# LOG SEVİYELERİ DOĞRUDAN SAYISAL DEĞERLERİYLE KULLANILACAKTIR: 
# INFO = 4, WARN = 2, CRIT = 1

# --- KRİTİK SABİT DEĞERLER (M3E ve USGS Standartları) ---
TIE_POINT_ACCURACY_START = 1.0  
TIE_POINT_ACCURACY_MIN = 0.3   
TIE_POINT_REDUCTION_STEP = 0.2 

CAMERA_ACCURACY_GCP_OVERRIDE = 10.0 
REPROJECTION_ERROR_TARGET = 0.3 
OPTIMIZATION_TOLERANCE = 0.0001 


def check_stop_criteria(prev_rmse):
    """
    USGS standardında optimizasyonun durma kriterini (Marker RMSE) kontrol eder.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    chunk = Metashape.app.document.chunk
    total_error_sq = 0.0
    num_markers = 0
    
    for m in chunk.markers:
        if m.reference.enabled:
            try:
                error = m.residual.norm()
            except AttributeError:
                Metashape.app.log(f"{timestamp} | Hata: Marker objesi 'residual' niteliğine sahip değil.", 1) # CRIT
                return True 
            
            total_error_sq += error ** 2
            num_markers += 1

    if num_markers == 0:
        Metashape.app.log(f"{timestamp} | Referansı etkin marker (GCP) bulunamadı.", 2) # WARN
        return False
    
    current_rmse = (total_error_sq / num_markers) ** 0.5 if num_markers > 0 else 0.0
    
    Metashape.app.log(f"{timestamp} | Optimizasyon Döngüsü - Güncel Marker RMSE (m): {current_rmse:.4f} m", 4) # INFO
    
    if abs(current_rmse - prev_rmse) < OPTIMIZATION_TOLERANCE:
        Metashape.app.log(f"{timestamp} | Durdurma Kriteri Sağlandı: RMSE farkı toleransın altında.", 4) # INFO
        return True
    
    return current_rmse

def usgs_professional_workflow():
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 🚨 KRİTİK BAŞLANGIÇ LOGU (TEST AMAÇLI):
    print("--- V3.0.0 BAŞLANGIÇ TESTİ GEÇTİ ---") 
    Metashape.app.log(f"{timestamp} | --- DAA Mühendislik Fotogrametri USGS Workflow v3.0.0 Başladı (NİHAİ ÇEKİRDEK YAPI) ---", 4) # INFO

    if not Metashape.app.document.chunk:
        Metashape.app.log(f"{timestamp} | Hata: Aktif chunk (iş parçası) bulunamadı.", 1) # CRIT
        return

    chunk = Metashape.app.document.chunk

    # 1. USGS Step 11: Kamera Referans Ayarları (M3E)
    Metashape.app.log(f"{timestamp} | --- Adım 11: Kamera Referans Ayarları (M3E) ---", 4) # INFO
    
    for camera in chunk.cameras:
        if camera.reference.enabled:
            camera.reference.accuracy = Metashape.Vector([CAMERA_ACCURACY_GCP_OVERRIDE, CAMERA_ACCURACY_GCP_OVERRIDE, CAMERA_ACCURACY_GCP_OVERRIDE])
    
    Metashape.app.log(f"{timestamp} | Kamera Doğruluğu (XYZ) {CAMERA_ACCURACY_GCP_OVERRIDE}m olarak ayarlandı (GCP Güvencesi).", 4) # INFO

    # 2. USGS Step 12: Temel Kalibrasyon ve Optimizasyon Ayarları
    Metashape.app.log(f"{timestamp} | --- Adım 12: Kalibrasyon ve Optimasyon Ayarları ---", 4) # INFO
    
    current_tie_point_accuracy = TIE_POINT_ACCURACY_START
    chunk.tiepoint_accuracy = current_tie_point_accuracy
    Metashape.app.log(f"{timestamp} | Tie Point Accuracy başlangıç değeri {current_tie_point_accuracy} px.", 4) # INFO

    optimization_flags = Metashape.CalibrationGroup.Adjustment
    
    if chunk.transform.matrix is None:
        chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True)
    else:
        chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True, transform_to_reference=True)
    Metashape.app.log(f"{timestamp} | İlk optimizasyon tamamlandı.", 4) # INFO

    # 3. USGS Step 13: Reprojection Error ve Tie Point Düzeltme Döngüsü
    Metashape.app.log(f"{timestamp} | --- Adım 13: USGS Reprojection/Tie Point Döngüsü (Hedef: {REPROJECTION_ERROR_TARGET} px) ---", 4) # INFO

    prev_rmse = float('inf')
    iter_count = 0
    max_iterations = 5 

    while iter_count < max_iterations:
        iter_count += 1
        Metashape.app.log(f"{timestamp} | --- İterasyon {iter_count} Başladı ---", 4) # INFO
        
        # 3.a Reprojection Error Hesaplama
        point_cloud = chunk.point_cloud
        max_reprojection_error = 0.0
        
        for point in point_cloud.points:
            if not point.valid: continue
            for proj in point.projections.values():
                error = proj.error
                if error > max_reprojection_error:
                    max_reprojection_error = error

        Metashape.app.log(f"{timestamp} | İterasyon {iter_count}: Max Reprojection Error = {max_reprojection_error:.4f} px", 4) # INFO
        
        # 3.b USGS Kriteri Kontrolü ve Ayıklama
        if max_reprojection_error > REPROJECTION_ERROR_TARGET:
            
            Metashape.PointCloud.selectByReprojection(chunk=chunk, error=REPROJECTION_ERROR_TARGET)
            chunk.point_cloud.removeSelectedPoints()
            Metashape.app.log(f"{timestamp} | Reprojection Error eşiği ({REPROJECTION_ERROR_TARGET} px) aşan noktalar silindi.", 4) # INFO

            # Tie Point Accuracy Sıkılaştırma
            if current_tie_point_accuracy > TIE_POINT_ACCURACY_MIN:
                current_tie_point_accuracy = max(TIE_POINT_ACCURACY_MIN, current_tie_point_accuracy - TIE_POINT_REDUCTION_STEP)
                chunk.tiepoint_accuracy = current_tie_point_accuracy
                Metashape.app.log(f"{timestamp} | Tie Point Accuracy sıkılaştırıldı: {current_tie_point_accuracy:.2f} px", 2) # WARN
            
            chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True)
            Metashape.app.log(f"{timestamp} | Kameralar yeniden optimize edildi.", 4) # INFO
            
            current_rmse = check_stop_criteria(prev_rmse)

            if current_rmse is True: 
                break
            
            if current_rmse is False:
                 Metashape.app.log(f"{timestamp} | Hata: Durdurma kriteri kontrolü başarısız.", 1) # CRIT
                 break
                 
            prev_rmse = current_rmse
            
        else:
            Metashape.app.log(f"{timestamp} | Max Reprojection Error hedefin altında. Döngü sonlandı.", 4) # INFO
            break
        
    # 4. USGS Step 15: Temizleme ve Final Optimizasyonu
    Metashape.app.log(f"{timestamp} | --- Adım 15: Final Optimizasyon ve Kalibrasyon Kilitleme ---", 4) # INFO
    
    chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True)
    Metashape.app.log(f"{timestamp} | Final Optimizasyon tamamlandı.", 4) # INFO
    
    Metashape.app.log(f"{timestamp} | --- USGS Workflow Başarıyla Tamamlandı ---", 4) # INFO
    
# usgs_professional_workflow()
