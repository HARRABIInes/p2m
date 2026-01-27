import argparse
import math
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


def build_map_url(lat, lon, zoom):
    """Construit l'URL OpenAerialMap avec lat, lon, zoom"""
    return f"https://map.openaerialmap.org/#/{lat},{lon},{zoom}"


def meters_to_deg(lat, meters):
    """Convertit une distance en mètres en degrés lat/lon"""
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * math.cos(math.radians(lat))
    return meters / m_per_deg_lat, meters / (m_per_deg_lon + 1e-12)


def linear_positions(center_lat, center_lon, step_m, direction="east"):
    """Génère positions selon direction: east, west, north, south"""
    dlat, dlng = meters_to_deg(center_lat, step_m)
    lat, lng = center_lat, center_lon
    
    # Définir les déltas selon la direction
    if direction.lower() == "north":
        dlat, dlng = 0, dlng
    elif direction.lower() == "south":
        dlat, dlng = 0, -dlng
    elif direction.lower() == "east":
        dlat, dlng = dlat, 0
    elif direction.lower() == "west":
        dlat, dlng = -dlat, 0
    
    while True:
        yield lat, lng
        lat += dlat
        lng += dlng


def parse_center_from_url(url):
    """Extrait lat, lon, zoom de l'URL OpenAerialMap"""
    try:
        if '#/' in url:
            part = url.split('#/')[1].split('?')[0]
            coords = part.split(',')[:3]
            if len(coords) >= 3:
                lat_s, lon_s, zoom_s = coords
                zoom_s = zoom_s.split('/')[0].strip()
                return float(lat_s), float(lon_s), int(float(zoom_s))
    except:
        pass
    return None


def take_captures(center_lat, center_lon, zoom, captures, step_m, outdir, direction="east", manual=False, start_index=0, driver=None):
    """Lance Selenium et capture des screenshots de la carte en se déplaçant"""
    out = Path(outdir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    print(f"Enregistrement dans: {out}")

    close_driver = False
    if driver is None:
        close_driver = True
        opts = Options()
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option('useAutomationExtension', False)
        if manual:
            opts.add_argument("--start-maximized")
        else:
            opts.add_argument("--headless=new")
            opts.add_argument("--window-size=1200,1200")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(60)

    if manual:
        try:
            driver.get(build_map_url(center_lat, center_lon, zoom))
        except Exception as e:
            print(f" La carte met du temps à charger (timeout réseau acceptable)")
        
        print(" Sélectionnez votre point de départ sur la carte...")
        print("  Appuyez sur Entrée quand vous avez terminé...\n")
        input("Appuyez sur Entrée pour lire les coordonnées: ")
        
        # Lire l'URL du navigateur
        current_url = driver.current_url
        print(f"URL détectée: {current_url[:80]}...")
        
        parsed = parse_center_from_url(current_url)
        if parsed:
            center_lat, center_lon, zoom = parsed
            print(f"✅ Coordonnées détectées: lat={center_lat:.6f}, lon={center_lon:.6f}, zoom={zoom}\n")
        else:
            print("⚠️  Impossible de parser l'URL, utilisation des coordonnées par défaut")
        
        # Demander la direction
        print("\n🧭 Choisissez la direction:")
        print("  1. Nord (↑)")
        print("  2. Sud (↓)")
        print("  3. est (→)")
        print("  4. ouest (←)")
        dir_choice = input("Direction (1-4): ").strip()
        
        direction_map = {"1": "east", "2": "west", "3": "north", "4": "south"}
        direction = direction_map.get(dir_choice, "east")
        print(f" Direction: {direction}\n")

    try:
        gen = linear_positions(center_lat, center_lon, step_m, direction)
        i, count = start_index, 0
        for lat, lon in gen:
            if count >= captures:
                break
            url = build_map_url(lat, lon, zoom)
            try:
                driver.get(url)
            except Exception as e:
                # Ignorer les timeouts de chargement - la page peut être suffisante
                print(f"Chargement partiel (timeout réseau ok): {e}")
                time.sleep(1.0)
            time.sleep(3.0)
            fname = out / f"cap_{i+1:03d}_{lat:.6f}_{lon:.6f}.png"
            driver.save_screenshot(str(fname))
            print(f"Saved {fname.name}")
            i += 1
            count += 1
    finally:
        if close_driver and not manual:
            driver.quit()
    
    return i, driver if not (close_driver and not manual) else None


def main():
    """Gère les arguments CLI et lance les captures (--manual pour mode interactif)"""
    p = argparse.ArgumentParser()
    p.add_argument("--captures", type=int, default=10)
    p.add_argument("--step", type=float, default=30.0)
    p.add_argument("--center-lat", type=float, default=9.840485751628874)
    p.add_argument("--center-lon", type=float, default=37.24850443221159)
    p.add_argument("--zoom", type=int, default=18)
    p.add_argument("--outdir", type=str, default="captures")
    p.add_argument("--manual", action="store_true")
    p.add_argument("--start-index", type=int, default=0)
    p.add_argument("--direction", type=str, default="east", choices=["east", "west", "north", "south"])
    args = p.parse_args()

    driver = None
    try:
        next_idx, driver = take_captures(args.center_lat, args.center_lon, args.zoom, args.captures, 
                                         args.step, args.outdir, direction=args.direction, manual=args.manual, start_index=args.start_index, driver=driver)
        
        if args.manual:
            while next_idx < 100:
                resp = input(f"\n{next_idx} images. Continuer? (o/n): ").strip().lower()
                if resp == 'n':
                    break
                next_idx, driver = take_captures(args.center_lat, args.center_lon, args.zoom, min(10, 100 - next_idx),
                                                 args.step, args.outdir, direction=args.direction, manual=True, start_index=next_idx, driver=driver)
            print(f"\nTotal: {next_idx} images.")
    finally:
        if driver:
            driver.quit()


if __name__ == '__main__':
    main()
