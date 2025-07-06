# set lib
from config.imports import *
from config.env import *
# from streamlit.runtime.scriptrunner import add_script_run_ctx

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
# Import weather, football, drug, paper search, culture event, and web search modules
from utils.weather import WeatherAPI
from utils.football import FootballAPI
from utils.drug_info import DrugAPI
from utils.paper_search import PaperSearchAPI
from utils.culture_event import CultureEventAPI
from utils.web_search import WebSearchAPI

# set logger
logging.basicConfig(level=logging.INFO)  # 디버깅을 위해 INFO 레벨로 변경
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
drug_api = DrugAPI(api_key=DRUG_API_KEY, cache_handler=cache_handler)
paper_search_api = PaperSearchAPI(ncbi_key=NCBI_KEY, cache_handler=cache_handler)
culture_event_api = CultureEventAPI(api_key=CULTURE_API_KEY, cache_handler=cache_handler)
web_search_api = WebSearchAPI(client_id=NAVER_CLIENT_ID, client_secret=NAVER_CLIENT_SECRET, cache_handler=cache_handler)  # 새로 추가

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

# 대화형 응답 (비동기)
conversation_cache = MemoryCache()
_client_instance = None

# 대화형 응답 함수 수정
async def get_conversational_response(query, chat_history):
    logger.info(f"대화형 응답 시작 - 쿼리: '{query}'")
    logger.info(f"세션 상태 확인: {hasattr(st, 'session_state')}")
    if hasattr(st, 'session_state'):
        logger.info(f"current_context: {getattr(st.session_state, 'current_context', 'None')}")
        logger.info(f"search_contexts 키 수: {len(getattr(st.session_state, 'search_contexts', {}))}")
    
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
    
    # 디버깅 로그 추가
    logger.info(f"현재 컨텍스트 존재: {current_context is not None}")
    if current_context:
        logger.info(f"컨텍스트 타입: {current_context.get('type')}")
        logger.info(f"컨텍스트 결과 길이: {len(str(current_context.get('result', '')))}")
    
    # 순서 기반 링크 요청 확인 (예: 3번째 링크 요약해줘)
    try:
        is_numbered_request, numbered_url = is_numbered_link_request(query, current_context)
        logger.info(f"순서 기반 요청: {is_numbered_request}, URL: {numbered_url}")
        
        if is_numbered_request and numbered_url:
            try:
                logger.info(f"웹페이지 요약 시작: {numbered_url}")
                summary = summarize_webpage_content(numbered_url, query)
                conversation_cache.setex(cache_key, 600, summary)
                return summary
            except Exception as e:
                logger.error(f"웹페이지 요약 오류: {str(e)}")
                return f"해당 링크의 내용을 가져올 수 없습니다: {str(e)} 😓"
        
        # 일반 URL 요약 요청 확인
        is_url_request, url = is_url_summarization_request(query)
        logger.info(f"URL 요약 요청: {is_url_request}, URL: {url}")
        
        if is_url_request and url:
            try:
                logger.info(f"직접 URL 요약 시작: {url}")
                summary = summarize_webpage_content(url, query)
                conversation_cache.setex(cache_key, 600, summary)
                return summary
            except Exception as e:
                logger.error(f"URL 요약 오류: {str(e)}")
                return f"해당 링크의 내용을 가져올 수 없습니다: {str(e)} 😓"
    
    except Exception as e:
        logger.error(f"링크 요약 처리 중 오류: {str(e)}")
        # 링크 요약 오류 시에도 일반 대화는 계속 진행
    
    # 일반 대화 처리
    messages = [
        {"role": "system", "content": "친절한 AI 챗봇입니다. 적절한 이모지 사용: ✅(완료), ❓(질문), 😊(친절)"}
    ]
    
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
                    context_desc += f"{i}. 제목: {title.strip()}\n   내용: {content.strip()}\n\n"
                
                # 검색 결과에서 URL을 추출하여 웹페이지 요약 제안
                urls_in_context = extract_urls_from_text(context_result)
                logger.info(f"검색 결과에서 추출된 URL 개수: {len(urls_in_context)}")
                if urls_in_context:
                    context_desc += f"\n\n검색 결과에 총 {len(urls_in_context)}개의 링크가 있습니다:\n"
                    for i, url in enumerate(urls_in_context, 1):
                        context_desc += f"{i}. {url}\n"
                    context_desc += "\n특정 링크의 전체 내용이 궁금하시면 다음과 같이 질문해주세요:\n"
                    context_desc += "- '첫 번째 링크 요약해줘' 또는 '3번째 링크 요약해줘'\n"
                    context_desc += "- 'URL + 요약해줘' 형태로 직접 URL 지정"
        
        # 다른 유형의 컨텍스트 처리 (약품 정보, 논문 등)
        elif context_type == "drug":
            context_desc = f"사용자가 '{context_query}' 약품에 대한 정보를 검색했습니다. 약품 정보를 기반으로 사용자의 질문에 답변해주세요."
        else:
            context_desc = f"사용자가 '{context_query}'에 대해 검색했습니다."
        
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
                if isinstance(results, str):
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
            future = executor.submit(culture_event_api.search_cultural_events, query)
            result = future.result()
        elif query_type == "drug":
            future = executor.submit(drug_api.get_drug_info, query)
            result = future.result()
        elif query_type == "arxiv_search":
            keywords = query.replace("공학논문", "").replace("arxiv", "").strip()
            future = executor.submit(paper_search_api.get_arxiv_papers, keywords)
            result = future.result()
        elif query_type == "pubmed_search":
            keywords = query.replace("의학논문", "").strip()
            future = executor.submit(paper_search_api.get_pubmed_papers, keywords)
            result = future.result()
        elif query_type == "naver_search":
            # 웹 검색 처리 로직
            future = executor.submit(web_search_api.search_and_create_context, query, st.session_state)
            result = future.result()
            
            # 컨텍스트 저장 확인 로그
            logger.info(f"검색 후 컨텍스트 상태: {st.session_state.current_context}")
            if hasattr(st.session_state, 'search_contexts'):
                logger.info(f"저장된 컨텍스트 수: {len(st.session_state.search_contexts)}")
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
    
    # 검색 컨텍스트 저장을 위한 변수 추가
    if "search_contexts" not in st.session_state:
        st.session_state.search_contexts = {}
    if "current_context" not in st.session_state:
        st.session_state.current_context = None
    
    # 사이드바에 도움말 추가
    with st.sidebar:
        st.header("도움말 📚")
        
        # 기본 기능 안내
        with st.expander("🌟 기본 기능"):
            st.markdown("""
            **날씨 정보** 🌤️
            - "서울 날씨", "파리 날씨 알려줘"
            - "내일 서울 날씨", "뉴욕 내일 날씨"
            
            **시간 정보** 🕒
            - "현재 시간", "오늘 날짜"
            - "런던 시간", "도쿄 시간 알려줘"
            
            **웹 검색** 🔍
            - "ChatGPT 검색", "파이썬 검색"
            - 검색 후 "3번째 링크 요약해줘"
            """)
        
        # 전문 정보 안내
        with st.expander("🎯 전문 정보"):
            st.markdown("""
            **의약품 정보** 💊
            - "타이레놀 효능", "아스피린 부작용"
            
            **논문 검색** 📚
            - "인공지능 공학논문"
            - "당뇨병 의학논문"
            
            **문화행사** 🎭
            - "서울 문화행사", "이번 주 공연"
            """)
        
        # 축구 정보 안내
        with st.expander("⚽ 축구 정보"):
            st.markdown("""
            **리그 순위** 🏆
            - "EPL 순위", "라리가 순위"
            - "분데스리가 순위", "세리에A 순위"
            
            **득점 순위** ⚽
            - "EPL 득점순위", "라리가 득점왕"
            
            **챔피언스리그** 🏅
            - "챔피언스리그 토너먼트"
            """)
        
        # 성격 검사 안내
        with st.expander("🧠 성격 검사"):
            st.markdown("""
            **MBTI** 🎭
            - "MBTI 검사", "MBTI 유형"
            - "ENFP 설명", "INTJ 특징"
            
            **다중지능** 🎨
            - "다중지능 검사", "다중지능 유형"
            - "언어지능 설명", "음악지능 직업"
            """)
        
        # 사용 팁
        with st.expander("💡 사용 팁"):
            st.markdown("""
            **검색 후 활용** 🔍
            - 검색 후 "요약해줘"
            - "첫 번째 결과 자세히 설명해줘"
            - "3번째 링크 요약해줘"
            
            **대화 연속성** 💬
            - 이전 결과에 대한 추가 질문 가능
            - 검색 결과 기반 상세 설명 요청
            
            **정확한 검색** 🎯
            - 구체적인 키워드 사용
            - 도시명은 한국어/영어 모두 가능
            """)
        
        # 지원 언어/지역
        with st.expander("🌍 지원 범위"):
            st.markdown("""
            **날씨 지원** 🌍
            - 전세계 주요 도시
            - 한국어/영어 도시명 모두 지원
            
            **축구 리그** ⚽
            - EPL, 라리가, 분데스리가
            - 세리에A, 리그1, 챔피언스리그
            
            **검색 언어** 💬
            - 한국어 우선 지원
            - 영어 검색 가능
            """)
    
    # 기존 메시지 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if isinstance(message["content"], dict) and "table" in message["content"]:
                st.markdown(message["content"]["header"])
                st.dataframe(message["content"]["table"])
                st.markdown(message["content"]["footer"])
            else:
                st.markdown(message["content"], unsafe_allow_html=True)

    # 사용자 입력 처리
    if user_prompt := st.chat_input("질문해 주세요!"):
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("답변을 준비하고 있습니다... 🤔")
            
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
                
                end_time = time.time()
                time_taken = end_time - start_time
                
                placeholder.empty()
                
                if isinstance(response, dict) and "table" in response:
                    st.markdown(response["header"])
                    st.dataframe(response["table"])
                    st.markdown(response["footer"])
                else:
                    st.markdown(response, unsafe_allow_html=True)
                
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                # 비동기로 채팅 기록 저장
                async_save_chat_history(
                    st.session_state.user_id,
                    st.session_state.session_id,
                    user_prompt,
                    response,
                    time_taken
                )
                
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