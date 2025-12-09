# ==============================================================================
# Metashape USGS PROFESSIONAL – v6.1 PLATINUM EDITION
# DAA Mühendislik – Deniz Aydınalp – 2025
# ------------------------------------------------------------------------------
# HEDEF: M3E ile USGS Standartlarında (RMSE <= 0.18 px)
# API: Metashape 1.6 Uyumlu (Legacy)
# YENİLİK: GCP (Marker) Doğruluğu en başta 0.02m (2cm) olarak sabitleniyor.
# AKIŞ: Hazırlık -> RU(10) -> PA(2) -> TPA(0.2) -> RE(0.18)
# ==============================================================================

import Metashape
from datetime import datetime

# --- KULLANICI HEDEFLERİ ---
TARGET_RU = 10.0       # Reconstruction Uncertainty
TARGET_PA = 2.0        # Projection Accuracy
TARGET_RE = 0.18       # FİNAL Reprojection Error Hedefi

# --- SİSTEM AYARLARI ---
GCP_ACCURACY_M        = 0.02  # GCP Koordinat Doğruluğu (2 cm)
CAMERA_ACCURACY_GCP   = 10.0  # M3E RTK verisini ezmek için (m)
CRITICAL_TIE_ACCURACY = 0.2   # Final aşamada geçilecek Tie Point Accuracy
MIN_REMAINING_PERCENT = 10.0  # Güvenlik Limiti (%)

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def print_header(title):
    print("\n" + "="*85)
    print(f"   {title}")
    print("="*85)

# --- BAŞLANGIÇ ---
print_header("DAA MÜHENDİSLİK | USGS v6.1 PLATINUM (GCP 2cm) | ADANA/TR")

chunk = Metashape.app.document.chunk
if not chunk:
    raise Exception("HATA: Çalışılacak aktif chunk bulunamadı!")

# --------------------------------------------------------------------------------
# ADIM 0: HAZIRLIK VE REFERANS AYARLARI
# --------------------------------------------------------------------------------
log("Sistem Hazırlığı Başlatılıyor...")

# 1. Kamera Doğrulukları (M3E RTK vs GCP)
# Kamerayı 10m yapıyoruz ki model GCP'ye yapışsın.
for cam in chunk.cameras:
    if cam.reference.enabled:
        cam.reference.accuracy = Metashape.Vector([CAMERA_ACCURACY_GCP, CAMERA_ACCURACY_GCP, CAMERA_ACCURACY_GCP])
    else:
        cam.reference.accuracy = Metashape.Vector([10, 10, 20])

# 2. GCP (Marker) Doğrulukları (YENİ: 0.02m)
log(f"-> GCP (Marker) Koordinat Doğruluğu Ayarlanıyor: {GCP_ACCURACY_M}m")
for m in chunk.markers:
    if m.reference.enabled:
        m.reference.accuracy = Metashape.Vector([GCP_ACCURACY_M, GCP_ACCURACY_M, GCP_ACCURACY_M])

# 3. Piksel Doğrulukları
chunk.marker_projection_accuracy = 0.5  # İnsan tıklaması
chunk.tiepoint_accuracy = 1.0           # Başlangıç gevşekliği

log(f"-> Kamera Ref: {CAMERA_ACCURACY_GCP}m | GCP Ref: {GCP_ACCURACY_M}m")

# 4. Başlangıç Optimizasyonu (M3E ve Stabilite Korumalı)
log("-> Başlangıç Optimizasyonu (b1/b2, k4, p3, p4 KAPALI)...")
chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True,
                      fit_k1=True, fit_k2=True, fit_k3=True, fit_k4=False, # KAPALI
                      fit_p1=True, fit_p2=True, fit_p3=False, fit_p4=False, # KAPALI
                      fit_b1=False, fit_b2=False,                           # KAPALI
                      adaptive_fitting=True)

# Orijinal Nokta Sayısı
initial_points = len([p for p in chunk.point_cloud.points if p.valid])
log(f"✅ Hazırlık Tamam. Başlangıç Nokta Sayısı: {initial_points}")


# ================================================================================
# AŞAMA 1: RECONSTRUCTION UNCERTAINTY (Hedef: 10 | Fren: %50)
# ================================================================================
print_header(f"AŞAMA 1: Reconstruction Uncertainty (Hedef: {TARGET_RU})")

step = 0
while True:
    step += 1
    
    f = Metashape.PointCloud.Filter()
    f.init(chunk, criterion=Metashape.PointCloud.Filter.ReconstructionUncertainty)
    values = f.values
    valid_values = [v for i, v in enumerate(values) if chunk.point_cloud.points[i].valid]
    
    if not valid_values: break
    valid_values.sort(reverse=True)
    
    max_val = valid_values[0]
    total_valid = len(valid_values)
    
    log(f"--- Tur {step} ---")
    log(f"   Mevcut Max RU: {max_val:.2f} (Hedef: {TARGET_RU})")

    if max_val <= TARGET_RU:
        log(f"✅ AŞAMA 1 BAŞARILI.")
        break
        
    # %50 Fren Hesabı
    count_over = len([v for v in valid_values if v > TARGET_RU])
    ratio = (count_over / total_valid) * 100
    
    threshold = TARGET_RU
    if ratio > 50.0:
        log(f"   ⚠️ Hedef çok agresif (%{ratio:.1f}). %50 freni devrede.")
        threshold = valid_values[int(total_valid * 0.50)]
        if threshold < TARGET_RU: threshold = TARGET_RU
    
    f.selectPoints(threshold)
    chunk.point_cloud.removeSelectedPoints()
    
    chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True,
                          fit_k1=True, fit_k2=True, fit_k3=True, fit_k4=False,
                          fit_p1=True, fit_p2=True, fit_p3=False, fit_p4=False,
                          fit_b1=False, fit_b2=False, adaptive_fitting=True)


# ================================================================================
# AŞAMA 2: PROJECTION ACCURACY (Hedef: 2.0 | Fren: %50)
# ================================================================================
print_header(f"AŞAMA 2: Projection Accuracy (Hedef: {TARGET_PA})")

step = 0
while True:
    step += 1
    f = Metashape.PointCloud.Filter()
    f.init(chunk, criterion=Metashape.PointCloud.Filter.ProjectionAccuracy)
    values = f.values
    valid_values = [v for i, v in enumerate(values) if chunk.point_cloud.points[i].valid]
    
    if not valid_values: break
    valid_values.sort(reverse=True)
    max_val = valid_values[0]
    total_valid = len(valid_values)
    
    log(f"--- Tur {step} ---")
    log(f"   Mevcut Max PA: {max_val:.2f} (Hedef: {TARGET_PA})")

    if max_val <= TARGET_PA:
        log(f"✅ AŞAMA 2 BAŞARILI.")
        break
        
    count_over = len([v for v in valid_values if v > TARGET_PA])
    ratio = (count_over / total_valid) * 100
    
    threshold = TARGET_PA
    if ratio > 50.0:
        log(f"   ⚠️ Hedef çok agresif (%{ratio:.1f}). %50 freni devrede.")
        threshold = valid_values[int(total_valid * 0.50)]
        if threshold < TARGET_PA: threshold = TARGET_PA
        
    f.selectPoints(threshold)
    chunk.point_cloud.removeSelectedPoints()
    
    chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True,
                          fit_k1=True, fit_k2=True, fit_k3=True, fit_k4=False,
                          fit_p1=True, fit_p2=True, fit_p3=False, fit_p4=False,
                          fit_b1=False, fit_b2=False, adaptive_fitting=True)


# ================================================================================
# ARA GEÇİŞ: TIE POINT ACCURACY SIKILAŞTIRMA
# ================================================================================
print_header(f"ARA GEÇİŞ: Tie Point Accuracy -> {CRITICAL_TIE_ACCURACY} px")
log("⚠️ Model sıkıştırılıyor...")

chunk.tiepoint_accuracy = CRITICAL_TIE_ACCURACY
chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True,
                      fit_k1=True, fit_k2=True, fit_k3=True, fit_k4=False,
                      fit_p1=True, fit_p2=True, fit_p3=False, fit_p4=False,
                      fit_b1=False, fit_b2=False, adaptive_fitting=True)


# ================================================================================
# AŞAMA 3: REPROJECTION ERROR (Hedef: 0.18 | Fren: %10 | Stop: Error>Accuracy)
# ================================================================================
print_header(f"AŞAMA 3: Reprojection Error (Hedef: {TARGET_RE} px)")
log(f"Stop Kuralları: 1) Hedef 2) < %{MIN_REMAINING_PERCENT} Nokta 3) Error > Accuracy ({GCP_ACCURACY_M}m)")

step = 0
max_loops = 50

while step < max_loops:
    step += 1
    
    f = Metashape.PointCloud.Filter()
    f.init(chunk, criterion=Metashape.PointCloud.Filter.ReprojectionError)
    values = f.values
    valid_values = [v for i, v in enumerate(values) if chunk.point_cloud.points[i].valid]
    
    if not valid_values: break
    valid_values.sort(reverse=True)
    
    max_err = valid_values[0]
    total_now = len(valid_values)
    
    log(f"--- Tur {step} | Max Hata: {max_err:.4f} px ---")
    
    # --- STOP 1: Hedef ---
    if max_err <= TARGET_RE:
        log(f"✅ HEDEF BAŞARILDI.")
        break
        
    # --- STOP 2: Nokta Güvenliği ---
    remaining_ratio = (total_now / initial_points) * 100
    if remaining_ratio < MIN_REMAINING_PERCENT:
        log(f"🛑 STOP: Kalan nokta %{remaining_ratio:.1f} (Riskli seviye).")
        break
        
    # --- STOP 3: Error > Accuracy (GCP Kontrolü) ---
    accuracy_fail = False
    for m in chunk.markers:
        if m.reference.enabled and m.position:
            # Kullanıcı doğruluğu (Bizim atadığımız 0.02)
            user_acc = m.reference.accuracy[0] if m.reference.accuracy else 0.02
            current_err = m.residual.norm()
            
            if current_err > user_acc:
                log(f"🛑 STOP: Marker '{m.label}' Hatası ({current_err:.3f}m) > Doğruluk ({user_acc:.3f}m)")
                accuracy_fail = True
                break
    
    if accuracy_fail:
        break

    # --- SİLME (%10 Cerrahi) ---
    count_over = len([v for v in valid_values if v > TARGET_RE])
    ratio_over = (count_over / total_now) * 100
    
    threshold = TARGET_RE
    if ratio_over > 10.0:
        log(f"   ⚠️ Hedef %{ratio_over:.1f} siliyor. %10 cerrahi kesim.")
        threshold = valid_values[int(total_now * 0.10)]
        if threshold < TARGET_RE: threshold = TARGET_RE
    else:
        log(f"   Durum Normal: Direkt hedef uygulanıyor.")

    f.selectPoints(threshold)
    chunk.point_cloud.removeSelectedPoints()
    
    # Optimize
    chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True,
                          fit_k1=True, fit_k2=True, fit_k3=True, fit_k4=False,
                          fit_p1=True, fit_p2=True, fit_p3=False, fit_p4=False,
                          fit_b1=False, fit_b2=False, adaptive_fitting=True)


# ================================================================================
# FİNAL RAPOR
# ================================================================================
print_header("FİNAL OPTİMİZASYON (Full Parametreler)")
# Son bir kez kilitle, ek parametreleri aç
chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True,
                      fit_k1=True, fit_k2=True, fit_k3=True, fit_k4=False,
                      fit_p1=True, fit_p2=True, fit_p3=False, fit_p4=False,
                      fit_b1=False, fit_b2=False, 
                      fit_corrections=True, tiepoint_covariance=True,
                      adaptive_fitting=True)

f.init(chunk, criterion=Metashape.PointCloud.Filter.ReprojectionError)
final_vals = [v for i, v in enumerate(f.values) if chunk.point_cloud.points[i].valid]
final_max = max(final_vals) if final_vals else 0
removed_total = 100 - ((len(final_vals) / initial_points) * 100)

print(f"🎯 Final Max Reprojection : {final_max:.4f} px")
print(f"📉 Toplam Silinen       : %{removed_total:.1f}")
print(f"🔍 Final Tie Point Acc    : {chunk.tiepoint_accuracy:.2f} px")

# GCP RMSE
gcp_sq_sum = 0
gcp_count = 0
for m in chunk.markers:
    if m.reference.enabled and m.position:
        gcp_sq_sum += m.residual.norm()**2
        gcp_count += 1

if gcp_count > 0:
    gcp_rmse = (gcp_sq_sum / gcp_count)**0.5
    print(f"📏 GCP/Marker RMSE        : {gcp_rmse*100:.3f} cm")
else:
    print("ℹ️  Aktif GCP yok.")
print("="*85)
