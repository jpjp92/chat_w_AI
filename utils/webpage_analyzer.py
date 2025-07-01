# utils/webpage_analyzer.py
from config.imports import *
import re
import logging
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

# PyPDF2 조건부 import
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("Warning: PyPDF2를 찾을 수 없습니다. PDF 파일 처리 기능이 비활성화됩니다.")

logger = logging.getLogger(__name__)

def fetch_pdf_content(url):
    """PDF 파일에서 텍스트 추출"""
    if not PDF_AVAILABLE:
        return f"PDF 처리 기능이 사용할 수 없습니다. HTML 버전이 있다면 해당 링크를 사용해주세요."
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # PDF 내용 읽기
        import io
        pdf_file = io.BytesIO(response.content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        text = ""
        # 첫 2-3 페이지만 읽기 (Abstract, Introduction 부분)
        max_pages = min(3, len(pdf_reader.pages))
        
        for page_num in range(max_pages):
            page = pdf_reader.pages[page_num]
            text += page.extract_text() + "\n"
        
        return text[:5000]  # 처음 5000자만 반환
        
    except Exception as e:
        logger.error(f"PDF 처리 오류: {str(e)}")
        return f"PDF 파일을 처리할 수 없습니다: {str(e)}"

def fetch_webpage_content(url):
    """웹페이지 또는 논문 내용 추출 (개선된 버전)"""
    try:
        # 논문 URL 특별 처리
        if is_arxiv_url(url):
            content = fetch_arxiv_metadata(url)
            if content:
                return content
        
        if is_pubmed_url(url):
            content = fetch_pubmed_abstract(url)
            if content:
                return content
        
        # PDF 파일 처리 (PyPDF2가 있는 경우만)
        if is_pdf_url(url):
            content = fetch_pdf_content(url)
            if content:
                return content
        
        # 기존 HTML 처리 로직
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 불필요한 태그 제거
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            tag.decompose()
        
        # 메인 콘텐츠 추출
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=['content', 'main', 'post'])
        
        if main_content:
            text = main_content.get_text(strip=True, separator='\n')
        else:
            text = soup.get_text(strip=True, separator='\n')
        
        # 너무 긴 텍스트는 일부만 반환
        return text[:8000] if len(text) > 8000 else text
        
    except Exception as e:
        logger.error(f"웹페이지 내용 추출 오류: {str(e)}")
        return f"'{url}' 내용을 가져올 수 없습니다. 오류: {str(e)}"

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

def is_pdf_url(url):
    """URL이 PDF 파일인지 확인"""
    return url.lower().endswith('.pdf') or 'pdf' in url.lower()

def is_arxiv_url(url):
    """ArXiv URL인지 확인"""
    return 'arxiv.org' in url.lower()

def is_pubmed_url(url):
    """PubMed URL인지 확인"""
    return 'pubmed.ncbi.nlm.nih.gov' in url.lower()

def fetch_arxiv_metadata(url):
    """ArXiv URL에서 메타데이터와 초록 추출"""
    try:
        # ArXiv ID 추출 (예: https://arxiv.org/abs/2301.12345 -> 2301.12345)
        arxiv_id = url.split('/')[-1].replace('abs/', '').replace('pdf/', '')
        
        import arxiv
        search = arxiv.Search(id_list=[arxiv_id])
        paper = next(search.results())
        
        content = f"""
        제목: {paper.title}
        저자: {', '.join(str(a) for a in paper.authors)}
        출판일: {paper.published.strftime('%Y-%m-%d')}
        
        초록:
        {paper.summary}
        """
        
        return content
        
    except Exception as e:
        logger.error(f"ArXiv 메타데이터 추출 오류: {str(e)}")
        return None

def fetch_pubmed_abstract(url):
    """PubMed URL에서 초록 추출"""
    try:
        # PMID 추출
        pmid = url.split('/')[-1].rstrip('/')
        
        # PubMed API 사용
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        summary_url = f"{base_url}esummary.fcgi"
        fetch_url = f"{base_url}efetch.fcgi"
        
        # 요약 정보 가져오기
        params = {"db": "pubmed", "id": pmid, "retmode": "json"}
        response = requests.get(summary_url, params=params, timeout=5)
        summary_data = response.json()
        
        # 초록 가져오기
        params = {"db": "pubmed", "id": pmid, "retmode": "xml", "rettype": "abstract"}
        response = requests.get(fetch_url, params=params, timeout=5)
        
        # XML 파싱해서 초록 추출
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.text)
        
        title = root.find(".//ArticleTitle").text if root.find(".//ArticleTitle") is not None else "제목 없음"
        abstract = root.find(".//AbstractText").text if root.find(".//AbstractText") is not None else "초록 없음"
        
        content = f"""
        제목: {title}
        PMID: {pmid}
        
        초록:
        {abstract}
        """
        
        return content
        
    except Exception as e:
        logger.error(f"PubMed 추출 오류: {str(e)}")
        return None
