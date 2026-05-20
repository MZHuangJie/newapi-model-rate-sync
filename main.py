import os
import sys
from PySide6.QtWidgets import QApplication
from app.main_window import MainWindow

def main():
    # Fix High DPI scaling issues on modern displays
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    
    # Load stylesheet
    script_dir = os.path.dirname(os.path.abspath(__file__))
    qss_path = os.path.join(script_dir, "app", "styles", "dark.qss")
    
    if os.path.exists(qss_path):
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                qss = f.read()
                app.setStyleSheet(qss)
        except Exception as e:
            print(f"Error loading stylesheet: {e}")
            
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
