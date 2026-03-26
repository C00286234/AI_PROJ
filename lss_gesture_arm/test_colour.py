import cv2
import config
from vision import ColourDetector

detector = ColourDetector()
cap = cv2.VideoCapture(config.CAMERA_VISION_INDEX)

print("Point the USB webcam at a RED object. Press Q to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    result = detector.detect_red(frame)
    display = detector.draw_detection(frame, result)

    status = "RED FOUND" if result.found else "No red detected"
    zone = result.horizontal_zone if result.found else ""
    colour = (0, 255, 0) if result.found else (0, 0, 200)
    cv2.putText(display, f"{status}  {zone}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, colour, 2)

    cv2.imshow("Colour Detection Test  |  Press Q to quit", display)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
