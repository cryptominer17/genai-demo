#!/bin/bash
set -e
echo "Installing dependencies..."
pip install -r requirements.txt -q
echo ""
echo "Starting GHCR Deploy UI..."
streamlit run deploy_ui.py
