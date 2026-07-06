import os
import threading
import json  # <--- Added for JSON parsing
from autocorrect import Speller                 #This acts as your spell-checker.
from gtts import gTTS                           #Google Text-to-Speech for audio output.
from playsound import playsound                  #To play the generated audio files.
from deep_translator import GoogleTranslator      #For translating the final output into different languages.

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QTextEdit, QFrame, QComboBox)   
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QTimer

# Import your vision thread from the core folder!
from core.vision import VideoThread

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_PATH = os.path.join(BASE_DIR, 'assets', 'svl.png')
DICT_PATH = os.path.join(BASE_DIR, 'assets', 'custom_dict.json') # <--- Added path for custom dictionary

class AITextEdit(QTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursorWidth(15) 

    def keyPressEvent(self, event):
        return 
    
    def mouseReleaseEvent(self, event):
        # Let the normal mouse click happen first
        super().mouseReleaseEvent(event)
        
        # UX MAGIC: If the user highlighted text to copy it, leave it alone.
        # But if they just clicked randomly, snap the cursor back to the end!
        if not self.textCursor().hasSelection():
            cursor = self.textCursor()
            cursor.movePosition(cursor.End)
            self.setTextCursor(cursor)

class SignLanguageApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Silent Voice - AI Gestural Keyboard")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("background-color: #0d1117; color: #c9d1d9;")  # Set a dark background and light text for the whole app
        
        self.is_detecting = False
        self.thread = None
        self.current_word_buffer = ""
        self.completed_text = ""
        self.current_line_english = ""
        
        self.spell = Speller(lang='en')

        fallback_list = ["qanber", "syed", "shah", "ali", "karachi", "sindh", "pakistan", "asif"]
        self.custom_dictionary = []
        
        try:
            if os.path.exists(DICT_PATH):
                with open(DICT_PATH, 'r') as file:
                    data = json.load(file)
                    self.custom_dictionary = data["protected_words"]
                print(f"Loaded {len(self.custom_dictionary)} custom words from JSON.")
            else:
                # 3. If file is missing, use the fallback list
                print("Warning: custom_dict.json not found. Using the hardcoded short list.")
                self.custom_dictionary = fallback_list
                
        except Exception as e:
            # 4. If the JSON is broken/corrupted, also use the fallback list
            print(f"Error reading JSON: {e}. Using the hardcoded short list.")
            self.custom_dictionary = fallback_list
        
        self.lang_map = {
            "English (US)": "en",
            "Urdu (Pakistan)": "ur",
            "Spanish (Spain)": "es",
            "French (France)": "fr",
            "German (Germany)": "de"
        }
        
        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        nav_frame = QFrame(self)
        nav_frame.setFixedWidth(280)
        nav_frame.setStyleSheet("background-color: #161b22; border-right: 2px solid #30363d;")
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(20, 40, 20, 40)

        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setFixedSize(240, 150)
        
        # Load the logo dynamically using the new folder path
        pixmap = QPixmap(LOGO_PATH)
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(240, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(scaled_pixmap)
            self.logo_label.setStyleSheet("border: none;") 
        else:
            self.logo_label.setStyleSheet("border: 2px dashed #30363d; border-radius: 10px;")
            self.logo_label.setText(f"[ LOGO MISSING ]\nPlease check assets folder")
            
        nav_layout.addWidget(self.logo_label)
        nav_layout.addSpacing(20)

        title_label = QLabel("SILENT VOICE")
        title_label.setStyleSheet("color: #00E5FF; font-size: 26px; font-weight: 900; border: none;")
        title_label.setAlignment(Qt.AlignCenter)
        nav_layout.addWidget(title_label)
        
        subtitle = QLabel("AI Gestural Keyboard")
        subtitle.setStyleSheet("color: #8b949e; font-size: 14px; border: none;")
        subtitle.setAlignment(Qt.AlignCenter)
        nav_layout.addWidget(subtitle)

        nav_layout.addSpacing(40)

        combo_label = QLabel("Translation Output:")
        combo_label.setStyleSheet("color: #8b949e; font-size: 12px; font-weight: bold; border: none;")
        nav_layout.addWidget(combo_label)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(list(self.lang_map.keys()))
        self.lang_combo.setStyleSheet("""
            QComboBox { background-color: #0d1117; color: #00E5FF; font-size: 14px; font-weight: bold; border: 2px solid #30363d; border-radius: 8px; padding: 10px; }
            QComboBox::drop-down { border: none; }
        """)
        self.lang_combo.setCursor(Qt.PointingHandCursor)
        self.lang_combo.setFocusPolicy(Qt.NoFocus) # <--- ADD THIS LINE to prevent focus issues with the combo box
        nav_layout.addWidget(self.lang_combo)

        nav_layout.addSpacing(30)

        self.btn_toggle = QPushButton("START CONVERSATION")
        self.btn_toggle.setFixedSize(235, 50)
        self.btn_toggle.setStyleSheet("QPushButton { background-color: #238636; color: white; font-size: 14px; font-weight: bold; border-radius: 8px; } QPushButton:hover { background-color: #2ea043; }")
        self.btn_toggle.setFocusPolicy(Qt.NoFocus) # <--- ADD THIS LINE to prevent focus issues with the button
        self.btn_toggle.clicked.connect(self.toggle_detection)
        nav_layout.addWidget(self.btn_toggle)

        nav_layout.addStretch()

        self.btn_quit = QPushButton("QUIT SYSTEM")
        self.btn_quit.setFixedSize(235, 50)
        self.btn_quit.setStyleSheet("QPushButton { background-color: transparent; color: #da3633; font-size: 14px; font-weight: bold; border: 2px solid #da3633; border-radius: 8px; } QPushButton:hover { background-color: #da3633; color: white; }")
        self.btn_quit.setFocusPolicy(Qt.NoFocus) # <--- ADD THIS LINE to prevent focus issues with the button
        self.btn_quit.clicked.connect(self.close)
        nav_layout.addWidget(self.btn_quit)

        main_layout.addWidget(nav_frame, 0)

        content_frame = QFrame(self)
        content_frame.setStyleSheet("background-color: #0d1117;")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(40, 40, 40, 40)
        content_layout.setSpacing(20)

        top_row_layout = QHBoxLayout()
        top_row_layout.setSpacing(20)

        buffer_frame = QFrame()
        buffer_frame.setStyleSheet("background-color: #161b22; border: 2px solid #30363d; border-radius: 12px;")
        buffer_layout = QVBoxLayout(buffer_frame)
        
        self.buffer_title = QLabel("LIVE WORD BUFFER (ENGLISH)")
        self.buffer_title.setStyleSheet("color: #8b949e; font-size: 14px; font-weight: bold; border: none;")
        buffer_layout.addWidget(self.buffer_title) # Make sure it says self.buffer_title here too!
        
        self.buffer_label = QLabel("")
        self.buffer_label.setAlignment(Qt.AlignCenter)
        self.buffer_label.setStyleSheet("color: #00E5FF; font-size: 50px; font-weight: bold; border: none; letter-spacing: 5px;")
        buffer_layout.addWidget(self.buffer_label, stretch=1) # stretch=1 buffer label takes up all available vertical space and stays centered
        
        top_row_layout.addWidget(buffer_frame, 2) 

        video_frame = QFrame()
        video_frame.setMinimumSize(400, 300) 
        video_frame.setStyleSheet("background-color: black; border: 2px solid #30363d; border-radius: 12px;")
        video_layout = QVBoxLayout(video_frame)
        video_layout.setContentsMargins(0,0,0,0)
        
        self.video_label = QLabel("CAMERA OFFLINE")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("color: #8b949e; font-size: 16px; font-weight: bold; border: none;")
        video_layout.addWidget(self.video_label)
        
        top_row_layout.addWidget(video_frame, 1) 
        content_layout.addLayout(top_row_layout, 1) 

        output_frame = QFrame()
        output_frame.setStyleSheet("background-color: #161b22; border: 2px solid #30363d; border-radius: 12px;")
        output_layout = QVBoxLayout(output_frame)
        
        output_header_layout = QHBoxLayout()
        self.output_title = QLabel("FINAL TRANSLATED OUTPUT")
        self.output_title.setStyleSheet("color: #8b949e; font-size: 14px; font-weight: bold; border: none;")
        output_header_layout.addWidget(self.output_title)
        output_header_layout.addStretch() 
        
        self.btn_copy = QPushButton("🧷")
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setFocusPolicy(Qt.NoFocus)
        self.btn_copy.setToolTip("Copy text to clipboard")
        self.btn_copy.setStyleSheet("QPushButton { background-color: #1f6feb; color: white; font-size: 20px; min-width: 45px; max-width: 45px; min-height: 45px; max-height: 45px; border-radius: 22px; border: none; } QPushButton:hover { background-color: #388bfd; }")
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        output_header_layout.addWidget(self.btn_copy)
        output_layout.addLayout(output_header_layout)

        self.text_box = AITextEdit() 
        self.text_box.setStyleSheet("QTextEdit { background-color: transparent; color: white; font-size: 32px; font-family: Helvetica; border: none; }")
        output_layout.addWidget(self.text_box)

        content_layout.addWidget(output_frame, 1) 
        main_layout.addWidget(content_frame, 1)
        self.text_box.clearFocus()

    def speak_word(self, word, lang_code):
        def speak():
            try:
                tts = gTTS(text=word, lang=lang_code)
                
                # Use the bridge to safely reset the warning on the UI thread
                QTimer.singleShot(0, self.reset_no_internet_warning) 
                
                filename = "temp_voice.mp3"
                tts.save(filename)
                playsound(filename)
                if os.path.exists(filename):
                    os.remove(filename)
            except Exception as e:
                print(f"Audio Error: {e}")
                
                # Use the bridge to safely trigger the warning on the UI thread!
                QTimer.singleShot(0, self.trigger_audio_warning)

        threading.Thread(target=speak, daemon=True).start() # daemon=True means this thread will automatically close when the main app

    def update_text(self, new_char):
        selected_lang = self.lang_combo.currentText()
        target_code = self.lang_map[selected_lang]

        if new_char == "SPACE":
            if self.current_word_buffer:
                raw_word = self.current_word_buffer.lower()
                if raw_word in self.custom_dictionary:
                    corrected_word = raw_word
                else:
                    corrected_word = self.spell(raw_word)
                
                self.current_line_english += corrected_word + " "
                
                if self.current_line_english.strip():
                    if target_code != 'en':
                        try:
                            translated_line = GoogleTranslator(source='en', target=target_code).translate(self.current_line_english.strip())

                            if translated_line:
                                self.reset_no_internet_warning()

                        except:
                            translated_line = self.current_line_english.strip()

                            self.output_title.setText("⚠️ No Internet ⚠️")
                            self.output_title.setStyleSheet("color: #da3633; font-size: 14px; font-weight: bold; border: none;")
                    else:
                        translated_line = self.current_line_english.strip()
                else:
                    translated_line = ""

                full_display = self.completed_text + translated_line.capitalize()
                self.text_box.setPlainText(full_display)
                cursor = self.text_box.textCursor()  # create a cursor object to manipulate the text cursor in the QTextEdit
                cursor.movePosition(cursor.End)      # move the cursor to the end of the text so that new text is always added at the end and the view scrolls down automatically
                self.text_box.setTextCursor(cursor)  # set the manipulated cursor back to the QTextEdit so that it takes effect
                self.current_word_buffer = ""
                self.buffer_label.setText("")
                self.reset_buffer_warning()     # Rest buffer full warning

        elif new_char == "NEW_LINE":
            if self.current_line_english.strip():
                if target_code != 'en':
                    try:
                        translated_line = GoogleTranslator(source='en', target=target_code).translate(self.current_line_english.strip())

                        if translated_line:
                                self.reset_no_internet_warning()

                    except:
                        translated_line = self.current_line_english.strip()

                        self.output_title.setText("⚠️ No Internet ⚠️")
                        self.output_title.setStyleSheet("color: #da3633; font-size: 14px; font-weight: bold; border: none;")
                else:
                    translated_line = self.current_line_english.strip()
                
                self.speak_word(translated_line, target_code)
                self.completed_text += translated_line.capitalize() + "\n"
                self.current_line_english = ""
                self.text_box.setPlainText(self.completed_text)
            else:
                self.completed_text += "\n"
                self.text_box.setPlainText(self.completed_text)

            cursor = self.text_box.textCursor()
            cursor.movePosition(cursor.End)
            self.text_box.setTextCursor(cursor)

        elif new_char == "BACKSPACE":
            if len(self.current_word_buffer) > 0:
                self.current_word_buffer = self.current_word_buffer[:-1]   # Remove the last character from the buffer
                self.buffer_label.setText(self.current_word_buffer)
                self.reset_buffer_warning()     # Rest buffer full warning

        elif new_char == "DEL_WORD":
            if self.current_line_english.strip():
                words = self.current_line_english.strip().split(" ")
                words.pop() 
                self.current_line_english = " ".join(words) + (" " if len(words) > 0 else "")
                
                if self.current_line_english.strip():
                    if target_code != 'en':
                        try:
                            translated_line = GoogleTranslator(source='en', target=target_code).translate(self.current_line_english.strip())

                            if translated_line:
                                self.reset_no_internet_warning()

                        except:
                            translated_line = self.current_line_english.strip()

                            self.output_title.setText("⚠️ No Internet ⚠️")
                            self.output_title.setStyleSheet("color: #da3633; font-size: 14px; font-weight: bold; border: none;")
                    else:
                        translated_line = self.current_line_english.strip()
                else:
                    translated_line = ""

                self.text_box.setPlainText(self.completed_text + translated_line.capitalize())
            
            cursor = self.text_box.textCursor()
            cursor.movePosition(cursor.End)
            self.text_box.setTextCursor(cursor)

        else:
            # self.current_word_buffer += new_char
            # self.buffer_label.setText(self.current_word_buffer)
            # --- THE BUFFER LIMIT FIX ---
            # Only add the new character if the buffer has less than 20 characters
            if len(self.current_word_buffer) < 20:
                self.current_word_buffer += new_char
                self.buffer_label.setText(self.current_word_buffer)
            else:
                # If they hit 20 characters, it ignores new input to protect the UI
                # print("Buffer Limit Reached: Awaiting SPACE or BACKSPACE")
                # If they hit the limit, flash the title red!
                self.buffer_title.setText("⚠️ BUFFER FULL - AWAITING SPACE ⚠️")
                self.buffer_title.setStyleSheet("color: #da3633; font-size: 14px; font-weight: bold; border: none;")
                
                # Automatically reset it back to normal after 2 seconds
                # QTimer.singleShot(2000, self.reset_buffer_warning)

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_box.toPlainText())
        self.btn_copy.setText("✔️")
        self.btn_copy.setStyleSheet("QPushButton { background-color: #238636; color: white; font-size: 20px; min-width: 45px; max-width: 45px; min-height: 45px; max-height: 45px; border-radius: 22px; border: none; }")
        QTimer.singleShot(1500, self.reset_copy_btn)  # Reset the button back to its original state after 1.5 seconds

    def reset_copy_btn(self):
        self.btn_copy.setText("🧷")
        self.btn_copy.setStyleSheet("QPushButton { background-color: #1f6feb; color: white; font-size: 20px; min-width: 45px; max-width: 45px; min-height: 45px; max-height: 45px; border-radius: 22px; border: none; } QPushButton:hover { background-color: #388bfd; }")

    def reset_buffer_warning(self):
        self.buffer_title.setText("LIVE WORD BUFFER (ENGLISH)")
        self.buffer_title.setStyleSheet("color: #8b949e; font-size: 14px; font-weight: bold; border: none;")

    def reset_no_internet_warning(self):
        self.output_title.setText("FINAL TRANSLATED OUTPUT")
        self.output_title.setStyleSheet("color: #8b949e; font-size: 14px; font-weight: bold; border: none;")

    def trigger_audio_warning(self):
        # This will safely run on the Main Thread!
        self.output_title.setText("⚠️ No Internet (Audio Failed) ⚠️")
        self.output_title.setStyleSheet("color: #da3633; font-size: 14px; font-weight: bold; border: none;")

    def toggle_detection(self):
        if not self.is_detecting:
            self.is_detecting = True
            self.btn_toggle.setText("PAUSE SYSTEM")
            self.btn_toggle.setStyleSheet("QPushButton { background-color: #d29922; color: white; font-size: 14px; font-weight: bold; border-radius: 8px; }")
            self.text_box.setFocusPolicy(Qt.StrongFocus)
            self.text_box.setFocus()
            self.current_word_buffer = ""
            self.buffer_label.setText("")
            
            self.thread = VideoThread()
            self.thread.change_pixmap_signal.connect(self.update_image)
            self.thread.new_char_signal.connect(self.update_text)
            self.thread.start()
        else:
            self.is_detecting = False
            self.btn_toggle.setText("RESUME CONVERSATION")
            self.btn_toggle.setStyleSheet("QPushButton { background-color: #238636; color: white; font-size: 14px; font-weight: bold; border-radius: 8px; } QPushButton:hover { background-color: #2ea043; }")
            self.text_box.clearFocus()
            self.text_box.setFocusPolicy(Qt.NoFocus)
            if self.thread:
                self.thread.stop()
            self.video_label.clear()
            self.video_label.setText("CAMERA OFFLINE")

    def update_image(self, qt_image):
        if not self.is_detecting:
            return
        scaled_pixmap = QPixmap.fromImage(qt_image).scaled(self.video_label.width(), self.video_label.height(), Qt.KeepAspectRatio)
        self.video_label.setPixmap(scaled_pixmap)

    def closeEvent(self, event):
        if self.thread:
            self.thread.stop()
        event.accept()  # Let the window close normally