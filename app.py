# set lib
from config.imports import *
from config.env import *

# Import utils modules
from utils.webpage_analyzer import (
    fetch_webpage_content, 
    summarize_webpage_content, 
    extract_urls_from_text,
    is_url_summarization_request,
    is_numbered_link_request,
    is_followup_question
)
from utils.providers import (
    select_best_provider_with_priority,
    select_random_available_provider,
    get_client
)
from utils.query_analyzer import (
    needs_search,
    extract_city_from_query,
    extract_city_from_time_query,
    extract_league_from_query,
    is_drug_inquiry,
    extract_drug_name,
    is_paper_search,
    extract_keywords_for_paper_search,
    is_time_query,
    LEAGUE_MAPPING
)
# Import weather, football, and drug modules
from utils.weather import WeatherAPI
from utils.football import FootballAPI
from utils.drug_info import DrugAPI

# set logger
logging.basicConfig(level=logging.WARNING if os.getenv("ENV") == "production" else logging.INFO)
logger = logging.getLogger("HybridChat")
logging.getLogger("streamlit").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# set cach
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

# 날짜 일괄적 수정 
def format_date(fordate):
    if fordate == 'No date':
        return '날짜 없음'
    try:
        date_obj = datetime.strptime(fordate, '%Y %b %d')
        return date_obj.strftime('%Y.%m.%d')
    except ValueError:
        return fordate

# JSON 파일에서 MBTI 및 다중지능 데이터 로드 (캐싱 적용)
def load_personality_data():
    cache_key = "personality_data"
    cached_data = cache_handler.get(cache_key)
    if cached_data:
        return cached_data
    
    try:
        with open("config/personality_multi_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        cache_handler.setex(cache_key, 86400, data)  # 24시간 캐싱
        return data
    except FileNotFoundError:
        logger.error("personality_multi_data.json 파일을 찾을 수 없습니다.")
        raise
    except json.JSONDecodeError:
        logger.error("personality_multi_data.json 파일의 형식이 잘못되었습니다.")
        raise

# 데이터 로드
personality_data = load_personality_data()
mbti_descriptions = personality_data["mbti_descriptions"]
multi_iq_descriptions = personality_data["multi_iq_descriptions"]
mbti_full_description = personality_data["mbti_full_description"]
multi_iq_full_description = personality_data["multi_iq_full_description"]

# 초기화 - API 클래스들을 utils에서 import하여 사용
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
weather_api = WeatherAPI(cache_handler=cache_handler, WEATHER_API_KEY=WEATHER_API_KEY)
football_api = FootballAPI(api_key=SPORTS_API_KEY, cache_handler=cache_handler)
drug_api = DrugAPI(api_key=DRUG_API_KEY, cache_handler=cache_handler)  # 새로 추가
naver_request_count = 0
NAVER_DAILY_LIMIT = 25000
st.set_page_config(page_title="AI 챗봇", page_icon="🤖")

# 세션 상태 초기화 부분에 검색 결과 컨텍스트 추가
def init_session_state():
    if "is_logged_in" not in st.session_state:
        st.session_state.is_logged_in = False
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! 무엇을 도와드릴까요?😊"}]
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "client" not in st.session_state or "provider_name" not in st.session_state:
        client, provider_name = select_random_available_provider()
        st.session_state.client = client
        st.session_state.provider_name = provider_name
    # 검색 결과 컨텍스트 저장을 위한 변수 추가
    if "search_contexts" not in st.session_state:
        st.session_state.search_contexts = {}
    if "current_context" not in st.session_state:
        st.session_state.current_context = None

# 문화 행사 관련 함수 
def fetch_xml(api_key: str) -> ET.Element:
    """API 키를 사용하여 XML 데이터를 가져옵니다."""
    url = f"http://openapi.seoul.go.kr:8088/{api_key}/xml/culturalEventInfo/1/100/"
    try:
        response = requests.get(url)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        return root
    except requests.exceptions.RequestException as e:
        logger.error(f"문화행사 API 호출 실패: {e}")
        return None

def select_target_district(root: ET.Element, target_district: str = ""):
    """
    target_district가 빈 문자열이면 XML에서 모든 구를 추출하여
    랜덤으로 5개 선택한 후 선택된 구 목록(리스트)을 반환합니다.
    target_district에 값이 있다면 그대로 반환합니다.
    """
    if target_district:
        return target_district
    districts = {row.findtext('GUNAME', default='정보 없음') for row in root.findall('.//row')}
    districts = [d for d in districts if d != "정보 없음"]
    if districts:
        selected_districts = random.sample(districts, min(5, len(districts)))
        return selected_districts
    else:
        return None

def extract_event_date(date_str: str):
    """
    날짜 문자열에서 시작일만 추출하여 datetime.date 객체로 반환합니다.
    파싱에 실패하면 None을 반환합니다.
    """
    date_match = re.match(r"(\d{4}[-./]\d{2}[-./]\d{2})", date_str)
    if not date_match:
        return None
    date_part = date_match.group(1).replace('.', '-').replace('/', '-')
    try:
        event_date = datetime.strptime(date_part, "%Y-%m-%d").date()
        return event_date
    except Exception:
        return None

def get_future_events(api_key: str, target_district: str = ""):
    """API 키와 target_district(빈 문자열이면 랜덤 선택)를 받아 미래 행사를 반환합니다."""
    root = fetch_xml(api_key)
    today = datetime.today().date()
    selected_district = select_target_district(root, target_district)
    if not selected_district:
        return "구 정보가 없습니다."
    
    events = []
    for row in root.findall('.//row'):
        district = row.findtext('GUNAME', default='정보 없음')
        date_str = row.findtext('DATE', default='정보 없음')
        event_date = extract_event_date(date_str)
        if not event_date or event_date <= today:
            continue
        # selected_district가 리스트이면 포함 여부, 문자열이면 동일 여부를 비교
        if isinstance(selected_district, list):
            if district not in selected_district:
                continue
        else:
            if district != selected_district:
                continue
        title = row.findtext('TITLE', default='정보 없음')
        place = row.findtext('PLACE', default='정보 없음')
        fee = row.findtext('USE_FEE', default='정보 없음')
        is_free = row.findtext('IS_FREE', default='정보 없음')
        link = row.findtext('HMPG_ADDR', default='정보 없음')
        image = row.findtext('MAIN_IMG', default='정보 없음')
        events.append({
            "title": title,
            "date": date_str,
            "place": place,
            "district": district,
            "fee": fee,
            "is_free": is_free,
            "link": link,
            "image": image
        })
    return events[:10]  # 최대 10개의 이벤트만 반환
# 시간 관련 함수
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
    if isinstance(answer, dict) and "table" in answer and isinstance(answer["table"], pd.DataFrame):
        answer_to_save = {
            "header": answer["header"],
            "table": answer["table"].to_dict(orient="records"),
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
    response = "🩺 **PubMed 논문 검색 결과** 🩺\n\n"
    response += "\n\n".join(
        [f"**논문 {i}**\n\n"
         f"🆔 **PMID**: {pmid}\n\n"
         f"📖 **제목**: {summaries['result'][pmid].get('title', 'No title')}\n\n"
         f"📅 **출판일**: {format_date(summaries['result'][pmid].get('pubdate', 'No date'))}\n\n"
         f"✍️ **저자**: {', '.join([author.get('name', '') for author in summaries['result'][pmid].get('authors', [])])}\n\n"
         f"📝 **초록**: {abstract_dict.get(pmid, 'No abstract')}\n\n"
         f"🔗 **논문 페이지**: https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
         for i, pmid in enumerate(pubmed_ids, 1)]
    ) + "\n\n더 궁금한 점 있나요? 😊"
    cache_handler.setex(cache_key, 3600, response)
    return response
    
# 대화형 응답 (비동기)
conversation_cache = MemoryCache()
_client_instance = None

# 대화형 응답 함수 수정
async def get_conversational_response(query, chat_history):
    cache_key = f"conv:{needs_search(query)}:{query}"
    cached = conversation_cache.get(cache_key)
    if cached:
        return cached
    
    # 현재 검색 컨텍스트 가져오기
    current_context = None
    if hasattr(st, 'session_state') and 'current_context' in st.session_state:
        current_context_id = st.session_state.current_context
        if current_context_id and current_context_id in st.session_state.search_contexts:
            current_context = st.session_state.search_contexts[current_context_id]
    
    # 순서 기반 링크 요청 확인 (예: 3번째 링크 요약해줘)
    is_numbered_request, numbered_url = is_numbered_link_request(query, current_context)
    if is_numbered_request:
        summary = summarize_webpage_content(numbered_url, query)
        conversation_cache.setex(cache_key, 600, summary)
        return summary
    
    # 일반 URL 요약 요청 확인
    is_url_request, url = is_url_summarization_request(query)
    if is_url_request:
        # URL 요약 처리
        summary = summarize_webpage_content(url, query)
        conversation_cache.setex(cache_key, 600, summary)
        return summary
    
    messages = [
        {"role": "system", "content": "친절한 AI 챗봇입니다. 적절한 이모지 사용: ✅(완료), ❓(질문), 😊(친절)"}
    ]
    
    # 현재 대화 컨텍스트가 있는지 확인
    current_context = None
    if hasattr(st, 'session_state') and 'current_context' in st.session_state:
        current_context_id = st.session_state.current_context
        if current_context_id and current_context_id in st.session_state.search_contexts:
            current_context = st.session_state.search_contexts[current_context_id]
    
    # 검색 컨텍스트가 있으면 시스템 프롬프트에 추가
    if current_context:
        context_type = current_context["type"]
        context_query = current_context["query"]
        context_result = current_context["result"]
        
        # 컨텍스트 유형에 따라 다른 지시 추가
        if context_type == "naver_search":
            # 테이블 데이터인 경우 처리
            if isinstance(context_result, dict) and "table" in context_result:
                table_json = context_result["table"].to_json(orient="records")
                context_desc = f"사용자가 '{context_query}'에 대해 검색했고, 다음 테이블 형태의 결과를 받았습니다: {table_json}"
            else:
                # 정규 표현식으로 웹 검색 결과만 추출
                cleaned_results = re.findall(r"\*\*결과 \d+\*\*\s*\n\n📄 \*\*제목\*\*: (.*?)\n\n📝 \*\*내용\*\*: (.*?)(?=\n\n🔗|\n\n더 궁금한)", context_result, re.DOTALL)
                context_desc = f"사용자가 '{context_query}'에 대해 웹 검색을 했고, 다음 결과를 받았습니다:\n\n"
                for i, (title, content) in enumerate(cleaned_results, 1):
                    context_desc += f"{i}. 제목: {title}\n   내용: {content}\n\n"
                
                # 검색 결과에서 URL을 추출하여 웹페이지 요약 제안
                urls_in_context = extract_urls_from_text(context_result)
                if urls_in_context:
                    context_desc += f"\n\n검색 결과에 총 {len(urls_in_context)}개의 링크가 있습니다.\n"
                    context_desc += "특정 링크의 전체 내용이 궁금하시면 다음과 같이 질문해주세요:\n"
                    context_desc += "- '첫 번째 링크 요약해줘' 또는 '3번째 링크 요약해줘'\n"
                    context_desc += "- 'URL + 요약해줘' 형태로 직접 URL 지정"
        
        # 다른 유형의 컨텍스트 처리 (약품 정보, 논문 등)
        elif context_type == "drug":
            # 약품 정보일 경우
            context_desc = f"사용자가 '{context_query}' 약품에 대한 정보를 검색했습니다. 약품 정보를 기반으로 사용자의 질문에 답변해주세요."
        
        # 공통 지시사항
        system_prompt = (
            "친절한 AI 챗봇입니다. 적절한 이모지 사용: ✅(완료), ❓(질문), 😊(친절).\n\n"
            f"{context_desc}\n\n"
            "사용자의 후속 질문은 이 검색 결과에 관한 것일 수 있습니다. 검색 결과의 내용을 기반으로 답변하세요.\n"
            "요약을 요청받으면 중요한 정보를 간결하게 요약하고, 설명을 요청받으면 더 자세한 정보를 제공하세요.\n"
            "검색 결과에 관련 정보가 없다면 정직하게 모른다고 답변하세요.\n"
            "사용자가 '첫 번째 링크', '3번째 링크' 등 순서로 링크를 언급하면 해당 순서의 웹페이지 전체 내용을 요약해드린다고 안내하세요.\n"
            "URL이나 링크에 대한 질문을 받으면, 해당 링크의 전체 내용을 확인하고 싶다면 '순서 + 링크 요약해줘' 또는 'URL + 요약해줘' 형태로 질문하라고 안내해주세요."
        )
        messages[0]["content"] = system_prompt
    
    # 최근 대화 기록 추가
    messages.extend([{"role": msg["role"], "content": msg["content"]} 
                    for msg in chat_history[-4:] if "더 궁금한 점 있나요?" not in msg["content"]])
    
    # 현재 질문 추가
    messages.append({"role": "user", "content": query})
    
    # 비동기 실행 전에 client 객체를 미리 가져옴
    try:
        if not hasattr(st, 'session_state') or 'client' not in st.session_state:
            client, _ = select_random_available_provider()
        else:
            client = st.session_state.client
            
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: client.chat.completions.create(
                model="gpt-4o-mini", messages=messages
            )
        )
        result = response.choices[0].message.content if response.choices else "응답을 생성할 수 없습니다."
    except Exception as e:
        logger.error(f"대화 응답 생성 중 오류: {str(e)}", exc_info=True)
        result = "응답을 생성하는 중 문제가 발생했습니다."
    conversation_cache.setex(cache_key, 600, result)
    return result

GREETINGS = ["안녕", "하이", "헬로", "ㅎㅇ", "왓업", "할롱", "헤이"]
GREETING_RESPONSE = "안녕하세요! 반갑습니다. 무엇을 도와드릴까요? 😊"

def process_query(query):
    cache_key = f"query:{hash(query)}"
    cached = cache_handler.get(cache_key)
    if cached is not None:
        return cached
    
    query_type = needs_search(query)
    query_lower = query.strip().lower().replace(" ", "")
    
    with ThreadPoolExecutor() as executor:
        if query_type == "weather":
            future = executor.submit(weather_api.get_city_weather, extract_city_from_query(query))
            result = future.result()
        elif query_type == "tomorrow_weather":
            future = executor.submit(weather_api.get_forecast_by_day, extract_city_from_query(query), 1)
            result = future.result()
        elif query_type == "time":
            if "오늘날짜" in query_lower or "현재날짜" in query_lower or "금일날짜" in query_lower:
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
        elif query_type == "cl_knockout":
            try:
                future = executor.submit(football_api.fetch_championsleague_knockout_matches)
                results = future.result()
                if isinstance(results, str):  # 에러 메시지인 경우
                    result = results
                elif not results:
                    result = "챔피언스리그 토너먼트 경기 결과가 없습니다."
                else:
                    df = pd.DataFrame(results)
                    result = {
                        "header": "챔피언스리그 Knockout Stage 결과",
                        "table": df,
                        "footer": "더 궁금한 점 있나요? 😊"
                    }
            except Exception as e:
                result = f"챔피언스리그 토너먼트 조회 중 오류: {str(e)} 😓"
        elif query_type == "cultural_event":
            # 문화행사 처리 로직
            target_district = query.replace("문화행사", "").strip()  # "문화행사" 키워드 제거
            future = executor.submit(get_future_events, CULTURE_API_KEY, target_district)
            events = future.result()
            if isinstance(events, str):  # 오류 메시지 반환
                return events
            elif not events:  # 결과가 없을 경우
                result = "해당 조건에 맞는 문화 행사가 없습니다."
            else:
                result = "🎭 **문화 행사 정보** 🎭\n\n"
                for i, event in enumerate(events, 1):
                    # 이미지 URL과 링크를 클릭 가능한 링크로 변경
                    image_link = f"[🖼️ 이미지 보기]({event['image']})" if event['image'] != '정보 없음' else "🖼️ 이미지 없음"
                    web_link = f"[🔗 웹사이트]({event['link']})" if event['link'] != '정보 없음' else "🔗 링크 없음"
                    
                    result += (
                        f"### {i}. {event['title']}\n\n"
                        f"📅 **날짜**: {event['date']}\n\n"
                        f"📍 **장소**: {event['place']} ({event['district']})\n\n"
                        f"💰 **요금**: {event['fee']} ({event['is_free']})\n\n"
                        f"{web_link} | {image_link}\n\n"
                        f"---\n\n"
                    )
                result += "더 궁금한 점 있나요? 😊"
                
        elif query_type == "drug":
            future = executor.submit(drug_api.get_drug_info, query)  # 수정된 부분
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
            search_query = query.lower().replace("검색", "").strip()
            future = executor.submit(get_naver_api_results, search_query)
            result = future.result()
            
            # 검색 결과를 컨텍스트에 저장
            context_id = str(uuid.uuid4())
            st.session_state.search_contexts[context_id] = {
                "type": "naver_search",
                "query": search_query,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
            st.session_state.current_context = context_id
            
            # 멀티턴 대화를 위한 안내 추가
            result += "\n\n💡 검색 결과에 대해 더 질문하시면 답변해드릴게요. 예를 들어:\n"
            result += "- '검색 결과를 요약해'\n"
            result += "- '첫 번째 결과에 대해 자세히 설명해줘'\n"
            result += "- '3번째 링크 요약해줘' (해당 순서 웹페이지 전체 내용 요약)\n"
            result += "- 'URL 요약해줘' (특정 링크의 전체 내용 확인)"
        elif query_type == "mbti":
            result = (
                "MBTI 검사를 원하시나요? ✨ 아래 사이트에서 무료로 성격 유형 검사를 할 수 있어요! 😊\n"
                "[16Personalities MBTI 검사](https://www.16personalities.com/ko/%EB%AC%B4%EB%A3%8C-%EC%84%B1%EA%B2%A9-%EC%9C%A0%ED%98%95-%EA%B2%80%EC%82%AC) 🌟\n"
                "이 사이트는 16가지 성격 유형을 기반으로 한 테스트를 제공하며, 결과에 따라 성격 설명과 인간관계 조언 등을 확인할 수 있어요! 💡"
            )
        elif query_type == "mbti_types":
            specific_type = query_lower.replace("mbti", "").replace("유형", "").replace("설명", "").strip().upper()
            if specific_type in mbti_descriptions:
                result = f"### 🎭 {specific_type} 한 줄 설명\n- ✅ **{specific_type}** {mbti_descriptions[specific_type]}"
            else:
                result = mbti_full_description
        elif query_type == "multi_iq":
            result = (
                "다중지능 검사를 원하시나요? 🎉 아래 사이트에서 무료로 다중지능 테스트를 해볼 수 있어요! 😄\n"
                "[Multi IQ Test](https://multiiqtest.com/) 🚀\n"
                "이 사이트는 하워드 가드너의 다중지능 이론을 기반으로 한 테스트를 제공하며, 다양한 지능 영역을 평가해줍니다! 📚✨"
            )
        elif query_type == "multi_iq_types":
            specific_type = query_lower.replace("다중지능", "").replace("multi_iq", "").replace("유형", "").replace("설명", "").strip().replace(" ", "")
            if specific_type in multi_iq_descriptions:
                result = f"### 🎨 {specific_type.replace('지능', ' 지능')} 한 줄 설명\n- 📖 **{specific_type.replace('지능', ' 지능')}** {multi_iq_descriptions[specific_type]['description']}"
            else:
                result = multi_iq_full_description
        elif query_type == "multi_iq_jobs":
            specific_type = query_lower.replace("다중지능", "").replace("multi_iq", "").replace("직업", "").replace("추천", "").strip().replace(" ", "")
            if specific_type in multi_iq_descriptions:
                result = f"### 🎨 {specific_type.replace('지능', ' 지능')} 추천 직업\n- 📖 **{specific_type.replace('지능', ' 지능')}**: {multi_iq_descriptions[specific_type]['description']}- **추천 직업**: {multi_iq_descriptions[specific_type]['jobs']}"
            else:
                result = multi_iq_full_description
        elif query_type == "multi_iq_full":
            result = multi_iq_full_description
        elif query_type == "conversation":
            if query_lower in GREETINGS:
                result = GREETING_RESPONSE
            else:
                result = asyncio.run(get_conversational_response(query, st.session_state.messages))
        else:
            result = "아직 지원하지 않는 기능이에요. 😅"
        
        cache_handler.setex(cache_key, 600, result)
        return result

# 기존 show_chat_dashboard 함수 내에서 사용자 입력 처리 부분 수정
def show_chat_dashboard():
    st.title("Chat with AI 🤖")
    if st.button("도움말 ℹ️"):
        st.info(
            "챗봇과 더 쉽게 대화하는 방법이에요! :\n"
            "1. **날씨** ☀️: '[도시명] 날씨' (예: 서울 날씨, 내일 서울 날씨)\n"
            "2. **시간/날짜** ⏱️: '[도시명] 시간' 또는 '오늘 날짜' (예: 마드리드 시간, 금일 날짜)\n"
            "3. **검색** 🌐: '[키워드] 검색해' 또는 '[키워드] 검색해줘' (예: 2025년 서울 전시회 검색해줘)\n"
            "   - 🔗 **검색 후 링크 분석**: '첫 번째 링크 요약해줘', '3번째 결과 분석해줘'\n"
            "4. **웹페이지 직접 분석** 📄: 'URL 요약해줘' 또는 'URL 분석해줘'\n"
            "   - 예: 'https://example.com 요약해줘', 'https://deepmind.google/models/gemini/flash/ 분석해줘'\n"
            "5. **약품검색** 💊: '약품검색 [약 이름]' (예: 약품검색 게보린)\n"
            "6. **공학논문** 📚: '공학논문 [키워드]' (예: 공학논문 Multimodal AI)\n"
            "7. **의학논문** 🩺: '의학논문 [키워드]' (예: 의학논문 cancer therapy)\n"
            "8. **축구 리그 정보** ⚽: '[리그 이름] 리그 순위 또는 리그득점순위' (예: EPL 리그순위, EPL 리그득점순위)\n"
            "   - 지원 리그: EPL, LaLiga, Bundesliga, Serie A, Ligue 1, ChampionsLeague\n"
            "   - **챔피언스리그 리그 단계**: '챔피언스리그 리그 순위' 또는 'UCL 리그순위'로 확인\n"
            "   - **챔피언스리그 토너먼트**: '챔피언스리그 토너먼트' 또는 'UCL 16강'(예: 챔피언스리그 16강)\n"
            "9. **MBTI** ✨: 'MBTI 검사',  'MBTI 유형', 'MBTI 설명' (예: MBTI 검사, INTJ 설명)\n"
            "10. **다중지능** 🎉: '다중지능 검사', '다중지능 유형', '다중지능 직업', (예: 다중지능 검사, 언어지능 직업)\n"
            "11. **문화행사** 🎭: '[지역구] 문화행사' 또는 '문화행사' (예: 강남구 문화행사, 문화행사)\n\n"
            "🌟 **고급 기능**:\n"
            "- 검색 후 후속 질문으로 특정 링크의 전체 내용 분석 가능\n"
            "- 웹페이지 URL을 직접 제공하여 내용 요약/분석 가능\n"
            "- 멀티턴 대화로 이전 검색 결과에 대한 추가 질문 가능\n\n"
            "궁금한 점 있으면 질문해주세요! 😊"
        )
   
    for msg in st.session_state.messages[-10:]:
        with st.chat_message(msg['role']):
            if isinstance(msg['content'], dict) and "table" in msg['content']:
                st.markdown(f"### {msg['content']['header']}")
                st.dataframe(pd.DataFrame(msg['content']['table']), use_container_width=True, hide_index=True)
                st.markdown(msg['content']['footer'])
            else:
                st.markdown(msg['content'], unsafe_allow_html=True)
    
    if user_prompt := st.chat_input("질문해 주세요!"):
        st.chat_message("user").markdown(user_prompt)
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("응답을 준비 중이에요.. ⏳")
            try:
                start_time = time.time()
                
                # 후속 질문인지 확인
                if is_followup_question(user_prompt) and st.session_state.current_context:
                    # 후속 질문으로 판단되면 기존 컨텍스트 유지하고 LLM에 전달
                    response = asyncio.run(get_conversational_response(user_prompt, st.session_state.messages))
                else:
                    # 새로운 질문이면 컨텍스트 초기화하고 일반 처리
                    if needs_search(user_prompt) is None:
                        st.session_state.current_context = None
                    response = process_query(user_prompt)
                
                time_taken = round(time.time() - start_time, 2)
                
                # 로딩 메시지 제거
                placeholder.empty()
                
                if isinstance(response, dict) and "table" in response:
                    st.markdown(f"### {response['header']}")
                    st.dataframe(response['table'], use_container_width=True, hide_index=True)
                    st.markdown(response['footer'])
                else:
                    st.markdown(response, unsafe_allow_html=True)
                
                st.session_state.messages.append({"role": "assistant", "content": response})
                async_save_chat_history(st.session_state.user_id, st.session_state.session_id, user_prompt, response, time_taken)
            
            except Exception as e:
                placeholder.empty()
                error_msg = f"응답을 준비하다 문제: {str(e)} 😓"
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

# 메인 실행 부분
def main():
    init_session_state()
    
    if not st.session_state.is_logged_in:
        show_login_page()
    else:
        show_chat_dashboard()

if __name__ == "__main__":
    main()