#!/bin/bash
# Development run script with auto-login

# Activate virtual environment
source venv/bin/activate

# Set auto-login environment variable
export DEV_AUTO_LOGIN=true

# Run Streamlit
streamlit run streamlit_app.py