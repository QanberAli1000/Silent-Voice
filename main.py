import sys
import mediapipe as mp 
from PyQt5.QtWidgets import QApplication
from gui.app_window import SignLanguageApp

if __name__ == "__main__":
    
    app = QApplication(sys.argv)
    window = SignLanguageApp()
    window.showMaximized()
    sys.exit(app.exec_())