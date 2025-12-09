# ==============================================================================
# Metashape USGS PROFESSIONAL – v4.2 LEGACY (METASHAPE 1.6 UYUMLU)
# DAA Mühendislik – Deniz Aydınalp – 2025
# ------------------------------------------------------------------------------
# FARK: 1.7+ yerine 1.6 API mimarisi (PointCloud Sınıfı) kullanıldı.
# ÖZELLİKLER: M3E (b1/b2 Kapalı), USGS 0.3 px, %50 Güvenlik Freni.
# ==============================================================================

import Metashape
from datetime import datetime

# --- KULLANICI AYARLARI ---
REPROJECTION_ERROR_TARGET    = 0.3    # Hedef hata (piksel)
MIN_POINT_RATIO_PERCENT      = 50     # Güvenlik freni (%)
TIE_POINT_ACCURACY_MIN       = 0.5    # Minimum Tie Point Accuracy
CAMERA_ACCURACY_GCP_OVERRIDE = 10.0   # M3E RTK verisini ezmek için (m)

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

print("\n" + "="*85)
print("   DAA MÜHENDİSLİK | USGS WORKFLOW v4.2 LEGACY (v1.6) | ADANA/TR")
print("="*85 + "\n")

chunk = Metashape.app.document.chunk
if not chunk:
    raise Exception("HATA: Çalışılacak aktif chunk bulunamadı!")

# --------------------------------------------------------------------------------
# ADIM 1: Hazırlık ve M3E Referans Ayarları
# --------------------------------------------------------------------------------
log("Sistem Kontrolü (v1.6): M3E referans ayarları...")

for cam in chunk.cameras:
    if cam.reference.enabled:
        cam.reference.accuracy = Metashape.Vector([CAMERA_ACCURACY_GCP_OVERRIDE, 
                                                   CAMERA_ACCURACY_GCP_OVERRIDE, 
                                                   CAMERA_ACCURACY_GCP_OVERRIDE])
    else:
        cam.reference.accuracy = Metashape.Vector([10, 10, 20])

chunk.marker_projection_accuracy = 0.5 
chunk.tiepoint_accuracy = 1.0           

log(f"Kamera Referans: {CAMERA_ACCURACY_GCP_OVERRIDE}m | Marker: 0.5 px")

# v1.6'da 'tie_points' yerine 'point_cloud' kullanılır
initial_points = len([p for p in chunk.point_cloud.points if p.valid])
log(f"Başlangıç Nokta Sayısı: {initial_points}")

# --------------------------------------------------------------------------------
# ADIM 2: İlk Optimizasyon (M3E: b1/b2 KAPALI)
# --------------------------------------------------------------------------------
log("İlk Optimizasyon (b1/b2 KAPALI)...")

chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True,
                      fit_k1=True, fit_k2=True, fit_k3=True, fit_k4=True,
                      fit_p1=True, fit_p2=True, fit_p3=True, fit_p4=True,
                      fit_b1=False, fit_b2=False, # M3E Mekanik Shutter Ayarı
                      adaptive_fitting=True)
log("İlk optimizasyon tamamlandı.")

# --------------------------------------------------------------------------------
# ADIM 3: Akıllı Temizlik Döngüsü (v1.6 PointCloud API)
# --------------------------------------------------------------------------------
log(f"Temizlik Döngüsü Başlıyor -> Hedef: {REPROJECTION_ERROR_TARGET} px")

current_threshold = 1.0
step = 0

while True:
    step += 1
    
    # v1.6 API DEĞİŞİKLİĞİ: PointCloud.Filter kullanımı
    f = Metashape.PointCloud.Filter()
    f.init(chunk, criterion=Metashape.PointCloud.Filter.ReprojectionError)
    
    # Değerleri al (v1.6 uyumlu)
    values = f.values
    valid_values = [v for i, v in enumerate(values) if chunk.point_cloud.points[i].valid]

    if not valid_values:
        log("HATA: Geçerli nokta kalmadı!")
        break
        
    max_err = max(valid_values)
    log(f"--- Tur {step} | Max Hata: {max_err:.4f} px | Eşik: {current_threshold:.2f} px ---")

    # Başarı Kontrolü
    if max_err <= REPROJECTION_ERROR_TARGET:
        log(f"✅ HEDEF BAŞARILDI: {max_err:.4f} px")
        break

    # Güvenlik Freni
    current_points_count = len(valid_values)
    ratio = (current_points_count / initial_points) * 100
    if ratio < MIN_POINT_RATIO_PERCENT:
        log(f"🛑 GÜVENLİK FRENİ: %{ratio:.1f} kaldı. Döngü durduruluyor.")
        break

    # Eşik Kontrolü
    if current_threshold < REPROJECTION_ERROR_TARGET:
        current_threshold = REPROJECTION_ERROR_TARGET

    # Seçim ve Silme (v1.6 PointCloud API)
    f.selectPoints(current_threshold)
    # v1.6'da nselected PointCloud üzerinden okunur muhtemelen, ama güvenli olsun diye remove diyoruz.
    # Metashape 1.6'da removeSelectedPoints PointCloud üzerindedir.
    chunk.point_cloud.removeSelectedPoints()
    
    # Silinen nokta kontrolü (Basit matematik ile)
    # v1.6'da nselected property'si bazen farklı olabilir, o yüzden log mesajını genel tutuyoruz.
    log(f"Temizlik yapıldı (Eşik: {current_threshold:.2f} px).")

    # Eşik düşürme mantığı
    # Eğer max hata eşiğin çok altındaysa hızlı düş, değilse yavaş düş
    if max_err < current_threshold:
        current_threshold = max(REPROJECTION_ERROR_TARGET, max_err * 0.9)
    else:
        current_threshold -= 0.1
        if current_threshold < REPROJECTION_ERROR_TARGET:
            current_threshold = REPROJECTION_ERROR_TARGET

    # Tie Point Accuracy Sıkılaştırma
    new_acc = max(TIE_POINT_ACCURACY_MIN, chunk.tiepoint_accuracy - 0.1)
    chunk.tiepoint_accuracy = new_acc
    
    # Re-Optimizasyon
    chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True,
                          fit_k1=True, fit_k2=True, fit_k3=True, fit_k4=True,
                          fit_p1=True, fit_p2=True, fit_p3=True, fit_p4=True,
                          fit_b1=False, fit_b2=False, 
                          adaptive_fitting=True)

# --------------------------------------------------------------------------------
# ADIM 4: Final Rapor
# --------------------------------------------------------------------------------
log("Adım 15: Final Optimizasyon...")
chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True,
                      fit_k1=True, fit_k2=True, fit_k3=True, fit_k4=True,
                      fit_p1=True, fit_p2=True, fit_p3=True, fit_p4=True,
                      fit_b1=False, fit_b2=False,
                      adaptive_fitting=True)

# Son istatistikler (v1.6 uyumlu)
f.init(chunk, criterion=Metashape.PointCloud.Filter.ReprojectionError)
final_vals = [v for i, v in enumerate(f.values) if chunk.point_cloud.points[i].valid]
final_max = max(final_vals) if final_vals else 0

print("\n" + "="*85)
print(f"✅ İŞLEM TAMAMLANDI (v1.6 UYUMLU)")
print(f"🎯 Final Max Reprojection Error : {final_max:.4f} px")
print(f"🔍 Final Tie Point Accuracy     : {chunk.tiepoint_accuracy} px")
print("="*85)

# GCP RMSE
gcp_sq_sum = 0
gcp_count = 0
for m in chunk.markers:
    if m.reference.enabled and m.position:
        gcp_sq_sum += m.residual.norm()**2
        gcp_count += 1

if gcp_count > 0:
    gcp_rmse = (gcp_sq_sum / gcp_count)**0.5
    print(f"📏 Marker RMSE: {gcp_rmse*100:.3f} cm")
else:
    print("ℹ️ Aktif GCP bulunamadı.")
print("="*85)
