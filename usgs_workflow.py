# ==============================================================================
# Metashape USGS Otomasyonu - v3.0.2 (Metashape 1.7.2 Uyumlu)
# DAA Mühendislik Bilişim - Deniz Aydınalp
# Güncelleme: 2025-12-09 | 1.7.2 API'si için reprojection filter düzeltildi
# ==============================================================================

import Metashape
from datetime import datetime

# --- KRİTİK SABİT DEĞERLER (M3E + USGS Standartları) ---
TIE_POINT_ACCURACY_START = 1.0
TIE_POINT_ACCURACY_MIN = 0.3
TIE_POINT_REDUCTION_STEP = 0.2
CAMERA_ACCURACY_GCP_OVERRIDE = 10.0          # metre cinsinden (GCP varsa bu değer ezilir)
REPROJECTION_ERROR_TARGET = 0.3              # piksel
OPTIMIZATION_TOLERANCE = 0.0001              # metre (marker RMSE farkı)
MAX_ITERATIONS = 6


def log(message, level=4):
    """Kolay loglama: 4=INFO, 2=WARN, 1=CRIT"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    Metashape.app.log(f"{timestamp} | {message}", level)


def check_stop_criteria(prev_rmse):
    """USGS durdurma kriteri: Marker RMSE değişimi çok küçükse dur"""
    chunk = Metashape.app.document.chunk
    total_error_sq = 0.0
    num_markers = 0

    for m in chunk.markers:
        if m.reference.enabled and m.position:  # position varsa residual var demektir
            try:
                error = m.residual.norm()
                total_error_sq += error ** 2
                num_markers += 1
            except:
                continue  # Hatalı marker'ı atla

    if num_markers == 0:
        log("Referansı etkin GCP bulunamadı, durdurma kriteri atlanıyor.", 2)
        return False, prev_rmse

    current_rmse = (total_error_sq / num_markers) ** 0.5
    log(f"Marker RMSE = {current_rmse:.5f} m (önceki: {prev_rmse:.5f} m)", 4)

    if abs(current_rmse - prev_rmse) < OPTIMIZATION_TOLERANCE:
        log(f"DURDURMA KRİTERİ SAĞLANDI → RMSE farkı < {OPTIMIZATION_TOLERANCE} m", 4)
        return True, current_rmse

    return False, current_rmse


def usgs_professional_workflow():

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("\n=== DAA MÜHENDİSLİK USGS WORKFLOW v3.0.2 BAŞLADI (1.7.2 Uyumlu) ===")
    log("--- DAA Mühendislik Fotogrametri USGS Workflow v3.0.2 Başladı (1.7.2 NİHAİ) ---", 4)

    if not Metashape.app.document.chunk:
        log("Hata: Aktif chunk (iş parçası) bulunamadı.", 1)
        return

    chunk = Metashape.app.document.chunk

    # 1. USGS Step 11: Kamera Referans Ayarları (M3E)
    log("--- Adım 11: Kamera Referans Ayarları (M3E) ---", 4)

    for camera in chunk.cameras:
        if camera.reference.enabled:
            camera.reference.accuracy = Metashape.Vector([CAMERA_ACCURACY_GCP_OVERRIDE, CAMERA_ACCURACY_GCP_OVERRIDE, CAMERA_ACCURACY_GCP_OVERRIDE])

    log(f"Kamera Doğruluğu (XYZ) {CAMERA_ACCURACY_GCP_OVERRIDE}m olarak ayarlandı (GCP Güvencesi).", 4)

    # 2. USGS Step 12: Temel Kalibrasyon ve Optimizasyon Ayarları
    log("--- Adım 12: Kalibrasyon ve Optimizasyon Ayarları ---", 4)

    current_tie_point_accuracy = TIE_POINT_ACCURACY_START
    chunk.tiepoint_accuracy = current_tie_point_accuracy
    log(f"Tie Point Accuracy başlangıç değeri {current_tie_point_accuracy} px.", 4)

    optimization_flags = Metashape.CalibrationGroup.Adjustment

    if chunk.transform.matrix is None:
        chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True)
    else:
        chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True)

    log("İlk optimizasyon tamamlandı.", 4)

    # 3. USGS Step 13: Reprojection Error ve Tie Point Düzeltme Döngüsü
    log(f"--- Adım 13: USGS Reprojection/Tie Point Döngüsü (Hedef: {REPROJECTION_ERROR_TARGET} px) ---", 4)

    prev_rmse = float('inf')
    iter_count = 0

    while iter_count < MAX_ITERATIONS:
        iter_count += 1
        log(f"--- İterasyon {iter_count} Başladı ---", 4)

        # 3.a 1.7.2 Uyumlu Reprojection Filter ile Max Error Hesapla & Seç
        f = Metashape.TiePoints.Filter()
        f.init(chunk, criterion=Metashape.TiePoints.Filter.ReprojectionError)
        list_values = f.values
        list_values_valid = [list_values[i] for i in range(len(list_values)) if chunk.tie_points.points[i].valid]
        max_reprojection_error = max(list_values_valid) if list_values_valid else 0.0

        log(f"İterasyon {iter_count}: Max Reprojection Error = {max_reprojection_error:.4f} px", 4)

        # 3.b USGS Kriteri Kontrolü ve Ayıklama (1.7.2 Filter API'si)
        if max_reprojection_error > REPROJECTION_ERROR_TARGET:
            # Hedef eşiğe göre seç ve sil (gradual selection gibi)
            f.selectPoints(REPROJECTION_ERROR_TARGET)
            num_selected = sum(1 for p in chunk.tie_points.points if p.selected)
            chunk.tie_points.removeSelectedPoints()
            log(f"Reprojection Error > {REPROJECTION_ERROR_TARGET} px olan {num_selected} tie point silindi.", 4)

            # Tie Point Accuracy Sıkılaştırma
            if current_tie_point_accuracy > TIE_POINT_ACCURACY_MIN:
                current_tie_point_accuracy = max(TIE_POINT_ACCURACY_MIN, current_tie_point_accuracy - TIE_POINT_REDUCTION_STEP)
                chunk.tiepoint_accuracy = current_tie_point_accuracy
                log(f"Tie Point Accuracy sıkılaştırıldı: {current_tie_point_accuracy:.2f} px", 2)

            chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True)
            log("Kameralar yeniden optimize edildi.", 4)

            # Durdurma Kriteri
            stop, prev_rmse = check_stop_criteria(prev_rmse)
            if stop:
                break

        else:
            log("Max Reprojection Error hedefin altında. Döngü sonlandı.", 4)
            break

    # 4. USGS Step 15: Temizleme ve Final Optimizasyonu
    log("--- Adım 15: Final Optimizasyon ve Kalibrasyon Kilitleme ---", 4)

    chunk.optimizeCameras(optimization_flags=optimization_flags, adaptive_fitting=True)
    log("Final Optimizasyon tamamlandı.", 4)

    log("--- USGS Workflow Başarıyla Tamamlandı (1.7.2) ---", 4)
    print("=== WORKFLOW TAMAMLANDI! Logları kontrol et. 🚀 ===")


# Çalıştırmak için bu satırı aç (yorumdan çıkar):
usgs_professional_workflow()
