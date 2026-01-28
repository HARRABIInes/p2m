from pathlib import Path
from PIL import Image

# ====== RÉGLAGES (à affiner une fois) ======
LEFT_CUT   = 520   # on coupe PLUS du panneau gauche
RIGHT_CUT  = 80    # on coupe un peu à droite (UI zoom)
TOP_CUT    = 80    # barre haute
BOTTOM_CUT = 200  # barre basse

TARGET_SIZE = (1080, 1080) 

INPUT_DIR = "captures"
OUTPUT_DIR = "captures_zoomed"


def main():
    out = Path(OUTPUT_DIR)
    out.mkdir(exist_ok=True)

    for img_path in Path(INPUT_DIR).glob("*.png"):
        img = Image.open(img_path)
        w, h = img.size

        crop_box = (
            LEFT_CUT,
            TOP_CUT,
            w - RIGHT_CUT,
            h - BOTTOM_CUT
        )

        cropped = img.crop(crop_box)

        if TARGET_SIZE:
            cropped = cropped.resize(TARGET_SIZE, Image.BILINEAR)

        cropped.save(out / img_path.name)
        print(f"✔ {img_path.name}")


if __name__ == "__main__":
    main()
