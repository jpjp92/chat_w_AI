import streamlit as st
import google.generativeai as genai
import os
from datetime import datetime
import json
import requests
from bs4 import BeautifulSoup
import re
import logging
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from pypdf import PdfReader
import io
from PIL import Image
import base64
from config.env import GEMINI_API_KEY

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 페이지 설정 ---
st.set_page_config(
    page_title="Chat with Gemini",
    page_icon="🚀",
    layout="wide"
)

# --- Gemini API 설정 ---
if not GEMINI_API_KEY:
    st.error("❌ GEMINI_API_KEY가 설정되지 않았습니다. Streamlit Secrets 또는 config/env.py를 확인하세요.")
    st.stop()

try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error(f"❌ API 키 오류: {e}")
    st.stop()

# --- 기존 함수들 (이미지, 유튜브, 웹페이지, PDF 처리 등) ---
def validate_image_file(uploaded_file):
    """업로드된 이미지 파일 유효성 검사"""
    supported_types = ['image/png', 'image/jpeg', 'image/webp']
    if uploaded_file.type not in supported_types:
        return False, f"지원되지 않는 이미지 형식입니다. 지원 형식: PNG, JPEG, WebP"
    max_size = 7 * 1024 * 1024  # 7MB
    if uploaded_file.size > max_size:
        return False, f"이미지 크기가 너무 큽니다. 최대 크기: 7MB, 현재 크기: {uploaded_file.size / (1024*1024):.1f}MB"
    return True, "유효한 이미지 파일입니다."

def process_image_for_gemini(uploaded_file):
    """Gemini API용 이미지 처리"""
    try:
        image = Image.open(uploaded_file)
        logger.info(f"이미지 크기: {image.size}, 모드: {image.mode}, 형식: {image.format}")
        return image
    except Exception as e:
        logger.error(f"이미지 처리 오류: {str(e)}")
        return None

def analyze_image_with_gemini(images, user_query, chat_session, detected_lang):
    """Gemini로 이미지 분석 (다중 이미지 지원)"""
    try:
        system_prompt = get_system_prompt(detected_lang)
        if detected_lang == "ko":
            prompt = f"""{system_prompt}

다음 이미지들을 분석해주세요.

사용자 질문: {user_query}

분석 지침:
1. 각 이미지에 보이는 주요 요소들을 설명
2. 이미지들 간의 관계나 공통점, 차이점 분석
3. 색상, 구도, 스타일 등의 시각적 특징
4. 텍스트가 있다면 읽어서 내용 설명
5. 사용자의 특정 질문이 있다면 그에 맞춰 분석
6. 이모지를 적절히 사용하여 가독성 향상
7. 반드시 한국어로만 답변하세요

형식:
📸 **이미지 분석 결과**

🔍 **주요 요소**:
- 이미지 1: ...
- 이미지 2: ...
- ...

🎨 **시각적 특징**:
- ...

📝 **텍스트 내용** (있는 경우):
- ...

💡 **추가 분석**:
- ...
"""
        else:
            prompt = f"""{system_prompt}

Please analyze the following images.

User Query: {user_query}

Analysis Guidelines:
1. Describe the main elements visible in each image
2. Analyze relationships, commonalities, or differences between images
3. Include visual features such as colors, composition, style
4. If there's text, read and describe the content
5. Focus on user's specific question if provided
6. Use appropriate emojis for readability
7. Respond only in English

Format:
📸 **Image Analysis Result**

🔍 **Main Elements**:
- Image 1: ...
- Image 2: ...
- ...

🎨 **Visual Features**:
- ...

📝 **Text Content** (if any):
- ...

💡 **Additional Analysis**:
- ...
"""
        message_content = [prompt] + images
        response = chat_session.send_message(message_content)
        return response.text
    except Exception as e:
        logger.error(f"이미지 분석 중 오류: {str(e)}")
        return f"❌ 이미지 분석 중 오류가 발생했습니다: {str(e)}"

def is_image_analysis_request(query, has_images):
    """이미지 분석 요청인지 확인"""
    if not has_images:
        return False
    analysis_keywords = ['분석', '설명', '알려줘', '무엇', '뭐', '어떤', '보여줘', '읽어줘', '해석', '분석해줘']
    return any(keyword in query for keyword in analysis_keywords)

def extract_video_id(url):
    """유튜브 URL에서 비디오 ID 추출 (쇼츠 포함)"""
    try:
        if 'youtu.be/' in url:
            return url.split('youtu.be/')[1].split('?')[0]
        elif 'youtube.com/watch' in url:
            parsed_url = urlparse(url)
            return parse_qs(parsed_url.query)['v'][0]
        elif 'youtube.com/embed/' in url:
            return url.split('embed/')[1].split('?')[0]
        elif 'youtube.com/shorts/' in url:
            return url.split('shorts/')[1].split('?')[0]
        else:
            return None
    except:
        return None

def is_youtube_url(url):
    """유튜브 URL인지 확인 (쇼츠 포함)"""
    youtube_domains = ['youtube.com', 'youtu.be', 'www.youtube.com']
    youtube_patterns = ['/watch', '/shorts/', '/embed/', 'youtu.be/']
    try:
        parsed_url = urlparse(url)
        domain_match = any(domain in parsed_url.netloc for domain in youtube_domains)
        pattern_match = any(pattern in url for pattern in youtube_patterns)
        return domain_match and pattern_match
    except:
        return False

def get_youtube_transcript(video_id):
    """유튜브 비디오의 자막 가져오기"""
    try:
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko'])
        except:
            try:
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
            except:
                transcript = YouTubeTranscriptApi.get_transcript(video_id)
        full_text = ' '.join([entry['text'] for entry in transcript])
        max_chars = 15000
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + "\n\n... (자막이 길어서 일부만 표시됩니다)"
        return full_text
    except Exception as e:
        logger.error(f"유튜브 자막 추출 오류: {str(e)}")
        return None

def extract_urls_from_text(text):
    """텍스트에서 URL을 추출"""
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, text)
    return urls

def is_youtube_summarization_request(query):
    """유튜브 요약 요청인지 확인"""
    urls = extract_urls_from_text(query)
    if urls:
        for url in urls:
            if is_youtube_url(url):
                summary_keywords = ['요약', '정리', '내용', '설명', '알려줘', '분석', '해석', '리뷰', '정보']
                for keyword in summary_keywords:
                    if keyword in query:
                        return True, url
    return False, None

def summarize_youtube_with_gemini(url, user_query, model, detected_lang):
    """유튜브 비디오를 Gemini로 요약"""
    try:
        video_id = extract_video_id(url)
        if not video_id:
            return "❌ 유효하지 않은 유튜브 URL입니다."
        transcript = get_youtube_transcript(video_id)
        if not transcript:
            return "❌ 이 유튜브 비디오의 자막을 가져올 수 없습니다."
        system_prompt = get_system_prompt(detected_lang)
        if detected_lang == "ko":
            prompt = f"""{system_prompt}

다음 유튜브 비디오의 자막 내용을 한국어로 요약해주세요.

유튜브 URL: {url}
사용자 질문: {user_query}

비디오 자막 내용:
{transcript}

요약 지침:
1. 비디오의 주요 내용을 5-7개 포인트로 정리
2. 중요한 정보나 핵심 메시지를 포함
3. 시간 순서대로 내용 구성
4. 사용자가 특정 질문을 했다면 그에 맞춰 요약
5. 이모지를 적절히 사용하여 가독성 향상
6. 출처 URL도 함께 제공
7. 반드시 한국어로만 답변하세요

형식:
🎬 **유튜브 비디오 요약**

🔗 **출처**: {url}

📝 **주요 내용**:
- 핵심 포인트 1
- 핵심 포인트 2
- ...

💡 **결론**: 비디오의 핵심 메시지나 결론
"""
        else:
            prompt = f"""{system_prompt}

Please summarize the following YouTube video transcript in English.

YouTube URL: {url}
User Query: {user_query}

Video Transcript:
{transcript}

Summary Guidelines:
1. Organize main content into 5-7 key points
2. Include important information and key messages
3. Structure content chronologically
4. Focus on user's specific question if provided
5. Use appropriate emojis for readability
6. Include source URL
7. Respond only in English

Format:
🎬 **YouTube Video Summary**

🔗 **Source**: {url}

📝 **Key Points**:
- Main point 1
- Main point 2
- ...

💡 **Conclusion**: Key message or conclusion from the video
"""
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"유튜브 요약 중 오류: {str(e)}")
        return f"❌ 유튜브 요약 중 오류가 발생했습니다: {str(e)}"

def is_url_summarization_request(query):
    """URL 요약 요청인지 확인 (유튜브 및 PDF 제외)"""
    urls = extract_urls_from_text(query)
    if urls:
        for url in urls:
            if not is_youtube_url(url) and not is_pdf_url(url):
                summary_keywords = ['요약', '정리', '내용', '설명', '알려줘', '분석', '해석', '리뷰', '정보']
                for keyword in summary_keywords:
                    if keyword in query:
                        return True, url
    return False, None

def fetch_webpage_content(url):
    """일반 웹페이지 HTML 내용 추출"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            tag.decompose()
        main_content = soup.find('main') or soup.find('article') or soup.body
        text = main_content.get_text(strip=True, separator='\n') if main_content else soup.get_text(strip=True, separator='\n')
        clean_text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
        if len(clean_text) > 8000:
            clean_text = clean_text[:8000] + "\n\n... (내용이 길어서 일부만 표시됩니다)"
        return clean_text
    except Exception as e:
        logger.error(f"웹페이지 내용 추출 오류: {str(e)}")
        return f"❌ '{url}' 내용을 가져올 수 없습니다: {str(e)}"

def summarize_webpage_with_gemini(url, user_query, model, detected_lang):
    """웹페이지 내용을 Gemini로 요약"""
    try:
        content = fetch_webpage_content(url)
        if content.startswith("❌"):
            return content
        system_prompt = get_system_prompt(detected_lang)
        if detected_lang == "ko":
            prompt = f"""{system_prompt}

다음 웹페이지의 내용을 한국어로 요약해주세요.

웹페이지 URL: {url}
사용자 질문: {user_query}

웹페이지 내용:
{content}

요약 지침:
1. 주요 핵심 내용을 3-5개 포인트로 정리
2. 중요한 정보나 수치가 있다면 포함
3. 사용자가 특정 질문을 했다면 그에 맞춰 요약
4. 이모지를 적절히 사용하여 가독성 향상
5. 출처 URL도 함께 제공
6. 반드시 한국어로만 답변하세요

형식:
📄 **웹페이지 요약**

🔗 **출처**: {url}

📝 **주요 내용**:
- 핵심 포인트 1
- 핵심 포인트 2
- ...

💡 **결론**: 간단한 결론이나 핵심 메시지
"""
        else:
            prompt = f"""{system_prompt}

Please summarize the following webpage content in English.

Webpage URL: {url}
User Query: {user_query}

Webpage Content:
{content}

Summary Guidelines:
1. Organize main points into 3-5 key bullets
2. Include important information or numbers if present
3. Focus on user's specific question if provided
4. Use appropriate emojis for readability
5. Include source URL
6. Respond only in English

Format:
📄 **Webpage Summary**

🔗 **Source**: {url}

📝 **Key Points**:
- Main point 1
- Main point 2
- ...

💡 **Conclusion**: Brief conclusion or key message
"""
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"웹페이지 요약 중 오류: {str(e)}")
        return f"❌ 웹페이지 요약 중 오류가 발생했습니다: {str(e)}"

def is_pdf_url(url):
    """PDF URL인지 확인"""
    return url.lower().endswith('.pdf') or '/pdf/' in url

def is_pdf_summarization_request(query):
    """PDF 요약 요청인지 확인"""
    urls = extract_urls_from_text(query)
    if urls:
        for url in urls:
            if is_pdf_url(url):
                summary_keywords = ['요약', '정리', '내용', '설명', '알려줘', '분석', '해석', '리뷰', '정보']
                for keyword in summary_keywords:
                    if keyword in query:
                        return True, url
    return False, None

def fetch_pdf_text(url, max_chars=8000):
    """PDF 파일에서 텍스트 추출"""
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        pdf_file = io.BytesIO(response.content)
        reader = PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
            if len(text) > max_chars:
                text = text[:max_chars] + "\n\n... (내용이 길어서 일부만 표시됩니다)"
                break
        metadata = reader.metadata or {}
        return text.strip(), metadata
    except Exception as e:
        return f"❌ PDF 파일을 처리할 수 없습니다: {e}", None

def summarize_pdf_with_gemini(url, user_query, model, detected_lang):
    """PDF 내용을 Gemini로 요약"""
    try:
        content, metadata = fetch_pdf_text(url)
        if content.startswith("❌"):
            return content
        metadata_info = {
            "title": metadata.get("/Title", "Unknown") if metadata else "Unknown",
            "author": metadata.get("/Author", "Unknown") if metadata else "Unknown"
        }
        system_prompt = get_system_prompt(detected_lang)
        if detected_lang == "ko":
            prompt = f"""{system_prompt}

다음 PDF 문서의 내용을 한국어로 요약해주세요.

PDF URL: {url}
PDF 제목: {metadata_info["title"]}
사용자 질문: {user_query}

PDF 내용:
{content}

요약 지침:
1. 주요 내용을 3-5개 포인트로 정리
2. 중요한 데이터나 기여도를 포함
3. 사용자가 특정 질문을 했다면 그에 맞춰 요약
4. 이모지를 적절히 사용하여 가독성 향상
5. 출처 URL과 제목 포함
6. 반드시 한국어로만 답변하세요

형식:
📄 **PDF 요약**

🔗 **출처**: {url}
📖 **제목**: {metadata_info["title"]}
📜 **저자**: {metadata_info["author"]}

📝 **주요 내용**:
- 포인트 1
- 포인트 2
- ...

💡 **핵심**: 주요 메시지나 의의
"""
        else:
            prompt = f"""{system_prompt}

Please summarize the following PDF document in English.

PDF URL: {url}
PDF Title: {metadata_info["title"]}
User Query: {user_query}

PDF Content:
{content}

Summary Guidelines:
1. Organize main points into 3-5 key bullets
2. Include important data or contributions
3. Focus on user's specific question if provided
4. Use appropriate emojis for readability
5. Include source URL and title
6. Respond only in English

Format:
📄 **PDF Summary**

🔗 **Source**: {url}
📖 **Title**: {metadata_info["title"]}
📜 **Author**: {metadata_info["author"]}

📝 **Key Points**:
- Point 1
- Point 2
- ...

💡 **Key Insight**: Main message or significance
"""
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"PDF 요약 중 오류: {str(e)}")
        return f"❌ PDF 요약 중 오류가 발생했습니다: {str(e)}"

def get_usage_count():
    """일일 사용량 추적"""
    today = datetime.now().strftime("%Y-%m-%d")
    if "usage_data" not in st.session_state:
        st.session_state.usage_data = {"date": today, "count": 0}
    if st.session_state.usage_data["date"] != today:
        st.session_state.usage_data = {"date": today, "count": 0}
    return st.session_state.usage_data["count"]

def increment_usage():
    """사용량 증가"""
    if "usage_data" in st.session_state:
        st.session_state.usage_data["count"] += 1
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        st.session_state.usage_data = {"date": today, "count": 1}

def detect_language(text):
    """텍스트에서 URL을 제외하고 언어 감지"""
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, text)
    for url in urls:
        text = text.replace(url, '')
    text = text.strip()
    if not text:
        return "ko"
    korean_chars = sum(1 for char in text if '\uac00' <= char <= '\ud7af')
    total_chars = len(text.replace(' ', ''))
    korean_ratio = korean_chars / total_chars if total_chars > 0 else 0
    return "ko" if korean_ratio > 0.3 else "en"

def get_system_prompt(language):
    """언어별 시스템 프롬프트"""
    if language == "ko":
        return """당신은 친근하고 도움이 되는 AI 어시스턴트입니다.
        다음 규칙을 따라주세요:
        - 한국어로만 답변하세요
        - 친근하고 자연스러운 톤을 사용하세요
        - 이모지를 적절히 활용하세요
        - 웹페이지, 유튜브, PDF 요약 기능을 제공할 수 있습니다
        - 이미지 분석 기능을 제공할 수 있습니다
        - 답변은 간결하면서도 유용하게 작성하세요"""
    else:
        return """You are a friendly and helpful AI assistant.
        Please follow these rules:
        - Respond only in English
        - Use a friendly and natural tone
        - Use appropriate emojis
        - You can provide webpage, YouTube, and PDF summarization features
        - You can provide image analysis features
        - Keep responses concise yet useful"""

# --- 사이드바: 채팅 내역 표시 ---
with st.sidebar:
    st.markdown("### 📜 채팅 내역")
    if st.session_state.get("messages"):
        for idx, message in enumerate(st.session_state.messages):
            with st.container():
                if message["role"] == "user":
                    st.markdown(f"**나**: {message['content'][:50]}...")
                else:
                    st.markdown(f"**Gemini**: {message['content'][:50]}...")
                if st.button(f"대화 {idx+1} 보기", key=f"history_{idx}"):
                    st.session_state.selected_message = message
                    # st.rerun() 제거: 선택된 메시지 표시를 메인 화면에서 처리
                st.markdown("---")
    else:
        st.markdown("아직 대화 기록이 없습니다.")

# --- 메인 앱 ---
st.title("🚀 Chat with Gemini")

# 초기 설정
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "system_language" not in st.session_state:
    st.session_state.system_language = "ko"
if "uploaded_images" not in st.session_state:
    st.session_state.uploaded_images = []
if "welcome_dismissed" not in st.session_state:
    st.session_state.welcome_dismissed = False

# Gemini 모델 초기화
system_prompt = get_system_prompt(st.session_state.system_language)
model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)

# 첫 방문 시 환영 메시지
if not st.session_state.messages and not st.session_state.welcome_dismissed:
    st.markdown("""
    <div style="text-align: center; margin: 20px 0;">
       
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("🌐 웹페이지 요약 예시", use_container_width=True):
            st.session_state.example_input = "https://www.google.com 이 사이트에 대해 설명해줘"
    with col2:
        if st.button("📺 유튜브 요약 예시", use_container_width=True):
            st.session_state.example_input = "https://www.youtube.com/watch?v=dQw4w9WgXcQ 이 영상 요약해줘"
    with col3:
        if st.button("📄 PDF 논문 요약 예시", use_container_width=True):
            st.session_state.example_input = "https://arxiv.org/pdf/2410.04064 요약해줘"
    with col4:
        if st.button("🖼️ 이미지 분석 예시", use_container_width=True):
            st.session_state.example_input = "이미지를 분석해줘"
    with col5:
        if st.button("💬 일상대화 예시", use_container_width=True):
            st.session_state.example_input = "오늘 기분이 어때?"

    if "example_input" in st.session_state:
        st.info(f"💡 예시 입력: {st.session_state.example_input}")
        st.markdown("아래 채팅 입력창에 직접 입력해보세요!")
        del st.session_state.example_input
    
    # if st.button("환영 메시지 닫기"):
    #     st.session_state.welcome_dismissed = True

# 채팅 기록 표시 (메인 채팅 영역)
chat_container = st.container()
with chat_container:
    if "selected_message" in st.session_state:
        message = st.session_state.selected_message
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "images" in message and message["images"]:
                cols = st.columns(min(3, len(message["images"])))
                for idx, img_data in enumerate(message["images"]):
                    with cols[idx % 3]:
                        img = Image.open(io.BytesIO(img_data))
                        st.image(img, caption=f"이미지 {idx+1}", use_container_width=True)
        if st.button("전체 대화 보기"):
            del st.session_state.selected_message  # 선택 해제
    else:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if "images" in message and message["images"]:
                    cols = st.columns(min(3, len(message["images"])))
                    for idx, img_data in enumerate(message["images"]):
                        with cols[idx % 3]:
                            img = Image.open(io.BytesIO(img_data))
                            st.image(img, caption=f"이미지 {idx+1}", use_container_width=True)

# 하단 고정 입력 영역
st.markdown("---")

# 이미지 업로드 영역
with st.expander("📎 이미지 첨부", expanded=False):
    uploaded_files = st.file_uploader(
        "이미지를 업로드하여 분석해보세요",
        type=['png', 'jpg', 'jpeg', 'webp'],
        accept_multiple_files=True,
        key="chat_image_uploader",
        help="이미지를 분석하고 싶다면 여기에 업로드하세요"
    )
    if uploaded_files:
        st.session_state.uploaded_images = uploaded_files
        st.success(f"📸 {len(uploaded_files)}개 이미지가 준비되었습니다!")
        cols = st.columns(min(4, len(uploaded_files)))
        for idx, img_file in enumerate(uploaded_files):
            with cols[idx % 4]:
                img = Image.open(img_file)
                st.image(img, caption=f"이미지 {idx+1}", use_container_width=True)

# 메인 채팅 입력창
user_input = st.chat_input("💬 메시지를 입력해주세요.")

# 채팅 입력 처리
if user_input:
    detected_lang = detect_language(user_input)
    if detected_lang != st.session_state.system_language:
        st.session_state.system_language = detected_lang
        system_prompt = get_system_prompt(detected_lang)
        model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)
        st.session_state.chat_history = []
        lang_change_msg = "언어가 변경되었습니다. 대화를 새로 시작합니다." if detected_lang == "ko" else "Language changed. Starting a new conversation."
        st.session_state.messages.append({"role": "assistant", "content": lang_change_msg})

    if get_usage_count() >= 100:
        st.error("⚠️ 일일 무료 한도를 초과했습니다!")
    else:
        increment_usage()
        image_data = []
        if st.session_state.uploaded_images:
            for img_file in st.session_state.uploaded_images:
                valid, msg = validate_image_file(img_file)
                if not valid:
                    st.error(msg)
                    continue
                img_file.seek(0)
                image_data.append(img_file.read())
        
        st.session_state.messages.append({
            "role": "user",
            "content": user_input,
            "images": image_data
        })
        
        is_youtube_request, youtube_url = is_youtube_summarization_request(user_input)
        is_webpage_request, webpage_url = is_url_summarization_request(user_input)
        is_pdf_request, pdf_url = is_pdf_summarization_request(user_input)
        has_images = len(st.session_state.uploaded_images) > 0
        is_image_analysis = is_image_analysis_request(user_input, has_images)
        
        with st.status("🤖 요청을 처리하는 중...", expanded=True) as status:
            if is_youtube_request:
                status.update(label="📺 유튜브 자막을 가져오는 중...")
                response = summarize_youtube_with_gemini(youtube_url, user_input, model, detected_lang)
            elif is_webpage_request:
                status.update(label="🌐 웹페이지 내용을 가져오는 중...")
                response = summarize_webpage_with_gemini(webpage_url, user_input, model, detected_lang)
            elif is_pdf_request:
                status.update(label="📄 PDF 내용을 가져오는 중...")
                response = summarize_pdf_with_gemini(pdf_url, user_input, model, detected_lang)
            elif is_image_analysis and has_images:
                status.update(label="📸 이미지를 분석하는 중...")
                images = [process_image_for_gemini(img) for img in st.session_state.uploaded_images]
                if all(img is not None for img in images):
                    chat_session = model.start_chat(history=[])
                    response = analyze_image_with_gemini(images, user_input, chat_session, detected_lang)
                else:
                    response = "❌ 이미지 처리 중 오류가 발생했습니다."
            else:
                status.update(label="💬 응답을 생성하는 중...")
                chat_session = model.start_chat(history=st.session_state.chat_history)
                response = chat_session.send_message(user_input).text
                st.session_state.chat_history = chat_session.history
            status.update(label="✅ 완료!", state="complete")
        
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.session_state.uploaded_images = []
        st.rerun()

# 하단 팁
# st.markdown("""
# <div style="text-align: center; color: #666; font-size: 14px; margin-top: 10px; padding: 10px; background-color: #f8f9fa; border-radius: 5px;">
#     💡 <strong>팁:</strong> URL을 붙여넣고 '요약해줘', 이미지를 업로드하고 '분석해줘', 또는 자유롭게 질문해보세요!
# </div>
""", unsafe_allow_html=True)