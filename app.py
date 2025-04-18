# 환경 변수 및 설정
from config.imports import *
from config.env import *

# 로깅 설정
logging.basicConfig(level=logging.WARNING if os.getenv("ENV") == "production" else logging.INFO)
logger = logging.getLogger("HybridChat")
logging.getLogger("streamlit").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

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

# MBTI 및 다중지능 데이터
mbti_descriptions = {
    "ISTJ": "(현실주의자) 🏛️📚🧑‍⚖️: 원칙을 중시하며 꼼꼼한 계획으로 목표를 달성!",
    "ISFJ": "(따뜻한 수호자) 🛡️🧸💖: 타인을 배려하며 헌신적인 도움을 주는 성격!",
    "INFJ": "(신비로운 조언자) 🌿🔮📖: 깊은 통찰력으로 사람들에게 영감을 주는 이상주의자!",
    "INTJ": "(전략가) 🧠♟️📈: 미래를 설계하며 목표를 향해 나아가는 마스터마인드!",
    "ISTP": "(만능 재주꾼) 🔧🕶️🏍️: 문제를 실질적으로 해결하는 실용적인 모험가!",
    "ISFP": "(예술가) 🎨🎵🦋: 감성을 표현하며 자유로운 삶을 추구하는 예술가!",
    "INFP": "(이상주의자) 🌌📜🕊️: 내면의 가치를 중시하며 세상을 더 나은 곳으로 만드는 몽상가!",
    "INTP": "(논리적인 철학자) 🤔📖⚙️: 호기심 많고 논리적으로 세상을 탐구하는 사색가!",
    "ESTP": "(모험가) 🏎️🔥🎤: 순간을 즐기며 도전과 모험을 사랑하는 활동가!",
    "ESFP": "(사교적인 연예인) 🎭🎤🎊: 사람들과 함께하며 분위기를 띄우는 파티의 중심!",
    "ENFP": "(자유로운 영혼) 🌈🚀💡: 창의적인 아이디어로 세상을 밝히는 열정적인 영혼!",
    "ENTP": "(토론가) 🗣️⚡♟️: 새로운 아이디어를 탐구하며 논쟁을 즐기는 혁신가!",
    "ESTJ": "(엄격한 관리자) 🏗️📊🛠️: 체계적으로 목표를 달성하는 리더십의 대가!",
    "ESFJ": "(친절한 외교관) 💐🤗🏡: 사람들을 연결하며 따뜻한 공동체를 만드는 외교관!",
    "ENFJ": "(열정적인 리더) 🌟🎤🫶: 타인을 이끌며 긍정적인 변화를 만드는 카리스마 리더!",
    "ENTJ": "(야망가) 👑📈🔥: 목표를 향해 돌진하며 큰 그림을 그리는 지휘관!"
}

multi_iq_descriptions = {
    "언어지능": {
        "description": "📝📚📢: 말과 글을 통해 생각을 표현하는 데 탁월!\n",
        "jobs": "소설가, 시인, 작가, 논설 / 동화 작가, 방송작가, 영화대본작가, 웹툰 작가 / 아나운서, 리포터, 성우 / 교사, 교수, 강사, 독서 지도사 / 언어치료사, 심리치료사, 구연동화가"
    },
    "논리수학지능": {
        "description": "🧮📊🧠: 분석적 사고와 문제 해결 능력이 뛰어남!\n",
        "jobs": "과학자, 물리학자, 수학자 / 의료공학, 전자공학, 컴퓨터 공학, 항공우주공학 / 애널리스트, 경영 컨설팅, 회계사, 세무사 / 투자분석가, M&A 전문가 / IT 컨설팅, 컴퓨터 프로그래머, web 개발 / 통신 신호처리, 통계학, AI 개발, 정보처리, 빅데이터 업무 / 은행원, 금융기관, 강사, 비평가, 논설 / 변호사, 변리사, 검사, 판사 / 의사, 건축가, 설계사"
    },
    "공간지능": {
        "description": "🎨📸🏛️: 그림과 디자인으로 공간을 아름답게 표현!\n",
        "jobs": "사진사, 촬영기사, 만화가, 애니메이션, 화가, 아티스트 / 건축 설계, 인테리어, 디자이너 / 지도 제작, 엔지니어, 발명가 / 전자공학, 기계공학, 통신공학, 산업공학, 로봇 개발 / 영화감독, 방송 피디, 푸드스타일리스트 / 광고 제작, 인쇄 업무"
    },
    "음악지능": {
        "description": "🎶🎧🎸: 소리와 리듬을 느끼고 창조하는 음악적 재능!\n",
        "jobs": "음악교사, 음향사, 작곡가, 작사가, 편곡가, 가수, 성악가 / 악기 연주 / 동시통역사, 성우 / 뮤지컬 배우 / 발레, 무용 / 음향 부문, 연예 기획사 / DJ, 개인 음악 방송, 가수 매니지먼트"
    },
    "신체운동지능": {
        "description": "🏀🤸‍♂️🏆: 몸을 활용해 스포츠와 움직임에서 두각!\n",
        "jobs": "외과의사, 치기공사, 한의사, 수의사, 간호사, 대체의학 / 물리치료사, 작업치료사 / 악기 연주, 성악가, 가수, 무용, 연극 / 스포츠, 체육교사, 모델 / 경찰, 경호원, 군인, 소방관 / 농업, 임업, 수산업, 축산업 / 공예, 액세서리 제작, 가구 제작"
    },
    "대인관계지능": {
        "description": "🤝🗣️💬: 사람들과 소통하며 관계를 잘 맺는 능력!\n",
        "jobs": "변호사, 검사, 판사, 법무사 / 교사, 교수, 강사 / 홍보 업무, 마케팅 / 지배인, 비서, 승무원, 판매업무 / 기자, 리포터, 보험서비스 / 외교관, 국제공무원, 경찰 / 병원코디네이터, 간호사 / 호텔리어, 학습지 교사, 웨딩플래너, 웃음치료사, 성직자"
    },
    "자기이해지능": {
        "description": "🧘‍♂️💭📖: 자신을 깊이 이해하고 성찰하는 내면의 힘!\n",
        "jobs": "변호사, 검사, 판사, 변리사, 평론가, 논설 / 교사, 교수, 심리상담사 / 스포츠 감독, 코치, 심판, 스포츠 해설가 / 협상가, CEO, CTO, 컨설팅, 마케팅, 회사 경영 / 기자, 아나운서, 요리사, 심사위원 / 의사, 제약 분야 연구원 / 성직자, 철학자, 투자분석가, 자산관리 / 영화감독, 작가, 건축가"
    },
    "자연친화지능": {
        "description": "🌿🐦🌍: 자연과 동물을 사랑하며 환경에 민감한 재능!\n",
        "jobs": "의사, 간호사, 물리치료, 임상병리 / 수의사, 동물 사육, 곤충 사육 / 건축 설계, 감리, 측량사, 조경 디자인 / 천문학자, 지질학자 / 생명공학, 기계 공학, 생물공학, 전자공학 / 의사, 간호사, 약제사, 임상병리 / 특수작물 재배, 농업, 임업, 축산업, 원예, 플로리스트"
    }
}

mbti_full_description = """
### 📝 MBTI 유형별 한 줄 설명
#### 🔥 외향형 (E) vs ❄️ 내향형 (I)  
- **E (외향형)** 🎉🗣️🚀🌞: 사람들과 어울리며 에너지를 얻는 사교적인 성격!  
- **I (내향형)** 📚🛋️🌙🤫: 혼자만의 시간을 즐기며 내면에 집중하는 성격!  
#### 📊 직관형 (N) vs 🧐 감각형 (S)  
- **N (직관형)** 💡✨🎨🔮: 창의적이고 큰 그림을 보며 아이디어를 중시!  
- **S (감각형)** 🔎📏🛠️🍽️: 현실적이고 구체적인 정보를 바탕으로 행동!  
#### 🤝 감정형 (F) vs ⚖️ 사고형 (T)  
- **F (감정형)** ❤️🥰🌸🫂: 공감과 사람 중심으로 따뜻한 결정을 내림!  
- **T (사고형)** 🧠⚙️📊📏: 논리와 객관적 판단으로 문제를 해결!  
#### ⏳ 판단형 (J) vs 🌊 인식형 (P)  
- **J (계획형)** 📅📌📝✅: 체계적이고 계획적으로 일을 처리하는 스타일!  
- **P (즉흥형)** 🎭🎢🌪️🌍: 유연하고 변화에 잘 적응하는 자유로운 스타일!  
#### 🎭 MBTI 유형별 한 줄 설명  
- ✅ **ISTJ** (현실주의자) 🏛️📚🧑‍⚖️: 원칙을 중시하며 꼼꼼한 계획으로 목표를 달성!  
- ✅ **ISFJ** (따뜻한 수호자) 🛡️🧸💖: 타인을 배려하며 헌신적인 도움을 주는 성격!  
- ✅ **INFJ** (신비로운 조언자) 🌿🔮📖: 깊은 통찰력으로 사람들에게 영감을 주는 이상주의자!  
- ✅ **INTJ** (전략가) 🧠♟️📈: 미래를 설계하며 목표를 향해 나아가는 마스터마인드!  
- ✅ **ISTP** (만능 재주꾼) 🔧🕶️🏍️: 문제를 실질적으로 해결하는 실용적인 모험가!  
- ✅ **ISFP** (예술가) 🎨🎵🦋: 감성을 표현하며 자유로운 삶을 추구하는 예술가!  
- ✅ **INFP** (이상주의자) 🌌📜🕊️: 내면의 가치를 중시하며 세상을 더 나은 곳으로 만드는 몽상가!  
- ✅ **INTP** (논리적인 철학자) 🤔📖⚙️: 호기심 많고 논리적으로 세상을 탐구하는 사색가!  
- ✅ **ESTP** (모험가) 🏎️🔥🎤: 순간을 즐기며 도전과 모험을 사랑하는 활동가!  
- ✅ **ESFP** (사교적인 연예인) 🎭🎤🎊: 사람들과 함께하며 분위기를 띄우는 파티의 중심!  
- ✅ **ENFP** (자유로운 영혼) 🌈🚀💡: 창의적인 아이디어로 세상을 밝히는 열정적인 영혼!  
- ✅ **ENTP** (토론가) 🗣️⚡♟️: 새로운 아이디어를 탐구하며 논쟁을 즐기는 혁신가!  
- ✅ **ESTJ** (엄격한 관리자) 🏗️📊🛠️: 체계적으로 목표를 달성하는 리더십의 대가!  
- ✅ **ESFJ** (친절한 외교관) 💐🤗🏡: 사람들을 연결하며 따뜻한 공동체를 만드는 외교관!  
- ✅ **ENFJ** (열정적인 리더) 🌟🎤🫶: 타인을 이끌며 긍정적인 변화를 만드는 카리스마 리더!  
- ✅ **ENTJ** (야망가) 👑📈🔥: 목표를 향해 돌진하며 큰 그림을 그리는 지휘관!
"""

multi_iq_full_description = """
### 🎨 다중지능 유형별 한 줄 설명 및 추천 직업  
- 📖 **언어 지능** 📝📚📢: 말과 글을 통해 생각을 표현하는 데 탁월!  
    - **추천 직업**: 소설가, 시인, 작가, 논설 / 동화 작가, 방송작가, 영화대본작가, 웹툰 작가 / 아나운서, 리포터, 성우 / 교사, 교수, 강사, 독서 지도사 / 언어치료사, 심리치료사, 구연동화가  
- 🔢 **논리-수학 지능** 🧮📊🧠: 분석적 사고와 문제 해결 능력이 뛰어남!  
    - **추천 직업**: 과학자, 물리학자, 수학자 / 의료공학, 전자공학, 컴퓨터 공학, 항공우주공학 / 애널리스트, 경영 컨설팅, 회계사, 세무사 / 투자분석가, M&A 전문가 / IT 컨설팅, 컴퓨터 프로그래머, web 개발 / 통신 신호처리, 통계학, AI 개발, 정보처리, 빅데이터 업무 / 은행원, 금융기관, 강사, 비평가, 논설 / 변호사, 변리사, 검사, 판사 / 의사, 건축가, 설계사  
- 🎨 **공간 지능** 🎨📸🏛️: 그림과 디자인으로 공간을 아름답게 표현!  
    - **추천 직업**: 사진사, 촬영기사, 만화가, 애니메이션, 화가, 아티스트 / 건축 설계, 인테리어, 디자이너 / 지도 제작, 엔지니어, 발명가 / 전자공학, 기계공학, 통신공학, 산업공학, 로봇 개발 / 영화감독, 방송 피디, 푸드스타일리스트 / 광고 제작, 인쇄 업무  
- 🎵 **음악 지능** 🎶🎧🎸: 소리와 리듬을 느끼고 창조하는 음악적 재능!  
    - **추천 직업**: 음악교사, 음향사, 작곡가, 작사가, 편곡가, 가수, 성악가 / 악기 연주 / 동시통역사, 성우 / 뮤지컬 배우 / 발레, 무용 / 음향 부문, 연예 기획사 / DJ, 개인 음악 방송, 가수 매니지먼트  
- 🏃 **신체-운동 지능** 🏀🤸‍♂️🏆: 몸을 활용해 스포츠와 움직임에서 두각!  
    - **추천 직업**: 외과의사, 치기공사, 한의사, 수의사, 간호사, 대체의학 / 물리치료사, 작업치료사 / 악기 연주, 성악가, 가수, 무용, 연극 / 스포츠, 체육교사, 모델 / 경찰, 경호원, 군인, 소방관 / 농업, 임업, 수산업, 축산업 / 공예, 액세서리 제작, 가구 제작  
- 🤝 **대인관계 지능** 🤝🗣️💬: 사람들과 소통하며 관계를 잘 맺는 능력!  
    - **추천 직업**: 변호사, 검사, 판사, 법무사 / 교사, 교수, 강사 / 홍보 업무, 마케팅 / 지배인, 비서, 승무원, 판매업무 / 기자, 리포터, 보험서비스 / 외교관, 국제공무원, 경찰 / 병원코디네이터, 간호사 / 호텔리어, 학습지 교사, 웨딩플래너, 웃음치료사, 성직자  
- 🧘 **자기 이해 지능** 🧘‍♂️💭📖: 자신을 깊이 이해하고 성찰하는 내면의 힘!  
    - **추천 직업**: 변호사, 검사, 판사, 변리사, 평론가, 논설 / 교사, 교수, 심리상담사 / 스포츠 감독, 코치, 심판, 스포츠 해설가 / 협상가, CEO, CTO, 컨설팅, 마케팅, 회사 경영 / 기자, 아나운서, 요리사, 심사위원 / 의사, 제약 분야 연구원 / 성직자, 철학자, 투자분석가, 자산관리 / 영화감독, 작가, 건축가  
- 🌱 **자연 친화 지능** 🌿🐦🌍: 자연과 동물을 사랑하며 환경에 민감한 재능!  
    - **추천 직업**: 의사, 간호사, 물리치료, 임상병리 / 수의사, 동물 사육, 곤충 사육 / 건축 설계, 감리, 측량사, 조경 디자인 / 천문학자, 지질학자 / 생명공학, 기계 공학, 생물공학, 전자공학 / 의사, 간호사, 약제사, 임상병리 / 특수작물 재배, 농업, 임업, 축산업, 원예, 플로리스트  
"""

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
        try:
            response = session.get(url, params=params, timeout=3)
            response.raise_for_status()
            return response.json()
        except:
            return self.cache.get(f"weather:{params.get('q', '')}") or "날씨 정보를 불러올 수 없습니다."

    @lru_cache(maxsize=100)
    def get_city_info(self, city_name):
        cache_key = f"city_info:{city_name}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        url = "http://api.openweathermap.org/geo/1.0/direct"
        params = {'q': city_name, 'limit': 1, 'appid': WEATHER_API_KEY}
        data = self.fetch_weather(url, params)
        if data and isinstance(data, list) and len(data) > 0:
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
        if isinstance(data, str):
            return data
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
        if isinstance(data, str):
            return data
        target_date = (datetime.now() + timedelta(days=days_from_today)).strftime('%Y-%m-%d')
        forecast_text = f"{city_info['name']}의 {target_date} 날씨 예보 🌤️\n\n"
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
                    f"{forecast['main']['temp']}°C 💧{forecast['main']['humidity']}% 🌬️{forecast['wind']['speed']}m/s\n\n"
                )
        
        result = forecast_text + "더 궁금한 점 있나요? 😊" if found else f"'{city_name}'의 {target_date} 날씨 예보를 찾을 수 없습니다."
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
        if isinstance(data, str):
            return data
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
                f"\n{info['weekday']}: {info['weather']} {weather_emoji} "
                f"최저 {info['temp_min']}°C 최고 {info['temp_max']}°C\n\n"
            )
        
        result = forecast_text + "\n더 궁금한 점 있나요? 😊"
        self.cache.setex(cache_key, self.cache_ttl, result)
        return result

# FootballAPI 클래스
class FootballAPI:
    def __init__(self, api_key, cache_ttl=600):
        self.api_key = api_key
        self.base_url = "https://api.football-data.org/v4/competitions"
        self.cache = cache_handler
        self.cache_ttl = cache_ttl

    def fetch_league_standings(self, league_code, league_name):
        cache_key = f"league_standings:{league_code}"
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            return cached_data

        url = f"{self.base_url}/{league_code}/standings"
        headers = {'X-Auth-Token': self.api_key}
        
        try:
            time.sleep(1)
            response = requests.get(url, headers=headers, timeout=3)
            response.raise_for_status()
            data = response.json()
            
            standings = data['standings'][0]['table'] if league_code not in ["CL"] else data['standings']
            if league_code in ["CL"]:
                standings_data = []
                for group in standings:
                    for team in group['table']:
                        standings_data.append({
                            '순위': team['position'],
                            '그룹': group['group'],
                            '팀': team['team']['name'],
                            '경기': team['playedGames'],
                            '승': team['won'],
                            '무': team['draw'],
                            '패': team['lost'],
                            '득점': team['goalsFor'],
                            '실점': team['goalsAgainst'],
                            '득실차': team['goalsFor'] - team['goalsAgainst'],
                            '포인트': team['points']
                        })
                df = pd.DataFrame(standings_data)
            else:
                df = pd.DataFrame([
                    {
                        '순위': team['position'],
                        '팀': team['team']['name'],
                        '경기': team['playedGames'],
                        '승': team['won'],
                        '무': team['draw'],
                        '패': team['lost'],
                        '득점': team['goalsFor'],
                        '실점': team['goalsAgainst'],
                        '득실차': team['goalsFor'] - team['goalsAgainst'],
                        '포인트': team['points']
                    } for team in standings
                ])
            
            result = {"league_name": league_name, "data": df}
            self.cache.setex(cache_key, self.cache_ttl, result)
            return result
        
        except requests.exceptions.RequestException as e:
            return {"league_name": league_name, "error": f"{league_name} 리그 순위를 가져오는 중 문제가 발생했습니다: {str(e)} 😓"}

    def fetch_league_scorers(self, league_code, league_name):
        cache_key = f"league_scorers:{league_code}"
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            return cached_data

        url = f"{self.base_url}/{league_code}/scorers"
        headers = {'X-Auth-Token': self.api_key}
        
        try:
            time.sleep(1)
            response = requests.get(url, headers=headers, timeout=3)
            response.raise_for_status()
            data = response.json()
            
            scorers = [{"순위": i+1, "선수": s['player']['name'], "팀": s['team']['name'], "득점": s['goals']} 
                       for i, s in enumerate(data['scorers'][:10])]
            df = pd.DataFrame(scorers)
            result = {"league_name": league_name, "data": df}
            self.cache.setex(cache_key, self.cache_ttl, result)
            return result
        
        except requests.exceptions.RequestException as e:
            return {"league_name": league_name, "error": f"{league_name} 리그 득점순위 정보를 가져오는 중 문제가 발생했습니다: {str(e)} 😓"}

# 초기화
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = Client(exclude_providers=["OpenaiChat", "Copilot", "Liaobots", "Jmuz", "PollinationsAI", "ChatGptEs"])
weather_api = WeatherAPI()
football_api = FootballAPI(api_key=SPORTS_API_KEY)
naver_request_count = 0
NAVER_DAILY_LIMIT = 25000
st.set_page_config(page_title="AI 챗봇", page_icon="🤖")

# 세션 상태 초기화
def init_session_state():
    if "is_logged_in" not in st.session_state:
        st.session_state.is_logged_in = False
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! 무엇을 도와드릴까요?😊"}]
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

# 도시 및 시간 추출
CITY_PATTERNS = [
    re.compile(r'(?:오늘|내일|모레|이번 주|주간)?\s*([가-힣a-zA-Z\s]{2,20}(?:시|군|city)?)의?\s*날씨', re.IGNORECASE),
    re.compile(r'(?:오늘|내일|모레|이번 주|주간)?\s*([가-힣a-zA-Z\s]{2,20}(?:시|군|city)?)\s*날씨', re.IGNORECASE),
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
]
def extract_city_from_time_query(query):
    for pattern in TIME_CITY_PATTERNS:
        match = pattern.search(query)
        if match:
            city = match.group(1).strip()
            if city != "현재":
                return city
    return "서울"

LEAGUE_MAPPING = {
    "epl": {"name": "프리미어리그 (영국)", "code": "PL"},
    "laliga": {"name": "라리가 (스페인)", "code": "PD"},
    "bundesliga": {"name": "분데스리가 (독일)", "code": "BL1"},
    "seriea": {"name": "세리에 A (이탈리아)", "code": "SA"},
    "ligue1": {"name": "리그 1 (프랑스)", "code": "FL1"},
    "championsleague": {"name": "챔피언스 리그", "code": "CL"}
}

def extract_league_from_query(query):
    query_lower = query.lower().replace(" ", "")
    league_keywords = {
        "epl": ["epl", "프리미어리그"],
        "laliga": ["laliga", "라리가"],
        "bundesliga": ["bundesliga", "분데스리가"],
        "seriea": ["seriea", "세리에a"],
        "ligue1": ["ligue1", "리그1"],
        "championsleague": ["championsleague", "챔피언스리그", "ucl"]
    }
    for league_key, keywords in league_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            return league_key
    return None

def get_kst_time():
    kst_timezone = pytz.timezone("Asia/Seoul")
    kst_time = datetime.now(kst_timezone)
    return f"대한민국 기준 : {kst_time.strftime('%Y년 %m월 %d일 %p %I:%M')}입니다. ⏰\n\n 더 궁금한 점 있나요? 😊"

def get_time_by_city(city_name="서울"):
    city_info = weather_api.get_city_info(city_name)
    if not city_info:
        return f"'{city_name}'의 시간 정보를 가져올 수 없습니다."
    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lng=city_info["lon"], lat=city_info["lat"]) or "Asia/Seoul"
    timezone = pytz.timezone(timezone_str)
    city_time = datetime.now(timezone)
    return f"현재 {city_name} 시간: {city_time.strftime('%Y년 %m월 %d일 %p %I:%M')}입니다. ⏰\n\n 더 궁금한 점 있나요? 😊"

# 사용자 및 채팅 기록 관리
def create_or_get_user(nickname):
    user = supabase.table("users").select("*").eq("nickname", nickname).execute()
    if user.data:
        return user.data[0]["id"], True
    new_user = supabase.table("users").insert({"nickname": nickname, "created_at": datetime.now().isoformat()}).execute()
    return new_user.data[0]["id"], False


def save_chat_history(user_id, session_id, question, answer, time_taken):
    # generator이면 content를 병합해서 문자열로 변환
    if hasattr(answer, '__iter__') and not isinstance(answer, (str, dict, list)):
        try:
            answer = ''.join([chunk.choices[0].delta.content for chunk in answer if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content])
        except Exception as e:
            answer = f"[streaming 응답 오류: {str(e)}]"

    supabase.table("chat_history").insert({
        "user_id": user_id,
        "session_id": session_id,
        "question": question,
        "answer": answer,
        "time_taken": time_taken,
        "created_at": datetime.now().isoformat()
    }).execute()

# def save_chat_history(user_id, session_id, question, answer, time_taken):
#     if isinstance(answer, dict) and "table" in answer and isinstance(answer["table"], pd.DataFrame):
#         answer_to_save = {
#             "header": answer["header"],
#             "table": answer["table"].to_dict(orient="records"),
#             "footer": answer["footer"]
#         }
#     else:
#         answer_to_save = answer
    
#     supabase.table("chat_history").insert({
#         "user_id": user_id,
#         "session_id": session_id,
#         "question": question,
#         "answer": answer_to_save,
#         "time_taken": time_taken,
#         "created_at": datetime.now().isoformat()
#     }).execute()

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
        response = requests.get(url, params=params, timeout=3)
        response.raise_for_status()
        data = response.json()
        if 'body' in data and 'items' in data['body'] and data['body']['items']:
            item = data['body']['items'][0]
            efcy = item.get('efcyQesitm', '정보 없음')[:150] + ("..." if len(item.get('efcyQesitm', '')) > 150 else "")
            use_method = item.get('useMethodQesitm', '정보 없음')[:150] + ("..." if len(item.get('useMethodQesitm', '')) > 150 else "")
            atpn = item.get('atpnQesitm', '정보 없음')[:150] + ("..." if len(item.get('atpnQesitm', '')) > 150 else "")
            
            result = (
                f"💊 **의약품 정보** 💊\n\n"
                f"✅ **약품명**: {item.get('itemName', '정보 없음')}\n\n"
                f"✅ **제조사**: {item.get('entpName', '정보 없음')}\n\n"
                f"✅ **효능**: {efcy}\n\n"
                f"✅ **용법용량**: {use_method}\n\n"
                f"✅ **주의사항**: {atpn}\n\n"
                f"더 궁금한 점 있나요? 😊"
            )
            cache_handler.setex(cache_key, 86400, result)
            return result
        return f"'{drug_name}'의 공식 정보를 찾을 수 없습니다."
    except Exception as e:
        logger.error(f"약품 API 오류: {str(e)}")
        return f"'{drug_name}'의 정보를 가져오는 중 문제가 발생했습니다. 😓"

# Naver API 검색
def get_naver_api_results(query):
    global naver_request_count
    cache_key = f"naver:{query}"
    cached = cache_handler.get(cache_key)
    if cached:
        return cached
    
    if naver_request_count >= NAVER_DAILY_LIMIT:
        return "검색 한도 초과로 결과를 가져올 수 없습니다. 😓"
    enc_text = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/webkr?query={enc_text}&display=5&sort=date"
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    request.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
    try:
        response = urllib.request.urlopen(request, timeout=3)
        naver_request_count += 1
        if response.getcode() == 200:
            data = json.loads(response.read().decode('utf-8'))
            results = data.get('items', [])
            if not results:
                return "검색 결과가 없습니다. 😓"
            
            response_text = "🌐 **웹 검색 결과** \n\n"
            response_text += "\n\n".join(
                [f"**결과 {i}**\n\n📄 **제목**: {re.sub(r'<b>|</b>', '', item['title'])}\n\n📝 **내용**: {re.sub(r'<b>|</b>', '', item.get('description', '내용 없음'))[:100]}...\n\n🔗 **링크**: {item.get('link', '')}"
                 for i, item in enumerate(results, 1)]
            ) + "\n\n더 궁금한 점 있나요? 😊"
            cache_handler.setex(cache_key, 3600, response_text)
            return response_text
    except Exception as e:
        logger.error(f"Naver API 오류: {str(e)}")
        return "검색 중 오류가 발생했습니다. 😓"

# ArXiv 논문 검색
def fetch_arxiv_paper(paper):
    return {
        "title": paper.title,
        "authors": ", ".join(str(a) for a in paper.authors),
        "summary": paper.summary[:200],
        "entry_id": paper.entry_id,
        "pdf_url": paper.pdf_url,
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
    
    response = "📚 **Arxiv 논문 검색 결과** 📚\n\n"
    response += "\n\n".join(
        [f"**논문 {i}**\n\n📄 **제목**: {r['title']}\n\n👥 **저자**: {r['authors']}\n\n📝 **초록**: {r['summary']}...\n\n🔗 **논문 페이지**: {r['entry_id']}\n\n📅 **출판일**: {r['published']}"
         for i, r in enumerate(results, 1)]
    ) + "\n\n더 궁금한 점 있나요? 😊"
    cache_handler.setex(cache_key, 3600, response)
    return response

# PubMed 논문 검색
base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

def search_pubmed(query, max_results=5):
    search_url = f"{base_url}esearch.fcgi"
    params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": max_results, "api_key": NCBI_KEY}
    response = requests.get(search_url, params=params, timeout=3)
    return response.json()

def get_pubmed_summaries(id_list):
    summary_url = f"{base_url}esummary.fcgi"
    params = {"db": "pubmed", "id": ",".join(id_list), "retmode": "json", "api_key": NCBI_KEY}
    response = requests.get(summary_url, params=params, timeout=3)
    return response.json()

def get_pubmed_abstract(id_list):
    fetch_url = f"{base_url}efetch.fcgi"
    params = {"db": "pubmed", "id": ",".join(id_list), "retmode": "xml", "rettype": "abstract", "api_key": NCBI_KEY}
    response = requests.get(fetch_url, params=params, timeout=3)
    return response.text

def extract_first_two_sentences(abstract_text):
    if not abstract_text or abstract_text.isspace():
        return "No abstract available"
    sentences = [s.strip() for s in abstract_text.split('.') if s.strip()]
    return " ".join(sentences[:2]) + "." if sentences else "No abstract available"

def parse_abstracts(xml_text):
    abstract_dict = {}
    try:
        root = ET.fromstring(xml_text)
        for article in root.findall(".//PubmedArticle"):
            pmid = article.find(".//MedlineCitation/PMID").text
            abstract_elem = article.find(".//Abstract/AbstractText")
            abstract = abstract_elem.text if abstract_elem is not None else "No abstract available"
            abstract_dict[pmid] = extract_first_two_sentences(abstract)
    except ET.ParseError:
        return {}
    return abstract_dict

def get_pubmed_papers(query, max_results=5):
    cache_key = f"pubmed:{query}:{max_results}"
    cached = cache_handler.get(cache_key)
    if cached:
        return cached
    
    search_results = search_pubmed(query, max_results)
    pubmed_ids = search_results["esearchresult"]["idlist"]
    if not pubmed_ids:
        return "해당 키워드로 의학 논문을 찾을 수 없습니다."
    
    summaries = get_pubmed_summaries(pubmed_ids)
    abstracts_xml = get_pubmed_abstract(pubmed_ids)
    abstract_dict = parse_abstracts(abstracts_xml)
    
    response = "📚 **PubMed 논문 검색 결과** 📚\n\n"
    response += "\n\n".join(
        [f"**논문 {i}**\n\n🆔 **PMID**: {pmid}\n\n📖 **제목**: {summaries['result'][pmid].get('title', 'No title')}\n\n📅 **출판일**: {summaries['result'][pmid].get('pubdate', 'No date')}\n\n✍️ **저자**: {', '.join([author.get('name', '') for author in summaries['result'][pmid].get('authors', [])])}\n\n📝 **초록**: {abstract_dict.get(pmid, 'No abstract')}"
         for i, pmid in enumerate(pubmed_ids, 1)]
    ) + "\n\n더 궁금한 점 있나요? 😊"
    cache_handler.setex(cache_key, 3600, response)
    return response

# 대화형 응답 (스트리밍 적용)
conversation_cache = MemoryCache()
async def get_conversational_response(query, messages):
    cache_key = f"conv:{needs_search(query)}:{query}"
    cached = conversation_cache.get(cache_key)
    if cached:
        return cached, False
    
    system_message = {"role": "system", "content": "친절한 AI 챗봇입니다. 적절한 이모지 사용: ✅(완료), ❓(질문), 😊(친절)"}
    conversation_history = [system_message] + messages[-2:] + [{"role": "user", "content": query}]
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=conversation_history,
            web_search=False,
            stream=True
        )
        return response, True
    except Exception as e:
        logger.error(f"대화 응답 생성 중 오류: {str(e)}")
        return f"응답을 생성하는 중 문제가 발생했습니다: {str(e)} 😓", False

GREETINGS = ["안녕", "하이", "헬로", "ㅎㅇ", "왓업", "할롱", "헤이"]
GREETING_RESPONSE = "안녕하세요! 반갑습니다. 무엇을 도와드릴까요? 😊"

@lru_cache(maxsize=100)
def needs_search(query):
    query_lower = query.strip().lower().replace(" ", "")
    if "날씨" in query_lower:
        return "weather" if "내일" not in query_lower else "tomorrow_weather"
    if "시간" in query_lower or "날짜" in query_lower:
        return "time"
    if "리그순위" in query_lower:
        return "league_standings"
    if "리그득점순위" in query_lower or "득점순위" in query_lower:
        return "league_scorers"
    if "약품검색" in query_lower:
        return "drug"
    if "공학논문" in query_lower or "arxiv" in query_lower:
        return "arxiv_search"
    if "의학논문" in query_lower:
        return "pubmed_search"
    if "검색" in query_lower:
        return "naver_search"
    if "mbti" in query_lower:
        if "유형" in query_lower or "설명" in query_lower:
            return "mbti_types"
        return "mbti"
    if "다중지능" in query_lower or "multi_iq" in query_lower:
        if "유형" in query_lower or "설명" in query_lower:
            return "multi_iq_types"
        if "직업" in query_lower or "추천" in query_lower:
            return "multi_iq_jobs"
        return "multi_iq"
    if any(greeting in query_lower for greeting in GREETINGS):
        return "conversation"
    return "conversation"

def process_query(query, messages):
    cache_key = f"query:{hash(query)}"
    cached = cache_handler.get(cache_key)
    if cached is not None:
        return cached, False
    
    query_type = needs_search(query)
    query_lower = query.strip().lower().replace(" ", "")
    
    with ThreadPoolExecutor() as executor:
        if query_type == "weather":
            future = executor.submit(weather_api.get_city_weather, extract_city_from_query(query))
            result = future.result()
            cache_handler.setex(cache_key, 600, result)
            return result, False
        elif query_type == "tomorrow_weather":
            future = executor.submit(weather_api.get_forecast_by_day, extract_city_from_query(query), 1)
            result = future.result()
            cache_handler.setex(cache_key, 600, result)
            return result, False
        elif query_type == "time":
            if "오늘날짜" in query_lower or "현재날짜" in query_lower or "금일날짜" in query_lower:
                result = get_kst_time()
            else:
                city = extract_city_from_time_query(query)
                future = executor.submit(get_time_by_city, city)
                result = future.result()
            cache_handler.setex(cache_key, 600, result)
            return result, False
        elif query_type == "league_standings":
            league_key = extract_league_from_query(query)
            if league_key:
                league_info = LEAGUE_MAPPING[league_key]
                future = executor.submit(football_api.fetch_league_standings, league_info["code"], league_info["name"])
                result = future.result()
                result = result["error"] if "error" in result else {
                    "header": f"{result['league_name']} 리그 순위",
                    "table": result["data"],
                    "footer": "더 궁금한 점 있나요? 😊"
                }
                cache_handler.setex(cache_key, 600, result)
            else:
                result = "지원하지 않는 리그입니다. 😓 지원 리그: EPL, LaLiga, Bundesliga, Serie A, Ligue 1"
            return result, False
        elif query_type == "league_scorers":
            league_key = extract_league_from_query(query)
            if league_key:
                league_info = LEAGUE_MAPPING[league_key]
                future = executor.submit(football_api.fetch_league_scorers, league_info["code"], league_info["name"])
                try:
                    result = future.result()
                    result = result["error"] if "error" in result else {
                        "header": f"{result['league_name']} 리그 득점순위 (상위 10명)",
                        "table": result["data"],
                        "footer": "더 궁금한 점 있나요? 😊"
                    }
                    cache_handler.setex(cache_key, 600, result)
                except Exception as e:
                    result = f"리그 득점순위 조회 중 오류 발생: {str(e)} 😓"
            else:
                result = "지원하지 않는 리그입니다. 😓 지원 리그: EPL, LaLiga, Bundesliga, Serie A, Ligue 1"
            return result, False
        elif query_type == "drug":
            future = executor.submit(get_drug_info, query)
            result = future.result()
            cache_handler.setex(cache_key, 600, result)
            return result, False
        elif query_type == "arxiv_search":
            keywords = query.replace("공학논문", "").replace("arxiv", "").strip()
            future = executor.submit(get_arxiv_papers, keywords)
            result = future.result()
            cache_handler.setex(cache_key, 600, result)
            return result, False
        elif query_type == "pubmed_search":
            keywords = query.replace("의학논문", "").strip()
            future = executor.submit(get_pubmed_papers, keywords)
            result = future.result()
            cache_handler.setex(cache_key, 600, result)
            return result, False
        elif query_type == "naver_search":
            search_query = query.lower().replace("검색", "").strip()
            future = executor.submit(get_naver_api_results, search_query)
            result = future.result()
            cache_handler.setex(cache_key, 600, result)
            return result, False
        elif query_type == "mbti":
            result = (
                "MBTI 검사를 원하시나요? ✨ 아래 사이트에서 무료로 성격 유형 검사를 할 수 있어요! 😊\n"
                "[16Personalities MBTI 검사](https://www.16personalities.com/ko/%EB%AC%B4%EB%A3%8C-%EC%84%B1%EA%B2%A9-%EC%9C%A0%ED%98%95-%EA%B2%80%EC%82%AC) 🌟\n"
                "이 사이트는 16가지 성격 유형을 기반으로 한 테스트를 제공하며, 결과에 따라 성격 설명과 인간관계 조언 등을 확인할 수 있어요! 💡"
            )
            cache_handler.setex(cache_key, 600, result)
            return result, False
        elif query_type == "mbti_types":
            specific_type = query_lower.replace("mbti", "").replace("유형", "").replace("설명", "").strip().upper()
            if specific_type in mbti_descriptions:
                result = f"### 🎭 {specific_type} 한 줄 설명\n- ✅ **{specific_type}** {mbti_descriptions[specific_type]}"
            else:
                result = mbti_full_description
            cache_handler.setex(cache_key, 600, result)
            return result, False
        elif query_type == "multi_iq":
            result = (
                "다중지능 검사를 원하시나요? 🎉 아래 사이트에서 무료로 다중지능 테스트를 해볼 수 있어요! 😄\n"
                "[Multi IQ Test](https://multiiqtest.com/) 🚀\n"
                "이 사이트는 하워드 가드너의 다중지능 이론을 기반으로 한 테스트를 제공하며, 다양한 지능 영역을 평가해줍니다! 📚✨"
            )
            cache_handler.setex(cache_key, 600, result)
            return result, False
        elif query_type == "multi_iq_types":
            specific_type = query_lower.replace("다중지능", "").replace("multi_iq", "").replace("유형", "").replace("설명", "").strip().replace(" ", "")
            if specific_type in multi_iq_descriptions:
                result = f"### 🎨 {specific_type.replace('지능', ' 지능')} 한 줄 설명\n- 📖 **{specific_type.replace('지능', ' 지능')}** {multi_iq_descriptions[specific_type]['description']}"
            else:
                result = multi_iq_full_description
            cache_handler.setex(cache_key, 600, result)
            return result, False
        elif query_type == "multi_iq_jobs":
            specific_type = query_lower.replace("다중지능", "").replace("multi_iq", "").replace("직업", "").replace("추천", "").strip().replace(" ", "")
            if specific_type in multi_iq_descriptions:
                result = f"### 🎨 {specific_type.replace('지능', ' 지능')} 추천 직업\n- 📖 **{specific_type.replace('지능', ' 지능')}**: {multi_iq_descriptions[specific_type]['description']}- **추천 직업**: {multi_iq_descriptions[specific_type]['jobs']}"
            else:
                result = multi_iq_full_description
            cache_handler.setex(cache_key, 600, result)
            return result, False
        elif query_type == "conversation":
            if query_lower in GREETINGS:
                result = GREETING_RESPONSE
                cache_handler.setex(cache_key, 600, result)
                return result, False
            elif "오늘날짜" in query_lower or "현재날짜" in query_lower or "금일날짜" in query_lower:
                result = get_kst_time()
                cache_handler.setex(cache_key, 600, result)
                return result, False
            else:
                response, is_stream = asyncio.run(get_conversational_response(query, messages))
                return response, is_stream
        else:
            result = "아직 지원하지 않는 기능이에요. 😅"
            cache_handler.setex(cache_key, 600, result)
            return result, False

def show_chat_dashboard():
    st.title("Chat with AI 🤖")
    
    # 도움말 버튼
    if st.button("도움말 ℹ️"):
        st.info(
            "챗봇과 더 쉽게 대화하는 방법이에요! 👇:\n"
            "1. **날씨** ☀️: '[도시명] 날씨' (예: 서울 날씨)\n"
            "2. **시간/날짜** ⏱️: '[도시명] 시간' 또는 '오늘 날짜' (예: 부산 시간, 금일 날짜)\n"
            "3. **리그순위** ⚽: '[리그 이름] 리그 순위 또는 리그득점순위' (예: EPL 리그순위, EPL 리그득점순위)\n"
            "   - 지원 리그: EPL, LaLiga, Bundesliga, Serie A, Ligue 1, ChampionsLeague\n"
            "4. **약품검색** 💊: '약품검색 [약 이름]' (예: 약품검색 게보린)\n"
            "5. **공학논문** 📚: '공학논문 [키워드]' (예: 공학논문 Multimodal AI)\n"
            "6. **의학논문** 🩺: '의학논문 [키워드]' (예: 의학논문 cancer therapy)\n"
            "7. **검색** 🌐: '검색 키워드' (예: 검색 최근 전시회 추천)\n"
            "8. **MBTI** ✨: 'MBTI' 또는 'MBTI 유형' (예: MBTI 검사, INTJ 설명)\n"
            "9. **다중지능** 🎉: '다중지능' 또는 '다중지능 유형' (예: 다중지능 검사, 언어지능 직업)\n\n"
            "궁금한 점 있으면 질문해주세요! 😊"
        )
    
    # 최근 메시지 표시
    for msg in st.session_state.messages[-10:]:
        with st.chat_message(msg['role']):
            if isinstance(msg['content'], dict) and "table" in msg['content']:
                st.markdown(f"### {msg['content']['header']}")
                st.dataframe(pd.DataFrame(msg['content']['table']), use_container_width=True, hide_index=True)
                st.markdown(msg['content']['footer'])
            else:
                st.markdown(msg['content'], unsafe_allow_html=True)
    
    # 사용자 입력 처리
    if user_prompt := st.chat_input("질문해 주세요!"):
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        
        with st.chat_message("user"):
            st.markdown(user_prompt)
        
        with st.chat_message("assistant"):
            # Spinner 적용
            with st.spinner("응답을 준비 중입니다... ⏳"):
                try:
                    start_time = time.time()
                    response, is_stream = process_query(user_prompt, st.session_state.messages)
                    time_taken = round(time.time() - start_time, 2)
                    
                    # 스트리밍 응답 처리
                    if is_stream:
                        chatbot_response = ""
                        message_placeholder = st.empty()
                        for chunk in response:
                            if hasattr(chunk, 'choices') and len(chunk.choices) > 0 and hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                                content = chunk.choices[0].delta.content
                                if content is not None:
                                    chatbot_response += content
                                    message_placeholder.markdown(chatbot_response + "▌")
                            else:
                                logger.warning(f"예상치 못한 청크 구조: {chunk}")
                        message_placeholder.markdown(chatbot_response)
                        st.session_state.messages.append({"role": "assistant", "content": chatbot_response})
                    else:
                        # 정적 응답 처리
                        if isinstance(response, dict) and "table" in response:
                            st.markdown(f"### {response['header']}")
                            st.dataframe(response['table'], use_container_width=True, hide_index=True)
                            st.markdown(response['footer'])
                        else:
                            st.markdown(response, unsafe_allow_html=True)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                    
                    # 대화 기록 비동기 저장
                    async_save_chat_history(st.session_state.user_id, st.session_state.session_id, user_prompt, response, time_taken)
                
                except Exception as e:
                    error_msg = f"응답을 준비하다 문제가 생겼어요: {str(e)} 😓"
                    logger.error(f"대화 처리 중 오류: {str(e)}", exc_info=True)
                    st.markdown(error_msg, unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})



def show_login_page():
    st.title("로그인 🤗")
    with st.form("login_form"):
        nickname = st.text_input("닉네임", placeholder="예: 후안")
        submit_button = st.form_submit_button("시작하기 🚀")
        
        if submit_button and nickname:
            try:
                user_id, is_existing = create_or_get_user(nickname)
                st.session_state.user_id = user_id
                st.session_state.is_logged_in = True
                st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! 무엇을 도와드릴까요? 도움말도 활용해 보세요 😊"}]
                st.session_state.session_id = str(uuid.uuid4())
                st.toast(f"환영합니다, {nickname}님! 🎉")
                time.sleep(1)
                st.rerun()
            except Exception:
                st.toast("로그인 중 오류가 발생했습니다. 다시 시도해주세요.", icon="❌")

def main():
    init_session_state()
    if not st.session_state.is_logged_in:
        show_login_page()
    else:
        show_chat_dashboard()

if __name__ == "__main__":
    main()
