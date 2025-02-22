import streamlit as st
import time
import uuid
from supabase import create_client
import os
from datetime import datetime, timedelta
import pytz
import logging
import requests
from bs4 import BeautifulSoup
import pandas as pd
from googlesearch import search
from g4f.client import Client
from timezonefinder import TimezoneFinder
import re
import json
import urllib.request
import urllib.parse
from langdetect import detect
from urllib.parse import quote
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from functools import lru_cache
from typing import Dict, Any

# 캐시 클래스 정의
class MemoryCache:
    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.expiry: Dict[str, float] = {}
    
    def get(self, key: str) -> Any:
        if key in self.cache:
            if time.time() < self.expiry[key]:
                return self.cache[key]
            else:
                del self.cache[key]
                del self.expiry[key]
        return None
    
    def setex(self, key: str, ttl: int, value: Any):
        self.cache[key] = value
        self.expiry[key] = time.time() + ttl

# WeatherAPI 클래스 정의
class WeatherAPI:
    def __init__(self, cache_ttl=600):
        self.cache = MemoryCache()
        self.cache_ttl = cache_ttl

    def get_city_weather(self, city_name):
        cache_key = f"weather:{city_name}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            logger.info(f"Cache hit for {cache_key}")
            return cached_data
        
        city_info = get_city_info(city_name)
        if not city_info:
            return f"'{city_name}'의 날씨 정보를 가져올 수 없습니다. ❌\n\n찾고 싶은 도시명을 말씀해 주세요. 예: '서울 날씨 알려줘'"
        
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {'lat': city_info["lat"], 'lon': city_info["lon"], 'appid': WEATHER_API_KEY, 'units': 'metric', 'lang': 'kr'}
        session = requests.Session()
        retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        try:
            response = session.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            weather_emojis = {'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Snow': '❄️', 'Thunderstorm': '⛈️', 'Drizzle': '🌦️', 'Mist': '🌫️'}
            weather_emoji = weather_emojis.get(data['weather'][0]['main'], '🌤️')
            display_name = f"{data['name']}, {data['sys']['country']}"
            result = (
                f"현재 {display_name} 날씨 정보 {weather_emoji}\n\n"
                f"날씨: {data['weather'][0]['description']}\n"
                f"현재 온도: {data['main']['temp']}°C 🌡️\n"
                f"체감 온도: {data['main']['feels_like']}°C 🤔\n"
                f"최저 온도: {data['main']['temp_min']}°C ⬇️\n"
                f"최고 온도: {data['main']['temp_max']}°C ⬆️\n"
                f"습도: {data['main']['humidity']}% 💧\n"
                f"풍속: {data['wind']['speed']}m/s 🌪️"
            )
            self.cache.setex(cache_key, self.cache_ttl, result)
            logger.info(f"Cache set for {cache_key}")
            return result
        except Exception as e:
            logger.error(f"날씨 처리 오류: {str(e)}")
            return f"'{city_name}'의 날씨 정보를 가져올 수 없습니다. ❌\n\n찾고 싶은 도시명을 말씀해 주세요."

    def get_forecast_by_day(self, city_name, days_from_today=1):
        cache_key = f"forecast:{city_name}:{days_from_today}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            logger.info(f"Cache hit for {cache_key}")
            return cached_data
        
        city_info = get_city_info(city_name)
        if not city_info:
            return f"'{city_name}'의 날씨 예보를 가져올 수 없습니다. ❌\n\n찾고 싶은 도시명을 말씀해 주세요."
        
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            'lat': city_info["lat"],
            'lon': city_info["lon"],
            'appid': WEATHER_API_KEY,
            'units': 'metric',
            'lang': 'kr'
        }
        session = requests.Session()
        retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        
        try:
            response = session.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            target_date = (datetime.now() + timedelta(days=days_from_today)).strftime('%Y-%m-%d')
            forecast_text = f"{city_info['name']}의 {target_date} 날씨 예보 🌤️\n\n"
            weather_emojis = {'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Snow': '❄️', 'Thunderstorm': '⛈️', 'Drizzle': '🌦️', 'Mist': '🌫️'}
            
            found = False
            for forecast in data['list']:
                dt = datetime.fromtimestamp(forecast['dt'])
                date_only = dt.strftime('%Y-%m-%d')
                if date_only == target_date:
                    found = True
                    time_only = dt.strftime('%H:%M')
                    weather_emoji = weather_emojis.get(forecast['weather'][0]['main'], '🌤️')
                    forecast_text += (
                        f"⏰ {time_only}  {forecast['weather'][0]['description']} {weather_emoji}  "
                        f"{forecast['main']['temp']}°C  💧{forecast['main']['humidity']}%  🌬️{forecast['wind']['speed']}m/s\n\n"
                    )
            
            if not found:
                result = f"'{city_name}'의 {target_date} 날씨 예보를 찾을 수 없습니다. ❌"
            else:
                result = forecast_text.strip()
            
            self.cache.setex(cache_key, self.cache_ttl, result)
            logger.info(f"Cache set for {cache_key}")
            return result
        
        except Exception as e:
            logger.error(f"날씨 예보 처리 오류: {str(e)}")
            return f"'{city_name}'의 날씨 예보를 가져올 수 없습니다. ❌"

    def get_weekly_forecast(self, city_name):
        cache_key = f"weekly_forecast:{city_name}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            logger.info(f"Cache hit for {cache_key}")
            return cached_data
        
        city_info = get_city_info(city_name)
        if not city_info:
            return f"'{city_name}'의 주간 예보를 가져올 수 없습니다. ❌\n\n찾고 싶은 도시명을 말씀해 주세요."
        
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            'lat': city_info["lat"],
            'lon': city_info["lon"],
            'appid': WEATHER_API_KEY,
            'units': 'metric',
            'lang': 'kr'
        }
        session = requests.Session()
        retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        
        try:
            response = session.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            today = datetime.now().date()
            week_end = today + timedelta(days=6)
            daily_forecast = {}
            weekdays_kr = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
            today_weekday = today.weekday()
            
            for forecast in data['list']:
                dt = datetime.fromtimestamp(forecast['dt']).date()
                if today <= dt <= week_end:
                    dt_str = dt.strftime('%Y-%m-%d')
                    if dt_str not in daily_forecast:
                        weekday_idx = (today_weekday + (dt - today).days) % 7
                        daily_forecast[dt_str] = {
                            'weekday': weekdays_kr[weekday_idx],
                            'temp_min': forecast['main']['temp_min'],
                            'temp_max': forecast['main']['temp_max'],
                            'weather': forecast['weather'][0]['description']
                        }
                    else:
                        daily_forecast[dt_str]['temp_min'] = min(daily_forecast[dt_str]['temp_min'], forecast['main']['temp_min'])
                        daily_forecast[dt_str]['temp_max'] = max(daily_forecast[dt_str]['temp_max'], forecast['main']['temp_max'])
            
            today_str = today.strftime('%Y-%m-%d')
            today_weekday_str = weekdays_kr[today_weekday]
            forecast_text = f"{today_str}({today_weekday_str}) 기준 {city_info['name']}의 주간 날씨 예보 🌤️\n\n"
            weather_emojis = {'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Snow': '❄️', 'Thunderstorm': '⛈️', 'Drizzle': '🌦️', 'Mist': '🌫️'}
            
            for date, info in daily_forecast.items():
                weather_emoji = weather_emojis.get(info['weather'].split()[0], '🌤️')
                forecast_text += (
                    f"{info['weekday']}: {info['weather']} {weather_emoji}  "
                    f"최저 {info['temp_min']}°C  최고 {info['temp_max']}°C\n\n"
                )
            
            self.cache.setex(cache_key, self.cache_ttl, forecast_text)
            logger.info(f"Cache set for {cache_key}")
            return forecast_text
        
        except Exception as e:
            logger.error(f"주간 예보 처리 오류: {str(e)}")
            return f"'{city_name}'의 주간 예보를 가져올 수 없습니다. ❌"

# Supabase 및 API 설정
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
DRUG_API_KEY = os.getenv("DRUG_API_KEY")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")  

# Supabase 및 GPT 클라이언트 초기화
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = Client()

# WeatherAPI 인스턴스 생성
weather_api = WeatherAPI(cache_ttl=600)

# Naver API 요청 카운터
naver_request_count = 0
NAVER_DAILY_LIMIT = 25000

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HybridChat")

# 페이지 설정
st.set_page_config(page_title="AI 챗봇", page_icon="🤖")

# 세션 상태 초기화
def init_session_state():
    if "is_logged_in" not in st.session_state:
        st.session_state.is_logged_in = False
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

init_session_state()

# 사용자 관리 및 채팅 기록 저장 함수
def create_or_get_user(nickname):
    try:
        user = supabase.table("users").select("*").eq("nickname", nickname).execute()
        if user.data:
            return user.data[0]["id"], True
        new_user = supabase.table("users").insert({
            "nickname": nickname,
            "created_at": datetime.now().isoformat()
        }).execute()
        return new_user.data[0]["id"], False
    except Exception as e:
        logger.error(f"사용자 생성/조회 중 오류 발생: {str(e)}")
        raise Exception("사용자 처리 중 오류가 발생했습니다.")

def save_chat_history(user_id, session_id, question, answer, time_taken):
    try:
        supabase.table("chat_history").insert({
            "user_id": user_id,
            "session_id": session_id,
            "question": question,
            "answer": answer,
            "time_taken": time_taken,
            "created_at": datetime.now().isoformat()
        }).execute()
    except Exception as e:
        logger.error(f"채팅 기록 저장 중 오류 발생: {str(e)}")
        st.error("채팅 기록 저장 중 오류가 발생했습니다.")

# OpenWeather Geocoding API로 도시 정보 가져오기
def get_city_info(city_name):
    url = "https://api.openweathermap.org/geo/1.0/direct"
    params = {'q': city_name, 'limit': 1, 'appid': WEATHER_API_KEY}
    session = requests.Session()
    retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    try:
        response = session.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data and len(data) > 0:
            city_info = {
                "name": data[0]["name"],
                "country": data[0]["country"],
                "lat": data[0]["lat"],
                "lon": data[0]["lon"]
            }
            logger.info(f"Geocoding 성공: {city_info}")
            return city_info
        return None
    except Exception as e:
        logger.error(f"Geocoding 실패 ({city_name}): {str(e)}")
        return None

def get_time_by_city(city_name="서울"):
    city_info = get_city_info(city_name)
    if not city_info:
        return f"'{city_name}'의 시간 정보를 가져올 수 없습니다. ❌\n\n찾고 싶은 도시명을 말씀해 주세요."
    tf = TimezoneFinder()
    try:
        timezone_str = tf.timezone_at(lng=city_info["lon"], lat=city_info["lat"]) or "Asia/Seoul"
        timezone = pytz.timezone(timezone_str)
        city_time = datetime.now(timezone)
        am_pm = "오전" if city_time.strftime("%p") == "AM" else "오후"
        return f"현재 {city_name} 시간: {city_time.strftime('%Y년 %m월 %d일')} {am_pm} {city_time.strftime('%I:%M')} ⏰"
    except Exception as e:
        logger.error(f"시간 처리 실패 ({city_name}): {str(e)}")
        return f"'{city_name}'의 시간 정보를 가져올 수 없습니다. ❌"

# 의약품 검색 함수
def get_drug_info(drug_name):
    url = 'http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList'
    params = {
        'serviceKey': DRUG_API_KEY,
        'pageNo': '1',
        'numOfRows': '1',
        'itemName': quote(drug_name),
        'type': 'json'
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        if 'body' in data and 'items' in data['body'] and data['body']['items']:
            item = data['body']['items'][0]
            def cut_to_sentence(text, max_len=150):
                if not text or len(text) <= max_len:
                    return text
                truncated = text[:max_len]
                last_punctuation = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'), truncated.rfind(','))
                if last_punctuation > 0:
                    result = truncated[:last_punctuation + 1]
                    if len(text) > max_len:
                        result += " 등"
                    return result
                return truncated + "..."
            efcy = cut_to_sentence(item.get('efcyQesitm', '정보 없음'))
            use_method_raw = cut_to_sentence(item.get('useMethodQesitm', '정보 없음'))
            atpn_raw = cut_to_sentence(item.get('atpnQesitm', '정보 없음'))
            use_method_raw = re.sub(r'(\d+)~(\d+)(세|정|mg)', r'\1-\2\3', use_method_raw)
            atpn_raw = re.sub(r'(\d+)~(\d+)(세|정|mg)', r'\1-\2\3', atpn_raw)
            use_method = use_method_raw.replace('. ', '.\n')
            atpn = atpn_raw.replace('. ', '.\n')
            return (
                f"💊 **의약품 정보** 💊\n\n"
                f"✅ **약품명**: {item.get('itemName', '정보 없음')}\n\n"
                f"✅ **제조사**: {item.get('entpName', '정보 없음')}\n\n"
                f"✅ **효능**: {efcy}\n\n"
                f"✅ **용법용량**: {use_method}\n\n"
                f"✅ **주의사항**: {atpn}\n\n"
                f"ℹ️ 자세한 정보는 <a href='https://www.health.kr/searchDrug/search_detail.asp'>약학정보원</a>에서 확인하세요! 🩺"
            )
        else:
            logger.info(f"'{drug_name}' API 검색 실패, 구글 검색으로 대체")
            search_results = search_and_summarize(f"{drug_name} 의약품 정보", num_results=5)
            if not search_results.empty:
                return (
                    f"'{drug_name}'에 대한 공식 의약품 정보를 찾을 수 없습니다. 🩺\n"
                    f"대신 웹에서 검색한 결과를 아래에 요약했어요:\n\n"
                    f"{get_ai_summary(search_results)}"
                )
            return f"'{drug_name}'에 대한 의약품 정보를 찾을 수 없습니다. 🩺"
    except Exception as e:
        logger.error(f"의약품 API 오류: {str(e)}")
        search_results = search_and_summarize(f"{drug_name} 의약품 정보", num_results=5)
        if not search_results.empty:
            return (
                f"'{drug_name}' 의약품 정보를 API에서 가져오는 중 오류가 발생했습니다. ❌\n"
                f"대신 웹에서 검색한 결과를 아래에 요약했어요:\n\n"
                f"{get_ai_summary(search_results)}"
            )
        return f"'{drug_name}' 의약품 정보를 가져오는 중 오류가 발생했습니다. ❌"

# 도시명 및 쿼리 추출 함수
def extract_city_from_query(query):
    time_keywords = ["오늘", "내일", "모레", "이번 주", "주간"]
    city_patterns = [
        r'(?:오늘|내일|모레|이번 주|주간)?\s*([가-힣a-zA-Z\s]{2,20}(?:시|군|city)?)의?\s*날씨',
        r'(?:오늘|내일|모레|이번 주|주간)?\s*([가-힣a-zA-Z\s]{2,20}(?:시|군|city)?)\s*날씨',
        r'날씨\s*(?:오늘|내일|모레|이번 주|주간)?\s*([가-힣a-zA-Z\s]{2,20}(?:시|군|city)?)',
        r'weather\s*(?:today|tomorrow|day after tomorrow|this week|weekly)?\s*in\s+([a-zA-Z\s]{2,20})',
        r'(?:오늘|내일|모레|이번 주|주간)?\s*([a-zA-Z\s]{2,20})\s+weather'
    ]
    for pattern in city_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            city = match.group(1).strip()
            if city not in time_keywords and city != "현재":
                return city
    return "서울"

def extract_city_from_time_query(query):
    city_patterns = [
        r'([가-힣a-zA-Z]{2,20}(?:시|군)?)의?\s*시간',
        r'([가-힣a-zA-Z]{2,20}(?:시|군)?)\s*시간',
        r'시간\s*([가-힣a-zA-Z\s]{2,20}(?:시|군)?)',
    ]
    for pattern in city_patterns:
        match = re.search(pattern, query)
        if match:
            city = match.group(1).strip()
            if city != "현재":
                return city
    return "서울"

# Naver API 검색 함수
def get_naver_api_results(query):
    global naver_request_count
    if naver_request_count >= NAVER_DAILY_LIMIT:
        logger.warning(f"Naver API 일일 제한 {NAVER_DAILY_LIMIT}회 초과, Google 검색으로 전환")
        return search_and_summarize(query, num_results=5)
    
    enc_text = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/webkr?query={enc_text}&display=10&sort=date"
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    request.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)

    results = []
    try:
        logger.info(f"Naver API 호출 시도: {query}, 현재 요청 횟수: {naver_request_count}")
        response = urllib.request.urlopen(request)
        naver_request_count += 1
        logger.info(f"Naver API 호출 성공: {query}, 요청 횟수 증가 -> {naver_request_count}")
        if response.getcode() == 200:
            response_body = response.read().decode('utf-8')
            data = json.loads(response_body)
            items = data.get('items', [])
            
            for item in items[:5]:  # 상위 5개만
                title = re.sub(r'<b>|</b>', '', item['title'])
                contents = re.sub(r'<b>|</b>', '', item.get('description', '내용 없음'))[:100] + "..."
                url = item.get('link', '링크 없음')
                date_str = item.get('pubDate', '')
                date = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z').strftime('%Y-%m-%d') if date_str else "날짜 없음"
                results.append({"title": title, "contents": contents, "url": url, "date": date})
    except Exception as e:
        logger.error(f"Naver API 호출 실패: {query}, 오류: {str(e)}, Google 검색으로 전환")
        return search_and_summarize(query, num_results=5)
    
    return pd.DataFrame(results)

# 웹 검색 및 요약 함수
def search_and_summarize(query, num_results=5):
    logger.info(f"Google 검색 사용: {query}")
    data = []
    try:
        for link in search(query, num_results=num_results):
            try:
                response = requests.get(link, timeout=5)
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.title.get_text() if soup.title else "No title"
                description = ' '.join([p.get_text() for p in soup.find_all('p')[:3]])
                data.append({
                    "keyword": query,
                    "link": link,
                    "title": title,
                    "contents": description[:500]
                })
            except Exception as e:
                logger.error(f"개별 검색 결과 처리 중 오류: {str(e)}")
                continue
        return pd.DataFrame(data)
    except Exception as e:
        logger.error(f"Google 검색 중 오류 발생: {str(e)}")
        return pd.DataFrame()

def get_ai_summary(search_results):
    if search_results.empty:
        return "검색 결과를 찾을 수 없습니다. ❌"
    context = "\n\n".join([f"출처: {row['title']}\n내용: {row['contents']}" for _, row in search_results.iterrows()])
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": f"다음 검색 결과를 분석하고, 핵심 내용을 2~3문장으로 요약해주세요:\n\n{context}"}]
        )
        summary = response.choices[0].message.content
        sources = "\n\n📚 참고 출처:\n" + "\n".join([f"- [{row['title']}]({row['url'] if 'url' in row else row['link']})" for _, row in search_results.iterrows()])
        return f"{summary}{sources}\n\n더 알고 싶으신가요? 추가로 물어보시면 더 알려드릴게요!"
    except Exception as e:
        logger.error(f"AI 요약 중 오류 발생: {str(e)}")
        return "검색 결과 요약 중 오류가 발생했습니다. ❌"

# 대화형 응답 생성 함수
def get_conversational_response(query, chat_history):
    messages = [{"role": "system", "content": "당신은 친절하고 상호작용적인 AI 챗봇입니다. 사용자의 질문에 답하고, 필요하면 추가 질문을 던져 대화를 이어가세요."}]
    for msg in chat_history[-5:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": query})
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"대화 응답 생성 중 오류: {str(e)}")
        return "대화 중 오류가 발생했어요. 다시 시도해 볼까요? 😅"

# 쿼리 타입 판단 함수
@lru_cache(maxsize=128)
def needs_search(query):
    query_lower = query.strip().lower()
    
    greeting_keywords = ["안녕", "하이", "반가워", "안뇽", "뭐해", "헬롱", "하잇", "헤이요", "왓업", "왓썹", "에이요"]
    emotion_keywords = ["배고프다", "배고프", "졸리다", "피곤하다", "화남", "열받음", "짜증남", "피곤함"]
    if any(greeting in query_lower for greeting in greeting_keywords) or \
       any(emo in query_lower for emo in emotion_keywords) or \
       len(query_lower) <= 3 and "?" not in query_lower:
        return "conversation"
    
    intent_keywords = ["추천해줘", "뭐 먹을까", "메뉴", "뭐할까"]
    if any(kw in query_lower for kw in intent_keywords):
        return "conversation"
    
    time_keywords = ["현재 시간", "시간", "몇 시", "지금", "몇시", "몇 시야", "지금 시간", "현재", "시계"]
    if any(keyword in query_lower for keyword in time_keywords) and \
       any(timeword in query_lower for timeword in ["시간", "몇시", "몇 시", "시계"]):
        return "time"
    
    weather_keywords = ["날씨", "온도", "기온"]
    if any(keyword in query_lower for keyword in weather_keywords) and "내일" in query_lower:
        return "tomorrow_weather"
    elif any(keyword in query_lower for keyword in weather_keywords) and "모레" in query_lower:
        return "day_after_tomorrow_weather"
    elif any(keyword in query_lower for keyword in weather_keywords) and any(kw in query_lower for kw in ["이번 주", "주간 예보", "주간 날씨"]):
        return "weekly_forecast"
    elif any(keyword in query_lower for keyword in weather_keywords):
        return "weather"
    
    drug_keywords = ["약", "의약품", "약품"]
    drug_pattern = r'^[가-힣a-zA-Z]{2,10}(?:약|정|시럽|캡슐)$'
    if any(keyword in query_lower for keyword in drug_keywords) or re.match(drug_pattern, query_lower):
        return "drug"
    
    if query_lower == "mbti 검사":
        return "mbti"
    if query_lower == "다중지능 검사":
        return "multi_iq"
    
    return "search"  # 기본적으로 검색으로 처리


# 대화형 응답 캐싱 추가
@lru_cache(maxsize=128)
def get_cached_conversational_response(query, chat_history_tuple):
    chat_history = list(chat_history_tuple)  # 튜플을 리스트로 변환
    messages = [{"role": "system", "content": "당신은 친절하고 상호작용적인 AI 챗봇입니다. 사용자의 질문에 답하고, 필요하면 추가 질문을 던져 대화를 이어가세요."}]
    for msg in chat_history[-5:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": query})
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"대화 응답 생성 중 오류: {str(e)}")
        return "대화 중 오류가 발생했어요. 다시 시도해 볼까요? 😅"

# 단순 인사에 대한 미리 정의된 응답
GREETING_RESPONSES = {
    "안녕": "안녕하세요! 반갑습니다! 😊",
    "안녕 반가워": "안녕하세요! 저도 반갑습니다! 오늘 기분이 어떠신가요? 😄",
    "하이": "하이! 좋은 하루 보내세요! 😊",
}



# 로그인 및 대시보드 함수
def show_login_page():
    st.title("로그인 🤗")
    with st.form("login_form"):
        nickname = st.text_input("닉네임을 입력하세요", placeholder="예: 후안")
        submit_button = st.form_submit_button("시작하기 🚀")
        if submit_button and nickname:
            try:
                user_id, is_existing = create_or_get_user(nickname)
                st.session_state.user_id = user_id
                st.session_state.is_logged_in = True
                if is_existing:
                    st.toast(f"환영합니다, {nickname}님! 🎉")
                else:
                    st.toast(f"새로운 사용자로 등록되었습니다. 환영합니다, {nickname}님! 🎉")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.toast(f"로그인 중 오류가 발생했습니다: {str(e)}", icon="❌")
        elif submit_button:
            st.toast("닉네임을 입력해주세요.", icon="⚠️")

def show_chat_dashboard():
    st.title("AI 챗봇 🤖")
    for message in st.session_state.chat_history:
        with st.chat_message(message['role']):
            st.markdown(message['content'], unsafe_allow_html=True)
    
    user_prompt = st.chat_input("질문해 주세요!")
    if user_prompt:
        st.chat_message("user").markdown(user_prompt)
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            message_placeholder.markdown("⏳ 응답 생성 중...")
            try:
                start_time = time.time()
                query_type = needs_search(user_prompt)
                base_response = ""

                if query_type == "mbti":
                    base_response = (
                        "MBTI 검사를 원하시나요? ✨ 아래 사이트에서 무료로 성격 유형 검사를 할 수 있어요! 😊\n\n"
                        "[16Personalities MBTI 검사](https://www.16personalities.com/ko/%EB%AC%B4%EB%A3%8C-%EC%84%B1%EA%B2%A9-%EC%9C%A0%ED%98%95-%EA%B2%80%EC%82%AC) 🌟\n\n"
                        "이 사이트는 16가지 성격 유형을 기반으로 한 테스트를 제공하며, 결과에 따라 성격 설명과 인간관계 조언 등을 확인할 수 있어요! 🧠💡"
                    )
                elif query_type == "multi_iq":
                    base_response = (
                        "다중지능 검사를 원하시나요? 🎉 아래 사이트에서 무료로 다중지능 테스트를 해볼 수 있어요! 😄\n\n"
                        "[Multi IQ Test](https://multiiqtest.com/) 🚀\n\n"
                        "이 사이트는 하워드 가드너의 다중지능 이론을 기반으로 한 테스트를 제공하며, 다양한 지능 영역을 평가해줍니다! 📚✨"
                    )
                elif query_type == "time":
                    city = extract_city_from_time_query(user_prompt)
                    base_response = get_time_by_city(city)
                elif query_type == "weather":
                    city = extract_city_from_query(user_prompt)
                    base_response = weather_api.get_city_weather(city)
                elif query_type == "tomorrow_weather":
                    city = extract_city_from_query(user_prompt)
                    base_response = weather_api.get_forecast_by_day(city, days_from_today=1)
                elif query_type == "day_after_tomorrow_weather":
                    city = extract_city_from_query(user_prompt)
                    base_response = weather_api.get_forecast_by_day(city, days_from_today=2)
                elif query_type == "weekly_forecast":
                    city = extract_city_from_query(user_prompt)
                    base_response = weather_api.get_weekly_forecast(city)
                elif query_type == "drug":
                    drug_name = user_prompt.strip()
                    base_response = get_drug_info(drug_name)
                elif query_type == "conversation":
                    # 단순 인사면 미리 정의된 응답 사용
                    if user_prompt.strip() in GREETING_RESPONSES:
                        base_response = GREETING_RESPONSES[user_prompt.strip()]
                    else:
                        base_response = get_cached_conversational_response(user_prompt, tuple(st.session_state.chat_history))
                elif query_type == "web_search":
                    language = detect(user_prompt)
                    if language == 'ko' and naver_request_count < NAVER_DAILY_LIMIT:
                        search_results = get_naver_api_results(user_prompt)
                    else:
                        search_results = search_and_summarize(user_prompt)
                    base_response = get_ai_summary(search_results)
                elif query_type == "general_query":
                    base_response = get_cached_conversational_response(user_prompt, tuple(st.session_state.chat_history))

                # 대화 맥락 반영 (conversation/general_query가 아닌 경우에만 추가 호출)
                if query_type in ["conversation", "general_query"]:
                    final_response = base_response
                else:
                    final_response = get_cached_conversational_response(
                        f"다음 정보를 바탕으로 사용자와 대화를 이어가세요:\n\n{base_response}\n\n사용자 질문: {user_prompt}",
                        tuple(st.session_state.chat_history)
                    )

                end_time = time.time()
                time_taken = round(end_time - start_time, 2)
                logger.info(f"응답 생성 완료: {user_prompt}, 소요 시간: {time_taken}초")
                
                st.session_state.chat_history.append({"role": "assistant", "content": final_response})
                message_placeholder.markdown(final_response, unsafe_allow_html=True)
                save_chat_history(st.session_state.user_id, st.session_state.session_id, user_prompt, final_response, time_taken)
            except Exception as e:
                error_message = f"❌ 오류 발생: {str(e)}\n\n다시 물어보시면 최선을 다해 답변해드릴게요!"
                logger.error(error_message)
                message_placeholder.markdown(error_message)
                st.session_state.chat_history.append({"role": "assistant", "content": error_message})
# 메인 실행
def main():
    init_session_state()
    if not st.session_state.is_logged_in:
        show_login_page()
    else:
        show_chat_dashboard()

if __name__ == "__main__":
    main()
