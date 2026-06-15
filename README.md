Hand Gesture System — GUI Update
Overview

This update introduces a GUI layer and a new entry point while preserving the existing data collection engine. The system now runs through a structured application flow instead of terminal-only execution.

Project Changes
New Files
src/main.py
Entry point. Orchestrates GUI → camera → recording pipeline.
src/gui.py
CustomTkinter-based configuration window.
Modified Files
src/collect_data.py
Removed terminal-only execution functions. Core engine logic remains unchanged.

requirements.txt
Added:

customtkinter>=5.2.0
Project Structure
src/
 ├── main.py
 ├── gui.py
 ├── collect_data.py
requirements.txt
Setup Instructions
1. Activate Virtual Environment

Windows:

.venv\Scripts\activate.bat

or (works in most setups without .bat):

.venv\Scripts\activate
2. Install Dependencies
pip install -r requirements.txt
3. Run Application
python src/main.py
Notes
GUI handles configuration before execution starts.
Data collection engine remains unchanged.
Terminal entry points were intentionally removed to enforce structured flow.
