from ultralytics import YOLO
import cv2
import os
from pathlib import Path


def main():
    """
    Traite toutes les images du dossier 'captures' avec YOLO
    """
    # Charger le modèle
    print("Chargement du modèle YOLOv8...")
    model = YOLO("yolov8n-seg.pt")
    
    captures_folder = "captures"
    if not os.path.exists(captures_folder):
        print(f"Erreur: Le dossier '{captures_folder}' n'existe pas!")
        return
    
    # Lister les images
    image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp')
    image_files = [f for f in os.listdir(captures_folder) 
                   if f.lower().endswith(image_extensions)]
    
    if not image_files:
        print(f"Aucune image trouvée dans '{captures_folder}'")
        return
    
    print(f"\n{'='*60}")
    print(f"Traitement de {len(image_files)} image(s)")
    print(f"{'='*60}\n")
    
    os.makedirs("results", exist_ok=True)
    
    # Boucler sur les images
    for idx, image_file in enumerate(image_files, 1):
        image_path = os.path.join(captures_folder, image_file)
        print(f"[{idx}/{len(image_files)}] Traitement: {image_file}")
        
        # Prédiction
        results = model.predict(source=image_path, conf=0.5, device=0, visualize=False)
        
        # Charger l'image
        image = cv2.imread(image_path)
        
        for result in results:
            boxes = result.boxes
            masks = result.masks
            
            if boxes is not None:
                print(f"  Détections: {len(boxes)}")
                for i, box in enumerate(boxes):
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = box.conf[0].cpu().numpy()
                    class_id = int(box.cls[0].cpu().numpy())
                    class_name = result.names[class_id]
                    
                    print(f"    {i+1}. {class_name} ({confidence:.2f})")
                    cv2.rectangle(image, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                    label = f"{class_name}: {confidence:.2f}"
                    cv2.putText(image, label, (int(x1), int(y1) - 10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            if masks is not None:
                for mask in masks:
                    mask_array = mask.cpu().numpy()
                    colored_mask = image.copy()
                    colored_mask[mask_array > 0.5] = [255, 0, 0]
                    image = cv2.addWeighted(image, 0.7, colored_mask, 0.3, 0)
        
        # Sauvegarder
        filename = Path(image_path).stem
        output_path = os.path.join("results", f"{filename}_result.jpg")
        cv2.imwrite(output_path, image)
    
    print(f"\n{'='*60}")
    print(f"Traitement terminé! Résultats dans 'results/'")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
