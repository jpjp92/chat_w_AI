# 라이브러리 설정
import streamlit as st
import time
import uuid
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

# Supabase 설정
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

# Supabase 클라이언트 초기화
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# GPT-4 클라이언트 초기화
client = Client()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HybridChat")

# 페이지 설정
st.set_page_config(
    page_title="AI 챗봇",
    page_icon="🤖",
    layout="wide"
)

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

# 사용자 관리 함수
def create_or_get_user(nickname):
    try:
        # 기존 사용자 검색
        user = supabase.table("users").select("*").eq("nickname", nickname).execute()
        
        if user.data:
            return user.data[0]["id"], True
        
        # 새 사용자 생성
        new_user = supabase.table("users").insert({
            "nickname": nickname,
            "created_at": datetime.now().isoformat()
        }).execute()
        
        return new_user.data[0]["id"], False
        
    except Exception as e:
        logger.error(f"사용자 생성/조회 중 오류 발생: {str(e)}")
        raise Exception("사용자 처리 중 오류가 발생했습니다.")

# 채팅 기록 저장 함수
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

# 주요 도시 매핑 확장 (한국어 - 영어)
CITY_MAPPING = {
    # 한국 도시
    "서울": "Seoul,KR", "부산": "Busan,KR", "대구": "Daegu,KR", 
    "인천": "Incheon,KR", "광주": "Gwangju,KR", "대전": "Daejeon,KR",
    "울산": "Ulsan,KR", "세종": "Sejong,KR", "제주": "Jeju,KR",
    # 해외 주요 도시
    "뉴욕": "New York,US", "런던": "London,GB", "파리": "Paris,FR",
    "도쿄": "Tokyo,JP", "베이징": "Beijing,CN", "시드니": "Sydney,AU",
    "로마": "Rome,IT", "베를린": "Berlin,DE", "마드리드": "Madrid,ES",
    "상하이": "Shanghai,CN", "홍콩": "Hong Kong,HK", "싱가포르": "Singapore,SG"
}

# 날씨 관련 함수들
def get_city_code(city_name):
    """
    도시명을 받아서 OpenWeather API용 도시 코드를 반환
    한글, 영문 도시명 모두 처리
    """
    # 이미 매핑된 도시인 경우
    if city_name in CITY_MAPPING:
        return CITY_MAPPING[city_name]
    
    # 영문으로 입력된 경우 (예: "New York", "London" 등)
    if all(ord(c) < 128 for c in city_name):
        return f"{city_name},US" if "," not in city_name else city_name
    
    # 한글 도시명을 영문으로 변환 시도
    geolocator = Nominatim(user_agent="geo_app")
    try:
        # 먼저 한국 도시로 검색
        location = geolocator.geocode(f"{city_name}, South Korea", language="en")
        if location:
            return f"{location.raw.get('display_name').split(',')[0].strip()},KR"
            
        # 전 세계 도시로 검색
        location = geolocator.geocode(city_name, language="en")
        if location:
            country_code = location.raw.get('address', {}).get('country_code', '').upper()
            city_name = location.raw.get('display_name').split(',')[0].strip()
            return f"{city_name},{country_code}" if country_code else city_name
            
    except Exception as e:
        logger.error(f"도시 코드 변환 실패: {str(e)}")
        
    return f"{city_name}"


def get_english_city_name(korean_city_name):
    """
    한국어 도시명을 영어로 변환
    """
    # 먼저 매핑된 도시인지 확인
    if korean_city_name in CITY_MAPPING:
        return CITY_MAPPING[korean_city_name]
    
    geolocator = Nominatim(user_agent="geo_app")
    try:
        # 첫 번째 시도: 도시명 + South Korea로 검색
        location = geolocator.geocode(f"{korean_city_name}, South Korea", language="en")
        if location and location.raw.get('display_name'):
            display_name = location.raw['display_name']
            city_name = display_name.split(',')[0].strip()
            return city_name if city_name else korean_city_name
            
        # 두 번째 시도: "시" 접미사 추가
        location_with_si = geolocator.geocode(f"{korean_city_name}시, South Korea", language="en")
        if location_with_si and location_with_si.raw.get('display_name'):
            display_name = location_with_si.raw['display_name']
            city_name = display_name.split(',')[0].strip()
            return city_name if city_name else korean_city_name
            
    except Exception as e:
        logger.error(f"도시 변환 실패: {str(e)}")
        
    return korean_city_name

def get_city_weather(city_name):
    """
    OpenWeather API에서 지정된 도시의 날씨 정보를 조회
    국내외 도시 모두 지원
    """
    city_code = get_city_code(city_name)
    url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        'q': city_code,
        'appid': WEATHER_API_KEY,
        'units': 'metric',
        'lang': 'kr'
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        weather_emojis = {
            'Clear': '☀️',
            'Clouds': '☁️',
            'Rain': '🌧️',
            'Snow': '❄️',
            'Thunderstorm': '⛈️',
            'Drizzle': '🌦️',
            'Mist': '🌫️'
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
# def get_city_weather(city_name):
#     """
#     OpenWeather API에서 지정된 도시의 날씨 정보를 조회
#     """
#     # 한글 도시명일 경우 변환
#     if any(char.isalpha() and ord(char) > 127 for char in city_name):
#         english_city = get_english_city_name(city_name)
#         if not english_city:
#             return f"'{city_name}'의 날씨 정보를 찾을 수 없습니다. ❌"
#         city_name = english_city
    
#     full_city_query = f"{city_name},KR"
#     url = "http://api.openweathermap.org/data/2.5/weather"
#     params = {
#         'q': full_city_query,
#         'appid': WEATHER_API_KEY,
#         'units': 'metric',
#         'lang': 'kr'
#     }
    
#     try:
#         response = requests.get(url, params=params, timeout=5)
#         response.raise_for_status()
#         data = response.json()
        
#         weather_emojis = {
#             'Clear': '☀️',
#             'Clouds': '☁️',
#             'Rain': '🌧️',
#             'Snow': '❄️',
#             'Thunderstorm': '⛈️',
#             'Drizzle': '🌦️',
#             'Mist': '🌫️'
#         }
        
#         weather_emoji = weather_emojis.get(data['weather'][0]['main'], '🌤️')
        
#         return (
#             f"현재 {city_name} 날씨 정보 {weather_emoji}\n\n"
#             f"날씨: {data['weather'][0]['description']}\n"
#             f"현재 온도: {data['main']['temp']}°C 🌡️\n"
#             f"체감 온도: {data['main']['feels_like']}°C 🤔\n"
#             f"최저 온도: {data['main']['temp_min']}°C ⬇️\n"
#             f"최고 온도: {data['main']['temp_max']}°C ⬆️\n"
#             f"습도: {data['main']['humidity']}% 💧\n"
#             f"풍속: {data['wind']['speed']}m/s 🌪️"
#         )
#     except requests.exceptions.RequestException as e:
#         logger.error(f"날씨 API 요청 오류: {str(e)}")
#         return f"'{city_name}'의 날씨 정보를 가져올 수 없습니다. ❌"
#     except KeyError as e:
#         logger.error(f"날씨 데이터 파싱 오류: {str(e)}")
#         return f"'{city_name}'의 날씨 데이터 형식이 올바르지 않습니다. ❌"
#     except Exception as e:
#         logger.error(f"예상치 못한 오류: {str(e)}")
#         return f"날씨 정보를 처리하는 중 오류가 발생했습니다. ❌"

def extract_city_from_query(query):
    """
    사용자 질의에서 도시명 추출 (한글/영문 모두 지원)
    """
    import re
    
    # 도시명 패턴: 한글 2-4글자 또는 영문 2-20글자 + 선택적 '시'/'군'/'city'
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
    
    # 매핑된 도시명 검색
    for city in CITY_MAPPING.keys():
        if city.lower() in query.lower():
            return city
    
    return "서울"  # 기본값
    
# def extract_city_from_query(query):
#     """
#     사용자 질의에서 도시명 추출
#     """
#     import re
    
#     # 도시명 패턴: 2-4글자 한글 + 선택적 '시'/'군'
#     city_patterns = [
#         r'([가-힣]{2,4}(?:시|군)?)의?\s*날씨',
#         r'([가-힣]{2,4}(?:시|군)?)\s*날씨',
#         r'날씨\s*([가-힣]{2,4}(?:시|군)?)',
#     ]
    
#     for pattern in city_patterns:
#         match = re.search(pattern, query)
#         if match:
#             return match.group(1)
    
#     # 매핑된 도시명 검색
#     for city in CITY_MAPPING.keys():
#         if city in query:
#             return city
    
#     return "서울"  # 기본값

# 시간 관련 함수들 수정
def get_timezone_by_city(city_name):
    """
    도시명을 입력받아 해당 지역의 타임존 반환
    """
    geolocator = Nominatim(user_agent="geo_app")
    tf = TimezoneFinder()
    
    try:
        location = geolocator.geocode(city_name, timeout=10)
        if location:
            timezone_str = tf.timezone_at(lng=location.longitude, lat=location.latitude)
            if timezone_str:
                return pytz.timezone(timezone_str)
    except Exception as e:
        logger.error(f"시간대 찾기 실패 ({city_name}): {str(e)}")
    
    return pytz.timezone("Asia/Seoul")  # 기본값: 서울

def get_time_by_city(city_name="서울"):
    """
    지정된 도시의 현재 시간을 반환
    """
    try:
        timezone = get_timezone_by_city(city_name)
        city_time = datetime.now(timezone)
        am_pm = "오전" if city_time.strftime("%p") == "AM" else "오후"
        
        return (f"현재 시간은 {city_name} 기준 {city_time.strftime('%Y년 %m월 %d일')} "
                f"{am_pm} {city_time.strftime('%I:%M')}입니다. ⏰")
    except Exception as e:
        logger.error(f"시간 가져오기 실패 ({city_name}): {str(e)}")
        return f"{city_name}의 시간 정보를 가져올 수 없습니다. 다시 시도해 주세요. ❌"

def extract_city_from_time_query(query):
    """
    시간 관련 쿼리에서 도시명 추출
    """
    import re
    
    # 도시명 패턴: 2-20글자 문자 + 선택적 '시'/'군'
    city_patterns = [
        r'([가-힣a-zA-Z]{2,20}(?:시|군)?)의?\s*시간',
        r'([가-힣a-zA-Z]{2,20}(?:시|군)?)\s*시간',
        r'시간\s*([가-힣a-zA-Z]{2,20}(?:시|군)?)',
    ]
    
    for pattern in city_patterns:
        match = re.search(pattern, query)
        if match:
            return match.group(1)
    
    return "서울"  # 기본값

# # 시간 관련 함수
# def get_korea_time():
#     seoul_tz = pytz.timezone("Asia/Seoul")
#     seoul_time = datetime.now(seoul_tz)
#     am_pm = "오전" if seoul_time.strftime("%p") == "AM" else "오후"
#     return f"현재 시간은 대한민국 기준 {seoul_time.strftime('%Y년 %m월 %d일')} {am_pm} {seoul_time.strftime('%I:%M')}입니다. ⏰"

# 웹 검색 관련 함수들
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
    
    context = "\n\n".join([
        f"출처: {row['title']}\n내용: {row['description']}"
        for _, row in search_results.iterrows()
    ])
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",  # gpt-4o를 gpt-4로 수정
            messages=[{
                "role": "user",
                "content": f"다음 검색 결과를 분석하고, 핵심 내용을 2~3문장으로 논리적으로 요약해주세요:\n\n{context}"
            }]
        )
        
        summary = response.choices[0].message.content
        sources = "\n\n📚 참고 출처:\n" + "\n".join([
            f"• [{row['title']}]({row['link']}) 🔗" 
            for _, row in search_results.iterrows()
        ])
        
        return f"{summary}\n{sources}"
    except Exception as e:
        logger.error(f"AI 요약 중 오류 발생: {str(e)}")
        return "검색 결과 요약 중 오류가 발생했습니다. ❌"

# 쿼리 분석 함수들
def extract_city_from_query(query):
    import re
    city_pattern = r'([가-힣]{2,4}(?:시|군)?)'
    
    match = re.search(f'{city_pattern}\\s*날씨', query)
    if match:
        return match.group(1)
    
    match = re.search(f'{city_pattern}의\\s*날씨', query)
    if match:
        return match.group(1)
    
    return "서울"

# needs_search 함수 수정
def needs_search(query):
    time_keywords = [
        "현재 시간", "시간", "몇 시", "지금", "시간", "몇시", 
        "몇 시야", "지금 시간", "현재", "시계"
    ]
    
    weather_keywords = ["날씨", "온도", "기온"]
    
    if any(keyword in query.lower() for keyword in time_keywords):
        if any(timeword in query.lower() for timeword in ["시간", "몇시", "몇 시", "시계"]):
            return "time"
    
    if any(keyword in query for keyword in weather_keywords):
        return "weather"
        
    return "search"


# def needs_search(query):
#     time_keywords = [
#         "현재 시간", "서울 시간", "한국 시간", "오늘 시간", "몇 시", 
#         "지금", "시간", "몇시", "몇 시야", "지금 시간",
#         "현재", "시계", "한국", "서울", "대한민국",
#         "지금 몇 시"
#     ]
    
#     weather_keywords = ["날씨", "온도", "기온"]
    
#     if any(keyword in query.lower() for keyword in time_keywords):
#         if any(timeword in query.lower() for timeword in ["시간", "몇시", "몇 시", "시계"]):
#             return "time"
    
#     if any(keyword in query for keyword in weather_keywords):
#         return "weather"
        
#     return "search"

# 로그인 페이지
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

# 메인 채팅 대시보드
def show_chat_dashboard():
    st.title("AI 챗봇 🤖")
    
    # 채팅 기록 출력
    for message in st.session_state.chat_history:
        with st.chat_message(message['role']):
            st.markdown(message['content'])
    
    # 사용자 입력
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
    # if user_prompt:
    #     st.chat_message("user").markdown(user_prompt)
    #     st.session_state.chat_history.append({"role": "user", "content": user_prompt})
        
    #     with st.chat_message("assistant"):
    #         message_placeholder = st.empty()
    #         message_placeholder.markdown("⏳ 응답 생성 중...")
            
    #         try:
    #             start_time = time.time()
    #             query_type = needs_search(user_prompt)
                
    #             if query_type == "time":
    #                 final_response = get_korea_time()
    #             elif query_type == "weather":
    #                 city = extract_city_from_query(user_prompt)
    #                 final_response = get_city_weather(city)
    #             else:
    #                 search_results = search_and_summarize(user_prompt)
    #                 final_response = get_ai_summary(search_results)
                
                end_time = time.time()
                time_taken = round(end_time - start_time, 2)
                
                st.session_state.chat_history.append({"role": "assistant", "content": final_response})
                message_placeholder.markdown(final_response)
                
                # 채팅 기록 저장
                save_chat_history(
                    st.session_state.user_id,
                    st.session_state.session_id,
                    user_prompt,
                    final_response,
                    time_taken
                )
                
            except Exception as e:
                error_message = f"❌ 오류 발생: {str(e)}"
                logger.error(error_message)
                message_placeholder.markdown(error_message)
                st.session_state.chat_history.append({"role": "assistant", "content": error_message})

# 메인 실행 부분
def main():
    init_session_state()
    
    if not st.session_state.is_logged_in:
        show_login_page()
    else:
        show_chat_dashboard()

# 스크립트가 직접 실행될 때만 main() 함수 호출
if __name__ == "__main__":
    main()
