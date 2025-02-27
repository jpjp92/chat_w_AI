# config/env.py

import os

# 환경 변수 로드
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
DRUG_API_KEY = os.getenv("DRUG_API_KEY")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
NCBI_KEY = os.getenv("NCBI_KEY")
