# 라이브러리 설정
import streamlit as st
import time
import uuid
from supabase import create_client
import os
from datetime import datetime
import pytz
import logging
import requests
from bs4 import BeautifulSoup
import pandas as pd
from googlesearch import search
from g4f.client import Client
from timezonefinder import TimezoneFinder
import re

# Supabase 설정
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

# Supabase 및 GPT 클라이언트 초기화
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = Client()

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

# 사용자 관리 및 채팅 기록 저장 함수 (변경 없음)
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

# 주요 도시 매핑 (필요 시 참조용으로 유지)
CITY_MAPPING = {
    "서울": "Seoul,KR", "부산": "Busan,KR", "대구": "Daegu,KR", 
    "인천": "Incheon,KR", "광주": "Gwangju,KR", "대전": "Daejeon,KR",
    "울산": "Ulsan,KR", "세종": "Sejong,KR", "제주": "Jeju,KR",
    "뉴욕": "New York,US", "런던": "London,GB", "파리": "Paris,FR",
    "도쿄": "Tokyo,JP", "베이징": "Beijing,CN", "시드니": "Sydney,AU",
    "로마": "Rome,IT", "베를린": "Berlin,DE", "마드리드": "Madrid,ES",
    "상하이": "Shanghai,CN", "홍콩": "Hong Kong,HK", "싱가포르": "Singapore,SG"
}

# OpenWeather Geocoding API로 도시 정보 가져오기
def get_city_info(city_name):
    """
    OpenWeather Geocoding API를 사용해 도시 정보(이름, 국가 코드, 좌표) 반환
    """
    url = "http://api.openweathermap.org/geo/1.0/direct"
    params = {
        'q': city_name,
        'limit': 1,
        'appid': WEATHER_API_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=5)
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
        else:
            logger.warning(f"도시 정보 없음: {city_name}")
            return None
    except Exception as e:
        logger.error(f"Geocoding 실패 ({city_name}): {str(e)}")
        return None

# 날씨 조회 함수 (Geocoding API 활용)
def get_city_weather(city_name):
    """
    OpenWeather API로 날씨 정보를 좌표 기반으로 조회
    """
    city_info = get_city_info(city_name)
    if not city_info:
        return f"'{city_name}'의 날씨 정보를 가져올 수 없습니다. 도시명을 확인해 주세요. ❌"

    url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        'lat': city_info["lat"],
        'lon': city_info["lon"],
        'appid': WEATHER_API_KEY,
        'units': 'metric',
        'lang': 'kr'
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        weather_emojis = {
            'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Snow': '❄️',
            'Thunderstorm': '⛈️', 'Drizzle': '🌦️', 'Mist': '🌫️'
        }
        
        weather_emoji = weather_emojis.get(data['weather'][0]['main'], '🌤️')
        display_name = f"{data['name']}, {data['sys']['country']}"
        
        return (
            f"현재 {display_name} 날씨 정보 {weather_emoji}\n\n"
            f"날씨: {data['weather'][0]['description']}\n"
            f"현재 온도: {data['main']['temp']}°C 🌡️\n"
            f"체감 온도: {data['main']['feels_like']}°C 🤔\n"
            f"최저 온도: {data['main']['temp_min']}°C ⬇️\n"
            f"최고 온도: {data['main']['temp_max']}°C ⬆️\n"
            f"습도: {data['main']['humidity']}% 💧\n"
            f"풍속: {data['wind']['speed']}m/s 🌪️"
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"날씨 API 요청 오류: {str(e)}")
        return f"'{city_name}'의 날씨 정보를 가져올 수 없습니다. ❌"
    except KeyError as e:
        logger.error(f"날씨 데이터 파싱 오류: {str(e)}")
        return f"'{city_name}'의 날씨 데이터 형식이 올바르지 않습니다. ❌"
    except Exception as e:
        logger.error(f"예상치 못한 오류: {str(e)}")
        return f"날씨 정보를 처리하는 중 오류가 발생했습니다. ❌"

# 시간 조회 함수 (Geocoding API 활용)
def get_time_by_city(city_name="서울"):
    """
    OpenWeather Geocoding API로 좌표를 얻어 타임존 계산 후 시간 반환
    """
    city_info = get_city_info(city_name)
    if not city_info:
        return f"'{city_name}'의 시간 정보를 가져올 수 없습니다. 도시명을 확인해 주세요. ❌"

    tf = TimezoneFinder()
    try:
        timezone_str = tf.timezone_at(lng=city_info["lon"], lat=city_info["lat"])
        if not timezone_str:
            logger.warning(f"타임존 찾기 실패, 기본값 사용: Asia/Seoul")
            timezone_str = "Asia/Seoul"
        
        timezone = pytz.timezone(timezone_str)
        city_time = datetime.now(timezone)
        am_pm = "오전" if city_time.strftime("%p") == "AM" else "오후"
        
        return f"현재 {city_name} 시간: {city_time.strftime('%Y년 %m월 %d일')} {am_pm} {city_time.strftime('%I:%M')} ⏰"
    except Exception as e:
        logger.error(f"시간 처리 실패 ({city_name}): {str(e)}")
        return f"'{city_name}'의 시간 정보를 가져올 수 없습니다. ❌"

# 도시명 추출 함수
def extract_city_from_query(query):
    """
    사용자 질의에서 도시명 추출 (한글/영문 모두 지원)
    """
    city_patterns = [
        r'([가-힣a-zA-Z\s]{2,20}(?:시|군|city)?)의?\s*날씨',
        r'([가-힣a-zA-Z\s]{2,20}(?:시|군|city)?)\s*날씨',
        r'날씨\s*([가-힣a-zA-Z\s]{2,20}(?:시|군|city)?)',
        r'weather\s+in\s+([a-zA-Z\s]{2,20})',
        r'([a-zA-Z\s]{2,20})\s+weather'
    ]
    
    for pattern in city_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    for city in CITY_MAPPING.keys():
        if city.lower() in query.lower():
            return city
    
    return "서울"

def extract_city_from_time_query(query):
    """
    시간 관련 쿼리에서 도시명 추출
    """
    city_patterns = [
        r'([가-힣a-zA-Z]{2,20}(?:시|군)?)의?\s*시간',
        r'([가-힣a-zA-Z]{2,20}(?:시|군)?)\s*시간',
        r'시간\s*([가-힣a-zA-Z]{2,20}(?:시|군)?)',
    ]
    
    for pattern in city_patterns:
        match = re.search(pattern, query)
        if match:
            return match.group(1)
    
    return "서울"

# 웹 검색 및 요약 함수 (변경 없음)
def search_and_summarize(query, num_results=5):
    logger.info(f"검색 시작: {query}")
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
                    "description": description[:500]
                })
            except Exception as e:
                logger.error(f"개별 검색 결과 처리 중 오류: {str(e)}")
                continue
        return pd.DataFrame(data)
    except Exception as e:
        logger.error(f"검색 중 오류 발생: {str(e)}")
        return pd.DataFrame()

def get_ai_summary(search_results):
    if search_results.empty:
        return "검색 결과를 찾을 수 없습니다. ❌"
    
    context = "\n\n".join([f"출처: {row['title']}\n내용: {row['description']}" for _, row in search_results.iterrows()])
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": f"다음 검색 결과를 분석하고, 핵심 내용을 2~3문장으로 요약해주세요:\n\n{context}"}]
        )
        summary = response.choices[0].message.content
        sources = "\n\n📚 참고 출처:\n" + "\n".join([f"• [{row['title']}]({row['link']}) 🔗" for _, row in search_results.iterrows()])
        return f"{summary}\n{sources}"
    except Exception as e:
        logger.error(f"AI 요약 중 오류 발생: {str(e)}")
        return "검색 결과 요약 중 오류가 발생했습니다. ❌"

# 쿼리 타입 판단 함수
def needs_search(query):
    time_keywords = ["현재 시간", "시간", "몇 시", "지금", "몇시", "몇 시야", "지금 시간", "현재", "시계"]
    weather_keywords = ["날씨", "온도", "기온"]
    
    if any(keyword in query.lower() for keyword in time_keywords):
        if any(timeword in query.lower() for timeword in ["시간", "몇시", "몇 시", "시계"]):
            return "time"
    if any(keyword in query for keyword in weather_keywords):
        return "weather"
    return "search"

# 로그인 및 대시보드 함수 (변경 없음)
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
                if is_existing:
                    st.success(f"환영합니다, {nickname}님!")
                else:
                    st.success(f"새로운 사용자로 등록되었습니다. 환영합니다, {nickname}님!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"로그인 중 오류가 발생했습니다: {str(e)}")
        elif submit_button:
            st.warning("닉네임을 입력해주세요.")

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
                start_time = time.time()
                query_type = needs_search(user_prompt)
                
                if query_type == "time":
                    city = extract_city_from_time_query(user_prompt)
                    final_response = get_time_by_city(city)
                elif query_type == "weather":
                    city = extract_city_from_query(user_prompt)
                    final_response = get_city_weather(city)
                else:
                    search_results = search_and_summarize(user_prompt)
                    final_response = get_ai_summary(search_results)
                
                end_time = time.time()
                time_taken = round(end_time - start_time, 2)
                
                st.session_state.chat_history.append({"role": "assistant", "content": final_response})
                message_placeholder.markdown(final_response)
                save_chat_history(st.session_state.user_id, st.session_state.session_id, user_prompt, final_response, time_taken)
            except Exception as e:
                error_message = f"❌ 오류 발생: {str(e)}"
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
