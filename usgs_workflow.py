# ==============================================================================
# Metashape USGS Otomasyonu - v1.5.1 Final Debug Yapı (Hata Yakalama Eklendi)
# DAA Mühendislik Bilişim - Deniz Aydınalp
# Güncelleme: 2025-12-09 | Silent Failure'ı Önlemek İçin Ana Fonskiyona Try/Except Eklendi
# ==============================================================================

import Metashape
from datetime import datetime

# --- KRİTİK SABİT DEĞERLER (M3E ve USGS Standartları) ---
TIE_POINT_ACCURACY_START = 1.0  
TIE_POINT_ACCURACY_MIN = 0.3   
TIE_POINT_REDUCTION_STEP = 0.2 

CAMERA_ACCURACY_GCP_OVERRIDE = 10.0 
REPROJECTION_ERROR_TARGET = 0.3 
OPTIMIZATION_TOLERANCE = 0.0001 

def check_stop_criteria(prev_rmse):
    # ... (Bu fonksiyon iç mantık olarak aynıdır, sadece loglama çağrıları Metashape.app.log ile yapılır) ...
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    chunk = Metashape.app.document.chunk
    total_error_sq = 0.0
    num_markers = 0
    
    for m in chunk.markers:
        if m.reference.enabled:
            try:
                error = m.residual.norm()
            except AttributeError:
                Metashape.app.log(f"{timestamp} | Hata: Marker objesi 'residual' niteliğine sahip değil.", Metashape.Critical)
                return True 
            
            total_error_sq += error ** 2
            num_markers += 1

    if num_markers == 0:
        Metashape.app.log(f"{timestamp} | Referansı etkin marker (GCP) bulunamadı.", Metashape.Warning)
        return False
    
    current_rmse = (total_error_sq / num_markers) ** 0.5 if num_markers > 0 else 0.0
    
    Metashape.app.log(f"{timestamp} | Optimizasyon Döngüsü - Güncel Marker RMSE (m): {current_rmse:.4f} m", Metashape.Information)
    
    if abs(current_rmse - prev_rmse) < OPTIMIZATION_TOLERANCE:
        Metashape.app.log(f"{timestamp} | Durdurma Kriteri Sağlandı: RMSE farkı toleransın altında.", Metashape.Information)
        return True
    
    return current_rmse

def usgs_professional_workflow():
    
    # KRİTİK DEBUG GİRİŞİ: Tüm ana bloğu try-except içine alıyoruz
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not Metashape.app.document.chunk:
            Metashape.app.log(f"{timestamp} | Hata: Aktif chunk (iş parçası) bulunamadı.", Metashape.Critical)
            return

        chunk = Metashape.app.document.chunk
        Metashape.app.log(f"{timestamp} | --- DAA Mühendislik Fotogrametri USGS Workflow v1.5.1 Başladı (Debug) ---", Metashape.Information)

        # 1. USGS Step 11: Kamera Referans Ayarları (M3E)
        Metashape.app.log(f"{timestamp} | --- Adım 11: Kamera Referans Ayarları (M3E) ---", Metashape.Information)
        
        for camera in chunk.cameras:
            if camera.reference.enabled:
                camera.reference.accuracy = Metashape.Vector([CAMERA_ACCURACY_GCP_OVERRIDE, CAMERA_ACCURACY_GCP_OVERRIDE, CAMERA_ACCURACY_GCP_OVERRIDE])
        
        Metashape.app.log(f"{timestamp} | Kamera Doğruluğu (XYZ) {CAMERA_ACCURACY_GCP_OVERRIDE}m olarak ayarlandı (GCP Güvencesi).", Metashape.Information)

        # 2. USGS Step 12: Temel Kalibrasyon ve Optimizasyon Ayarları
        Metashape.app.log(f"{timestamp} | --- Adım 12: Kalibrasyon ve Optimasyon Ayarları ---", Metashape.Information)
        
        current_tie_point_accuracy = TIE_POINT_ACCURACY_START
        chunk.tiepoint_accuracy = current_tie_point_accuracy
        Metashape.app.log(f"{timestamp} | Tie Point Accuracy başlangıç değeri {current_tie_point_accuracy} px.", Metashape.Information)

        optimization_flags = Metashape.CalibrationGroup.Adjustment
        
        if chunk.transform.matrix is None:
            chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True)
        else:
            chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True, transform_to_reference=True)
        Metashape.app.log(f"{timestamp} | İlk optimizasyon tamamlandı.", Metashape.Information)

        # 3. USGS Step 13: Reprojection Error ve Tie Point Düzeltme Döngüsü
        Metashape.app.log(f"{timestamp} | --- Adım 13: USGS Reprojection/Tie Point Döngüsü (Hedef: {REPROJECTION_ERROR_TARGET} px) ---", Metashape.Information)

        prev_rmse = float('inf')
        iter_count = 0
        max_iterations = 5 

        while iter_count < max_iterations:
            iter_count += 1
            Metashape.app.log(f"{timestamp} | --- İterasyon {iter_count} Başladı ---", Metashape.Information)
            
            # 3.a Reprojection Error Hesaplama
            point_cloud = chunk.point_cloud
            max_reprojection_error = 0.0
            
            for point in point_cloud.points:
                if not point.valid: continue
                for proj in point.projections.values():
                    error = proj.error
                    if error > max_reprojection_error:
                        max_reprojection_error = error

            Metashape.app.log(f"{timestamp} | İterasyon {iter_count}: Max Reprojection Error = {max_reprojection_error:.4f} px", Metashape.Information)
            
            # 3.b USGS Kriteri Kontrolü ve Ayıklama
            if max_reprojection_error > REPROJECTION_ERROR_TARGET:
                
                Metashape.PointCloud.selectByReprojection(chunk=chunk, error=REPROJECTION_ERROR_TARGET)
                chunk.point_cloud.removeSelectedPoints()
                Metashape.app.log(f"{timestamp} | Reprojection Error eşiği ({REPROJECTION_ERROR_TARGET} px) aşan noktalar silindi.", Metashape.Information)

                # Tie Point Accuracy Sıkılaştırma
                if current_tie_point_accuracy > TIE_POINT_ACCURACY_MIN:
                    current_tie_point_accuracy = max(TIE_POINT_ACCURACY_MIN, current_tie_point_accuracy - TIE_POINT_REDUCTION_STEP)
                    chunk.tiepoint_accuracy = current_tie_point_accuracy
                    Metashape.app.log(f"{timestamp} | Tie Point Accuracy sıkılaştırıldı: {current_tie_point_accuracy:.2f} px", Metashape.Warning)
                
                chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True)
                Metashape.app.log(f"{timestamp} | Kameralar yeniden optimize edildi.", Metashape.Information)
                
                current_rmse = check_stop_criteria(prev_rmse)

                if current_rmse is True: 
                    break
                
                if current_rmse is False:
                     Metashape.app.log(f"{timestamp} | Hata: Durdurma kriteri kontrolü başarısız.", Metashape.Critical)
                     break
                     
                prev_rmse = current_rmse
                
            else:
                Metashape.app.log(f"{timestamp} | Max Reprojection Error hedefin altında. Döngü sonlandı.", Metashape.Information)
                break
            
        # 4. USGS Step 15: Temizleme ve Final Optimizasyonu
        Metashape.app.log(f"{timestamp} | --- Adım 15: Final Optimizasyon ve Kalibrasyon Kilitleme ---", Metashape.Information)
        
        chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True)
        Metashape.app.log(f"{timestamp} | Final Optimizasyon tamamlandı.", Metashape.Information)
        
        Metashape.app.log(f"{timestamp} | --- USGS Workflow Başarıyla Tamamlandı ---", Metashape.Information)
    
    except Exception as e:
        # Kod çalıştıysa buraya düşer ve hatayı konsola basar.
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        import traceback
        Metashape.app.log(f"{timestamp} | KRİTİK HATA: Scriptin ana gövdesi çalışırken beklenmedik bir hata oluştu: {e}", Metashape.Critical)
        Metashape.app.log(traceback.format_exc(), Metashape.Critical)
        
# usgs_professional_workflow()
