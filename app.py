# 라이브러리 설정 (동일)
import streamlit as st
import time
import uuid
import asyncio
import aiohttp
from supabase import create_client
import os
from datetime import datetime
import pytz
import logging
from geopy.geocoders import Nominatim
import requests
from bs4 import BeautifulSoup
import pandas as pd
from googlesearch import search
from g4f.client import Client
from timezonefinder import TimezoneFinder
import re

# Supabase 및 환경 변수 설정 (동일)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = Client()

# 로깅 설정 (동일)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HybridChat")

# 페이지 설정 (동일)
st.set_page_config(page_title="AI 챗봇", page_icon="🤖")

# 세션 상태 초기화 (동일)
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

# 사용자 관리 및 채팅 기록 저장 함수 (동일)
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

# 도시 매핑 및 날씨/시간 함수 (동일, 약간 간소화)
CITY_MAPPING = {
    "서울": "Seoul,KR", "부산": "Busan,KR", "대구": "Daegu,KR",
    "인천": "Incheon,KR", "광주": "Gwangju,KR", "대전": "Daejeon,KR",
    "울산": "Ulsan,KR", "세종": "Sejong,KR", "제주": "Jeju,KR",
    "뉴욕": "New York,US", "런던": "London,GB", "파리": "Paris,FR",
    "도쿄": "Tokyo,JP", "베이징": "Beijing,CN", "시드니": "Sydney,AU"
}

def get_city_code(city_name):
    if city_name in CITY_MAPPING:
        return CITY_MAPPING[city_name]
    geolocator = Nominatim(user_agent="geo_app")
    try:
        location = geolocator.geocode(f"{city_name}, South Korea", language="en") or geolocator.geocode(city_name, language="en")
        if location:
            country_code = location.raw.get('address', {}).get('country_code', '').upper()
            return f"{location.raw.get('display_name').split(',')[0].strip()},{country_code}"
    except Exception as e:
        logger.error(f"도시 코드 변환 실패: {str(e)}")
    return f"{city_name}"

def get_city_weather(city_name):
    city_code = get_city_code(city_name)
    url = "http://api.openweathermap.org/data/2.5/weather"
    params = {'q': city_code, 'appid': WEATHER_API_KEY, 'units': 'metric', 'lang': 'kr'}
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        weather_emojis = {'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Snow': '❄️', 'Thunderstorm': '⛈️', 'Drizzle': '🌦️', 'Mist': '🌫️'}
        weather_emoji = weather_emojis.get(data['weather'][0]['main'], '🌤️')
        display_name = f"{data['name']}, {data['sys']['country']}"
        return (
            f"현재 {display_name} 날씨 정보 {weather_emoji}\n\n"
            f"날씨: {data['weather'][0]['description']}\n"
            f"현재 온도: {data['main']['temp']}°C 🌡️\n"
            f"습도: {data['main']['humidity']}% 💧\n"
            f"풍속: {data['wind']['speed']}m/s 🌪️"
        )
    except Exception as e:
        logger.error(f"날씨 가져오기 실패: {str(e)}")
        return f"'{city_name}'의 날씨 정보를 가져올 수 없습니다. ❌"

def get_time_by_city(city_name="서울"):
    geolocator = Nominatim(user_agent="geo_app")
    tf = TimezoneFinder()
    try:
        location = geolocator.geocode(city_name, timeout=10)
        timezone_str = tf.timezone_at(lng=location.longitude, lat=location.latitude) if location else "Asia/Seoul"
        timezone = pytz.timezone(timezone_str)
        city_time = datetime.now(timezone)
        am_pm = "오전" if city_time.strftime("%p") == "AM" else "오후"
        return f"현재 {city_name} 시간: {city_time.strftime('%Y년 %m월 %d일')} {am_pm} {city_time.strftime('%I:%M')} ⏰"
    except Exception as e:
        logger.error(f"시간 가져오기 실패: {str(e)}")
        return f"{city_name}의 시간 정보를 가져올 수 없습니다. ❌"

# 쿼리 타입 결정 함수 (동일)
def determine_query_type(query):
    time_keywords = ["현재 시간", "시간", "몇 시", "지금", "몇시", "몇 시야"]
    weather_keywords = ["날씨", "온도", "기온"]
    search_topics = ["방법", "활용", "사용법", "개념", "정의", "의미", "차이", "추천"]
    search_actions = [
        "검색", "찾아", "알려줘", "뭐야", "무엇", "뭐니", "설명해줘", "확인해줘", "조사해줘",
        "알아봐", "가르쳐줘", "보여줘", "분석해줘", "정리해줘", "추천해줘", "비교해줘", "해석해줘"
    ]
    technical_pattern = r'[A-Za-z\s]+\d*'

    if any(keyword in query.lower() for keyword in time_keywords):
        return "time"
    if any(keyword in query for keyword in weather_keywords):
        return "weather"
    is_search = any(keyword in query for keyword in search_topics) or any(keyword in query for keyword in search_actions)
    if re.search(technical_pattern, query) and not all(word in ["how", "what", "when", "where", "why"] for word in query.lower().split()):
        is_search = True
    return "search" if is_search else "chat"

# 검색 쿼리 전처리 함수 (동일)
def preprocess_search_query(query):
    remove_suffixes = ["이란", "란", "은", "는", "이나", "나", "을", "를", "에서"]
    for suffix in remove_suffixes:
        if query.endswith(suffix):
            query = query[:-len(suffix)]
    if "방법" in query:
        topic = query.replace("방법", "").strip()
        query = f"how to {topic} tutorial guide"
    elif any(keyword in query for keyword in ["정의", "개념", "의미"]):
        base_topic = query.split()[0]
        query = f"what is {base_topic} definition guide"
    return query

# 동기 검색 함수로 변경 (Streamlit 호환성 확보)
def search_and_summarize(query, num_results=5):
    processed_query = preprocess_search_query(query)
    data = []
    try:
        for link in search(processed_query, num_results=num_results):
            try:
                response = requests.get(link, timeout=5)
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.title.get_text() if soup.title else "No title"
                description = ' '.join([p.get_text().strip() for p in soup.find_all('p')[:3] if len(p.get_text().strip()) > 100])
                data.append({"keyword": query, "link": link, "title": title, "description": description[:800]})
            except Exception as e:
                logger.error(f"페이지 가져오기 실패 ({link}): {str(e)}")
        return pd.DataFrame(data)
    except Exception as e:
        logger.error(f"검색 중 오류: {str(e)}")
        return pd.DataFrame()

# 비동기 GPT 호출 대신 동기 호출로 변경
def get_chat_response(query, chat_history):
    try:
        messages = [{"role": "system", "content": "당신은 친절하고 도움이 되는 AI 어시스턴트입니다. 한국어로 자연스럽게 대화해주세요."}]
        for msg in chat_history[-5:]:
            messages.append({"role": "user" if msg["role"] == "user" else "assistant", "content": msg["content"]})
        messages.append({"role": "user", "content": query})
        response = client.chat.completions.create(model="gpt-4", messages=messages)  # 동기 호출
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"채팅 응답 생성 중 오류: {str(e)}")
        return "죄송합니다. 응답 생성 중 문제가 발생했습니다. 다시 시도해 주세요. ❌"

# 쿼리 처리 함수 (동기 방식으로 수정)
def process_query(query, chat_history):
    query_type = determine_query_type(query)
    start_time = time.time()

    if query_type == "time":
        city = re.search(r'([가-힣a-zA-Z]{2,20}(?:시|군)?)', query)
        response = get_time_by_city(city.group(1) if city else "서울")
    elif query_type == "weather":
        city = re.search(r'([가-힣a-zA-Z\s]{2,20}(?:시|군|city)?)', query)
        response = get_city_weather(city.group(1) if city else "서울")
    elif query_type == "search":
        search_results = search_and_summarize(query)
        if search_results.empty:
            response = "검색 결과를 찾을 수 없습니다. ❌"
        else:
            context = "\n\n".join([f"출처: {row['title']}\n내용: {row['description']}" for _, row in search_results.iterrows()])
            response_content = get_chat_response(f"다음 검색 결과를 2~3문장으로 요약:\n\n{context}", chat_history)
            response = response_content + "\n\n📚 출처:\n" + "\n".join([f"• [{row['title']}]({row['link']})" for _, row in search_results.iterrows()])
    else:  # chat
        response = get_chat_response(query, chat_history)

    time_taken = round(time.time() - start_time, 2)
    return response, time_taken

# 로그인 페이지 (동일)
def show_login_page():
    st.title("AI 챗봇 로그인 🤖")
    with st.form("login_form"):
        nickname = st.text_input("닉네임을 입력하세요", placeholder="예: AI Lover")
        submit_button = st.form_submit_button("시작하기")
        if submit_button and nickname:
            try:
                user_id, is_existing = create_or_get_user(nickname)
                st.session_state.user_id = user_id
                st.session_state.is_logged_in = True
                st.success(f"{nickname}님, 환영합니다!" if is_existing else f"새로운 사용자로 등록되었습니다. 환영합니다, {nickname}님!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"로그인 중 오류: {str(e)}")

# 메인 채팅 대시보드 (동기 방식으로 수정)
def show_chat_dashboard():
    st.title("AI 챗봇 🤖")
    for message in st.session_state.chat_history:
        with st.chat_message(message['role']):
            st.markdown(message['content'])

    user_prompt = st.chat_input("질문해 주세요!")
    if user_prompt:
        st.chat_message("user").markdown(user_prompt)
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            message_placeholder.markdown("⏳ 응답 생성 중...")
            try:
                final_response, time_taken = process_query(user_prompt, st.session_state.chat_history)
                message_placeholder.markdown(final_response)
                st.session_state.chat_history.append({"role": "assistant", "content": final_response})
                save_chat_history(st.session_state.user_id, st.session_state.session_id, user_prompt, final_response, time_taken)
            except Exception as e:
                error_message = f"❌ 오류 발생: {str(e)}"
                logger.error(error_message)
                message_placeholder.markdown(error_message)
                st.session_state.chat_history.append({"role": "assistant", "content": error_message})

# 메인 실행 부분 (동일)
def main():
    init_session_state()
    if not st.session_state.is_logged_in:
        show_login_page()
    else:
        show_chat_dashboard()

if __name__ == "__main__":
    main()
