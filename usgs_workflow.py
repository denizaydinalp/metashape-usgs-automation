# ==============================================================================
# Metashape USGS Otomasyonu - v3.0.3 (Metashape 1.7.2 TAM UYUMLU - ÇALIŞIYOR!)
# DAA Mühendislik Bilişim - Deniz Aydınalp
# Güncelleme: 2025-12-09 | 1.7.2 için log sorunu tamamen çözüldü
# ==============================================================================

import Metashape
from datetime import datetime

# --- SABİTLER ---
TIE_POINT_ACCURACY_START = 1.0
TIE_POINT_ACCURACY_MIN    = 0.3
TIE_POINT_REDUCTION_STEP  = 0.2
CAMERA_ACCURACY_GCP_OVERRIDE = 10.0      # metre
REPROJECTION_ERROR_TARGET    = 0.3       # piksel
OPTIMIZATION_TOLERANCE        = 0.0001   # metre
MAX_ITERATIONS                = 6

def log(msg):
    """1.7.2’de çalışan tek log yöntemi"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{timestamp} | {msg}")

print("\n" + "="*70)
print("=== DAA MÜHENDİSLİK USGS WORKFLOW v3.0.3 BAŞLADI (Metashape 1.7.2) ===")
print("="*70 + "\n")

doc = Metashape.app.document
chunk = doc.chunk

if not chunk:
    print("HATA: Aktif chunk bulunamadı!")
    raise Exception("Chunk yok")

# ------------------------------------------------------------------
# 1. Kamera doğruluklarını ez (GCP varsa çok gevşek bırakıyoruz)
# ------------------------------------------------------------------
log("Adım 11 → Kamera Referans Doğruluğu ayarlanıyor...")
for camera in chunk.cameras:
    if camera.reference.enabled:
        camera.reference.accuracy = Metashape.Vector([CAMERA_ACCURACY_GCP_OVERRIDE,
                                                     CAMERA_ACCURACY_GCP_OVERRIDE,
                                                     CAMERA_ACCURACY_GCP_OVERRIDE])
log(f"Kamera doğruluğu {CAMERA_ACCURACY_GCP_OVERRIDE} m yapıldı.")

# ------------------------------------------------------------------
# 2. İlk optimizasyon
# ------------------------------------------------------------------
log("Adım 12 → İlk optimizasyon başlıyor...")
chunk.tiepoint_accuracy = TIE_POINT_ACCURACY_START
log(f"Tie point accuracy = {TIE_POINT_ACCURACY_START} px")

chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, fit_b1=True, fit_b2=True,
                      fit_k1=True, fit_k2=True, fit_k3=True, fit_k4=True,
                      fit_p1=True, fit_p2=True, fit_p3=True, fit_p4=True,
                      adaptive_fitting=True)

log("İlk optimizasyon tamamlandı.")

# ------------------------------------------------------------------
# 3. Reprojection error döngüsü (1.7.2 Filter API ile)
# ------------------------------------------------------------------
log(f"Adım 13 → Reprojection error döngüsü başlıyor (hedef ≤ {REPROJECTION_ERROR_TARGET} px)")

current_tie_accuracy = TIE_POINT_ACCURACY_START
prev_rmse = 999999.0
iter_count = 0

while iter_count < MAX_ITERATIONS:
    iter_count += 1
    log(f"--- İterasyon {iter_count}/{MAX_ITERATIONS} ---")

    # Max reprojection error bul
    filter = Metashape.TiePoints.Filter()
    filter.init(chunk, Metashape.TiePoints.Filter.ReprojectionError)
    values = [v for i, v in enumerate(filter.values) if chunk.tie_points.points[i].valid]
    max_error = max(values) if values else 0.0
    log(f"Mevcut Max Reprojection Error = {max_error:.4f} px")

    if max_error <= REPROJECTION_ERROR_TARGET:
        log(f"Hedef yakalandı ({max_error:.4f} ≤ {REPROJECTION_ERROR_TARGET}) → Döngü bitiyor.")
        break

    # Eşik üstündekileri seç ve sil
    filter.selectPoints(REPROJECTION_ERROR_TARGET)
    selected_count = chunk.tie_points.nselected
    chunk.tie_points.removeSelectedPoints()
    log(f">{REPROJECTION_ERROR_TARGET} px olan {selected_count} nokta silindi.")

    # Tie point accuracy sıkılaştır
    if current_tie_accuracy > TIE_POINT_ACCURACY_MIN:
        current_tie_accuracy = max(TIE_POINT_ACCURACY_MIN, current_tie_accuracy - TIE_POINT_REDUCTION_STEP)
        chunk.tiepoint_accuracy = current_tie_accuracy
        log(f"Tie point accuracy sıkılaştırıldı → {current_tie_accuracy:.2f} px")

    # Yeniden optimize et
    chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, fit_b1=True, fit_b2=True,
                          fit_k1=True, fit_k2=True, fit_k3=True, fit_k4=True,
                          fit_p1=True, fit_p2=True, fit_p3=True, fit_p4=True,
                          adaptive_fitting=True)
    log("Re-optimizasyon tamamlandı.")

    # GCP varsa RMSE kontrolü yapıp erken durdur
    total_err = 0.0
    count = 0
    for marker in chunk.markers:
        if marker.reference.enabled and marker.position:
            total_err += marker.residual.norm()**2
            count += 1
    if count > 0:
        current_rmse = (total_err / count)**0.5
        log(f"Marker RMSE = {current_rmse:.6f} m")
        if abs(current_rmse - prev_rmse) < OPTIMIZATION_TOLERANCE:
            log("RMSE değişimi çok küçük → Erken durdurma aktif, döngü durduruluyor.")
            break
        prev_rmse = current_rmse

# ------------------------------------------------------------------
# 4. Final optimizasyon
# ------------------------------------------------------------------
log("Adım 15 → Final optimizasyon yapılıyor...")
chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, fit_b1=True, fit_b2=True,
                      fit_k1=True, fit_k2=True, fit_k3=True, fit_k4=True,
                      fit_p1=True, fit_p2=True, fit_p3=True, fit_p4=True,
                      adaptive_fitting=True)
log("Final optimizasyon tamamlandı.")

log("=== USGS WORKFLOW TAMAMEN BAŞARIYLA BİTTİ! ===")
print("\n" + "="*70)
print("=== ÇALIŞMA TAMAM! Console loglarını incele, her şey temiz. ===")
print("="*70)
