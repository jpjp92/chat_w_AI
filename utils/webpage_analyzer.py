# utils/webpage_analyzer.py
from config.imports import *
import re

def fetch_webpage_content(url):
    """웹페이지의 텍스트 내용을 가져옵니다"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 불필요한 태그 제거
        for script in soup(["script", "style", "nav", "footer", "aside", "header"]):
            script.decompose()
        
        # 메인 콘텐츠 추출 시도
        main_content = None
        content_selectors = [
            'article', 'main', '.content', '.post-content', 
            '.article-content', '.entry-content', '.post-body'
        ]
        
        for selector in content_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        if not main_content:
            main_content = soup.find('body')
        
        if main_content:
            text = main_content.get_text(separator=' ', strip=True)
            # 텍스트 정리
            text = re.sub(r'\s+', ' ', text)  # 연속된 공백을 하나로
            text = re.sub(r'\n+', '\n', text)  # 연속된 줄바꿈을 하나로
            
            # 너무 긴 텍스트는 제한 (토큰 제한 고려)
            if len(text) > 8000:
                text = text[:8000] + "..."
            
            return text
        
        return "내용을 추출할 수 없습니다."
        
    except requests.exceptions.RequestException as e:
        return f"웹페이지 요청 오류: {str(e)}"
    except Exception as e:
        return f"내용 추출 오류: {str(e)}"

def summarize_webpage_content(url, user_query="", client=None):
    """웹페이지 내용을 요약합니다"""
    try:
        content = fetch_webpage_content(url)
        
        if content.startswith(("웹페이지 요청 오류", "내용 추출 오류", "내용을 추출할 수 없습니다")):
            return content
        
        # LLM을 사용해 내용 요약
        if not client:
            from utils.providers import select_random_available_provider
            client, _ = select_random_available_provider()
        
        prompt = f"""
다음 웹페이지의 내용을 한국어로 요약해주세요.

웹페이지 URL: {url}
사용자 질문: {user_query if user_query else "전체 내용 요약"}

웹페이지 내용:
{content}

요약 지침:
1. 주요 핵심 내용을 3-5개 포인트로 정리
2. 중요한 정보나 수치가 있다면 포함
3. 사용자가 특정 질문을 했다면 그에 맞춰 요약
4. 이모지를 적절히 사용하여 가독성 향상
5. 출처 URL도 함께 제공

형식:
📄 **웹페이지 요약**

🔗 **출처**: {url}

📝 **주요 내용**:
- 핵심 포인트 1
- 핵심 포인트 2
- ...

💡 **결론**: 간단한 결론이나 핵심 메시지
"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 웹페이지 내용을 정확하고 간결하게 요약하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.3
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"요약 생성 중 오류가 발생했습니다: {str(e)}"
        
    except Exception as e:
        return f"웹페이지 요약 중 오류: {str(e)}"

def extract_urls_from_text(text):
    """텍스트에서 URL을 추출합니다"""
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, text)
    return urls

def is_url_summarization_request(query):
    """URL 요약 요청인지 확인합니다"""
    urls = extract_urls_from_text(query)
    if urls:
        summary_keywords = ['요약', '정리', '내용', '설명', '알려줘', '분석', '해석', '리뷰', '정보']
        for keyword in summary_keywords:
            if keyword in query:
                return True, urls[0]  # 첫 번째 URL 반환
    return False, None

def is_numbered_link_request(query, search_context):
    """순서 기반 링크 요청인지 확인합니다 (예: 3번째 링크 요약해줘)"""
    if not search_context or search_context.get("type") != "naver_search":
        return False, None
    
    # 숫자 패턴과 한글 패턴을 분리
    number_patterns = [
        r'(\d+)번째\s*(?:링크|결과|사이트)',
        r'(\d+)번\s*(?:링크|결과|사이트)', 
        r'(\d+)\.?\s*(?:링크|결과|사이트)',
    ]
    
    korean_patterns = [
        r'첫\s*번째\s*(?:링크|결과|사이트)',
        r'두\s*번째\s*(?:링크|결과|사이트)',
        r'세\s*번째\s*(?:링크|결과|사이트)',
        r'네\s*번째\s*(?:링크|결과|사이트)',
        r'다섯\s*번째\s*(?:링크|결과|사이트)'
    ]
    
    # 숫자를 한글로 변환
    korean_numbers = {'첫': 1, '두': 2, '세': 3, '네': 4, '다섯': 5}
    
    number = None
    
    # 숫자 패턴 확인
    for pattern in number_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            number = int(match.group(1))
            break
    
    # 한글 숫자 패턴 확인
    if number is None:
        for pattern in korean_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                # 한글 숫자 처리
                for korean, num in korean_numbers.items():
                    if korean in query:
                        number = num
                        break
                if number:
                    break
    
    if number is not None:
        # 검색 결과에서 해당 순서의 URL 추출
        search_result = search_context.get("result", "")
        urls = extract_urls_from_text(search_result)
        
        if urls and len(urls) >= number:
            summary_keywords = ['요약', '정리', '내용', '설명', '알려줘', '분석']
            if any(keyword in query for keyword in summary_keywords):
                return True, urls[number - 1]  # 0부터 시작하므로 -1
    
    return False, None

def is_followup_question(query):
    """후속 질문인지 확인하고, 컨텍스트를 유지해야 하는지 결정합니다."""
    
    # 후속 질문 패턴
    followup_patterns = [
        r'이에 대해|이것에 대해|관련해서|더 자세히|요약해?줘',
        r'설명해?줘|알려?줘|어떤|왜|이유|뭐야|뭐지|뭐임',
        r'이게 무슨|이건 무슨|무슨 의미|의미가 뭐|첫 번째|두 번째|세 번째',
        r'다시 설명|다시 알려줘|한 번 더|더 알려줘|추가 정보|추가로|구체적',
        r'같은 주제|계속|그리고|그 다음|추가 질문|연관된',
        r'링크|사이트|웹페이지|이 주소|url'
    ]
    
    # 검색 요청이 아니고, 후속 질문 패턴과 일치하면 컨텍스트 유지
    from utils.query_analyzer import needs_search
    if not needs_search(query):
        for pattern in followup_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return True
    
    # URL이 포함된 경우도 후속 질문으로 처리
    if extract_urls_from_text(query):
        return True
    
    # 그 외에는 새로운 질문으로 처리
    return False
