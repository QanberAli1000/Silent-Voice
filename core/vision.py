import os
import cv2
import numpy as np
import mediapipe as mp
import pickle
from PyQt5.QtGui import QImage
from PyQt5.QtCore import QThread, pyqtSignal

# --- DYNAMIC FILE PATHS ---
# This ensures Python always finds your models no matter where you run the script from
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALPHABET_MODEL_PATH = os.path.join(BASE_DIR, 'models', 'alphabets_rf_model_normalized.pkl')
NUMBERS_MODEL_PATH = os.path.join(BASE_DIR, 'models', 'numbers_rf_model_normalized.pkl')

print("Loading Alphabet Model (Right Hand)...")
with open(ALPHABET_MODEL_PATH, 'rb') as f:
    alphabet_model = pickle.load(f)

print("Loading Numbers Model (Left Hand)...")
with open(NUMBERS_MODEL_PATH, 'rb') as f: 
    numbers_model = pickle.load(f)

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)
    new_char_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._run_flag = True
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.hands = self.mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.7)
        
        self.recent_predictions = []      
        self.FRAMES_TO_SMOOTH = 10        
        self.cooldown_frames = 0  

    def run(self):
        cap = cv2.VideoCapture(0)
        while self._run_flag:
            ret, frame = cap.read()
            if ret:
                frame = cv2.flip(frame, 1) 
                frame = cv2.resize(frame, (640, 480))
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                results = self.hands.process(rgb_frame)
                current_stable_char = ""
                
                if self.cooldown_frames > 0:
                    self.cooldown_frames -= 1
                
                if results.multi_hand_landmarks and results.multi_handedness:
                    for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                        hand_label = results.multi_handedness[idx].classification[0].label
                        self.mp_drawing.draw_landmarks(rgb_frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                        
                        raw_row = []
                        for landmark in hand_landmarks.landmark:
                            raw_row.extend([landmark.x, landmark.y, landmark.z])
                            
                        wrist_x, wrist_y, wrist_z = raw_row[0], raw_row[1], raw_row[2]
                        shifted_row = []
                        for i in range(0, len(raw_row), 3):
                            shifted_row.append(raw_row[i] - wrist_x)
                            shifted_row.append(raw_row[i+1] - wrist_y)
                            shifted_row.append(raw_row[i+2] - wrist_z)
                            
                        max_val = max(list(map(abs, shifted_row)))
                        if max_val == 0: max_val = 1
                        normalized_row = [val / max_val for val in shifted_row]
                        
                        X_live = np.array(normalized_row).reshape(1, -1)
                        lm = hand_landmarks.landmark
                        
                        if hand_label == "Right":
                            predicted_char = str(alphabet_model.predict(X_live)[0])
                            
                            tips_up = all(lm[tip].y < lm[pip].y for tip, pip in zip([8, 12, 16, 20], [6, 10, 14, 18]))
                            thumb_out = abs(lm[4].x - lm[0].x) > 0.15
                            
                            index_closed = lm[8].y > lm[6].y
                            middle_closed = lm[12].y > lm[10].y
                            ring_closed = lm[16].y > lm[14].y
                            pinky_closed = lm[20].y > lm[18].y
                            
                            thumb_left = lm[4].x < lm[3].x < lm[2].x
                            thumb_far_from_index = abs(lm[4].x - lm[8].x) > 0.1 
                            
                            if tips_up and thumb_out:
                                predicted_char = "SPACE"
                            elif thumb_left and thumb_far_from_index and index_closed and middle_closed and ring_closed and pinky_closed:
                                predicted_char = "NEW_LINE"
                                
                        elif hand_label == "Left":
                            predicted_char = str(numbers_model.predict(X_live)[0])
                            
                            index_up = lm[8].y < lm[6].y
                            middle_up = lm[12].y < lm[10].y
                            ring_up = lm[16].y < lm[14].y
                            pinky_up = lm[20].y < lm[18].y
                            left_thumb_out = abs(lm[4].x - lm[0].x) > 0.15
                            
                            if index_up and pinky_up and not middle_up and not ring_up and not left_thumb_out:
                                predicted_char = "BACKSPACE"
                            elif left_thumb_out and index_up and pinky_up and not middle_up and not ring_up:
                                predicted_char = "DEL_WORD"
                        else:
                            predicted_char = ""
                        
                        if self.cooldown_frames == 0:
                            self.recent_predictions.append(predicted_char)
                            if len(self.recent_predictions) > self.FRAMES_TO_SMOOTH:
                                self.recent_predictions.pop(0)
                            
                            if self.recent_predictions.count(predicted_char) == self.FRAMES_TO_SMOOTH:
                                current_stable_char = predicted_char
                else:
                    self.recent_predictions = []
                    
                if current_stable_char:
                    self.new_char_signal.emit(current_stable_char) 
                    self.cooldown_frames = 20
                    self.recent_predictions = [] 

                if self.cooldown_frames > 0:
                    cv2.putText(rgb_frame, "WAIT...", (450, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 3)
                if results.multi_handedness:
                    current_hand = results.multi_handedness[0].classification[0].label
                    cv2.putText(rgb_frame, f"Detected: {current_hand} Hand", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)

                h, w, ch = rgb_frame.shape    # h = 480 , w = 640, ch = 3
                bytes_per_line = ch * w         # 3 * 640 = 1920  no of bytes in one row of the image
                qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)  # Convert the RGB frame to a QImage for display in the PyQt GUI
                self.change_pixmap_signal.emit(qt_image)

        cap.release()  # Release the camera when the thread is stopped
        self.hands.close()   # Clean up Mediapipe resources when the thread is stopped so that they dont keep filling up memory

    def stop(self):
        self._run_flag = False