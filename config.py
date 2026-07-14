import os
from dotenv import load_dotenv

load_dotenv(override=True)

# If running on Streamlit Cloud, load secrets into environment
# so existing code (email_sender, etc.) can access them via os.getenv
try:
    import streamlit as st
    for key in st.secrets:
        if key not in os.environ:
            os.environ[key] = str(st.secrets[key])
except (ImportError, RuntimeError):
    pass  # Not in Streamlit context, rely on .env / env vars


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    CERTIFICATE_FOLDER = os.getenv("CERTIFICATE_FOLDER", "generated_certificates")

    # Mail settings - Gmail SMTP with App Password
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "rg05.koickal@gmail.com")
