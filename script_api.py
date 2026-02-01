import argparse
import math
import time
import requests
from pathlib import Path
from PIL import Image
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


def build_map_url(lat, lon, zoom):
    return f"https://map.openaerialmap.org/#/{lat},{lon},{zoom}"


def meters_to_deg(lat, meters):
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * math.cos(math.radians(lat))
    return meters / m_per_deg_lat, meters / (m_per_deg_lon + 1e-12)


def linear_positions(center_lat, center_lon, step_m, direction="east"):
    dlat, dlng = meters_to_deg(center_lat, step_m)
    lat, lng = center_lat, center_lon
    
    if direction.lower() == "north":
        dlat, dlng = dlat, 0
    elif direction.lower() == "south":
        dlat, dlng = -dlat, 0
    elif direction.lower() == "east":
        dlat, dlng = 0, dlng
    elif direction.lower() == "west":
        dlat, dlng = 0, -dlng
    
    while True:
        yield lat, lng
        lat += dlat
        lng += dlng


def parse_center_from_url(url):
    try:
        if '#/' in url:
            part = url.split('#/')[1].split('?')[0]
            coords = part.split(',')[:3]
            if len(coords) >= 3:
                lon_s, lat_s, zoom_s = coords
                zoom_s = zoom_s.split('/')[0].strip()
                return float(lat_s), float(lon_s), int(float(zoom_s))
    except:
        pass
    return None


def get_tile_coords(lat, lon, zoom):
    """Convertit lat/lon en coordonnées tuile XYZ"""
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def download_image(lat, lon, zoom, output_path, index):
    try:
        center_x, center_y = get_tile_coords(lat, lon, zoom)
        print(f"    Coords: lat={lat:.6f}, lon={lon:.6f} → Tuile z={zoom}, x={center_x}, y={center_y}")
        
        grid_size =4 # 5x5 = 1280x1280px (plus proche que 4x4)
        half = grid_size // 2
        canvas_size = grid_size * 256  # 1280 pour 5x5, 2048 pour 8x8, etc.
        combined = Image.new('RGB', (canvas_size, canvas_size), 'white')
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        for dx in range(-half, half + 1):
            for dy in range(-half, half + 1):
                tile_x, tile_y = center_x + dx, center_y + dy
                url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{zoom}/{tile_y}/{tile_x}"
                
                try:
                    response = requests.get(url, timeout=10, headers=headers)
                    response.raise_for_status()
                    tile_img = Image.open(BytesIO(response.content))
                    x_pos = (dx + half) * 256
                    y_pos = (dy + half) * 256
                    combined.paste(tile_img, (x_pos, y_pos))
                except Exception as e:
                    print(f"      ⚠ Tuile ({tile_x},{tile_y}): {e}")
        
        fname = output_path / f"cap_{index:03d}_{lat:.6f}_{lon:.6f}.png"
        combined.save(str(fname))
        print(f"  ✓ {fname.name} ({canvas_size}x{canvas_size} pixels)")
        return fname
    except Exception as e:
        print(f"  ✗ Erreur: {e}")
        return None


def select_point_on_map(center_lat, center_lon, zoom):
    """Lance Selenium pour que l'utilisateur choisisse le point de départ (retourne aussi le driver)"""
    
    print("  Sélection du point de départ")
    
    print("\n Ouverture de la carte...")
    
    opts = Options()
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option('useAutomationExtension', False)
    opts.add_argument("--start-maximized")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(60)
    
    url = build_map_url(center_lat, center_lon, zoom)
    driver.get(url)
    
    print(" ⏳ Attente du chargement (5-10 secondes)...")
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "leaflet-container"))
        )
    except:
        print(" ⚠ Timeout, continuons...")
    
    time.sleep(2.0)
    
    print("\n ✓ Carte chargée!")
    print("\n Sélectionnez votre point de départ en cliquant sur la carte...")
    print(" Vous pouvez zoomer/déplacer la carte comme vous le souhaitez")
    print("\n Appuyez sur Entrée quand vous avez choisi le point de départ...\n")
    input(" ➜ ")
    
    # Lire l'URL finale
    current_url = driver.current_url
    parsed = parse_center_from_url(current_url)
    
    if parsed:
        lat, lon, zoom_final = parsed
        print(f"\n ✓ Point sélectionné: lat={lat:.6f}, lon={lon:.6f}, zoom={zoom_final}")
        return lat, lon, zoom_final, driver  # Retourner aussi le driver
    else:
        print("\n ⚠ Impossible de lire l'URL, utilisation des coordonnées initiales")
        return center_lat, center_lon, zoom, driver


def take_captures_api(center_lat, center_lon, zoom, captures, step_m, outdir, direction="east", start_index=0):
    """Télécharge des images satellite via l'API"""
    out = Path(outdir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    print(f"\nEnregistrement dans: {out}")
    print(f"Coordonnées: lat={center_lat:.6f}, lon={center_lon:.6f}, zoom={zoom}")
    print(f"Direction: {direction}, Pas: {step_m}m\n")
    
    try:
        gen = linear_positions(center_lat, center_lon, step_m, direction)
        i = start_index
        count = 0
        
        for lat, lon in gen:
            if count >= captures:
                break
            
            print(f"Image {count+1}/{captures}:")
            download_image(lat, lon, zoom, out, i+1)
            
            i += 1
            count += 1
            time.sleep(2.0)  # Respecter la politique OSM: délai de 2 secondes minimum
    
    except KeyboardInterrupt:
        print(f"\nInterruption utilisateur. {i} images téléchargées.")
    
    return i


def main():
    """Gère les arguments CLI"""
    p = argparse.ArgumentParser(description="Télécharge des images satellite via OpenAerialMap")
    p.add_argument("--captures", type=int, default=8, help="Nombre d'images")
    p.add_argument("--step", type=float, default=100.0, help="Pas entre les images (m)")
    p.add_argument("--center-lat", type=float, default=9.840485751628874)
    p.add_argument("--center-lon", type=float, default=37.24850443221159)
    p.add_argument("--zoom", type=int, default=24)
    p.add_argument("--outdir", type=str, default="captures")
    p.add_argument("--start-index", type=int, default=0)
    p.add_argument("--direction", type=str, default="east", 
                   choices=["east", "west", "north", "south"])
    
    args = p.parse_args()
    
    # Ouvrir la carte et laisser l'utilisateur sélectionner le point
    center_lat, center_lon, zoom, driver = select_point_on_map(
        args.center_lat, args.center_lon, args.zoom
    )
    
    print(f"\n ✓ Coordonnées de départ confirmées: lat={center_lat:.6f}, lon={center_lon:.6f}, zoom={zoom}")
    
    # Demander la direction
    print("\n Choisissez la direction:")
    print("  1. Est (→)")
    print("  2. Ouest (←)")
    print("  3. Nord (↑)")
    print("  4. Sud (↓)")
    dir_choice = input(" Direction (1-4): ").strip()
    direction_map = {"1": "east", "2": "west", "3": "north", "4": "south"}
    direction = direction_map.get(dir_choice, "east")
    
    # Boucle pour télécharger par batch de 10 jusqu'à 100
    print(f"\n ⏳ Téléchargement de {args.captures} images...")
    next_idx = take_captures_api(
        center_lat, center_lon, zoom,
        args.captures, args.step, args.outdir,
        direction=direction, start_index=args.start_index
    )
    
    # Demander si continuer (LA CARTE RESTE OUVERTE)
    while next_idx < 100:
        resp = input(f"\n{next_idx} images. Continuer? (o/n): ").strip().lower()
        if resp == 'n':
            break
        
        # Charger une nouvelle position sur la MÊME carte (sans fermer)
        print("\n Sélectionnez un nouveau point de départ sur la carte...")
        print(" Appuyez sur Entrée quand vous avez choisi le point de départ...\n")
        input(" ➜ ")
        
        # Lire l'URL finale
        current_url = driver.current_url
        parsed = parse_center_from_url(current_url)
        
        if parsed:
            center_lat, center_lon, zoom = parsed
            print(f"\n ✓ Nouveau point: lat={center_lat:.6f}, lon={center_lon:.6f}, zoom={zoom}")
        else:
            print("\n ⚠ Impossible de lire la nouvelle position")
        
        # Demander la direction
        print("\n Choisissez la direction:")
        print("  1. Est (→)")
        print("  2. Ouest (←)")
        print("  3. Nord (↑)")
        print("  4. Sud (↓)")
        dir_choice = input(" Direction (1-4): ").strip()
        direction = direction_map.get(dir_choice, "east")
        
        # Télécharger 10 de plus
        next_idx = take_captures_api(
            center_lat, center_lon, zoom,
            min(8, 100 - next_idx),
            args.step, args.outdir,
            direction=direction, start_index=next_idx
        )
    
    print(f"\n✓ Total: {next_idx} images téléchargées")


if __name__ == '__main__':
    main()
