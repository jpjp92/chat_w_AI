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
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor
import arxiv
from diskcache import Cache
from functools import lru_cache

# 환경 변수 로드
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
DRUG_API_KEY = os.getenv("DRUG_API_KEY")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

# 로깅 설정
logging.basicConfig(level=logging.WARNING if os.getenv("ENV") == "production" else logging.INFO)
logger = logging.getLogger("HybridChat")

# 캐시 설정
cache = Cache("cache_directory")

class MemoryCache:
    def __init__(self):
        self.cache = {}
        self.expiry = {}
    
    def get(self, key):
        if key in self.cache and time.time() < self.expiry[key]:
            return self.cache[key]
        return cache.get(key)
    
    def setex(self, key, ttl, value):
        self.cache[key] = value
        self.expiry[key] = time.time() + ttl
        cache.set(key, value, expire=ttl)

cache_handler = MemoryCache()

# WeatherAPI 클래스
class WeatherAPI:
    def __init__(self, cache_ttl=600):
        self.cache = cache_handler
        self.cache_ttl = cache_ttl

    def fetch_weather(self, url, params):
        session = requests.Session()
        retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        response = session.get(url, params=params, timeout=5)
        response.raise_for_status()
        return response.json()

    @lru_cache(maxsize=100)
    def get_city_info(self, city_name):
        cache_key = f"city_info:{city_name}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        url = "http://api.openweathermap.org/geo/1.0/direct"
        params = {'q': city_name, 'limit': 1, 'appid': WEATHER_API_KEY}
        data = self.fetch_weather(url, params)
        if data and len(data) > 0:
            city_info = {"name": data[0]["name"], "lat": data[0]["lat"], "lon": data[0]["lon"]}
            self.cache.setex(cache_key, 86400, city_info)
            return city_info
        return None

    def get_city_weather(self, city_name):
        cache_key = f"weather:{city_name}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        city_info = self.get_city_info(city_name)
        if not city_info:
            return f"'{city_name}'의 날씨 정보를 가져올 수 없습니다."
        
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {'lat': city_info["lat"], 'lon': city_info["lon"], 'appid': WEATHER_API_KEY, 'units': 'metric', 'lang': 'kr'}
        data = self.fetch_weather(url, params)
        weather_emojis = {'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Snow': '❄️', 'Thunderstorm': '⛈️', 'Drizzle': '🌦️', 'Mist': '🌫️'}
        weather_emoji = weather_emojis.get(data['weather'][0]['main'], '🌤️')
        result = (
            f"현재 {data['name']}, {data['sys']['country']} 날씨 {weather_emoji}\n"
            f"날씨: {data['weather'][0]['description']}\n"
            f"온도: {data['main']['temp']}°C\n"
            f"체감: {data['main']['feels_like']}°C\n"
            f"습도: {data['main']['humidity']}%\n"
            f"풍속: {data['wind']['speed']}m/s\n"
            f"더 궁금한 점 있나요? 😊"
        )
        self.cache.setex(cache_key, self.cache_ttl, result)
        return result

    def get_forecast_by_day(self, city_name, days_from_today=1):
        cache_key = f"forecast:{city_name}:{days_from_today}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        city_info = self.get_city_info(city_name)
        if not city_info:
            return f"'{city_name}'의 날씨 예보를 가져올 수 없습니다."
        
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {'lat': city_info["lat"], 'lon': city_info["lon"], 'appid': WEATHER_API_KEY, 'units': 'metric', 'lang': 'kr'}
        data = self.fetch_weather(url, params)
        target_date = (datetime.now() + timedelta(days=days_from_today)).strftime('%Y-%m-%d')
        forecast_text = f"{city_info['name']}의 {target_date} 날씨 예보 🌤️\n"
        weather_emojis = {'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Snow': '❄️', 'Thunderstorm': '⛈️', 'Drizzle': '🌦️', 'Mist': '🌫️'}
        
        found = False
        for forecast in data['list']:
            dt = datetime.fromtimestamp(forecast['dt']).strftime('%Y-%m-%d')
            if dt == target_date:
                found = True
                time_only = datetime.fromtimestamp(forecast['dt']).strftime('%H:%M')
                weather_emoji = weather_emojis.get(forecast['weather'][0]['main'], '🌤️')
                forecast_text += (
                    f"⏰ {time_only} {forecast['weather'][0]['description']} {weather_emoji} "
                    f"{forecast['main']['temp']}°C 💧{forecast['main']['humidity']}% 🌬️{forecast['wind']['speed']}m/s\n"
                )
        
        result = forecast_text + "\n더 궁금한 점 있나요? 😊" if found else f"'{city_name}'의 {target_date} 날씨 예보를 찾을 수 없습니다."
        self.cache.setex(cache_key, self.cache_ttl, result)
        return result

    def get_weekly_forecast(self, city_name):
        cache_key = f"weekly_forecast:{city_name}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        city_info = self.get_city_info(city_name)
        if not city_info:
            return f"'{city_name}'의 주간 예보를 가져올 수 없습니다."
        
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {'lat': city_info["lat"], 'lon': city_info["lon"], 'appid': WEATHER_API_KEY, 'units': 'metric', 'lang': 'kr'}
        data = self.fetch_weather(url, params)
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
        forecast_text = f"{today_str}({today_weekday_str}) 기준 {city_info['name']}의 주간 날씨 예보 🌤️\n"
        weather_emojis = {'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Snow': '❄️', 'Thunderstorm': '⛈️', 'Drizzle': '🌦️', 'Mist': '🌫️'}
        
        for date, info in daily_forecast.items():
            weather_emoji = weather_emojis.get(info['weather'].split()[0], '🌤️')
            forecast_text += (
                f"{info['weekday']}: {info['weather']} {weather_emoji} "
                f"최저 {info['temp_min']}°C 최고 {info['temp_max']}°C\n"
            )
        
        result = forecast_text + "\n더 궁금한 점 있나요? 😊"
        self.cache.setex(cache_key, self.cache_ttl, result)
        return result

# 초기화
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = Client()
weather_api = WeatherAPI()
naver_request_count = 0
NAVER_DAILY_LIMIT = 25000
st.set_page_config(page_title="AI 챗봇", page_icon="🤖")

# 세션 상태 초기화
if "is_logged_in" not in st.session_state:
    st.session_state.is_logged_in = False
    st.session_state.user_id = None
    st.session_state.chat_history = []
    st.session_state.session_id = str(uuid.uuid4())

# 도시 추출
CITY_PATTERNS = [
    re.compile(r'(?:오늘|내일|모레|이번 주|주간)?\s*([가-힣a-zA-Z\s]{2,20}(?:시|군|city)?)의?\s*날씨', re.IGNORECASE),
    re.compile(r'(?:오늘|내일|모레|이번 주|주간)?\s*([가-힣a-zA-Z\s]{2,20}(?:시|군|city)?)\s*날씨', re.IGNORECASE),
    re.compile(r'날씨\s*(?:오늘|내일|모레|이번 주|주간)?\s*([가-힣a-zA-Z\s]{2,20}(?:시|군|city)?)', re.IGNORECASE),
]
def extract_city_from_query(query):
    for pattern in CITY_PATTERNS:
        match = pattern.search(query)
        if match:
            city = match.group(1).strip()
            if city not in ["오늘", "내일", "모레", "이번 주", "주간", "현재"]:
                return city
    return "서울"

TIME_CITY_PATTERNS = [
    re.compile(r'([가-힣a-zA-Z]{2,20}(?:시|군)?)의?\s*시간'),
    re.compile(r'([가-힣a-zA-Z]{2,20}(?:시|군)?)\s*시간'),
    re.compile(r'시간\s*([가-힣a-zA-Z\s]{2,20}(?:시|군)?)'),
]
def extract_city_from_time_query(query):
    for pattern in TIME_CITY_PATTERNS:
        match = pattern.search(query)
        if match:
            city = match.group(1).strip()
            if city != "현재":
                return city
    return "서울"

# 시간 정보
def get_time_by_city(city_name="서울"):
    city_info = weather_api.get_city_info(city_name)
    if not city_info:
        return f"'{city_name}'의 시간 정보를 가져올 수 없습니다."
    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lng=city_info["lon"], lat=city_info["lat"]) or "Asia/Seoul"
    timezone = pytz.timezone(timezone_str)
    city_time = datetime.now(timezone)
    am_pm = "오전" if city_time.strftime("%p") == "AM" else "오후"
    return f"현재 {city_name} 시간: {city_time.strftime('%Y년 %m월 %d일 %p %I:%M')} ⏰\n더 궁금한 점 있나요? 😊"

# 사용자 및 채팅 기록 관리
def create_or_get_user(nickname):
    user = supabase.table("users").select("*").eq("nickname", nickname).execute()
    if user.data:
        return user.data[0]["id"], True
    new_user = supabase.table("users").insert({"nickname": nickname, "created_at": datetime.now().isoformat()}).execute()
    return new_user.data[0]["id"], False

def save_chat_history(user_id, session_id, question, answer, time_taken):
    supabase.table("chat_history").insert({
        "user_id": user_id, "session_id": session_id, "question": question,
        "answer": answer, "time_taken": time_taken, "created_at": datetime.now().isoformat()
    }).execute()

def async_save_chat_history(user_id, session_id, question, answer, time_taken):
    threading.Thread(target=save_chat_history, args=(user_id, session_id, question, answer, time_taken)).start()

# 의약품 검색
def get_drug_info(drug_query):
    drug_name = drug_query.replace("약품검색", "").strip()
    cache_key = f"drug:{drug_name}"
    cached = cache_handler.get(cache_key)
    if cached:
        return cached
    
    url = 'http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList'
    params = {'serviceKey': DRUG_API_KEY, 'pageNo': '1', 'numOfRows': '1', 'itemName': urllib.parse.quote(drug_name), 'type': 'json'}
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        if 'body' in data and 'items' in data['body'] and data['body']['items']:
            item = data['body']['items'][0]
            efcy = item.get('efcyQesitm', '정보 없음')[:150] + ("..." if len(item.get('efcyQesitm', '')) > 150 else "")
            use_method = item.get('useMethodQesitm', '정보 없음')[:150] + ("..." if len(item.get('useMethodQesitm', '')) > 150 else "")
            atpn = item.get('atpnQesitm', '정보 없음')[:150] + ("..." if len(item.get('atpnQesitm', '')) > 150 else "")
            result = (
                f"💊 **의약품 정보** 💊\n"
                f"✅ **약품명**: {item.get('itemName', '정보 없음')}\n"
                f"✅ **제조사**: {item.get('entpName', '정보 없음')}\n"
                f"✅ **효능**: {efcy}\n"
                f"✅ **용법용량**: {use_method}\n"
                f"✅ **주의사항**: {atpn}\n"
                f"ℹ️ 자세한 정보는 [약학정보원](https://www.health.kr/searchDrug/search_detail.asp)에서 확인하세요! 🩺\n"
                f"더 궁금한 점 있으신가요? 😊"
            )
            cache_handler.setex(cache_key, 86400, result)
            return result
        else:
            return search_and_summarize_drug(drug_name)
    except Exception as e:
        logger.error(f"약품 API 오류: {str(e)}")
        return search_and_summarize_drug(drug_name)

def search_and_summarize_drug(drug_name):
    search_results = search_and_summarize(f"{drug_name} 의약품 정보", num_results=5)
    if not search_results.empty:
        return f"'{drug_name}' 공식 정보 없음. 웹 검색 요약:\n{get_ai_summary(search_results)}"
    return f"'{drug_name}' 의약품 정보를 찾을 수 없습니다."

# Naver API 및 웹 검색
def get_naver_api_results(query):
    global naver_request_count
    if naver_request_count >= NAVER_DAILY_LIMIT:
        return search_and_summarize(query, num_results=5)
    enc_text = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/webkr?query={enc_text}&display=10&sort=date"
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    request.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
    results = []
    try:
        response = urllib.request.urlopen(request)
        naver_request_count += 1
        if response.getcode() == 200:
            data = json.loads(response.read().decode('utf-8'))
            for item in data.get('items', [])[:5]:
                title = re.sub(r'<b>|</b>', '', item['title'])
                contents = re.sub(r'<b>|</b>', '', item.get('description', '내용 없음'))[:100] + "..."
                results.append({"title": title, "contents": contents, "url": item.get('link', ''), "date": item.get('pubDate', '')})
    except Exception:
        return search_and_summarize(query, num_results=5)
    return pd.DataFrame(results)

def search_and_summarize(query, num_results=5):
    data = []
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(requests.get, link, timeout=5) for link in search(query, num_results=num_results)]
        for future in futures:
            try:
                response = future.result()
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.title.get_text() if soup.title else "No title"
                description = ' '.join([p.get_text() for p in soup.find_all('p')[:3]])
                data.append({"title": title, "contents": description[:500], "link": response.url})
            except Exception:
                continue
    return pd.DataFrame(data)

def get_ai_summary(search_results):
    if search_results.empty:
        return "검색 결과를 찾을 수 없습니다."
    context = "\n".join([f"출처: {row['title']}\n내용: {row['contents']}" for _, row in search_results.iterrows()])
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"검색 결과를 2~3문장으로 요약:\n{context}"}]
    )
    summary = response.choices[0].message.content
    sources = "\n📜 **출처**\n" + "\n".join([f"🌐 [{row['title']}]({row['link']})" for _, row in search_results.iterrows()])
    return f"{summary}{sources}\n더 궁금한 점 있나요? 😊"

# 논문 검색
def fetch_arxiv_paper(paper):
    return {
        "title": paper.title,
        "authors": ", ".join(str(a) for a in paper.authors),
        "summary": paper.summary[:200],
        "entry_id": paper.entry_id,
        "pdf_url": paper.get_pdf_url(),
        "published": paper.published.strftime('%Y-%m-%d')
    }

def get_arxiv_papers(query, max_results=3):
    cache_key = f"arxiv:{query}:{max_results}"
    cached = cache_handler.get(cache_key)
    if cached:
        return cached
    search = arxiv.Search(query=query, max_results=max_results, sort_by=arxiv.SortCriterion.SubmittedDate)
    with ThreadPoolExecutor() as executor:
        results = list(executor.map(fetch_arxiv_paper, search.results()))
    if not results:
        return "해당 키워드로 논문을 찾을 수 없습니다."
    response = "📚 **Arxiv 논문 검색 결과** 📚\n" + "\n".join(
        [f"**논문 {i}**\n"
         f"📄 **제목**: {r['title']}\n"
         f"👥 **저자**: {r['authors']}\n"
         f"📝 **초록**: {r['summary']}...\n"
         f"🔗 **논문 페이지**: {r['entry_id']}\n"
         f"📥 **PDF 다운로드**: [{r['pdf_url'].split('/')[-1]}]({r['pdf_url']})\n"
         f"📅 **출판일**: {r['published']}\n"
         f"{'-' * 50}"
         for i, r in enumerate(results, 1)]
    ) + "\n더 많은 논문을 보고 싶다면 말씀해 주세요! 😊"
    cache_handler.setex(cache_key, 3600, response)
    return response

# 대화형 응답
conversation_cache = MemoryCache()
def get_conversational_response(query, chat_history):
    cache_key = f"conv:{needs_search(query)}:{query}:{hash(str(chat_history[-5:]))}"
    cached = conversation_cache.get(cache_key)
    if cached:
        return cached
    messages = [{"role": "system", "content": "친절하고 상호작용적인 AI 챗봇입니다."}] + [
        {"role": msg["role"], "content": msg["content"]} for msg in chat_history[-5:]
    ] + [{"role": "user", "content": query}]
    response = client.chat.completions.create(model="gpt-4", messages=messages)
    result = response.choices[0].message.content
    conversation_cache.setex(cache_key, 600, result)
    return result

GREETING_RESPONSES = {
    "안녕": "안녕하세요! 반갑습니다! 😊",
    "안녕 반가워": "안녕하세요! 저도 반갑습니다! 오늘 기분이 어떠신가요? 😄",
    "하이": "하이! 좋은 하루 보내세요! 😊",
    "헬로": "안녕하세요! 반갑습니다! 😊",
    "헤이": "헤이! 잘 지내세요? 😄",
    "왓업": "왓업! 뭐하고 계신가요? 😊",
    "왓썹": "안녕하세요! 오늘 기분이 어떠신가요? 😄",
}

# 쿼리 분류
def needs_search(query):
    query_lower = query.strip().lower()
    greeting_keywords = ["안녕", "하이", "반가워", "안뇽", "뭐해", "헬로", "헬롱", "하잇", "헤이", "헤이요", "왓업", "왓썹", "에이요"]
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
    elif any(keyword in query_lower for keyword in weather_keywords) and ("주간" in query_lower or any(kw in query_lower for kw in ["이번 주", "주간 예보", "주간 날씨"])):
        return "weekly_forecast"
    elif any(keyword in query_lower for keyword in weather_keywords):
        return "weather"
    drug_keywords = ["약품검색"]
    drug_pattern = r'^약품검색\s+[가-힣a-zA-Z]{2,10}(?:약|정|시럽|캡슐)?$'
    if any(keyword in query_lower for keyword in drug_keywords) and re.match(drug_pattern, query_lower):
        return "drug"
    if query_lower == "mbti 검사":
        return "mbti"
    if query_lower == "다중지능 검사":
        return "multi_iq"
    arxiv_keywords = ["논문검색", "arxiv", "paper", "research"]
    if any(kw in query_lower for kw in arxiv_keywords) and len(query_lower) > 5:
        return "arxiv_search"
    search_keywords = ["검색", "알려줘", "정보", "뭐야", "무엇이야", "무엇인지", "찾아서", "정리해줘", "설명해줘", "알고싶어", "알려줄래"]
    if any(kw in query_lower for kw in search_keywords) and len(query_lower) > 5:
        return "web_search"
    return "general_query"

# UI 함수
def show_login_page():
    st.title("로그인 🤗")
    with st.form("login_form"):
        nickname = st.text_input("닉네임", placeholder="예: 후안")
        if st.form_submit_button("시작하기 🚀") and nickname:
            user_id, is_existing = create_or_get_user(nickname)
            st.session_state.user_id = user_id
            st.session_state.is_logged_in = True
            st.toast(f"환영합니다, {nickname}님! 🎉")
            time.sleep(1)
            st.rerun()

@st.cache_data(ttl=600)
def get_cached_response(query):
    return process_query(query)

def process_query(query):
    query_type = needs_search(query)
    if query_type == "mbti":
        return (
            "MBTI 검사를 원하시나요? ✨ 아래 사이트에서 무료로 성격 유형 검사를 할 수 있어요! 😊\n"
            "[16Personalities MBTI 검사](https://www.16personalities.com/ko/%EB%AC%B4%EB%A3%8C-%EC%84%B1%EA%B2%A9-%EC%9C%A0%ED%98%95-%EA%B2%80%EC%82%AC) 🌟\n"
            "이 사이트는 16가지 성격 유형을 기반으로 한 테스트를 제공하며, 결과에 따라 성격 설명과 인간관계 조언 등을 확인할 수 있어요! 🧠💡"
        )
    elif query_type == "multi_iq":
        return (
            "다중지능 검사를 원하시나요? 🎉 아래 사이트에서 무료로 다중지능 테스트를 해볼 수 있어요! 😄\n"
            "[Multi IQ Test](https://multiiqtest.com/) 🚀\n"
            "이 사이트는 하워드 가드너의 다중지능 이론을 기반으로 한 테스트를 제공하며, 다양한 지능 영역을 평가해줍니다! 📚✨"
        )
    elif query_type == "time":
        city = extract_city_from_time_query(query)
        return get_time_by_city(city)
    elif query_type == "weather":
        city = extract_city_from_query(query)
        return weather_api.get_city_weather(city)
    elif query_type == "tomorrow_weather":
        city = extract_city_from_query(query)
        return weather_api.get_forecast_by_day(city, days_from_today=1)
    elif query_type == "day_after_tomorrow_weather":
        city = extract_city_from_query(query)
        return weather_api.get_forecast_by_day(city, days_from_today=2)
    elif query_type == "weekly_forecast":
        city = extract_city_from_query(query)
        return weather_api.get_weekly_forecast(city)
    elif query_type == "drug":
        return get_drug_info(query)
    elif query_type == "conversation":
        if query.strip() in GREETING_RESPONSES:
            return GREETING_RESPONSES[query.strip()]
        return get_conversational_response(query, st.session_state.chat_history)
    elif query_type == "web_search":
        language = detect(query)
        if language == 'ko' and naver_request_count < NAVER_DAILY_LIMIT:
            return get_ai_summary(get_naver_api_results(query))
        return get_ai_summary(search_and_summarize(query))
    elif query_type == "arxiv_search":
        keywords = query.replace("논문검색", "").replace("arxiv", "").replace("paper", "").replace("research", "").strip()
        return get_arxiv_papers(keywords)
    elif query_type == "general_query":
        return get_conversational_response(query, st.session_state.chat_history)
    return "아직 지원하지 않는 기능이에요. 😅"

def show_chat_dashboard():
    st.title("AI 챗봇 🤖")
    
    # 도움말 버튼 추가
    if st.button("도움말 ℹ️"):
        st.info(
            "챗봇을 더 잘 활용하려면 아래 형식을 참고하세요:\n\n"
            "1. **약품검색** 💊: '약품검색 [약 이름]' (예: 약품검색 타이레놀)\n"
            "2. **논문검색** 📚: '논문검색 [키워드]' (예: 논문검색 machine learning)\n"
            "3. **날씨검색** ☀️: '[도시명] 날씨' 또는 '내일 [도시명] 날씨' (예: 서울 날씨, 내일 부산 날씨)\n\n"
            "궁금한 점이 있으면 언제든 질문해주세요! 😊"
        )
    
    # 채팅 기록 표시
    for msg in st.session_state.chat_history:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'], unsafe_allow_html=True)
    
    # 사용자 입력 처리
    if user_prompt := st.chat_input("질문해 주세요!"):
        st.chat_message("user").markdown(user_prompt)
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("⏳ 응답 생성 중...")
            start_time = time.time()
            with ThreadPoolExecutor() as executor:
                future = executor.submit(get_cached_response, user_prompt)
                response = future.result()
            time_taken = round(time.time() - start_time, 2)
            placeholder.markdown(response, unsafe_allow_html=True)
            st.session_state.chat_history.append({"role": "assistant", "content": response})
            async_save_chat_history(st.session_state.user_id, st.session_state.session_id, user_prompt, response, time_taken)

# 메인 실행
def main():
    if not st.session_state.is_logged_in:
        show_login_page()
    else:
        show_chat_dashboard()

if __name__ == "__main__":
    main()
    
# import streamlit as st
# import time
# import uuid
# from supabase import create_client
# import os
# from datetime import datetime, timedelta
# import pytz
# import logging
# import requests
# from bs4 import BeautifulSoup
# import pandas as pd
# from googlesearch import search
# from g4f.client import Client
# from timezonefinder import TimezoneFinder
# import re
# import json
# import urllib.request
# import urllib.parse
# from langdetect import detect
# from requests.adapters import HTTPAdapter
# from requests.packages.urllib3.util.retry import Retry
# from concurrent.futures import ThreadPoolExecutor
# import arxiv
# from diskcache import Cache
# from functools import lru_cache

# # 환경 변수 로드
# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
# DRUG_API_KEY = os.getenv("DRUG_API_KEY")
# NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
# NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

# # 로깅 설정
# logging.basicConfig(level=logging.WARNING if os.getenv("ENV") == "production" else logging.INFO)
# logger = logging.getLogger("HybridChat")

# # 캐시 설정 (디스크 캐시)
# cache = Cache("cache_directory")

# class MemoryCache:
#     def __init__(self):
#         self.cache = {}
#         self.expiry = {}
    
#     def get(self, key):
#         if key in self.cache and time.time() < self.expiry[key]:
#             return self.cache[key]
#         return cache.get(key)
    
#     def setex(self, key, ttl, value):
#         self.cache[key] = value
#         self.expiry[key] = time.time() + ttl
#         cache.set(key, value, expire=ttl)

# cache_handler = MemoryCache()

# # WeatherAPI 클래스 (병렬 처리 및 캐싱)
# class WeatherAPI:
#     def __init__(self, cache_ttl=600):
#         self.cache = cache_handler
#         self.cache_ttl = cache_ttl

#     def fetch_weather(self, url, params):
#         session = requests.Session()
#         retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
#         adapter = HTTPAdapter(max_retries=retry_strategy)
#         session.mount("https://", adapter)
#         response = session.get(url, params=params, timeout=5)
#         response.raise_for_status()
#         return response.json()

#     @lru_cache(maxsize=100)
#     def get_city_info(self, city_name):
#         cache_key = f"city_info:{city_name}"
#         cached = self.cache.get(cache_key)
#         if cached:
#             return cached
#         url = "http://api.openweathermap.org/geo/1.0/direct"
#         params = {'q': city_name, 'limit': 1, 'appid': WEATHER_API_KEY}
#         data = self.fetch_weather(url, params)
#         if data and len(data) > 0:
#             city_info = {"name": data[0]["name"], "lat": data[0]["lat"], "lon": data[0]["lon"]}
#             self.cache.setex(cache_key, 86400, city_info)  # 24시간 캐싱
#             return city_info
#         return None

#     def get_city_weather(self, city_name):
#         cache_key = f"weather:{city_name}"
#         cached_data = self.cache.get(cache_key)
#         if cached_data:
#             return cached_data
        
#         city_info = self.get_city_info(city_name)
#         if not city_info:
#             return f"'{city_name}'의 날씨 정보를 가져올 수 없습니다."
        
#         url = "https://api.openweathermap.org/data/2.5/weather"
#         params = {'lat': city_info["lat"], 'lon': city_info["lon"], 'appid': WEATHER_API_KEY, 'units': 'metric', 'lang': 'kr'}
#         data = self.fetch_weather(url, params)
#         weather_emojis = {'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Snow': '❄️', 'Thunderstorm': '⛈️', 'Drizzle': '🌦️', 'Mist': '🌫️'}
#         weather_emoji = weather_emojis.get(data['weather'][0]['main'], '🌤️')
#         result = (
#             f"현재 {data['name']}, {data['sys']['country']} 날씨 {weather_emoji}\n"
#             f"날씨: {data['weather'][0]['description']}\n"
#             f"온도: {data['main']['temp']}°C\n"
#             f"체감: {data['main']['feels_like']}°C\n"
#             f"습도: {data['main']['humidity']}%\n"
#             f"풍속: {data['wind']['speed']}m/s\n"
#             f"더 궁금한 점 있나요? 😊"
#         )
#         self.cache.setex(cache_key, self.cache_ttl, result)
#         return result

#     def get_forecast_by_day(self, city_name, days_from_today=1):
#         cache_key = f"forecast:{city_name}:{days_from_today}"
#         cached_data = self.cache.get(cache_key)
#         if cached_data:
#             return cached_data
        
#         city_info = self.get_city_info(city_name)
#         if not city_info:
#             return f"'{city_name}'의 날씨 예보를 가져올 수 없습니다."
        
#         url = "https://api.openweathermap.org/data/2.5/forecast"
#         params = {'lat': city_info["lat"], 'lon': city_info["lon"], 'appid': WEATHER_API_KEY, 'units': 'metric', 'lang': 'kr'}
#         data = self.fetch_weather(url, params)
#         target_date = (datetime.now() + timedelta(days=days_from_today)).strftime('%Y-%m-%d')
#         forecast_text = f"{city_info['name']}의 {target_date} 날씨 예보 🌤️\n"
#         weather_emojis = {'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Snow': '❄️', 'Thunderstorm': '⛈️', 'Drizzle': '🌦️', 'Mist': '🌫️'}
        
#         found = False
#         for forecast in data['list']:
#             dt = datetime.fromtimestamp(forecast['dt']).strftime('%Y-%m-%d')
#             if dt == target_date:
#                 found = True
#                 time_only = datetime.fromtimestamp(forecast['dt']).strftime('%H:%M')
#                 weather_emoji = weather_emojis.get(forecast['weather'][0]['main'], '🌤️')
#                 forecast_text += (
#                     f"⏰ {time_only} {forecast['weather'][0]['description']} {weather_emoji} "
#                     f"{forecast['main']['temp']}°C 💧{forecast['main']['humidity']}% 🌬️{forecast['wind']['speed']}m/s\n"
#                 )
        
#         result = forecast_text + "\n더 궁금한 점 있나요? 😊" if found else f"'{city_name}'의 {target_date} 날씨 예보를 찾을 수 없습니다."
#         self.cache.setex(cache_key, self.cache_ttl, result)
#         return result

#     def get_weekly_forecast(self, city_name):
#         cache_key = f"weekly_forecast:{city_name}"
#         cached_data = self.cache.get(cache_key)
#         if cached_data:
#             return cached_data
        
#         city_info = self.get_city_info(city_name)
#         if not city_info:
#             return f"'{city_name}'의 주간 예보를 가져올 수 없습니다."
        
#         url = "https://api.openweathermap.org/data/2.5/forecast"
#         params = {'lat': city_info["lat"], 'lon': city_info["lon"], 'appid': WEATHER_API_KEY, 'units': 'metric', 'lang': 'kr'}
#         data = self.fetch_weather(url, params)
#         today = datetime.now().date()
#         week_end = today + timedelta(days=6)
#         daily_forecast = {}
#         weekdays_kr = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
#         today_weekday = today.weekday()
        
#         for forecast in data['list']:
#             dt = datetime.fromtimestamp(forecast['dt']).date()
#             if today <= dt <= week_end:
#                 dt_str = dt.strftime('%Y-%m-%d')
#                 if dt_str not in daily_forecast:
#                     weekday_idx = (today_weekday + (dt - today).days) % 7
#                     daily_forecast[dt_str] = {
#                         'weekday': weekdays_kr[weekday_idx],
#                         'temp_min': forecast['main']['temp_min'],
#                         'temp_max': forecast['main']['temp_max'],
#                         'weather': forecast['weather'][0]['description']
#                     }
#                 else:
#                     daily_forecast[dt_str]['temp_min'] = min(daily_forecast[dt_str]['temp_min'], forecast['main']['temp_min'])
#                     daily_forecast[dt_str]['temp_max'] = max(daily_forecast[dt_str]['temp_max'], forecast['main']['temp_max'])
        
#         today_str = today.strftime('%Y-%m-%d')
#         today_weekday_str = weekdays_kr[today_weekday]
#         forecast_text = f"{today_str}({today_weekday_str}) 기준 {city_info['name']}의 주간 날씨 예보 🌤️\n"
#         weather_emojis = {'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Snow': '❄️', 'Thunderstorm': '⛈️', 'Drizzle': '🌦️', 'Mist': '🌫️'}
        
#         for date, info in daily_forecast.items():
#             weather_emoji = weather_emojis.get(info['weather'].split()[0], '🌤️')
#             forecast_text += (
#                 f"{info['weekday']}: {info['weather']} {weather_emoji} "
#                 f"최저 {info['temp_min']}°C 최고 {info['temp_max']}°C\n"
#             )
        
#         result = forecast_text + "\n더 궁금한 점 있나요? 😊"
#         self.cache.setex(cache_key, self.cache_ttl, result)
#         return result

# # 초기화
# supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
# client = Client()
# weather_api = WeatherAPI()
# naver_request_count = 0
# NAVER_DAILY_LIMIT = 25000
# st.set_page_config(page_title="AI 챗봇", page_icon="🤖")

# # 세션 상태 초기화
# if "is_logged_in" not in st.session_state:
#     st.session_state.is_logged_in = False
#     st.session_state.user_id = None
#     st.session_state.chat_history = []
#     st.session_state.session_id = str(uuid.uuid4())

# # 도시 추출
# CITY_PATTERNS = [
#     re.compile(r'(?:오늘|내일|모레|이번 주|주간)?\s*([가-힣a-zA-Z\s]{2,20}(?:시|군|city)?)의?\s*날씨', re.IGNORECASE),
#     re.compile(r'(?:오늘|내일|모레|이번 주|주간)?\s*([가-힣a-zA-Z\s]{2,20}(?:시|군|city)?)\s*날씨', re.IGNORECASE),
#     re.compile(r'날씨\s*(?:오늘|내일|모레|이번 주|주간)?\s*([가-힣a-zA-Z\s]{2,20}(?:시|군|city)?)', re.IGNORECASE),
# ]
# def extract_city_from_query(query):
#     for pattern in CITY_PATTERNS:
#         match = pattern.search(query)
#         if match:
#             city = match.group(1).strip()
#             if city not in ["오늘", "내일", "모레", "이번 주", "주간", "현재"]:
#                 return city
#     return "서울"

# TIME_CITY_PATTERNS = [
#     re.compile(r'([가-힣a-zA-Z]{2,20}(?:시|군)?)의?\s*시간'),
#     re.compile(r'([가-힣a-zA-Z]{2,20}(?:시|군)?)\s*시간'),
#     re.compile(r'시간\s*([가-힣a-zA-Z\s]{2,20}(?:시|군)?)'),
# ]
# def extract_city_from_time_query(query):
#     for pattern in TIME_CITY_PATTERNS:
#         match = pattern.search(query)
#         if match:
#             city = match.group(1).strip()
#             if city != "현재":
#                 return city
#     return "서울"

# # 시간 정보
# def get_time_by_city(city_name="서울"):
#     city_info = weather_api.get_city_info(city_name)
#     if not city_info:
#         return f"'{city_name}'의 시간 정보를 가져올 수 없습니다."
#     tf = TimezoneFinder()
#     timezone_str = tf.timezone_at(lng=city_info["lon"], lat=city_info["lat"]) or "Asia/Seoul"
#     timezone = pytz.timezone(timezone_str)
#     city_time = datetime.now(timezone)
#     am_pm = "오전" if city_time.strftime("%p") == "AM" else "오후"
#     return f"현재 {city_name} 시간: {city_time.strftime('%Y년 %m월 %d일 %p %I:%M')} ⏰\n더 궁금한 점 있나요? 😊"

# # 사용자 및 채팅 기록 관리
# def create_or_get_user(nickname):
#     user = supabase.table("users").select("*").eq("nickname", nickname).execute()
#     if user.data:
#         return user.data[0]["id"], True
#     new_user = supabase.table("users").insert({"nickname": nickname, "created_at": datetime.now().isoformat()}).execute()
#     return new_user.data[0]["id"], False

# def save_chat_history(user_id, session_id, question, answer, time_taken):
#     supabase.table("chat_history").insert({
#         "user_id": user_id, "session_id": session_id, "question": question,
#         "answer": answer, "time_taken": time_taken, "created_at": datetime.now().isoformat()
#     }).execute()

# def async_save_chat_history(user_id, session_id, question, answer, time_taken):
#     threading.Thread(target=save_chat_history, args=(user_id, session_id, question, answer, time_taken)).start()

# # 의약품 검색
# def get_drug_info(drug_name):
#     cache_key = f"drug:{drug_name}"
#     cached = cache_handler.get(cache_key)
#     if cached:
#         return cached
#     url = 'http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList'
#     params = {'serviceKey': DRUG_API_KEY, 'pageNo': '1', 'numOfRows': '1', 'itemName': urllib.parse.quote(drug_name), 'type': 'json'}
#     try:
#         response = requests.get(url, params=params, timeout=5)
#         response.raise_for_status()
#         data = response.json()
#         if 'body' in data and 'items' in data['body'] and data['body']['items']:
#             item = data['body']['items'][0]
#             def cut_to_sentence(text, max_len=150):
#                 if not text or len(text) <= max_len:
#                     return text
#                 truncated = text[:max_len]
#                 last_punctuation = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'), truncated.rfind(','))
#                 if last_punctuation > 0:
#                     result = truncated[:last_punctuation + 1]
#                     if len(text) > max_len:
#                         result += " 등"
#                     return result
#                 return truncated + "..."
#             efcy = cut_to_sentence(item.get('efcyQesitm', '정보 없음'))
#             use_method = cut_to_sentence(item.get('useMethodQesitm', '정보 없음'))
#             atpn = cut_to_sentence(item.get('atpnQesitm', '정보 없음'))
#             result = (
#                 f"💊 **의약품 정보** 💊\n"
#                 f"✅ **약품명**: {item.get('itemName', '정보 없음')}\n"
#                 f"✅ **제조사**: {item.get('entpName', '정보 없음')}\n"
#                 f"✅ **효능**: {efcy}\n"
#                 f"✅ **용법용량**: {use_method}\n"
#                 f"✅ **주의사항**: {atpn}\n"
#                 f"ℹ️ 자세한 정보는 <a href='https://www.health.kr/searchDrug/search_detail.asp'>약학정보원</a>에서 확인하세요! 🩺\n"
#                 f"더 궁금한 점 있으신가요? 😊"
#             )
#             cache_handler.setex(cache_key, 86400, result)  # 24시간 캐싱
#             return result
#         else:
#             return search_and_summarize_drug(drug_name)
#     except Exception as e:
#         return search_and_summarize_drug(drug_name)

# def search_and_summarize_drug(drug_name):
#     search_results = search_and_summarize(f"{drug_name} 의약품 정보", num_results=5)
#     if not search_results.empty:
#         return f"'{drug_name}' 공식 정보 없음. 웹 검색 요약:\n{get_ai_summary(search_results)}"
#     return f"'{drug_name}' 의약품 정보를 찾을 수 없습니다."

# # Naver API 및 웹 검색
# def get_naver_api_results(query):
#     global naver_request_count
#     if naver_request_count >= NAVER_DAILY_LIMIT:
#         return search_and_summarize(query, num_results=5)
#     enc_text = urllib.parse.quote(query)
#     url = f"https://openapi.naver.com/v1/search/webkr?query={enc_text}&display=10&sort=date"
#     request = urllib.request.Request(url)
#     request.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
#     request.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
#     results = []
#     try:
#         response = urllib.request.urlopen(request)
#         naver_request_count += 1
#         if response.getcode() == 200:
#             data = json.loads(response.read().decode('utf-8'))
#             for item in data.get('items', [])[:5]:
#                 title = re.sub(r'<b>|</b>', '', item['title'])
#                 contents = re.sub(r'<b>|</b>', '', item.get('description', '내용 없음'))[:100] + "..."
#                 results.append({"title": title, "contents": contents, "url": item.get('link', ''), "date": item.get('pubDate', '')})
#     except Exception:
#         return search_and_summarize(query, num_results=5)
#     return pd.DataFrame(results)

# def search_and_summarize(query, num_results=5):
#     data = []
#     with ThreadPoolExecutor() as executor:  # 병렬 처리
#         futures = [executor.submit(requests.get, link, timeout=5) for link in search(query, num_results=num_results)]
#         for future in futures:
#             try:
#                 response = future.result()
#                 soup = BeautifulSoup(response.text, 'html.parser')
#                 title = soup.title.get_text() if soup.title else "No title"
#                 description = ' '.join([p.get_text() for p in soup.find_all('p')[:3]])
#                 data.append({"title": title, "contents": description[:500], "link": response.url})
#             except Exception:
#                 continue
#     return pd.DataFrame(data)

# def get_ai_summary(search_results):
#     if search_results.empty:
#         return "검색 결과를 찾을 수 없습니다."
#     context = "\n".join([f"출처: {row['title']}\n내용: {row['contents']}" for _, row in search_results.iterrows()])
#     response = client.chat.completions.create(
#         model="gpt-4o",
#         messages=[{"role": "user", "content": f"검색 결과를 2~3문장으로 요약:\n{context}"}]
#     )
#     summary = response.choices[0].message.content
#     sources = "\n📜 **출처**\n" + "\n".join([f"🌐 [{row['title']}]({row['link']})" for _, row in search_results.iterrows()])
#     return f"{summary}{sources}\n더 궁금한 점 있나요? 😊"

# # 논문 검색
# # 논문 검색
# def fetch_arxiv_paper(paper):
#     return {
#         "title": paper.title,
#         "authors": ", ".join(str(a) for a in paper.authors),
#         "summary": paper.summary[:200],
#         "entry_id": paper.entry_id,
#         "pdf_url": paper.get_pdf_url(),  # PDF 링크 추가
#         "published": paper.published.strftime('%Y-%m-%d')
#     }

# def get_arxiv_papers(query, max_results=3):
#     cache_key = f"arxiv:{query}:{max_results}"
#     cached = cache_handler.get(cache_key)
#     if cached:
#         return cached
#     search = arxiv.Search(query=query, max_results=max_results, sort_by=arxiv.SortCriterion.SubmittedDate)
#     with ThreadPoolExecutor() as executor:
#         results = list(executor.map(fetch_arxiv_paper, search.results()))
#     if not results:
#         return "해당 키워드로 논문을 찾을 수 없습니다."
#     response = "📚 **Arxiv 논문 검색 결과** 📚\n" + "\n".join(
#         [f"**논문 {i}**\n"
#          f"📄 **제목**: {r['title']}\n"
#          f"👥 **저자**: {r['authors']}\n"
#          f"📝 **초록**: {r['summary']}...\n"
#          f"🔗 **논문 페이지**: {r['entry_id']}\n"
#          f"📥 **PDF 다운로드**: [{r['pdf_url'].split('/')[-1]}]({r['pdf_url']})\n"  # PDF 링크 추가
#          f"📅 **출판일**: {r['published']}\n"
#          f"{'-' * 50}"
#          for i, r in enumerate(results, 1)]
#     ) + "\n더 많은 논문을 보고 싶다면 말씀해 주세요! 😊"
#     cache_handler.setex(cache_key, 3600, response)
#     return response

# # 대화형 응답
# conversation_cache = MemoryCache()
# def get_conversational_response(query, chat_history):
#     cache_key = f"conv:{needs_search(query)}:{query}:{hash(str(chat_history[-5:]))}"
#     cached = conversation_cache.get(cache_key)
#     if cached:
#         return cached
#     messages = [{"role": "system", "content": "친절하고 상호작용적인 AI 챗봇입니다."}] + [
#         {"role": msg["role"], "content": msg["content"]} for msg in chat_history[-5:]
#     ] + [{"role": "user", "content": query}]
#     response = client.chat.completions.create(model="gpt-4", messages=messages)
#     result = response.choices[0].message.content
#     conversation_cache.setex(cache_key, 600, result)
#     return result

# GREETING_RESPONSES = {
#     "안녕": "안녕하세요! 반갑습니다! 😊",
#     "안녕 반가워": "안녕하세요! 저도 반갑습니다! 오늘 기분이 어떠신가요? 😄",
#     "하이": "하이! 좋은 하루 보내세요! 😊",
#     "헬로": "안녕하세요! 반갑습니다! 😊",
#     "헤이": "헤이! 잘 지내세요? 😄",
#     "왓업": "왓업! 뭐하고 계신가요? 😊",
#     "왓썹": "안녕하세요! 오늘 기분이 어떠신가요? 😄",
# }

# # 쿼리 분류
# def needs_search(query):
#     query_lower = query.strip().lower()
#     greeting_keywords = ["안녕", "하이", "반가워", "안뇽", "뭐해", "헬로", "헬롱", "하잇", "헤이", "헤이요", "왓업", "왓썹", "에이요"]
#     emotion_keywords = ["배고프다", "배고프", "졸리다", "피곤하다", "화남", "열받음", "짜증남", "피곤함"]
#     if any(greeting in query_lower for greeting in greeting_keywords) or \
#        any(emo in query_lower for emo in emotion_keywords) or \
#        len(query_lower) <= 3 and "?" not in query_lower:
#         return "conversation"
#     intent_keywords = ["추천해줘", "뭐 먹을까", "메뉴", "뭐할까"]
#     if any(kw in query_lower for kw in intent_keywords):
#         return "conversation"
#     time_keywords = ["현재 시간", "시간", "몇 시", "지금", "몇시", "몇 시야", "지금 시간", "현재", "시계"]
#     if any(keyword in query_lower for keyword in time_keywords) and \
#        any(timeword in query_lower for timeword in ["시간", "몇시", "몇 시", "시계"]):
#         return "time"
#     weather_keywords = ["날씨", "온도", "기온"]
#     if any(keyword in query_lower for keyword in weather_keywords) and "내일" in query_lower:
#         return "tomorrow_weather"
#     elif any(keyword in query_lower for keyword in weather_keywords) and "모레" in query_lower:
#         return "day_after_tomorrow_weather"
#     elif any(keyword in query_lower for keyword in weather_keywords) and ("주간" in query_lower or any(kw in query_lower for kw in ["이번 주", "주간 예보", "주간 날씨"])):
#         return "weekly_forecast"
#     elif any(keyword in query_lower for keyword in weather_keywords):
#         return "weather"
#     drug_keywords = ["약", "의약품", "약품"]
#     drug_pattern = r'^[가-힣a-zA-Z]{2,10}(?:약|정|시럽|캡슐)$'
#     if any(keyword in query_lower for keyword in drug_keywords) and re.match(drug_pattern, query_lower):
#         return "drug"
#     if query_lower == "mbti 검사":
#         return "mbti"
#     if query_lower == "다중지능 검사":
#         return "multi_iq"
#     arxiv_keywords = ["논문검색", "arxiv", "paper", "research"]
#     if any(kw in query_lower for kw in arxiv_keywords) and len(query_lower) > 5:
#         return "arxiv_search"
#     search_keywords = ["검색", "알려줘", "정보", "뭐야", "무엇이야", "무엇인지", "찾아서", "정리해줘", "설명해줘", "알고싶어", "알려줄래"]
#     if any(kw in query_lower for kw in search_keywords) and len(query_lower) > 5:
#         return "web_search"
#     return "general_query"

# # UI 함수
# def show_login_page():
#     st.title("로그인 🤗")
#     with st.form("login_form"):
#         nickname = st.text_input("닉네임", placeholder="예: 후안")
#         if st.form_submit_button("시작하기 🚀") and nickname:
#             user_id, is_existing = create_or_get_user(nickname)
#             st.session_state.user_id = user_id
#             st.session_state.is_logged_in = True
#             st.toast(f"환영합니다, {nickname}님! 🎉")
#             time.sleep(1)
#             st.rerun()

# @st.cache_data(ttl=600)
# def get_cached_response(query):
#     return process_query(query)

# def process_query(query):
#     query_type = needs_search(query)
#     if query_type == "mbti":
#         return (
#             "MBTI 검사를 원하시나요? ✨ 아래 사이트에서 무료로 성격 유형 검사를 할 수 있어요! 😊\n"
#             "[16Personalities MBTI 검사](https://www.16personalities.com/ko/%EB%AC%B4%EB%A3%8C-%EC%84%B1%EA%B2%A9-%EC%9C%A0%ED%98%95-%EA%B2%80%EC%82%AC) 🌟\n"
#             "이 사이트는 16가지 성격 유형을 기반으로 한 테스트를 제공하며, 결과에 따라 성격 설명과 인간관계 조언 등을 확인할 수 있어요! 🧠💡"
#         )
#     elif query_type == "multi_iq":
#         return (
#             "다중지능 검사를 원하시나요? 🎉 아래 사이트에서 무료로 다중지능 테스트를 해볼 수 있어요! 😄\n"
#             "[Multi IQ Test](https://multiiqtest.com/) 🚀\n"
#             "이 사이트는 하워드 가드너의 다중지능 이론을 기반으로 한 테스트를 제공하며, 다양한 지능 영역을 평가해줍니다! 📚✨"
#         )
#     elif query_type == "time":
#         city = extract_city_from_time_query(query)
#         return get_time_by_city(city)
#     elif query_type == "weather":
#         city = extract_city_from_query(query)
#         return weather_api.get_city_weather(city)
#     elif query_type == "tomorrow_weather":
#         city = extract_city_from_query(query)
#         return weather_api.get_forecast_by_day(city, days_from_today=1)
#     elif query_type == "day_after_tomorrow_weather":
#         city = extract_city_from_query(query)
#         return weather_api.get_forecast_by_day(city, days_from_today=2)
#     elif query_type == "weekly_forecast":
#         city = extract_city_from_query(query)
#         return weather_api.get_weekly_forecast(city)
#     elif query_type == "drug":
#         return get_drug_info(query.strip())
#     elif query_type == "conversation":
#         if query.strip() in GREETING_RESPONSES:
#             return GREETING_RESPONSES[query.strip()]
#         return get_conversational_response(query, st.session_state.chat_history)
#     elif query_type == "web_search":
#         language = detect(query)
#         if language == 'ko' and naver_request_count < NAVER_DAILY_LIMIT:
#             return get_ai_summary(get_naver_api_results(query))
#         return get_ai_summary(search_and_summarize(query))
#     elif query_type == "arxiv_search":
#         keywords = query.replace("논문검색", "").replace("arxiv", "").replace("paper", "").replace("research", "").strip()
#         return get_arxiv_papers(keywords)
#     elif query_type == "general_query":
#         return get_conversational_response(query, st.session_state.chat_history)
#     return "아직 지원하지 않는 기능이에요. 😅"

# def show_chat_dashboard():
#     st.title("AI 챗봇 🤖")
#     for msg in st.session_state.chat_history:
#         with st.chat_message(msg['role']):
#             st.markdown(msg['content'], unsafe_allow_html=True)
    
#     if user_prompt := st.chat_input("질문해 주세요!"):
#         st.chat_message("user").markdown(user_prompt)
#         st.session_state.chat_history.append({"role": "user", "content": user_prompt})
#         with st.chat_message("assistant"):
#             placeholder = st.empty()
#             placeholder.markdown("⏳ 응답 생성 중...")
#             start_time = time.time()
#             with ThreadPoolExecutor() as executor:
#                 future = executor.submit(get_cached_response, user_prompt)
#                 response = future.result()
#             time_taken = round(time.time() - start_time, 2)
#             placeholder.markdown(response, unsafe_allow_html=True)
#             st.session_state.chat_history.append({"role": "assistant", "content": response})
#             async_save_chat_history(st.session_state.user_id, st.session_state.session_id, user_prompt, response, time_taken)

# # 메인 실행
# def main():
#     if not st.session_state.is_logged_in:
#         show_login_page()
#     else:
#         show_chat_dashboard()

# if __name__ == "__main__":
#     main()
