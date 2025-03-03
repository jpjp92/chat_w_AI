# # app2.py

# 라이브러리 설정
from config.imports import *
from config.env import *

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

# WeatherAPI 클래스 (기존 로직 유지)
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

# SportsAPI 클래스 추가
class SportsAPI:
    def __init__(self, api_key, cache_ttl=86400):
        self.cache = cache_handler
        self.cache_ttl = cache_ttl
        self.base_url = "https://www.thesportsdb.com/api/v1/json"
        self.api_key = api_key

    def fetch_team_id(self, team_name):
        """팀 이름을 통해 팀 ID를 조회"""
        cache_key = f"team_id:{team_name}"
        cached_team_id = self.cache.get(cache_key)
        if cached_team_id:
            return cached_team_id

        url = f"{self.base_url}/{self.api_key}/searchteams.php"
        params = {'t': team_name.replace(' ', '%20')}
        try:
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            if data['teams']:
                team_id = data['teams'][0]['idTeam']
                self.cache.setex(cache_key, self.cache_ttl, team_id)
                return team_id
            else:
                logger.warning(f"팀 {team_name}을 찾을 수 없습니다.")
                return None
        except Exception as e:
            logger.error(f"팀 ID 조회 중 오류: {str(e)}")
            return None

    def fetch_team_schedule(self, team_name, month):
        """팀의 경기 일정을 조회하고 지정된 월에 해당하는 경기만 필터링"""
        cache_key = f"sports_schedule:{team_name}:{month}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data

        team_id = self.fetch_team_id(team_name)
        if not team_id:
            return f"'{team_name}'의 경기 일정을 찾을 수 없습니다. 😓"

        url = f"{self.base_url}/{self.api_key}/eventsnext.php"
        params = {'id': team_id}
        try:
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            if not data['events']:
                return f"'{team_name}'의 예정된 경기가 없습니다. 😓"

            league_color = {
                "UEFA Champions League": "color: #FFD700;",
                "LaLiga": "color: #FF4500;",
                "Copa del Rey": "color: #4169E1;",
            }

            result = f"**⚽ {team_name}의 {month}월 경기 일정 ⚽**\n\n"
            result += "-" * 75 + "\n\n"
            found = False
            today = datetime.now().date()
            for event in data['events']:
                event_date_str = event['dateEvent']
                event_date = datetime.strptime(event_date_str, '%Y-%m-%d')
                if event_date.month == month and event_date.year == 2025:
                    found = True
                    event_time = event['strTime'] if event['strTime'] else "시간 미정"
                    timezone_info = "(CET)"

                    event_date_only = datetime.strptime(event_date_str, '%Y-%m-%d').date()
                    if event_date_only == today:
                        date_label = f"📅 날짜: {event_date_str} {event_time} {timezone_info} (오늘! 🔥)"
                    elif event_date_only == today + timedelta(days=1):
                        date_label = f"📅 날짜: {event_date_str} {event_time} {timezone_info} (내일! 🔥)"
                    else:
                        date_label = f"📅 날짜: {event_date_str} {event_time} {timezone_info}"

                    league_style = league_color.get(event['strLeague'], "color: #000000;")
                    league_display = f"<span style='{league_style}'>🏆 리그: {event['strLeague']}</span>"

                    result += (
                        f"{date_label}\n\n"
                        f"🏟️ 팀: {event['strEvent']} (홈: {event['strHomeTeam']} vs 원정: {event['strAwayTeam']})\n\n"
                        f"{league_display}\n\n"
                        f"📍 장소: {event.get('strVenue', '미정')}\n\n"
                        f"{'-' * 75}\n\n"
                    )

            if not found:
                result = f"'{team_name}'의 {month}월 경기 일정이 없습니다. 😓\n\n"
            result += "더 궁금한 점 있나요? 😊"
            self.cache.setex(cache_key, self.cache_ttl, result)
            return result

        except Exception as e:
            logger.error(f"경기 일정 조회 중 오류: {str(e)}")
            return f"경기 일정을 가져오는 중 문제가 발생했습니다. 😓\n\n더 궁금한 점 있나요? 😊"

    def fetch_league_schedule(self, league_key, month, initial_limit=5):
        """리그의 경기 일정을 조회하고 초기에는 최대 initial_limit 경기 표시"""
        cache_key = f"league_schedule:{league_key}:{month}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data

        if league_key not in LEAGUE_MAPPING:
            return f"'{league_key}' 리그를 찾을 수 없습니다. 😓"

        league_info = LEAGUE_MAPPING[league_key]
        league_id = league_info['id']
        league_name = league_info['name']

        url = f"{self.base_url}/{self.api_key}/eventsnextleague.php"
        params = {'id': league_id}
        try:
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            if not data['events']:
                return f"'{league_name}'의 예정된 경기가 없습니다. 😓"

            league_color = {
                "English Premier League": "color: #800080;",
                "German Bundesliga": "color: #FF0000;",
                "Italian Serie A": "color: #008000;",
                "French Ligue 1": "color: #0000FF;",
                "UEFA Europa League": "color: #FFA500;",
                "South Korean K League 1": "color: #FFD700;",
                "AFC Champions League Elite": "color: #00CED1;"
            }

            events = sorted(data['events'], key=lambda x: x['dateEvent'])
            filtered_events = [event for event in events if datetime.strptime(event['dateEvent'], '%Y-%m-%d').month == month and datetime.strptime(event['dateEvent'], '%Y-%m-%d').year == 2025]

            if not filtered_events:
                return f"'{league_name}'의 {month}월 경기 일정이 없습니다. 😓\n\n더 궁금한 점 있나요? 😊"

            initial_events = filtered_events[:initial_limit]
            remaining_events = filtered_events[initial_limit:]

            if f"show_more_{league_key}_{month}" not in st.session_state:
                st.session_state[f"show_more_{league_key}_{month}"] = False

            result = f"**⚽ {league_name}의 {month}월 경기 일정 ⚽**\n\n"
            result += "-" * 75 + "\n\n"
            today = datetime.now().date()
            for event in initial_events:
                event_date_str = event['dateEvent']
                event_date = datetime.strptime(event_date_str, '%Y-%m-%d')
                event_time = event['strTime'] if event['strTime'] else "시간 미정"

                timezone_info = "(CET)"
                if league_key in ["k league 1", "kleague1", "afc champions league elite", "afcchampionsleagueelite"]:
                    timezone_info = "(KST)"

                event_date_only = datetime.strptime(event_date_str, '%Y-%m-%d').date()
                if event_date_only == today:
                    date_label = f"📅 날짜: {event_date_str} {event_time} {timezone_info} (오늘! 🔥)"
                elif event_date_only == today + timedelta(days=1):
                    date_label = f"📅 날짜: {event_date_str} {event_time} {timezone_info} (내일! 🔥)"
                else:
                    date_label = f"📅 날짜: {event_date_str} {event_time} {timezone_info}"

                league_style = league_color.get(league_name, "color: #000000;")
                league_display = f"<span style='{league_style}'>🏆 리그: {league_name}</span>"

                result += (
                    f"{date_label}\n\n"
                    f"🏟️ 팀: {event['strEvent']} (홈: {event['strHomeTeam']} vs 원정: {event['strAwayTeam']})\n\n"
                    f"{league_display}\n\n"
                    f"📍 장소: {event.get('strVenue', '미정')}\n\n"
                    f"{'-' * 75}\n\n"
                )

            if remaining_events:
                result += "더 많은 경기를 보려면 아래 버튼을 클릭하세요:\n\n"
                if st.button("더 보기", key=f"show_more_{league_key}_{month}"):
                    st.session_state[f"show_more_{league_key}_{month}"] = True

                if st.session_state[f"show_more_{league_key}_{month}"]:
                    for event in remaining_events:
                        event_date_str = event['dateEvent']
                        event_date = datetime.strptime(event_date_str, '%Y-%m-%d')
                        event_time = event['strTime'] if event['strTime'] else "시간 미정"

                        timezone_info = "(CET)"
                        if league_key in ["k league 1", "kleague1", "afc champions league elite", "afcchampionsleagueelite"]:
                            timezone_info = "(KST)"

                        event_date_only = datetime.strptime(event_date_str, '%Y-%m-%d').date()
                        if event_date_only == today:
                            date_label = f"📅 날짜: {event_date_str} {event_time} {timezone_info} (오늘! 🔥)"
                        elif event_date_only == today + timedelta(days=1):
                            date_label = f"📅 날짜: {event_date_str} {event_time} {timezone_info} (내일! 🔥)"
                        else:
                            date_label = f"📅 날짜: {event_date_str} {event_time} {timezone_info}"

                        league_style = league_color.get(league_name, "color: #000000;")
                        league_display = f"<span style='{league_style}'>🏆 리그: {league_name}</span>"

                        result += (
                            f"{date_label}\n\n"
                            f"🏟️ 팀: {event['strEvent']} (홈: {event['strHomeTeam']} vs 원정: {event['strAwayTeam']})\n\n"
                            f"{league_display}\n\n"
                            f"📍 장소: {event.get('strVenue', '미정')}\n\n"
                            f"{'-' * 75}\n\n"
                        )

            result += "더 궁금한 점 있나요? 😊"
            self.cache.setex(cache_key, self.cache_ttl, result)
            return result

        except Exception as e:
            logger.error(f"리그 경기 일정 조회 중 오류: {str(e)}")
            return f"리그 경기 일정을 가져오는 중 문제가 발생했습니다. 😓\n\n더 궁금한 점 있나요? 😊"

# 초기화
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = Client()
weather_api = WeatherAPI()
sports_api = SportsAPI(api_key="3")  # TheSportsDB API 키 설정 (예시)
naver_request_count = 0
NAVER_DAILY_LIMIT = 25000
st.set_page_config(page_title="AI 챗봇", page_icon="🤖")

# 세션 상태 초기화 함수
def init_session_state():
    if "is_logged_in" not in st.session_state:
        st.session_state.is_logged_in = False
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "session_id" not in st.session_state:
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

# 팀 및 리그 추출
SPORTS_PATTERNS = [
    re.compile(r'([가-힣a-zA-Z\s]{2,20}(?:시|팀)?)\s*(?:[0-9]{1,2}월)?\s*(?:경기일정|경기 일정|스케줄|일정)', re.IGNORECASE),
    re.compile(r'(?:[0-9]{1,2}월)?\s*([가-힣a-zA-Z\s]{2,20}(?:시|팀)?)\s*(?:경기일정|경기 일정|스케줄|일정)', re.IGNORECASE),
]
MONTH_PATTERN = re.compile(r'([0-9]{1,2})월')

LEAGUE_MAPPING = {
    "epl": {"name": "English Premier League", "id": 4328},
    "bundesliga": {"name": "German Bundesliga", "id": 4331},
    "serie a": {"name": "Italian Serie A", "id": 4332},
    "seriea": {"name": "Italian Serie A", "id": 4332},
    "ligue 1": {"name": "French Ligue 1", "id": 4334},
    "ligue1": {"name": "French Ligue 1", "id": 4334},
    "europa league": {"name": "UEFA Europa League", "id": 4480},
    "europaleague": {"name": "UEFA Europa League", "id": 4480},
    "k league 1": {"name": "South Korean K League 1", "id": 4356},
    "kleague1": {"name": "South Korean K League 1", "id": 4356},
    "afc champions league elite": {"name": "AFC Champions League Elite", "id": 4517},
    "afcchampionsleagueelite": {"name": "AFC Champions League Elite", "id": 4517},
}

def extract_team_from_query(query):
    for pattern in SPORTS_PATTERNS:
        match = pattern.search(query)
        if match:
            team = match.group(1).strip()
            return team
    return None

def extract_league_from_query(query):
    query_lower = query.strip().lower()
    for league_key in LEAGUE_MAPPING.keys():
        if league_key in query_lower:
            return league_key
    return None

def extract_month_from_query(query):
    match = MONTH_PATTERN.search(query)
    if match:
        return int(match.group(1))
    return datetime.now().month

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
            use_method_raw = item.get('useMethodQesitm', '정보 없음')
            atpn = item.get('atpnQesitm', '정보 없음')[:150] + ("..." if len(item.get('atpnQesitm', '')) > 150 else "")
            use_method = use_method_raw[:150] + ("..." if len(use_method_raw) > 150 else "")
            
            result = (
                f"💊 **의약품 정보** 💊\n\n"
                f"✅ **약품명**: {item.get('itemName', '정보 없음')}\n\n"
                f"✅ **제조사**: {item.get('entpName', '정보 없음')}\n\n"
                f"✅ **효능**: {efcy}\n\n"
                f"✅ **용법용량**: {use_method}\n\n"
                f"✅ **주의사항**: {atpn}\n\n"
                f"ℹ️ 자세한 정보는 [약학정보원](https://www.health.kr/searchDrug/search_detail.asp)에서 확인하세요! 🩺\n\n"
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
                link = response.url if response.url else None
                if not link:
                    logger.warning(f"링크 누락 발생: query={query}, title={title}, url=없음")
                data.append({"title": title, "contents": description[:500], "link": link})
            except Exception as e:
                logger.error(f"검색 요청 실패: query={query}, error={str(e)}")
                continue
    df = pd.DataFrame(data)
    if df.empty or 'link' not in df.columns or df['link'].isnull().all():
        logger.warning(f"검색 결과 비어있음 또는 모든 링크 누락: query={query}, data={data}")
    return df

def get_ai_summary(search_results):
    if search_results.empty:
        return "검색 결과를 찾을 수 없습니다."
    context = "\n".join([f"출처: {row['title']}\n내용: {row['contents']}" for _, row in search_results.iterrows()])
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"검색 결과를 2~3문장으로 요약:\n{context}"}]
    )
    summary = response.choices[0].message.content
    sources = "\n\n📜 **출처**\n" + "\n".join(
        [f"🌐 [{row['title']}]({row.get('link', '링크 없음')})" 
         for _, row in search_results.iterrows()]
    )
    return f"{summary}{sources}\n\n더 궁금한 점 있나요? 😊"

# 논문 검색 (ArXiv)
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
        [f"**논문 {i}**\n\n"
         f"📄 **제목**: {r['title']}\n\n"
         f"👥 **저자**: {r['authors']}\n\n"
         f"📝 **초록**: {r['summary']}...\n\n"
         f"🔗 **논문 페이지**: {r['entry_id']}\n\n"
         f"📥 **PDF 다운로드**: [{r['pdf_url'].split('/')[-1]}]({r['pdf_url']})\n\n"
         f"📅 **출판일**: {r['published']}\n\n"
         f"{'-' * 50}"
         for i, r in enumerate(results, 1)]
    ) + "\n\n더 많은 논문을 보고 싶다면 말씀해 주세요! 😊"
    cache_handler.setex(cache_key, 3600, response)
    return response

# PubMed 논문 검색
base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

def search_pubmed(query, max_results=5):
    search_url = f"{base_url}esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results,
        "api_key": NCBI_KEY
    }
    response = requests.get(search_url, params=params)
    return response.json()

def get_pubmed_summaries(id_list):
    summary_url = f"{base_url}esummary.fcgi"
    ids = ",".join(id_list)
    params = {
        "db": "pubmed",
        "id": ids,
        "retmode": "json",
        "api_key": NCBI_KEY
    }
    response = requests.get(summary_url, params=params)
    return response.json()

def get_pubmed_abstract(id_list):
    fetch_url = f"{base_url}efetch.fcgi"
    ids = ",".join(id_list)
    params = {
        "db": "pubmed",
        "id": ids,
        "retmode": "xml",
        "rettype": "abstract",
        "api_key": NCBI_KEY
    }
    response = requests.get(fetch_url, params=params)
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
            pmid_elem = article.find(".//MedlineCitation/PMID")
            abstract_elem = article.find(".//Abstract/AbstractText")
            pmid = pmid_elem.text if pmid_elem is not None else None
            abstract = abstract_elem.text if abstract_elem is not None else "No abstract available"
            if pmid:
                abstract_dict[pmid] = extract_first_two_sentences(abstract)
    except ET.ParseError as e:
        logger.error(f"XML 파싱 오류 발생: {e}")
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
    
    response = "📚 **PubMed 의학 논문 검색 결과** 📚\n\n"
    response += "\n\n".join(
        [f"**논문 {i}**\n\n"
         f"🆔 **PMID**: {pmid}\n\n"
         f"📖 **제목**: {summaries['result'][pmid].get('title', 'No title available')}\n\n"
         f"📅 **출판일**: {summaries['result'][pmid].get('pubdate', 'No date available')}\n\n"
         f"✍️ **저자**: {', '.join([author.get('name', '') for author in summaries['result'][pmid].get('authors', [])])}\n\n"
         f"🔗 **링크**: {'https://doi.org/' + next((aid['value'] for aid in summaries['result'][pmid].get('articleids', []) if aid['idtype'] == 'doi'), None) if next((aid['value'] for aid in summaries['result'][pmid].get('articleids', []) if aid['idtype'] == 'doi'), None) else f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/'}\n\n"
         f"📝 **초록**: {abstract_dict.get(pmid, 'No abstract available')}\n\n"
         f"{'-' * 50}"
         for i, pmid in enumerate(pubmed_ids, 1)]
    ) + "\n\n더 많은 의학 논문을 보고 싶다면 말씀해 주세요! 😊"
    cache_handler.setex(cache_key, 3600, response)
    return response

# 대화형 응답
conversation_cache = MemoryCache()
def get_conversational_response(query, chat_history):
    cache_key = f"conv:{needs_search(query)}:{query}:{hash(str(chat_history[-5:]))}"
    cached = conversation_cache.get(cache_key)
    if cached:
        return cached
    
    emoji_list = (
        "체크리스트 이모지:\n"
        "✅ 완료된 항목 | ☑️ 체크 상자 (체크됨) | ✓ 체크 표시 | ✔️ 굵은 체크 표시 | ❌ 취소/실패 항목 | ⬜ 빈 상자 | ⚪ 빈 원 | 🔘 라디오 버튼 | 📌 핀으로 고정된 항목 | 🚀 시작/출시 항목\n\n"
        "상태 표시 이모지:\n"
        "🟢 녹색 원 (성공/활성) | 🔴 빨간 원 (실패/중요) | 🟡 노란 원 (주의/진행 중) | 🔄 업데이트/진행 중 | ⏱️ 대기 중/시간 관련 | 🔍 검토 중/검색\n\n"
        "개발 관련 이모지:\n"
        "💻 코드/프로그래밍 | 🔧 도구/설정 | 🐛 버그 | 📦 패키지/모듈 | 📝 문서/노트 | 🗂️ 폴더/분류 | ⚙️ 설정/구성 | 🔒 보안/잠금 | 📊 데이터/통계 | 📈 성장/증가\n\n"
        "섹션 구분 이모지:\n"
        "📋 목록/체크리스트 | 📚 책/문서 | 💡 아이디어/팁 | ⚠️ 주의/경고 | 🎯 목표/타겟 | 🔗 링크/연결 | 👥 사용자/팀 | 📅 일정/캘린더\n\n"
        "기타 유용한 이모지:\n"
        "🌟 하이라이트/중요 항목 | ✨ 특별/개선 항목 | 📱 모바일 | 🖥️ 데스크톱 | 🏗️ 아키텍처 | 🚧 작업 중 | 💬 의견/코멘트 | 🌐 웹/글로벌 | 📤 배포/업로드 | 📥 다운로드/수신"
    )
    
    messages = [
        {"role": "system", "content": (
            "당신은 친절하고 상호작용적인 AI 챗봇입니다. 사용자의 질문에 답하고, 필요하면 추가 질문을 던져 대화를 이어가세요. "
            "응답 내용에 따라 적절한 이모지를 아래 목록에서 선택해 자연스럽게 삽입하세요. 이모지는 문맥에 맞게 사용하고, 과도하게 많지 않도록 하세요:\n\n" + emoji_list
        )}] + [
        {"role": msg["role"], "content": msg["content"]} for msg in chat_history[-5:]
    ] + [{"role": "user", "content": query}]
    
    response = client.chat.completions.create(model="gpt-4", messages=messages)
    result = response.choices[0].message.content
    conversation_cache.setex(cache_key, 600, result)
    return result

GREETING_RESPONSES = {
    "안녕": "안녕하세요! 반갑습니다! 😊",
    "안녕 반가워": "안녕하세요! 저도 반갑습니다! 오늘 기분이 어떠신가요? 😄",
    "하이": "하이! 무엇을 도와드릴까요? 😊",
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
    pubmed_keywords = ["의학논문"]
    if any(kw in query_lower for kw in pubmed_keywords) and len(query_lower) > 5:
        return "pubmed_search"
    sports_keywords = ["경기일정", "경기 일정", "스케줄", "일정"]
    league_keywords = list(LEAGUE_MAPPING.keys())
    if any(kw in query_lower for kw in sports_keywords):
        for league in league_keywords:
            if league in query_lower:
                return "league_schedule"
        for pattern in SPORTS_PATTERNS:
            match = pattern.search(query)
            if match:
                return "sports_schedule"
    search_keywords = ["검색", "알려줘", "정보", "뭐야", "무엇이야", "무엇인지", "찾아서", "정리해줘", "설명해줘", "알고싶어", "알려줄래","알아","뭐냐", "알려줘", "찾아줘"]
    if any(kw in query_lower for kw in search_keywords) and len(query_lower) > 5:
        return "web_search"
    return "general_query"

# UI 함수
def show_login_page():
    st.title("로그인 🤗")
    with st.form("login_form"):
        nickname = st.text_input("닉네임", placeholder="예: 후안")
        submit_button = st.form_submit_button("시작하기 🚀")
        
        if submit_button:
            if nickname:
                try:
                    user_id, is_existing = create_or_get_user(nickname)
                    st.session_state.user_id = user_id
                    st.session_state.is_logged_in = True
                    st.session_state.chat_history = []
                    st.session_state.session_id = str(uuid.uuid4())
                    
                    if is_existing:
                        st.toast(f"환영합니다, {nickname}님! 🎉")
                    else:
                        st.toast(f"새로운 사용자로 등록되었습니다. 환영합니다, {nickname}님! 🎉")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.toast(f"로그인 중 오류가 발생했습니다. 다시 시도해주세요.", icon="❌")
            else:
                st.toast("닉네임을 입력해주세요.", icon="⚠️")

@st.cache_data(ttl=600)
def get_cached_response(query):
    return process_query(query)

def process_query(query):
    init_session_state()
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
    elif query_type == "sports_schedule":
        team = extract_team_from_query(query)
        month = extract_month_from_query(query)
        return sports_api.fetch_team_schedule(team, month)
    elif query_type == "league_schedule":
        league_key = extract_league_from_query(query)
        month = extract_month_from_query(query)
        return sports_api.fetch_league_schedule(league_key, month)
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
    elif query_type == "pubmed_search":
        keywords = query.replace("의학논문", "").strip()
        return get_pubmed_papers(keywords)
    elif query_type == "general_query":
        return get_conversational_response(query, st.session_state.chat_history)
    return "아직 지원하지 않는 기능이에요. 😅"

def handle_error(e, context="작업 중", user_friendly_msg="응답을 준비하다 문제가 생겼어요. 😓"):
    logger.error(f"{context} 오류 발생: {str(e)}", exc_info=True)
    return user_friendly_msg

def show_chat_dashboard():
    st.title("AI 챗봇 🤖")
    
    init_session_state()
    
    if st.button("도움말 ℹ️"):
        st.info(
            "챗봇과 더 쉽게 대화하는 방법이에요! 👇:\n\n"
            "1. **약품검색** 💊: '약품검색 [약 이름]' (예: 약품검색 타이레놀정)\n"
            "2. **논문검색 (ArXiv)** 📚: '논문검색 [키워드]' (예: 논문검색 machine learning)\n"
            "3. **의학논문검색 (PubMed)** 🩺: '의학논문 [키워드]' (예: 의학논문 gene therapy)\n"
            "4. **날씨검색** ☀️: '[도시명] 날씨' 또는 '내일 [도시명] 날씨' (예: 서울 날씨, 내일 서울 날씨)\n"
            "5. **시간검색** ⏱️: '[도시명] 시간' (예: 파리 시간, 뉴욕 시간)\n"
            "6. **경기일정 검색** ⚽: \n"
            "   - 팀별 일정: '[팀 이름] [월] 경기일정' (예: AT 마드리드 3월 경기일정)\n"
            "   - 리그별 일정: '[리그 이름] [월] 경기일정' (예: EPL 3월 경기일정)\n"
            "   - 지원 리그: EPL, Bundesliga, Serie A, Ligue 1, Europa League, K League 1, AFC Champions League Elite\n\n"
            "궁금한 점이 있으면 언제든 질문해주세요! 😊"
        )
    
    for msg in st.session_state.chat_history:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'], unsafe_allow_html=True)
    
    if user_prompt := st.chat_input("질문해 주세요!"):
        st.chat_message("user").markdown(user_prompt)
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})
        with st.chat_message("assistant"):
            try:
                with st.spinner("응답을 준비 중이에요.. ⏳"):
                    start_time = time.time()
                    with ThreadPoolExecutor() as executor:
                        future = executor.submit(get_cached_response, user_prompt)
                        response = future.result()
                    time_taken = round(time.time() - start_time, 2)
                
                st.markdown(response, unsafe_allow_html=True)
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                async_save_chat_history(st.session_state.user_id, st.session_state.session_id, user_prompt, response, time_taken)
            
            except Exception as e:
                error_msg = handle_error(e, "대화 처리 중", "응답을 준비하다 문제가 생겼어요. 😓")
                st.markdown(error_msg, unsafe_allow_html=True)
                st.session_state.chat_history.append({"role": "assistant", "content": error_msg})

# 메인 실행
def main():
    init_session_state()
    if not st.session_state.is_logged_in:
        show_login_page()
    else:
        show_chat_dashboard()

if __name__ == "__main__":
    main()

# from config.imports import *
# from config.env import *

# # 로깅 설정
# logging.basicConfig(
#     level=logging.WARNING if os.getenv("ENV") == "production" else logging.INFO,
#     filename="chatbot_errors.log",
#     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
# )
# logger = logging.getLogger("HybridChat")

# # 병렬 처리 설정
# MAX_WORKERS = min(multiprocessing.cpu_count() * 2, 8)

# # 캐시 설정
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

# # 공통 에러 처리 함수
# def handle_error(e, context="작업 중", user_friendly_msg="알 수 없는 오류가 발생했어요. 😅 다시 시도해 주세요!"):
#     logger.error(f"{context} 오류 발생: {str(e)}", exc_info=True)
#     return f"{user_friendly_msg}\n\n⚠️ 오류 내용: {str(e)}"

# # WeatherAPI 클래스
# class WeatherAPI:
#     def __init__(self, cache_ttl=600):
#         self.cache = cache_handler
#         self.cache_ttl = cache_ttl

#     def fetch_weather(self, url, params):
#         try:
#             session = requests.Session()
#             retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
#             adapter = HTTPAdapter(max_retries=retry_strategy)
#             session.mount("https://", adapter)
#             logger.info(f"날씨 API 요청: {url} with params {params}")
#             response = session.get(url, params=params, timeout=3)
#             response.raise_for_status()
#             return response.json()
#         except requests.RequestException as e:
#             return handle_error(e, "날씨 API 호출 중", f"날씨 정보를 가져오지 못했어요. API 키를 확인해 주세요. 🌧️")

#     @lru_cache(maxsize=100)
#     def get_city_info(self, city_name):
#         cache_key = f"city_info:{city_name}"
#         cached = self.cache.get(cache_key)
#         if cached:
#             return cached
#         try:
#             url = "http://api.openweathermap.org/geo/1.0/direct"
#             params = {'q': city_name, 'limit': 1, 'appid': WEATHER_API_KEY}
#             with ThreadPoolExecutor(max_workers=1) as executor:
#                 future = executor.submit(self.fetch_weather, url, params)
#                 data = future.result()
#             if isinstance(data, str):
#                 return data
#             if data and len(data) > 0:
#                 city_info = {"name": data[0]["name"], "lat": data[0]["lat"], "lon": data[0]["lon"]}
#                 self.cache.setex(cache_key, 86400, city_info)
#                 return city_info
#             return None
#         except Exception as e:
#             return handle_error(e, "도시 정보 조회 중", f"'{city_name}' 위치 정보를 찾지 못했어요. 🗺️")

#     def get_city_weather(self, city_name):
#         cache_key = f"weather:{city_name}"
#         cached_data = self.cache.get(cache_key)
#         if cached_data:
#             return cached_data
        
#         city_info = self.get_city_info(city_name)
#         if not city_info or isinstance(city_info, str):
#             return city_info if isinstance(city_info, str) else f"'{city_name}'의 날씨 정보를 가져올 수 없습니다."
        
#         try:
#             url = "https://api.openweathermap.org/data/2.5/weather"
#             params = {'lat': city_info["lat"], 'lon': city_info["lon"], 'appid': WEATHER_API_KEY, 'units': 'metric', 'lang': 'kr'}
#             with ThreadPoolExecutor(max_workers=1) as executor:
#                 future = executor.submit(self.fetch_weather, url, params)
#                 data = future.result()
#             if isinstance(data, str):
#                 return data
#             weather_emojis = {'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Snow': '❄️', 'Thunderstorm': '⛈️', 'Drizzle': '🌦️', 'Mist': '🌫️'}
#             weather_emoji = weather_emojis.get(data['weather'][0]['main'], '🌤️')
#             result = (
#                 f"현재 {data['name']}, {data['sys']['country']} 날씨 {weather_emoji}\n"
#                 f"날씨: {data['weather'][0]['description']}\n"
#                 f"온도: {data['main']['temp']}°C\n"
#                 f"체감: {data['main']['feels_like']}°C\n"
#                 f"습도: {data['main']['humidity']}%\n"
#                 f"풍속: {data['wind']['speed']}m/s\n"
#                 f"더 궁금한 점 있나요? 😊"
#             )
#             self.cache.setex(cache_key, self.cache_ttl, result)
#             return result
#         except Exception as e:
#             return handle_error(e, "현재 날씨 조회 중", f"'{city_name}' 날씨 정보를 가져오지 못했어요. 🌦️")

#     def get_forecast_by_day(self, city_name, days_from_today=1):
#         cache_key = f"forecast:{city_name}:{days_from_today}"
#         cached_data = self.cache.get(cache_key)
#         if cached_data:
#             return cached_data
        
#         city_info = self.get_city_info(city_name)
#         if not city_info or isinstance(city_info, str):
#             return city_info if isinstance(city_info, str) else f"'{city_name}'의 날씨 예보를 가져올 수 없습니다."
        
#         try:
#             url = "https://api.openweathermap.org/data/2.5/forecast"
#             params = {'lat': city_info["lat"], 'lon': city_info["lon"], 'appid': WEATHER_API_KEY, 'units': 'metric', 'lang': 'kr'}
#             with ThreadPoolExecutor(max_workers=1) as executor:
#                 future = executor.submit(self.fetch_weather, url, params)
#                 data = future.result()
#             if isinstance(data, str):
#                 return data
#             target_date = (datetime.now() + timedelta(days=days_from_today)).strftime('%Y-%m-%d')
#             forecast_text = f"{city_info['name']}의 {target_date} 날씨 예보 🌤️\n\n"
#             weather_emojis = {'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Snow': '❄️', 'Thunderstorm': '⛈️', 'Drizzle': '🌦️', 'Mist': '🌫️'}
#             found = False

#             forecast_lines = []
#             for forecast in data['list']:
#                 dt = datetime.fromtimestamp(forecast['dt']).strftime('%Y-%m-%d')
#                 if dt == target_date:
#                     time_only = datetime.fromtimestamp(forecast['dt']).strftime('%H:%M')
#                     weather_emoji = weather_emojis.get(forecast['weather'][0]['main'], '🌤️')
#                     forecast_lines.append(
#                         f"⏰ {time_only} {forecast['weather'][0]['description']} {weather_emoji} "
#                         f"{forecast['main']['temp']}°C 💧{forecast['main']['humidity']}% 🌬️{forecast['wind']['speed']}m/s"
#                     )
#                     found = True
            
#             forecast_text += "\n\n".join(forecast_lines)
#             result = forecast_text + "\n\n더 궁금한 점 있나요? 😊" if found else f"'{city_name}'의 {target_date} 날씨 예보를 찾을 수 없습니다."
#             self.cache.setex(cache_key, self.cache_ttl, result)
#             return result
#         except Exception as e:
#             return handle_error(e, "날씨 예보 조회 중", f"'{city_name}' 예보를 가져오지 못했어요. ⛅")

#     def get_weekly_forecast(self, city_name):
#         cache_key = f"weekly_forecast:{city_name}"
#         cached_data = self.cache.get(cache_key)
#         if cached_data:
#             return cached_data
        
#         city_info = self.get_city_info(city_name)
#         if not city_info or isinstance(city_info, str):
#             return city_info if isinstance(city_info, str) else f"'{city_name}'의 주간 예보를 가져올 수 없습니다."
        
#         try:
#             url = "https://api.openweathermap.org/data/2.5/forecast"
#             params = {'lat': city_info["lat"], 'lon': city_info["lon"], 'appid': WEATHER_API_KEY, 'units': 'metric', 'lang': 'kr'}
#             with ThreadPoolExecutor(max_workers=1) as executor:
#                 future = executor.submit(self.fetch_weather, url, params)
#                 data = future.result()
#             if isinstance(data, str):
#                 return data
            
#             today = datetime.now().date()
#             week_end = today + timedelta(days=6)
#             daily_forecast = {}
#             weekdays_kr = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
#             today_weekday = today.weekday()

#             for forecast in data['list']:
#                 dt = datetime.fromtimestamp(forecast['dt']).date()
#                 if today <= dt <= week_end:
#                     dt_str = dt.strftime('%Y-%m-%d')
#                     weekday_idx = (today_weekday + (dt - today).days) % 7
#                     info = {
#                         'weekday': weekdays_kr[weekday_idx],
#                         'temp_min': forecast['main']['temp_min'],
#                         'temp_max': forecast['main']['temp_max'],
#                         'weather': forecast['weather'][0]['description']
#                     }
#                     if dt_str not in daily_forecast:
#                         daily_forecast[dt_str] = info
#                     else:
#                         daily_forecast[dt_str]['temp_min'] = min(daily_forecast[dt_str]['temp_min'], info['temp_min'])
#                         daily_forecast[dt_str]['temp_max'] = max(daily_forecast[dt_str]['temp_max'], info['temp_max'])
            
#             today_str = today.strftime('%Y-%m-%d')
#             today_weekday_str = weekdays_kr[today_weekday]
#             forecast_text = f"{today_str}({today_weekday_str}) 기준 {city_info['name']}의 주간 날씨 예보 🌤️\n"
#             weather_emojis = {'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Snow': '❄️', 'Thunderstorm': '⛈️', 'Drizzle': '🌦️', 'Mist': '🌫️'}
            
#             for date, info in daily_forecast.items():
#                 weather_emoji = weather_emojis.get(info['weather'].split()[0], '🌤️')
#                 forecast_text += (
#                     f"{info['weekday']}: {info['weather']} {weather_emoji} "
#                     f"최저 {info['temp_min']}°C 최고 {info['temp_max']}°C\n"
#                 )
            
#             result = forecast_text + "\n더 궁금한 점 있나요? 😊"
#             self.cache.setex(cache_key, self.cache_ttl, result)
#             return result
#         except Exception as e:
#             return handle_error(e, "주간 날씨 예보 조회 중", f"'{city_name}' 주간 예보를 가져오지 못했어요. ☔")

# # 초기화
# supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
# client = Client()
# weather_api = WeatherAPI()
# naver_request_count = 0
# NAVER_DAILY_LIMIT = 25000
# st.set_page_config(page_title="AI 챗봇", page_icon="🤖")

# # 세션 상태 초기화 함수
# def init_session_state():
#     if "is_logged_in" not in st.session_state:
#         st.session_state.is_logged_in = False
#     if "user_id" not in st.session_state:
#         st.session_state.user_id = None
#     if "chat_history" not in st.session_state:
#         st.session_state.chat_history = []
#     if "session_id" not in st.session_state:
#         st.session_state.session_id = str(uuid.uuid4())

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
#     try:
#         city_info = weather_api.get_city_info(city_name)
#         if not city_info or isinstance(city_info, str):
#             return city_info if isinstance(city_info, str) else f"'{city_name}'의 시간 정보를 가져올 수 없습니다."
#         tf = TimezoneFinder()
#         timezone_str = tf.timezone_at(lng=city_info["lon"], lat=city_info["lat"]) or "Asia/Seoul"
#         timezone = pytz.timezone(timezone_str)
#         city_time = datetime.now(timezone)
#         am_pm = "오전" if city_time.strftime("%p") == "AM" else "오후"
#         return f"현재 {city_name} 시간: {city_time.strftime('%Y년 %m월 %d일 %p %I:%M')} ⏰\n더 궁금한 점 있나요? 😊"
#     except Exception as e:
#         return handle_error(e, "시간 정보 조회 중", f"'{city_name}'의 시간을 가져오지 못했어요. ⏱️")

# # 사용자 및 채팅 기록 관리
# def create_or_get_user(nickname):
#     try:
#         user = supabase.table("users").select("*").eq("nickname", nickname).execute()
#         if user.data:
#             return user.data[0]["id"], True
#         new_user = supabase.table("users").insert({"nickname": nickname, "created_at": datetime.now().isoformat()}).execute()
#         return new_user.data[0]["id"], False
#     except Exception as e:
#         return handle_error(e, "사용자 생성/조회 중", "사용자 정보를 처리하지 못했어요. 😓"), False

# def save_chat_history(user_id, session_id, question, answer, time_taken):
#     try:
#         supabase.table("chat_history").insert({
#             "user_id": user_id, "session_id": session_id, "question": question,
#             "answer": answer, "time_taken": time_taken, "created_at": datetime.now().isoformat()
#         }).execute()
#     except Exception as e:
#         logger.error(f"채팅 기록 저장 실패: {str(e)}")

# def async_save_chat_history(user_id, session_id, question, answer, time_taken):
#     threading.Thread(target=save_chat_history, args=(user_id, session_id, question, answer, time_taken)).start()

# # 의약품 검색
# def get_drug_info(drug_query):
#     drug_name = drug_query.replace("약품검색", "").strip()
#     cache_key = f"drug:{drug_name}"
#     cached = cache_handler.get(cache_key)
#     if cached:
#         return cached
    
#     url = 'http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList'
#     params = {'serviceKey': DRUG_API_KEY, 'pageNo': '1', 'numOfRows': '1', 'itemName': urllib.parse.quote(drug_name), 'type': 'json'}
    
#     try:
#         with ThreadPoolExecutor(max_workers=1) as executor:
#             future = executor.submit(requests.get, url, params=params, timeout=3)
#             response = future.result()
#         response.raise_for_status()
#         data = response.json()
#         if 'body' in data and 'items' in data['body'] and data['body']['items']:
#             item = data['body']['items'][0]
#             efcy = item.get('efcyQesitm', '정보 없음')[:150] + ("..." if len(item.get('efcyQesitm', '')) > 150 else "")
#             use_method_raw = item.get('useMethodQesitm', '정보 없음')
#             atpn = item.get('atpnQesitm', '정보 없음')[:150] + ("..." if len(item.get('atpnQesitm', '')) > 150 else "")
#             use_method = use_method_raw[:150] + ("..." if len(use_method_raw) > 150 else "")
#             result = (
#                 f"💊 **의약품 정보** 💊\n\n"
#                 f"✅ **약품명**: {item.get('itemName', '정보 없음')}\n\n"
#                 f"✅ **제조사**: {item.get('entpName', '정보 없음')}\n\n"
#                 f"✅ **효능**: {efcy}\n\n"
#                 f"✅ **용법용량**: {use_method}\n\n"
#                 f"✅ **주의사항**: {atpn}\n\n"
#                 f"ℹ️ 자세한 정보는 [약학정보원](https://www.health.kr/searchDrug/search_detail.asp)에서 확인하세요! 🩺\n\n"
#                 f"더 궁금한 점 있으신가요? 😊"
#             )
#             cache_handler.setex(cache_key, 86400, result)
#             return result
#         else:
#             return search_and_summarize_drug(drug_name)
#     except requests.RequestException as e:
#         logger.warning(f"약품 API 호출 실패, 웹 검색으로 전환: {drug_name}")
#         return search_and_summarize_drug(drug_name)
#     except Exception as e:
#         return handle_error(e, "약품 정보 조회 중", f"'{drug_name}' 정보를 가져오는 데 실패했어요. 💊")

# def search_and_summarize_drug(drug_name):
#     try:
#         search_results = search_and_summarize(f"{drug_name} 의약품 정보", num_results=5)
#         if not search_results.empty:
#             return f"'{drug_name}' 공식 정보 없음. 웹 검색 요약:\n{get_ai_summary(search_results)}"
#         return f"'{drug_name}' 의약품 정보를 찾을 수 없습니다."
#     except Exception as e:
#         return handle_error(e, "약품 웹 검색 중", f"'{drug_name}' 검색에 실패했어요. 🔍")

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
#         with ThreadPoolExecutor(max_workers=1) as executor:
#             future = executor.submit(urllib.request.urlopen, request)
#             response = future.result()
#         naver_request_count += 1
#         if response.getcode() == 200:
#             data = json.loads(response.read().decode('utf-8'))
#             for item in data.get('items', [])[:5]:
#                 title = re.sub(r'<b>|</b>', '', item['title'])
#                 contents = re.sub(r'<b>|</b>', '', item.get('description', '내용 없음'))[:100] + "..."
#                 results.append({"title": title, "contents": contents, "url": item.get('link', ''), "date": item.get('pubDate', '')})
#     except Exception:
#         logger.warning(f"Naver API 호출 실패, 웹 검색으로 전환: {query}")
#         return search_and_summarize(query, num_results=5)
#     return pd.DataFrame(results)

# def search_and_summarize(query, num_results=5):
#     data = []
#     with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
#         futures = [executor.submit(requests.get, link, timeout=3) for link in search(query, num_results=num_results)]
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

# def process_search_result(row):
#     try:
#         return f"출처: {row['title']}\n내용: {row['contents']}"
#     except Exception:
#         return ""

# def get_ai_summary(search_results):
#     try:
#         if search_results.empty:
#             return "검색 결과를 찾을 수 없습니다."
#         context = "\n".join(process_search_result(row) for _, row in search_results.iterrows())
#         with ThreadPoolExecutor(max_workers=1) as executor:
#             future = executor.submit(client.chat.completions.create, model="gpt-4o", messages=[{"role": "user", "content": f"검색 결과를 2~3문장으로 요약:\n{context}"}])
#             response = future.result()
#         summary = response.choices[0].message.content
#         sources = "\n\n📜 **출처**\n" + "\n".join(
#             [f"🌐 [{row['title']}]({row.get('link', '링크 없음')})" for _, row in search_results.iterrows()]
#         )
#         return f"{summary}{sources}\n\n더 궁금한 점 있나요? 😊"
#     except Exception as e:
#         return handle_error(e, "검색 결과 요약 중", "검색 결과를 요약하지 못했어요. 😓")

# # 논문 검색 (ArXiv)
# def fetch_arxiv_paper(paper):
#     try:
#         return {
#             "title": paper.title,
#             "authors": ", ".join(str(a) for a in paper.authors),
#             "summary": paper.summary[:200],
#             "entry_id": paper.entry_id,
#             "pdf_url": paper.pdf_url,
#             "published": paper.published.strftime('%Y-%m-%d')
#         }
#     except Exception as e:
#         return handle_error(e, "ArXiv 논문 처리 중", "논문 정보를 가져오지 못했어요. 📄")

# def get_arxiv_papers(query, max_results=3):
#     cache_key = f"arxiv:{query}:{max_results}"
#     cached = cache_handler.get(cache_key)
#     if cached:
#         return cached
    
#     try:
#         search_obj = arxiv.Search(query=query, max_results=max_results, sort_by=arxiv.SortCriterion.SubmittedDate)
#         with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
#             results = list(executor.map(fetch_arxiv_paper, search_obj.results()))
#         if not results:
#             return "해당 키워드로 논문을 찾을 수 없습니다."
        
#         response = "📚 **Arxiv 논문 검색 결과** 📚\n\n"
#         response += "\n\n".join(
#             [f"**논문 {i}**\n\n"
#              f"📄 **제목**: {r['title']}\n\n"
#              f"👥 **저자**: {r['authors']}\n\n"
#              f"📝 **초록**: {r['summary']}...\n\n"
#              f"🔗 **논문 페이지**: {r['entry_id']}\n\n"
#              f"📥 **PDF 다운로드**: [{r['pdf_url'].split('/')[-1]}]({r['pdf_url']})\n\n"
#              f"📅 **출판일**: {r['published']}\n\n"
#              f"{'-' * 50}"
#              for i, r in enumerate(results, 1) if not isinstance(r, str)]
#         ) + "\n\n더 많은 논문을 보고 싶다면 말씀해 주세요! 😊"
#         cache_handler.setex(cache_key, 3600, response)
#         return response
#     except Exception as e:
#         return handle_error(e, "ArXiv 논문 검색 중", "논문 검색에 실패했어요. 📚")

# # PubMed 논문 검색
# base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

# def search_pubmed(query, max_results=5):
#     search_url = f"{base_url}esearch.fcgi"
#     params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": max_results, "api_key": NCBI_KEY}
#     try:
#         with ThreadPoolExecutor(max_workers=1) as executor:
#             future = executor.submit(requests.get, search_url, params=params)
#             response = future.result()
#         response.raise_for_status()
#         return response.json()
#     except requests.RequestException as e:
#         return handle_error(e, "PubMed 검색 중", "의학 논문 검색에 실패했어요. 🩺")

# def get_pubmed_summaries(id_list):
#     summary_url = f"{base_url}esummary.fcgi"
#     ids = ",".join(id_list)
#     params = {"db": "pubmed", "id": ids, "retmode": "json", "api_key": NCBI_KEY}
#     try:
#         with ThreadPoolExecutor(max_workers=1) as executor:
#             future = executor.submit(requests.get, summary_url, params=params)
#             response = future.result()
#         response.raise_for_status()
#         return response.json()
#     except requests.RequestException as e:
#         return handle_error(e, "PubMed 요약 조회 중", "논문 요약을 가져오지 못했어요. 📖")

# def get_pubmed_abstract(id_list):
#     fetch_url = f"{base_url}efetch.fcgi"
#     ids = ",".join(id_list)
#     params = {"db": "pubmed", "id": ids, "retmode": "xml", "rettype": "abstract", "api_key": NCBI_KEY}
#     try:
#         with ThreadPoolExecutor(max_workers=1) as executor:
#             future = executor.submit(requests.get, fetch_url, params=params)
#             response = future.result()
#         response.raise_for_status()
#         return response.text
#     except requests.RequestException as e:
#         return handle_error(e, "PubMed 초록 조회 중", "논문 초록을 가져오지 못했어요. 📝")

# def extract_first_two_sentences(abstract_text):
#     if not abstract_text or abstract_text.isspace():
#         return "No abstract available"
#     sentences = [s.strip() for s in abstract_text.split('.') if s.strip()]
#     return " ".join(sentences[:2]) + "." if sentences else "No abstract available"

# def parse_abstracts(xml_text):
#     abstract_dict = {}
#     try:
#         root = ET.fromstring(xml_text)
#         for article in root.findall(".//PubmedArticle"):
#             pmid_elem = article.find(".//MedlineCitation/PMID")
#             abstract_elem = article.find(".//Abstract/AbstractText")
#             pmid = pmid_elem.text if pmid_elem is not None else None
#             abstract = abstract_elem.text if abstract_elem is not None else "No abstract available"
#             if pmid:
#                 abstract_dict[pmid] = extract_first_two_sentences(abstract)
#     except ET.ParseError as e:
#         logger.error(f"PubMed XML 파싱 오류: {e}")
#         return {}
#     return abstract_dict

# def get_pubmed_papers(query, max_results=5):
#     if "tissuge" in query.lower():
#         query = query.replace("tissuge", "tissue")
#         logger.info(f"오타 보정: {query}")
    
#     cache_key = f"pubmed:{query}:{max_results}"
#     cached = cache_handler.get(cache_key)
#     if cached:
#         return cached
    
#     try:
#         search_results = search_pubmed(query, max_results)
#         if isinstance(search_results, str):
#             return search_results
#         pubmed_ids = search_results["esearchresult"]["idlist"]
#         if not pubmed_ids:
#             return f"'{query}'로 의학 논문을 찾을 수 없습니다. 키워드를 확인해 주세요."
        
#         summaries = get_pubmed_summaries(pubmed_ids)
#         if isinstance(summaries, str):
#             return summaries
        
#         abstracts_xml = get_pubmed_abstract(pubmed_ids)
#         if isinstance(abstracts_xml, str):
#             return abstracts_xml
#         abstract_dict = parse_abstracts(abstracts_xml)
        
#         response = "📚 **PubMed 의학 논문 검색 결과** 📚\n\n"
#         for i, pmid in enumerate(pubmed_ids, 1):
#             summary = summaries['result'].get(pmid, {})
#             title = summary.get('title', 'No title available')
#             pubdate = summary.get('pubdate', 'No date available')
#             authors = ", ".join(author.get('name', '') for author in summary.get('authors', [])) or "No authors available"
#             doi = next((aid['value'] for aid in summary.get('articleids', []) if aid['idtype'] == 'doi'), None)
#             link = f"https://doi.org/{doi}" if doi else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
#             abstract = abstract_dict.get(pmid, "No abstract available")
            
#             response += (
#                 f"**논문 {i}**\n\n"
#                 f"🆔 **PMID**: {pmid}\n\n"
#                 f"📖 **제목**: {title}\n\n"
#                 f"📅 **출판일**: {pubdate}\n\n"
#                 f"✍️ **저자**: {authors}\n\n"
#                 f"🔗 **링크**: {link}\n\n"
#                 f"📝 **초록**: {abstract}\n\n"
#                 f"{'-' * 50}\n\n"
#             )
        
#         response += "더 많은 의학 논문을 보고 싶다면 말씀해 주세요! 😊"
#         cache_handler.setex(cache_key, 3600, response)
#         return response
#     except Exception as e:
#         return handle_error(e, "PubMed 논문 검색 중", "의학 논문 검색에 실패했어요. 🩺")

# # 대화형 응답
# conversation_cache = MemoryCache()
# def get_conversational_response(query, chat_history):
#     cache_key = f"conv:{needs_search(query)}:{query}:{hash(str(chat_history[-5:]))}"
#     cached = conversation_cache.get(cache_key)
#     if cached:
#         return cached
    
#     emoji_list = (
#         "체크리스트 이모지:\n✅ 완료된 항목 | ☑️ 체크 상자 (체크됨) | ✓ 체크 표시 | ✔️ 굵은 체크 표시 | ❌ 취소/실패 항목 | ⬜ 빈 상자 | ⚪ 빈 원 | 🔘 라디오 버튼 | 📌 핀으로 고정된 항목 | 🚀 시작/출시 항목\n\n"
#         "상태 표시 이모지:\n🟢 녹색 원 (성공/활성) | 🔴 빨간 원 (실패/중요) | 🟡 노란 원 (주의/진행 중) | 🔄 업데이트/진행 중 | ⏱️ 대기 중/시간 관련 | 🔍 검토 중/검색\n\n"
#         "개발 관련 이모지:\n💻 코드/프로그래밍 | 🔧 도구/설정 | 🐛 버그 | 📦 패키지/모듈 | 📝 문서/노트 | 🗂️ 폴더/분류 | ⚙️ 설정/구성 | 🔒 보안/잠금 | 📊 데이터/통계 | 📈 성장/증가\n\n"
#         "섹션 구분 이모지:\n📋 목록/체크리스트 | 📚 책/문서 | 💡 아이디어/팁 | ⚠️ 주의/경고 | 🎯 목표/타겟 | 🔗 링크/연결 | 👥 사용자/팀 | 📅 일정/캘린더\n\n"
#         "기타 유용한 이모지:\n🌟 하이라이트/중요 항목 | ✨ 특별/개선 항목 | 📱 모바일 | 🖥️ 데스크톱 | 🏗️ 아키텍처 | 🚧 작업 중 | 💬 의견/코멘트 | 🌐 웹/글로벌 | 📤 배포/업로드 | 📥 다운로드/수신"
#     )
    
#     messages = [
#         {"role": "system", "content": (
#             "당신은 친절하고 상호작용적인 AI 챗봇입니다. 사용자의 질문에 답하고, 필요하면 추가 질문을 던져 대화를 이어가세요. "
#             "응답 내용에 따라 적절한 이모지를 아래 목록에서 선택해 자연스럽게 삽입하세요. 이모지는 문맥에 맞게 사용하고, 과도하게 많지 않도록 하세요:\n\n" + emoji_list
#         )}] + [
#         {"role": msg["role"], "content": msg["content"]} for msg in chat_history[-5:]
#     ] + [{"role": "user", "content": query}]
    
#     try:
#         response = client.chat.completions.create(model="gpt-4", messages=messages)
#         result = response.choices[0].message.content
#         conversation_cache.setex(cache_key, 3600, result)
#         return result
#     except Exception as e:
#         return handle_error(e, "GPT 대화 생성 중", "대화를 생성하는 데 문제가 생겼어요. 😓 잠시 후 다시 물어보세요!")

# GREETING_RESPONSES = {
#     "안녕": "안녕하세요! 반갑습니다! 😊",
#     "안녕 반가워": "안녕하세요! 저도 반갑습니다! 오늘 기분이 어떠신가요? 😄",
#     "하이": "하이! 무엇을 도와드릴까요? 😊",
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
#     drug_keywords = ["약품검색"]
#     drug_pattern = r'^약품검색\s+[가-힣a-zA-Z]{2,10}(?:약|정|시럽|캡슐)?$'
#     if any(keyword in query_lower for keyword in drug_keywords) and re.match(drug_pattern, query_lower):
#         return "drug"
#     if query_lower == "mbti 검사":
#         return "mbti"
#     if query_lower == "다중지능 검사":
#         return "multi_iq"
#     arxiv_keywords = ["논문검색", "arxiv", "paper", "research"]
#     if any(kw in query_lower for kw in arxiv_keywords) and len(query_lower) > 5:
#         return "arxiv_search"
#     pubmed_keywords = ["의학논문"]
#     if any(kw in query_lower for kw in pubmed_keywords) and len(query_lower) > 5:
#         return "pubmed_search"
#     search_keywords = ["검색", "알려줘", "정보", "뭐야", "무엇이야", "무엇인지", "찾아서", "정리해줘", "설명해줘", "알고싶어", "알려줄래", "알아", "뭐냐", "알려줘", "찾아줘"]
#     if any(kw in query_lower for kw in search_keywords) and len(query_lower) > 5:
#         return "web_search"
#     return "general_query"

# # UI 함수
# def show_login_page():
#     st.title("로그인 🤗")
#     with st.form("login_form"):
#         nickname = st.text_input("닉네임", placeholder="예: 후안")
#         submit_button = st.form_submit_button("시작하기 🚀")
        
#         if submit_button:
#             if nickname:
#                 try:
#                     user_id, is_existing = create_or_get_user(nickname)
#                     if isinstance(user_id, str):
#                         st.toast(user_id, icon="❌")
#                         return
#                     st.session_state.user_id = user_id
#                     st.session_state.is_logged_in = True
#                     st.session_state.chat_history = []
#                     st.session_state.session_id = str(uuid.uuid4())
                    
#                     if is_existing:
#                         st.toast(f"환영합니다, {nickname}님! 🎉")
#                     else:
#                         st.toast(f"새로운 사용자로 등록되었습니다. 환영합니다, {nickname}님! 🎉")
#                     time.sleep(1)
#                     st.rerun()
#                 except Exception as e:
#                     st.toast(handle_error(e, "로그인 처리 중", "로그인에 실패했어요. 😓"), icon="❌")
#             else:
#                 st.toast("닉네임을 입력해주세요.", icon="⚠️")

# @st.cache_data(ttl=3600, show_spinner=False)
# def get_cached_response(query):
#     return process_query(query)

# def fetch_city_weather(city, weather_api):
#     return weather_api.get_city_weather(city)

# def process_query(query):
#     init_session_state()
#     query_type = needs_search(query)
    
#     try:
#         if query_type == "mbti":
#             return (
#                 "MBTI 검사를 원하시나요? ✨ 아래 사이트에서 무료로 성격 유형 검사를 할 수 있어요! 😊\n"
#                 "[16Personalities MBTI 검사](https://www.16personalities.com/ko/%EB%AC%B4%EB%A3%8C-%EC%84%B1%EA%B2%A9-%EC%9C%A0%ED%98%95-%EA%B2%80%EC%82%AC) 🌟\n"
#                 "이 사이트는 16가지 성격 유형을 기반으로 한 테스트를 제공하며, 결과에 따라 성격 설명과 인간관계 조언 등을 확인할 수 있어요! 🧠💡"
#             )
#         elif query_type == "multi_iq":
#             return (
#                 "다중지능 검사를 원하시나요? 🎉 아래 사이트에서 무료로 다중지능 테스트를 해볼 수 있어요! 😄\n"
#                 "[Multi IQ Test](https://multiiqtest.com/) 🚀\n"
#                 "이 사이트는 하워드 가드너의 다중지능 이론을 기반으로 한 테스트를 제공하며, 다양한 지능 영역을 평가해줍니다! 📚✨"
#             )
#         elif query_type == "time":
#             city = extract_city_from_time_query(query)
#             return get_time_by_city(city)
#         elif query_type == "weather":
#             cities = [city.strip() for city in query.split("와") if "날씨" in city] or [extract_city_from_query(query)]
#             results = []
#             q = queue.Queue()
#             for city in cities:
#                 q.put(city)
            
#             def worker():
#                 while not q.empty():
#                     try:
#                         city = q.get()
#                         result = fetch_city_weather(city, weather_api)
#                         results.append(result)
#                         q.task_done()
#                     except Exception as e:
#                         results.append(handle_error(e, f"{city} 날씨 조회 중", f"'{city}' 날씨를 가져오지 못했어요. 🌧️"))
            
#             with ThreadPoolExecutor(max_workers=min(len(cities), MAX_WORKERS)) as executor:
#                 for _ in range(min(len(cities), MAX_WORKERS)):
#                     executor.submit(worker)
#             q.join()
#             return "\n\n".join(results)
#         elif query_type == "tomorrow_weather":
#             city = extract_city_from_query(query)
#             return weather_api.get_forecast_by_day(city, days_from_today=1)
#         elif query_type == "day_after_tomorrow_weather":
#             city = extract_city_from_query(query)
#             return weather_api.get_forecast_by_day(city, days_from_today=2)
#         elif query_type == "weekly_forecast":
#             city = extract_city_from_query(query)
#             return weather_api.get_weekly_forecast(city)
#         elif query_type == "drug":
#             return get_drug_info(query)
#         elif query_type == "conversation":
#             if query.strip() in GREETING_RESPONSES:
#                 return GREETING_RESPONSES[query.strip()]
#             return get_conversational_response(query, st.session_state.chat_history)
#         elif query_type == "web_search":
#             language = detect(query)
#             if language == 'ko' and naver_request_count < NAVER_DAILY_LIMIT:
#                 return get_ai_summary(get_naver_api_results(query))
#             return get_ai_summary(search_and_summarize(query))
#         elif query_type == "arxiv_search":
#             keywords = query.replace("논문검색", "").replace("arxiv", "").replace("paper", "").replace("research", "").strip()
#             return get_arxiv_papers(keywords)
#         elif query_type == "pubmed_search":
#             keywords = query.replace("의학논문", "").strip()
#             return get_pubmed_papers(keywords)
#         elif query_type == "general_query":
#             return get_conversational_response(query, st.session_state.chat_history)
#         return "아직 지원하지 않는 기능이에요. 😅"
#     except Exception as e:
#         return handle_error(e, "쿼리 처리 중", "질문을 처리하는 중 문제가 생겼어요. 😥 다시 시도해 주세요!")

# def show_chat_dashboard():
#     st.title("AI 챗봇 🤖")
#     init_session_state()
    
#     if st.button("도움말 ℹ️"):
#         st.info(
#             "챗봇과 더 쉽게 대화하는 방법이에요! 👇:\n\n"
#             "1. **약품검색** 💊: '약품검색 [약 이름]' (예: 약품검색 타이레놀정)\n"
#             "2. **논문검색 (ArXiv)** 📚: '논문검색 [키워드]' (예: 논문검색 machine learning)\n"
#             "3. **의학논문검색 (PubMed)** 🩺: '의학논문 [키워드]' (예: 의학논문 gene therapy)\n"
#             "4. **날씨검색** ☀️: '[도시명] 날씨' 또는 '내일 [도시명] 날씨' (예: 서울 날씨, 내일 서울 날씨)\n"
#             "5. **시간검색** ⏱️: '[도시명] 시간' (예: 파리 시간, 뉴욕 시간)\n\n"
#             "궁금한 점이 있으면 언제든 질문해주세요! 😊"
#         )
    
#     for msg in st.session_state.chat_history[-10:]:
#         with st.chat_message(msg['role']):
#             st.markdown(msg['content'], unsafe_allow_html=True)
    
#     if user_prompt := st.chat_input("질문해 주세요!"):
#         st.chat_message("user").markdown(user_prompt)
#         st.session_state.chat_history.append({"role": "user", "content": user_prompt})
#         with st.chat_message("assistant"):
#             with st.spinner("응답을 준비 중이에요..."):
#                 start_time = time.time()
#                 try:
#                     response = get_cached_response(user_prompt)
#                     time_taken = round(time.time() - start_time, 2)
#                     st.markdown(response, unsafe_allow_html=True)
#                     st.session_state.chat_history.append({"role": "assistant", "content": response})
#                     async_save_chat_history(st.session_state.user_id, st.session_state.session_id, user_prompt, response, time_taken)
#                 except Exception as e:
#                     error_msg = handle_error(e, "대화 처리 중", "응답을 준비하다 문제가 생겼어요. 😓")
#                     st.markdown(error_msg, unsafe_allow_html=True)
#                     st.session_state.chat_history.append({"role": "assistant", "content": error_msg})

# # 메인 실행
# def main():
#     init_session_state()
#     if not st.session_state.is_logged_in:
#         show_login_page()
#     else:
#         show_chat_dashboard()

# if __name__ == "__main__":
#     main()
