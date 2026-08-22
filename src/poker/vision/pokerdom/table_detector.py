import cv2
import numpy as np

class TableDetector:
    def __init__(self):
        # HSV range for poker table green cloth
        self.lower_green = np.array([40, 40, 40])
        self.upper_green = np.array([80, 255, 255])

    def find_table(self, image):
        """
        Finds the largest green contour and returns its bounding box (x, y, w, h).
        Returns None if no suitable table is found.
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_green, self.upper_green)

        # Morphological operations to clean up the mask
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        # Get the largest contour
        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)

        # Heuristic: the table should be a significant portion of the image
        img_area = image.shape[0] * image.shape[1]
        if area < img_area * 0.1: # At least 10% of the screen
            return None

        return cv2.boundingRect(largest_contour)

    def get_absolute_roi(self, table_bbox, norm_roi):
        """
        Converts a normalized ROI (0.0 to 1.0) into absolute pixel coordinates based on the table bbox.
        """
        tx, ty, tw, th = table_bbox
        nx, ny, nw, nh = norm_roi

        x = int(tx + nx * tw)
        y = int(ty + ny * th)
        w = int(nw * tw)
        h = int(nh * th)

        return (x, y, w, h)
