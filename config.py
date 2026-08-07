import os
from datetime import timedelta
from dotenv import load_dotenv

# ✅ Load .env file FIRST
load_dotenv()

class Config:
    SECRET_KEY = 'allison-electronics-secret-2026'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    IS_VERCEL = 'VERCEL' in os.environ or 'NOW' in os.environ
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

    if IS_VERCEL:
        UPLOAD_FOLDER = '/tmp/static/uploads'
        STATIC_FOLDER = '/tmp/static'
    else:
        UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'static', 'uploads')
        STATIC_FOLDER = os.path.join(PROJECT_ROOT, 'static')

    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    # ===== SUPABASE CONFIGURATION =====
    SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://hzqrdwerkgfmfaufabjr.supabase.co')
    
    # ✅ FIX: Remove the hardcoded fallback key
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
    
    # ✅ Debug: Print if key is loaded
    if SUPABASE_KEY:
        print(f"🔑 Supabase key loaded: {SUPABASE_KEY[:20]}...")
    else:
        print("❌ WARNING: SUPABASE_KEY not found in environment!")
    
    SUPABASE_HEADERS = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }

    DATA_FILE = os.path.join(PROJECT_ROOT, 'offline_data.json')
