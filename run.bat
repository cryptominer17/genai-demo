@echo off
echo Installing dependencies...
pip install -r requirements.txt --quiet
echo.
echo Starting GHCR Deploy UI...
streamlit run deploy_ui.py
pause
