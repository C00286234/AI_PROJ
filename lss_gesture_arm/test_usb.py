import cv2
import time

cap = cv2.VideoCapture(1)
print("Opened:", cap.isOpened())
time.sleep(2)
ret, frame = cap.read()
print("Read success:", ret)
if ret:
    print("Frame shape:", frame.shape)
    cv2.imshow("USB Test", frame)
    cv2.waitKey(3000)
cap.release()
cv2.destroyAllWindows()
