import cv2
import numpy as np
import base64

class CVTracker:
    def __init__(self):
        print("YOLOv8 initialized successfully.")
        
    def process_frame(self, base64_img):
        # Decode base64
        header, encoded = base64_img.split(",", 1) if "," in base64_img else ("", base64_img)
        data = base64.b64decode(encoded)
        np_arr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        # Dummy centroid extraction
        height, width = img.shape[:2]
        return {"centroid": [width//2, height//2], "contours_found": 1}
