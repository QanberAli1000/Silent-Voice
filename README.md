Silent Voice: Real-Time Sign Language Interpreter

Overview

Silent Voice is a production-ready desktop application that translates static sign language gestures into text and speech in real-time. Built using a Bimanual Architecture, it separates alphabetic characters (Right Hand) and numbers/control gestures (Left Hand) to eliminate class collision.

The system leverages Google MediaPipe for computationally lightweight 3D landmark extraction and a Random Forest Classifier to achieve 100% accuracy at 30 FPS on standard consumer CPU hardware.

Features

Real-Time Translation: Translates static gestures to text instantly.

Multithreaded GUI: Built with PyQt5 for a completely fluid, lag-free user experience.

Hardware Agnostic: Runs entirely on standard laptop CPUs via standard webcams (no GPU or sensor gloves required).

Graceful Degradation: Features automatic offline English fallbacks if the Google Translation/TTS API drops.

Audio Output: Integrated Google Text-to-Speech (gTTS) for vocal communication.

Tech Stack

Application Architecture: PyQt5 (Python)

Computer Vision: OpenCV, Google MediaPipe

Machine Learning: Scikit-Learn (Random Forest)

NLP & Audio: Autocorrect, Deep Translator, gTTS

How to Run

Clone the repository.

Install the required dependencies: pip install -r requirements.txt

Run the main application file (e.g., python main.py or python vision.py).

Note: The models folder contains the pre-trained .pkl files required for inference.