"""Version simplifiée de script.py

But: script minimal, commenté en français ligne par ligne.
Fonctionnalités: mode `--manual` (vous choisissez la couche/zoom/position),
pas en mètres (`--step`, défaut 15 m), capture en spirale autour du point.
"""

import argparse
import math
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


# Construire l'URL de la carte centrée sur (lat,lon,zoom)
def build_map_url(lat, lon, zoom):
    return f"https://map.openaerialmap.org/#/{lat},{lon},{zoom}"


# Convertit une distance (mètres) en degrés (lat, lon) approximatifs
def meters_to_deg(lat, meters):
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * math.cos(math.radians(lat))
    return meters / m_per_deg_lat, meters / (m_per_deg_lon + 1e-12)


# Générateur qui avance linéairement le long de la côte (vers l'est)
def linear_positions(center_lat, center_lon, step_m):
    """Génère des positions qui avancent vers l'est le long de la côte."""
    dlat, dlng = meters_to_deg(center_lat, step_m)
    lat = center_lat
    lng = center_lon
    # avancer vers l'est
    while True:
        yield lat, lng
        lng += dlng


# Lire lat,lon,zoom depuis une URL de la carte
def parse_center_from_url(url):
    try:
        if '#/' in url:
            part = url.split('#/')[1]
            first = part.split('/')[0]
            lat_s, lon_s, zoom_s = first.split(',')[:3]
            return float(lat_s), float(lon_s), int(float(zoom_s))
    except Exception:
        pass
    return None


# Fonction principale de capture
def take_captures(center_lat, center_lon, zoom, captures, step_m, outdir, manual=False, start_index=0, driver=None):
    out = Path(outdir).resolve()  # Chemin absolu
    out.mkdir(parents=True, exist_ok=True)
    print(f"Enregistrement dans: {out}")  # Affiche le chemin exact

    close_driver = False
    
    # Créer le driver seulement si pas fourni
    if driver is None:
        close_driver = True
        # Options: si manuel, ouvrir fenêtre visible
        opts = Options()
        opts.add_argument("--no-default-browser-check")
        opts.add_argument("--disable-extensions")
        if manual:
            opts.add_argument("--start-maximized")
        else:
            opts.add_argument("--headless=new")
            opts.add_argument("--window-size=1200,1200")

        svc = Service(ChromeDriverManager().install())
        # Augmenter les timeouts pour éviter les problèmes de connexion
        driver = webdriver.Chrome(service=svc, options=opts)
        driver.set_page_load_timeout(60)  # timeout 60 secondes pour charger une page
        driver.set_script_timeout(60)  # timeout 60 secondes pour les scripts

    # En mode manuel: ouvrez la carte et attendez que l'utilisateur positionne
    if manual:
        try:
            driver.get(build_map_url(center_lat, center_lon, zoom))
        except Exception as e:
            print(f"Erreur lors du chargement: {e}. Le navigateur devrait tout de même être ouvert.")
        print("Ouvert: sélectionnez Mapbox Satellite, positionnez la carte et zoom manuellement, puis revenez ici et appuyez Entrée.")
        time.sleep(2.0)  # laisser le temps de charger
        input()
        
        # Lire les coordonnées depuis l'URL de la carte
        try:
            parsed = parse_center_from_url(driver.current_url)
            if parsed:
                center_lat, center_lon, zoom = parsed
                print(f"Coordonnées détectées: {center_lat}, {center_lon}, zoom: {zoom}")
        except Exception:
            pass

    try:
        gen = linear_positions(center_lat, center_lon, step_m)
        i = start_index
        count = 0
        for lat, lon in gen:
            if count >= captures:
                break
            url = build_map_url(lat, lon, zoom)
            driver.get(url)
            time.sleep(3.0)  # attendre le chargement des tuiles (3 secondes)
            fname = out / f"cap_{i+1:03d}_{lat:.6f}_{lon:.6f}.png"
            driver.save_screenshot(str(fname))
            print("Saved", fname)
            i += 1
            count += 1
    finally:
        # Ne fermer le driver que si on l'a créé ET qu'on n'est pas en mode manuel
        if close_driver and not manual:
            driver.quit()
    
    # Retourner le driver seulement s'il n'a pas été fermé
    return i, driver if not (close_driver and not manual) else None  # Retourner l'index et le driver si ouvert


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--captures", type=int, default=10)  # Par défaut 10 images
    p.add_argument("--step", type=float, default=30.0, help="pas en mètres")
    p.add_argument("--center-lat", type=float, default=36.8180)
    p.add_argument("--center-lon", type=float, default=10.3320)
    p.add_argument("--zoom", type=int, default=19)
    p.add_argument("--outdir", type=str, default="captures")
    p.add_argument("--manual", action="store_true")
    p.add_argument("--start-index", type=int, default=0, help="Index de départ pour nommer les fichiers")
    args = p.parse_args()

    driver = None
    try:
        next_index, driver = take_captures(args.center_lat, args.center_lon, args.zoom, args.captures, args.step, args.outdir, manual=args.manual, start_index=args.start_index, driver=driver)
        
        # En mode interactif, proposer de continuer
        if args.manual:
            while next_index < 100:
                resp = input(f"\n{next_index} images capturées. Continuer avec 10 de plus? (O/n): ").strip().lower()
                if resp == 'n':
                    break
                next_index, driver = take_captures(args.center_lat, args.center_lon, args.zoom, min(10, 100 - next_index), args.step, args.outdir, manual=True, start_index=next_index, driver=driver)
            print(f"\nTotal: {next_index} images capturées.")
    finally:
        if driver:
            driver.quit()




if __name__ == '__main__':
    main()
