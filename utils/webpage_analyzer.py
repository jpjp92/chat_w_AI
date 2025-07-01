# utils/webpage_analyzer.py
from config.imports import *
import re
import logging
import xml.etree.ElementTree as ET  # 누락된 import 추가
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

logger = logging.getLogger(__name__)  # 닫는 괄호 추가

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

def is_pdf_url(url):
    """URL이 PDF 파일인지 확인"""
    return url.lower().endswith('.pdf') or 'pdf' in url.lower()

def is_arxiv_url(url):
    """ArXiv URL인지 확인 (다양한 형태 지원)"""
    arxiv_patterns = [
        r'arxiv\.org',
        r'arxiv-export\.library\.cornell\.edu',
        r'export\.arxiv\.org'
    ]
    
    for pattern in arxiv_patterns:
        if re.search(pattern, url.lower()):
            return True
    return False

def is_pubmed_url(url):
    """PubMed URL인지 확인"""
    return 'pubmed.ncbi.nlm.nih.gov' in url.lower()

def fetch_arxiv_metadata(url):
    """ArXiv URL에서 메타데이터와 초록 추출"""
    try:
        # ArXiv ID 추출 로직 개선
        arxiv_id = url.split('/')[-1]
        
        # 버전 정보 처리 (v1, v2 등)
        if 'v' in arxiv_id and arxiv_id.split('v')[-1].isdigit():
            arxiv_id = arxiv_id.split('v')[0]
        
        # 불필요한 부분 제거
        arxiv_id = arxiv_id.replace('abs/', '').replace('pdf/', '').replace('.pdf', '')
        
        # ArXiv 라이브러리 사용
        import arxiv
        search = arxiv.Search(id_list=[arxiv_id])
        
        try:
            paper = next(search.results())
        except StopIteration:
            return f"❌ ArXiv 논문 {arxiv_id}를 찾을 수 없습니다. ID를 확인해주세요."
        
        # 카테고리 정보 추가
        categories = ', '.join(paper.categories) if paper.categories else "미분류"
        
        # 저자 정보 (최대 5명까지만 표시)
        authors = [str(a) for a in paper.authors[:5]]
        if len(paper.authors) > 5:
            authors.append(f"외 {len(paper.authors) - 5}명")
        author_list = ', '.join(authors)
        
        # 출판일 처리
        pub_date = paper.published.strftime('%Y년 %m월 %d일') if paper.published else "날짜 정보 없음"
        
        content = f"""📄 **ArXiv 논문 정보**

🔗 **링크**: {url}
📋 **ArXiv ID**: {arxiv_id}
📅 **출판일**: {pub_date}
📚 **카테고리**: {categories}

📖 **제목**: 
{paper.title}

👥 **저자**: 
{author_list}

📝 **초록**:
{paper.summary}

💡 **추가 정보**: 이 논문에 대해 더 자세한 질문을 하시면 초록 내용을 기반으로 답변해드릴게요!
        """
        
        return content.strip()
        
    except ImportError:
        return "❌ ArXiv 라이브러리가 설치되지 않았습니다. pip install arxiv로 설치해주세요."
    except Exception as e:
        logger.error(f"ArXiv 메타데이터 추출 오류: {str(e)}")
        return f"❌ ArXiv 논문 정보를 가져오는 중 오류가 발생했습니다: {str(e)}"

def fetch_pubmed_abstract(url):
    """PubMed URL에서 초록 추출"""
    try:
        # PMID 추출
        pmid = url.split('/')[-1].rstrip('/')
        
        # 숫자가 아닌 경우 처리
        if not pmid.isdigit():
            return f"❌ 유효하지 않은 PMID입니다: {pmid}"
        
        # PubMed API 사용
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        fetch_url = f"{base_url}efetch.fcgi"
        
        # 초록 가져오기
        params = {
            "db": "pubmed", 
            "id": pmid, 
            "retmode": "xml", 
            "rettype": "abstract"
        }
        
        response = requests.get(fetch_url, params=params, timeout=10)
        response.raise_for_status()
        
        # XML 파싱해서 초록 추출
        root = ET.fromstring(response.text)
        
        # 제목 추출
        title_elem = root.find(".//ArticleTitle")
        title = title_elem.text if title_elem is not None else "제목 없음"
        
        # 초록 추출 (여러 AbstractText가 있을 수 있음)
        abstract_elems = root.findall(".//AbstractText")
        if abstract_elems:
            abstract_parts = []
            for elem in abstract_elems:
                label = elem.get('Label', '')
                text = elem.text or ''
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            abstract = '\n'.join(abstract_parts)
        else:
            abstract = "초록 없음"
        
        # 저자 정보 추출
        author_elems = root.findall(".//Author")
        authors = []
        for author in author_elems[:5]:  # 최대 5명만
            last_name = author.findtext("LastName", "")
            first_name = author.findtext("ForeName", "")
            if last_name and first_name:
                authors.append(f"{first_name} {last_name}")
            elif last_name:
                authors.append(last_name)
        
        if len(author_elems) > 5:
            authors.append(f"외 {len(author_elems) - 5}명")
        
        author_list = ', '.join(authors) if authors else "저자 정보 없음"
        
        content = f"""📄 **PubMed 논문 정보**

🔗 **링크**: {url}
📋 **PMID**: {pmid}

📖 **제목**: 
{title}

👥 **저자**: 
{author_list}

📝 **초록**:
{abstract}

💡 **추가 정보**: 이 논문에 대해 더 자세한 질문을 하시면 초록 내용을 기반으로 답변해드릴게요!
        """
        
        return content.strip()
        
    except requests.RequestException as e:
        logger.error(f"PubMed API 요청 오류: {str(e)}")
        return f"❌ PubMed API 요청 중 오류가 발생했습니다: {str(e)}"
    except ET.ParseError as e:
        logger.error(f"XML 파싱 오류: {str(e)}")
        return f"❌ PubMed 응답 파싱 중 오류가 발생했습니다: {str(e)}"
    except Exception as e:
        logger.error(f"PubMed 추출 오류: {str(e)}")
        return f"❌ PubMed 논문 정보를 가져오는 중 오류가 발생했습니다: {str(e)}"

def fetch_webpage_content(url):
    """웹페이지 또는 논문 내용 추출 (개선된 버전)"""
    try:
        # URL 정규화
        url = normalize_arxiv_url(url)
        
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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 불필요한 태그 제거
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'advertisement']):
            tag.decompose()
        
        # 메인 콘텐츠 추출 (우선순위 순)
        main_content = (
            soup.find('main') or 
            soup.find('article') or 
            soup.find('div', class_=re.compile(r'content|main|post|article', re.I)) or
            soup.find('div', id=re.compile(r'content|main|post|article', re.I))
        )
        
        if main_content:
            text = main_content.get_text(strip=True, separator='\n')
        else:
            # 전체 body에서 텍스트 추출
            body = soup.find('body')
            if body:
                text = body.get_text(strip=True, separator='\n')
            else:
                text = soup.get_text(strip=True, separator='\n')
        
        # 텍스트 정리
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        clean_text = '\n'.join(lines)
        
        # 너무 긴 텍스트는 일부만 반환
        if len(clean_text) > 8000:
            clean_text = clean_text[:8000] + "\n\n... (내용이 길어서 일부만 표시됩니다)"
        
        return clean_text
        
    except requests.RequestException as e:
        logger.error(f"웹페이지 요청 오류: {str(e)}")
        return f"❌ '{url}' 웹페이지에 접근할 수 없습니다. 네트워크 오류: {str(e)}"
    except Exception as e:
        logger.error(f"웹페이지 내용 추출 오류: {str(e)}")
        return f"❌ '{url}' 내용을 가져올 수 없습니다. 오류: {str(e)}"

def normalize_arxiv_url(url):
    """ArXiv URL을 정규화 (PDF -> Abstract)"""
    if is_arxiv_url(url):
        # PDF 링크인 경우, Abstract 링크로 변환
        if '/pdf/' in url:
            url = url.replace('/pdf/', '/abs/')
        # .pdf 확장자 제거
        if url.endswith('.pdf'):
            url = url[:-4]
    
    return url

def summarize_webpage_content(url, user_query="", client=None):
    """웹페이지 내용을 요약합니다"""
    try:
        content = fetch_webpage_content(url)
        
        # 오류 메시지인 경우 그대로 반환
        if content.startswith("❌"):
            return content
        
        # LLM을 사용해 내용 요약
        if not client:
            from utils.providers import select_random_available_provider
            client, _ = select_random_available_provider()
        
        prompt = f"""다음 웹페이지의 내용을 한국어로 요약해주세요.

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
- 핵심 포인트 3

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
            logger.error(f"LLM 요약 생성 오류: {str(e)}")
            return f"❌ 요약 생성 중 오류가 발생했습니다: {str(e)}"
        
    except Exception as e:
        logger.error(f"웹페이지 요약 오류: {str(e)}")
        return f"❌ 웹페이지 요약 중 오류: {str(e)}"

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
