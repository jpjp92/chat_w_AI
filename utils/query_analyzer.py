# utils/query_analyzer.py
import re
from functools import lru_cache

# 도시 및 시간 추출
CITY_PATTERNS = [
    re.compile(r'(?:오늘|내일|모레|이번 주|주간)?\s*([가-힣a-zA-Z\s]{2,20}(?:시|군|city)?)의?\s*날씨', re.IGNORECASE),
    re.compile(r'(?:오늘|내일|모레|이번 주|주간)?\s*([가-힣a-zA-Z\s]{2,20}(?:시|군|city)?)\s*날씨', re.IGNORECASE),
]

TIME_CITY_PATTERNS = [
    re.compile(r'([가-힣a-zA-Z]{2,20}(?:시|군)?)의?\s*시간'),
    re.compile(r'([가-힣a-zA-Z]{2,20}(?:시|군)?)\s*시간'),
]

GREETINGS = ["안녕", "하이", "헬로", "ㅎㅇ", "왓업", "할롱", "헤이"]

def extract_city_from_query(query):
    for pattern in CITY_PATTERNS:
        match = pattern.search(query)
        if match:
            city = match.group(1).strip()
            if city not in ["오늘", "내일", "모레", "이번 주", "주간", "현재"]:
                return city
    return "서울"

def extract_city_from_time_query(query):
    for pattern in TIME_CITY_PATTERNS:
        match = pattern.search(query)
        if match:
            city = match.group(1).strip()
            if city != "현재":
                return city
    return "서울"

# 축구리그 
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

def is_time_query(query):
    """시간 관련 질문인지 정확하게 판단"""
    
    # 긍정적 시간 패턴들
    positive_patterns = [
        r'(서울|도쿄|뉴욕|런던|파리|베를린|마드리드|로마|밀라노|시드니|홍콩|싱가포르|모스크바|두바이|라스베이거스|시카고|토론토|멜버른)\s*(시간|time)',
        r'(현재|지금)\s*(시간|time)',
        r'몇\s*시',
        r'(오늘|현재|지금|금일)\s*(날짜|date)',
        r'what\s*time',
        r'시간\s*(알려|궁금)',
        r'몇시인지',
        r'time\s*in'
    ]
    
    # 부정적 컨텍스트
    negative_patterns = [
        r'실시간.*?(축구|야구|농구|경기|스포츠|뉴스|주식|코인|정보)',
        r'시간.*?(부족|없어|모자라|부족해|없다|남아)',
        r'언제.*?시간',
        r'시간대.*?날씨',
        r'시간당',
        r'시간.*?(걸려|소요|필요)',
        r'몇.*?시간.*?(후|뒤|전)',
        r'시간.*?(맞춰|맞추|조정)',
        r'시간표',
        r'시간.*?(예약|약속|일정)'
    ]
    
    # 부정적 컨텍스트 확인
    for pattern in negative_patterns:
        if re.search(pattern, query):
            return False
    
    # 긍정적 패턴 확인
    for pattern in positive_patterns:
        if re.search(pattern, query):
            return True
    
    return False

@lru_cache(maxsize=100)
def needs_search(query):
    query_lower = query.strip().lower().replace(" ", "")
    if "날씨" in query_lower:
        return "weather" if "내일" not in query_lower else "tomorrow_weather"
    if "시간" in query_lower or "날짜" in query_lower:
        if is_time_query(query_lower):
            return "time"
    if "문화행사" in query_lower:
        return "cultural_event"
    if "리그순위" in query_lower:
        return "league_standings"
    if "리그득점순위" in query_lower or "득점순위" in query_lower:
        return "league_scorers"
    if ("챔피언스리그" in query_lower or "ucl" in query_lower) and (
        "토너먼트" in query_lower or "knockout" in query_lower or "16강" in query_lower or "8강" in query_lower or "4강" in query_lower or "결승" in query_lower):
        return "cl_knockout"
    if "약품검색" in query_lower:
        return "drug"
    if "공학논문" in query_lower or "arxiv" in query_lower:
        return "arxiv_search"
    if "의학논문" in query_lower:
        return "pubmed_search"
    if "검색해줘" in query_lower or "검색해" in query_lower:
        return "naver_search"

    # MBTI 관련
    if "mbti검사" in query_lower:
        return "mbti"
    if "mbti유형설명" in query_lower or "mbti유형" in query_lower or "mbti설명" in query_lower:
        return "mbti_types"
    
    # 다중지능 관련
    if "다중지능유형설명" in query_lower or "다중지능유형" in query_lower or "다중지능설명" in query_lower or \
       "다중지능 유형 설명" in query.strip().lower() or "다중지능 유형" in query.strip().lower():
        return "multi_iq_types"
    if "다중지능직업" in query_lower or "다중지능추천" in query_lower or \
       "다중지능 직업" in query.strip().lower() or "다중지능 추천" in query.strip().lower():
        return "multi_iq_jobs"
    if "다중지능검사" in query_lower or "다중지능 검사" in query.strip().lower():
        return "multi_iq"
    if "다중지능" in query_lower:
        return "multi_iq_full"
    
    if any(greeting in query_lower for greeting in GREETINGS):
        return "conversation"
    return "conversation"

def is_drug_inquiry(query):
    """약품 관련 질문인지 확인"""
    query_lower = query.lower().replace(" ", "")
    return "약품검색" in query_lower

def extract_drug_name(query):
    """약품 이름 추출"""
    import re
    # "약품검색 [약품명]" 패턴에서 약품명 추출
    match = re.search(r'약품검색\s+(.+)', query, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""

def is_paper_search(query):
    """논문 검색 요청인지 확인"""
    query_lower = query.lower().replace(" ", "")
    return "공학논문" in query_lower or "arxiv" in query_lower or "의학논문" in query_lower

def extract_keywords_for_paper_search(query):
    """논문 검색을 위한 키워드 추출"""
    import re
    # "공학논문 [키워드]" 또는 "의학논문 [키워드]" 패턴에서 키워드 추출
    patterns = [
        r'공학논문\s+(.+)',
        r'의학논문\s+(.+)',
        r'arxiv\s+(.+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""

def is_pharmacy_search(query):
    """약국 검색 쿼리인지 확인"""
    query_lower = query.lower().replace(" ", "")
    
    pharmacy_keywords = [
        "약국", "약국정보", "약국검색", "약국운영", "약국시간",
        "서울약국", "약국찾기", "약국위치", "약국운영시간"
    ]
    
    for keyword in pharmacy_keywords:
        if keyword in query_lower:
            return True
    
    # 지역구 + 약국 패턴
    districts = [
        "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구",
        "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구",
        "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"
    ]
    
    for district in districts:
        if district in query and "약국" in query_lower:
            return True
    
    return False

def extract_pharmacy_location(query):
    """쿼리에서 약국 위치 정보 추출"""
    districts = [
        "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구",
        "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구",
        "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"
    ]
    
    for district in districts:
        if district in query:
            return district
    
    return None

def needs_search(query):
    """쿼리 타입을 분석하여 적절한 검색 타입을 반환"""
    query_lower = query.strip().lower().replace(" ", "")
    if "날씨" in query_lower:
        return "weather" if "내일" not in query_lower else "tomorrow_weather"
    if "시간" in query_lower or "날짜" in query_lower:
        if is_time_query(query_lower):
            return "time"
    if "문화행사" in query_lower:
        return "cultural_event"
    if "리그순위" in query_lower:
        return "league_standings"
    if "리그득점순위" in query_lower or "득점순위" in query_lower:
        return "league_scorers"
    if ("챔피언스리그" in query_lower or "ucl" in query_lower) and (
        "토너먼트" in query_lower or "knockout" in query_lower or "16강" in query_lower or "8강" in query_lower or "4강" in query_lower or "결승" in query_lower):
        return "cl_knockout"
    if "약품검색" in query_lower:
        return "drug"
    if "공학논문" in query_lower or "arxiv" in query_lower:
        return "arxiv_search"
    if "의학논문" in query_lower:
        return "pubmed_search"
    if "검색해줘" in query_lower or "검색해" in query_lower:
        return "naver_search"

    # MBTI 관련
    if "mbti검사" in query_lower:
        return "mbti"
    if "mbti유형설명" in query_lower or "mbti유형" in query_lower or "mbti설명" in query_lower:
        return "mbti_types"
    
    # 다중지능 관련
    if "다중지능유형설명" in query_lower or "다중지능유형" in query_lower or "다중지능설명" in query_lower or \
       "다중지능 유형 설명" in query.strip().lower() or "다중지능 유형" in query.strip().lower():
        return "multi_iq_types"
    if "다중지능직업" in query_lower or "다중지능추천" in query_lower or \
       "다중지능 직업" in query.strip().lower() or "다중지능 추천" in query.strip().lower():
        return "multi_iq_jobs"
    if "다중지능검사" in query_lower or "다중지능 검사" in query.strip().lower():
        return "multi_iq"
    if "다중지능" in query_lower:
        return "multi_iq_full"
    
    if any(greeting in query_lower for greeting in GREETINGS):
        return "conversation"
    return "conversation"
