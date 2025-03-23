# 라이브러리 설정
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
            time.sleep(1)  # API 요청 간격 조절
            response = requests.get(url, headers=headers, timeout=3)
            response.raise_for_status()
            data = response.json()
            
            standings = data['standings'][0]['table'] if league_code not in ["CL"] else data['standings']
            if league_code in ["CL"]:  # 챔피언스 리그는 그룹 스테이지 처리
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
            else:  # 일반 리그
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
            time.sleep(1)  # API 요청 간격 조절
            response = requests.get(url, headers=headers, timeout=3)
            response.raise_for_status()
            data = response.json()
            
            scorers = [{"순위": i+1, "선수": s['player']['name'], "팀": s['team']['name'], "득점": s['goals']} 
                       for i, s in enumerate(data['scorers'][:10])]  # 상위 10명
            df = pd.DataFrame(scorers)
            result = {"league_name": league_name, "data": df}
            self.cache.setex(cache_key, self.cache_ttl, result)
            return result
        
        except requests.exceptions.RequestException as e:
            return {"league_name": league_name, "error": f"{league_name} 리그 득점순위 정보를 가져오는 중 문제가 발생했습니다: {str(e)} 😓"}
    

# 초기화
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = Client(exclude_providers=["OpenaiChat", "Copilot", "Liaobots", "Jmuz", "PollinationsAI", "ChatGptEs"])  # 문제 제공자 제외
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
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
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

# 리그 추출 함수 수정 (띄어쓰기 유연성 개선)
def extract_league_from_query(query):
    query_lower = query.lower().replace(" ", "")  # 공백 제거
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

# KST 시간 반환 함수 추가
def get_kst_time():
    kst_timezone = pytz.timezone("Asia/Seoul")
    kst_time = datetime.now(kst_timezone)
    return f"대한민국 기준 : {kst_time.strftime('%Y년 %m월 %d일 %p %I:%M')}입니다. ⏰\n\n 더 궁금한 점 있나요? 😊"

# 시간 정보
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
    if isinstance(answer, dict) and "table" in answer and isinstance(answer["table"], pd.DataFrame):
        answer_to_save = {
            "header": answer["header"],
            "table": answer["table"].to_dict(orient="records"),  # DataFrame 직렬화
            "footer": answer["footer"]
        }
    else:
        answer_to_save = answer
    
    supabase.table("chat_history").insert({
        "user_id": user_id,
        "session_id": session_id,
        "question": question,
        "answer": answer_to_save,
        "time_taken": time_taken,
        "created_at": datetime.now().isoformat()
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

# Naver API 검색 (웹 검색)
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
            
            response_text = "🌐 **웹 검색 결과** 🌐\n\n"
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

# 대화형 응답 (비동기)
conversation_cache = MemoryCache()
async def get_conversational_response(query, chat_history):
    cache_key = f"conv:{needs_search(query)}:{query}"
    cached = conversation_cache.get(cache_key)
    if cached:
        return cached
    
    messages = [
        {"role": "system", "content": "친절한 AI 챗봇입니다. 적절한 이모지 사용: ✅(완료), ❓(질문), 😊(친절)"},
        {"role": "user", "content": query}
    ] + [{"role": msg["role"], "content": msg["content"]} 
         for msg in chat_history[-2:] if "더 궁금한 점 있나요?" not in msg["content"]]
    
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(None, lambda: client.chat.completions.create(
            model="gpt-4o", messages=messages))
        result = response.choices[0].message.content if response.choices else "응답을 생성할 수 없습니다."
    except (IndexError, Exception) as e:  # IndexError 및 기타 예외 처리
        logger.error(f"대화 응답 생성 중 오류: {str(e)}", exc_info=True)
        result = "응답을 생성하는 중 문제가 발생했습니다."
    conversation_cache.setex(cache_key, 600, result)
    return result

# GREETING_RESPONSES 개선
GREETINGS = ["안녕", "하이", "헬로", "ㅎㅇ", "왓업", "할롱", "헤이"]
GREETING_RESPONSE = "안녕하세요! 반갑습니다. 무엇을 도와드릴까요? 😊"

# 쿼리 분류
@lru_cache(maxsize=100)
def needs_search(query):
    query_lower = query.strip().lower().replace(" ", "")  # 공백 제거로 유연성 확보
    if "날씨" in query_lower:
        return "weather" if "내일" not in query_lower else "tomorrow_weather"
    if "시간" in query_lower or "날짜" in query_lower:
        return "time"
    if "리그순위" in query_lower:
        return "league_standings"
    if "리그득점순위" in query_lower or "득점순위" in query_lower:  # 띄어쓰기 없이도 인식
        return "league_scorers"
    if "약품검색" in query_lower:
        return "drug"
    if "공학논문" in query_lower or "arxiv" in query_lower:
        return "arxiv_search"
    if "의학논문" in query_lower:
        return "pubmed_search"
    if "검색" in query_lower:
        return "naver_search"
    if any(greeting in query_lower for greeting in GREETINGS):
        return "conversation"
    return "conversation"

# 쿼리 처리 (오류 처리 강화)
def process_query(query):
    cache_key = f"query:{hash(query)}"
    cached = cache_handler.get(cache_key)
    if cached is not None:
        return cached
    
    query_type = needs_search(query)
    query_lower = query.strip().lower()
    query_no_space = query_lower.replace(" ", "")  # 띄어쓰기 제거 추가
    
    with ThreadPoolExecutor() as executor:
        if query_type == "weather":
            future = executor.submit(weather_api.get_city_weather, extract_city_from_query(query))
            result = future.result()
        elif query_type == "tomorrow_weather":
            future = executor.submit(weather_api.get_forecast_by_day, extract_city_from_query(query), 1)
            result = future.result()
        elif query_type == "time":
            # 띄어쓰기 제거된 쿼리로 키워드 검색
            if "오늘날짜" in query_no_space or "현재날짜" in query_no_space or "금일날짜" in query_no_space:
                result = get_kst_time()
            else:
                city = extract_city_from_time_query(query)
                future = executor.submit(get_time_by_city, city)
                result = future.result()
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
            else:
                result = "지원하지 않는 리그입니다. 😓 지원 리그: EPL, LaLiga, Bundesliga, Serie A, Ligue 1"
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
                except Exception as e:
                    result = f"리그 득점순위 조회 중 오류 발생: {str(e)} 😓"
            else:
                result = "지원하지 않는 리그입니다. 😓 지원 리그: EPL, LaLiga, Bundesliga, Serie A, Ligue 1"
        elif query_type == "drug":
            future = executor.submit(get_drug_info, query)
            result = future.result()
        elif query_type == "arxiv_search":
            keywords = query.replace("공학논문", "").replace("arxiv", "").strip()
            future = executor.submit(get_arxiv_papers, keywords)
            result = future.result()
        elif query_type == "pubmed_search":
            keywords = query.replace("의학논문", "").strip()
            future = executor.submit(get_pubmed_papers, keywords)
            result = future.result()
        elif query_type == "naver_search":
            search_query = query_lower.replace("검색", "").strip()
            future = executor.submit(get_naver_api_results, search_query)
            result = future.result()
        elif query_type == "conversation":
            if query_lower in GREETINGS:
                result = GREETING_RESPONSE
            # 띄어쓰기 제거된 쿼리로 키워드 검색
            elif "오늘날짜" in query_no_space or "현재날짜" in query_no_space or "금일날짜" in query_no_space:
                result = get_kst_time()
            else:
                result = asyncio.run(get_conversational_response(query, st.session_state.chat_history))
        else:
            result = "아직 지원하지 않는 기능이에요. 😅"
        
        cache_handler.setex(cache_key, 600, result)
        return result

# UI 함수 (도움말 업데이트)
def show_chat_dashboard():
    st.title("AI 챗봇 🤖")
    
    if st.button("도움말 ℹ️"):
        st.info(
            "챗봇과 더 쉽게 대화 하는 방법이에요! 👇:\n"
            "1. **날씨** ☀️: '[도시명] 날씨' (예: 서울 날씨)\n"
            "2. **시간/날짜** ⏱️: '[도시명] 시간' 또는 '오늘 날짜' (예: 부산 시간, 금일 날짜)\n"
            "3. **리그순위** ⚽: '[리그 이름] 리그 순위 또는 리그득점순위'(예: EPL 리그순위, EPL 리그득점순위)\n"
            "   - 지원 리그: EPL, LaLiga, Bundesliga, Serie A, Ligue 1, ChampionsLeague\n"
            "4. **약품검색** 💊: '약품검색 [약 이름]' (예: 약품검색 게보린)\n"
            "5. **공학논문** 📚: '공학논문 [키워드]' (예: 공학논문 Multimodal AI)\n"
            "6. **의학논문** 🩺: '의학논문 [키워드]' (예: 의학논문 cancer therapy)\n"
            "7. **검색** 🌐: '검색 키워드' (예: 검색 최근 전시회 추천)\n\n"
            "궁금한 점 있으면 질문해주세요! 😊"
        )
    
    for msg in st.session_state.chat_history[-10:]:
        with st.chat_message(msg['role']):
            if isinstance(msg['content'], dict) and "table" in msg['content']:
                st.markdown(f"### {msg['content']['header']}")
                st.dataframe(pd.DataFrame(msg['content']['table']), use_container_width=True, hide_index=True)
                st.markdown(msg['content']['footer'])
            else:
                st.markdown(msg['content'], unsafe_allow_html=True)
    
    if user_prompt := st.chat_input("질문해 주세요!"):
        st.chat_message("user").markdown(user_prompt)
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("응답을 준비 중이에요.. ⏳")
            try:
                start_time = time.time()
                response = process_query(user_prompt)
                time_taken = round(time.time() - start_time, 2)
                
                placeholder.empty()
                if isinstance(response, dict) and "table" in response:
                    st.markdown(f"### {response['header']}")
                    st.dataframe(response['table'], use_container_width=True, hide_index=True)
                    st.markdown(response['footer'])
                else:
                    st.markdown(response, unsafe_allow_html=True)
                
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                async_save_chat_history(st.session_state.user_id, st.session_state.session_id, user_prompt, response, time_taken)
            
            except Exception as e:
                placeholder.empty()
                error_msg = f"응답을 준비하다 문제가 생겼어요: {str(e)} 😓"
                logger.error(f"대화 처리 중 오류: {str(e)}", exc_info=True)
                st.markdown(error_msg, unsafe_allow_html=True)
                st.session_state.chat_history.append({"role": "assistant", "content": error_msg})

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
                st.session_state.chat_history = []
                st.session_state.session_id = str(uuid.uuid4())
                st.toast(f"환영합니다, {nickname}님! 🎉")
                time.sleep(1)
                st.rerun()
            except Exception:
                st.toast("로그인 중 오류가 발생했습니다. 다시 시도해주세요.", icon="❌")

# 메인 실행
def main():
    init_session_state()
    if not st.session_state.is_logged_in:
        show_login_page()
    else:
        show_chat_dashboard()

if __name__ == "__main__":
    main()
