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

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 페이지 설정 ---
st.set_page_config(
    page_title="Chat with Gemini",
    page_icon="🚀",
    layout="wide"
)

# --- 이미지 처리 함수들 ---
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

# --- 유튜브 처리 함수들 ---
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
        elif 'youtube.com/shorts/' in url:  # 쇼츠 URL 처리 추가
            return url.split('shorts/')[1].split('?')[0]
        else:
            return None
    except:
        return None

def is_youtube_url(url):
    """유튜브 URL인지 확인 (쇼츠 포함)"""
    youtube_domains = ['youtube.com', 'youtu.be', 'www.youtube.com']
    youtube_patterns = ['/watch', '/shorts/', '/embed/', 'youtu.be/']  # 쇼츠 패턴 추가
    
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

💡 **결론**: 비 Video의 핵심 메시지나 결론
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

# --- 웹페이지 처리 함수들 ---
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

💡 **Conclusion**: Brief conclusion or katılı mesaj
"""
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"웹페이지 요약 중 오류: {str(e)}")
        return f"❌ 웹페이지 요약 중 오류가 발생했습니다: {str(e)}"

# --- PDF 처리 함수들 ---
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

# --- 유틸리티 함수들 ---
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

# --- 사이드바 ---
with st.sidebar:
    st.markdown("## ⚙️ 설정")
    api_key = st.text_input("🔑 Gemini API 키", type="password", help="Google AI Studio에서 발급받은 API 키를 입력하세요")
    if api_key:
        try:
            genai.configure(api_key=api_key)
            st.success("✅ API 키 연결 완료!")
        except Exception as e:
            st.error(f"❌ API 키 오류: {e}")

    st.markdown("---")
    usage_count = get_usage_count()
    free_limit = 100
    st.markdown("### 📊 오늘의 사용량")
    progress = min(usage_count / free_limit, 1.0)
    st.progress(progress)
    st.markdown(f"**{usage_count}/{free_limit}** 회 사용")
    if usage_count >= free_limit:
        st.error("⚠️ 일일 무료 한도를 초과했습니다!")
    elif usage_count >= free_limit * 0.8:
        st.warning("⚠️ 일일 한도에 가까워지고 있습니다!")

    st.markdown("---")
    st.markdown("### 💡 사용 가이드")
    st.markdown("""
    - **API 키**: [Google AI Studio](https://aistudio.google.com/app/apikey)에서 발급
    - **입력**: 사이드바에 API 키 입력
    - **기능**:
      - 🌐 웹페이지 요약: "https://example.com 요약해줘"
      - 📺 유튜브 요약: "https://youtube.com/watch?v=... 내용 정리"
      - 📄 PDF 요약: "https://example.com/sample.pdf 분석해줘"
      - 📸 이미지 분석: 이미지 업로드 후 "이거 설명해줘"
      - 💬 일반 채팅: "오늘 기분이 어때?"
    """)

# --- 메인 앱 ---
st.title("🚀 Chat with Gemini")

if api_key:
    try:
        genai.configure(api_key=api_key)
        
        # 초기 설정
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
        if "system_language" not in st.session_state:
            st.session_state.system_language = "ko"
        if "uploaded_images" not in st.session_state:
            st.session_state.uploaded_images = []

        # Gemini 모델 초기화
        system_prompt = get_system_prompt(st.session_state.system_language)
        model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)

        # 첫 방문 시에만 환영 메시지 표시 (채팅 기록이 없을 때)
        if not st.session_state.messages:
            st.markdown("""
            ### 🎉 Welcome to Gemini Chat!
            
            이 AI 어시스턴트는 다양한 기능을 제공합니다:
            
            <div style="display: flex; flex-wrap: wrap; gap: 15px; margin: 20px 0;">
                <div style="flex: 1; min-width: 300px; padding: 15px; border: 1px solid #e0e0e0; border-radius: 10px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
                    <h4>🌐 웹페이지 요약</h4>
                    <p>URL과 함께 "요약해줘"를 입력하면 웹페이지 내용을 분석해드립니다.</p>
                    <small>예: "https://example.com 내용 정리해줘"</small>
                </div>
                <div style="flex: 1; min-width: 300px; padding: 15px; border: 1px solid #e0e0e0; border-radius: 10px; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white;">
                    <h4>📺 유튜브 요약</h4>
                    <p>유튜브 링크를 보내면 자막을 추출해서 요약해드립니다.</p>
                    <small>예: "https://youtube.com/watch?v=... 요약해줘"</small>
                </div>
                <div style="flex: 1; min-width: 300px; padding: 15px; border: 1px solid #e0e0e0; border-radius: 10px; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white;">
                    <h4>📄 PDF 분석</h4>
                    <p>PDF 링크를 보내면 문서 내용을 분석해드립니다.</p>
                    <small>예: "https://example.com/file.pdf 분석해줘"</small>
                </div>
                <div style="flex: 1; min-width: 300px; padding: 15px; border: 1px solid #e0e0e0; border-radius: 10px; background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); color: white;">
                    <h4>📸 이미지 분석</h4>
                    <p>이미지를 업로드하고 질문하면 상세하게 분석해드립니다.</p>
                    <small>예: 이미지 업로드 후 "이거 뭐야?"</small>
                </div>
            </div>
            
            <div style="text-align: center; margin: 20px 0;">
                <h4>🚀 빠른 시작 예시</h4>
            </div>
            """, unsafe_allow_html=True)
            
            # 빠른 예시 버튼들 (첫 방문 시에만)
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("🌐 웹페이지 요약 예시", use_container_width=True):
                    st.session_state.example_input = "https://www.google.com 이 사이트에 대해 설명해줘"
                    
            with col2:
                if st.button("📺 유튜브 요약 예시", use_container_width=True):
                    st.session_state.example_input = "https://www.youtube.com/watch?v=dQw4w9WgXcQ 이 영상 요약해줘"
                    
            with col3:
                if st.button("🤖 AI 질문 예시", use_container_width=True):
                    st.session_state.example_input = "인공지능의 미래에 대해 어떻게 생각해?"
                    
            with col4:
                if st.button("💡 창의적 질문 예시", use_container_width=True):
                    st.session_state.example_input = "달에 집을 짓는다면 어떤 점을 고려해야 할까?"

            # 예시 버튼 클릭 시 입력 필드에 텍스트 설정
            if "example_input" in st.session_state:
                st.info(f"💡 예시 입력: {st.session_state.example_input}")
                st.markdown("아래 채팅 입력창에 직접 입력해보세요!")
                del st.session_state.example_input
                
            st.markdown("---")
            st.markdown("### 💬 대화를 시작해보세요!")

        # 채팅 기록 표시 (메인 채팅 영역)
        chat_container = st.container()
        with chat_container:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
                    # 이미지 표시 (메시지에 이미지가 포함된 경우)
                    if "images" in message and message["images"]:
                        cols = st.columns(min(3, len(message["images"])))
                        for idx, img_data in enumerate(message["images"]):
                            with cols[idx % 3]:
                                img = Image.open(io.BytesIO(img_data))
                                st.image(img, caption=f"이미지 {idx+1}", use_container_width=True)

        # 하단 고정 입력 영역
        st.markdown("---")
        
        # 이미지 업로드 영역 (채팅 입력 바로 위)
        with st.expander("📎 이미지 첨부", expanded=False):
            uploaded_files = st.file_uploader(
                "이미지를 업로드하여 분석해보세요",
                type=['png', 'jpg', 'jpeg', 'webp'],
                accept_multiple_files=True,
                key="chat_image_uploader",
                help="이미지를 분석하고 싶다면 여기에 업로드하세요"
            )
            
            # 업로드된 이미지 미리보기
            if uploaded_files:
                st.session_state.uploaded_images = uploaded_files
                st.success(f"📸 {len(uploaded_files)}개 이미지가 준비되었습니다!")
                
                # 이미지 미리보기를 가로로 나열
                cols = st.columns(min(4, len(uploaded_files)))
                for idx, img_file in enumerate(uploaded_files):
                    with cols[idx % 4]:
                        img = Image.open(img_file)
                        st.image(img, caption=f"이미지 {idx+1}", use_container_width=True)

        # 메인 채팅 입력창 (항상 하단에 위치)
        user_input = st.chat_input("💬 메시지를 입력하세요... (URL, 질문, 또는 이미지와 함께)")

        # 채팅 입력 처리
        if user_input:
            detected_lang = detect_language(user_input)
            
            # 언어 변경 처리
            if detected_lang != st.session_state.system_language:
                st.session_state.system_language = detected_lang
                system_prompt = get_system_prompt(detected_lang)
                model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)
                st.session_state.chat_history = []
                lang_change_msg = "언어가 변경되었습니다. 대화를 새로 시작합니다." if detected_lang == "ko" else "Language changed. Starting a new conversation."
                st.session_state.messages.append({"role": "assistant", "content": lang_change_msg})

            # 사용량 확인
            if get_usage_count() >= 100:
                st.error("⚠️ 일일 무료 한도를 초과했습니다!")
            else:
                increment_usage()
                
                # 사용자 메시지 및 이미지 저장
                image_data = []
                if st.session_state.uploaded_images:
                    for img_file in st.session_state.uploaded_images:
                        valid, msg = validate_image_file(img_file)
                        if not valid:
                            st.error(msg)
                            continue
                        img_file.seek(0)  # 파일 포인터 초기화
                        image_data.append(img_file.read())
                
                st.session_state.messages.append({
                    "role": "user",
                    "content": user_input,
                    "images": image_data
                })
                
                # 요청 유형 확인
                is_youtube_request, youtube_url = is_youtube_summarization_request(user_input)
                is_webpage_request, webpage_url = is_url_summarization_request(user_input)
                is_pdf_request, pdf_url = is_pdf_summarization_request(user_input)
                has_images = len(st.session_state.uploaded_images) > 0
                is_image_analysis = is_image_analysis_request(user_input, has_images)
                
                # 응답 처리
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
                
                # 응답 저장
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                # 이미지 초기화
                st.session_state.uploaded_images = []
                
                # 페이지 새로고침으로 최신 메시지 표시
                st.rerun()

        # 하단 팁 (고정)
        st.markdown("""
        <div style="text-align: center; color: #666; font-size: 14px; margin-top: 10px; padding: 10px; background-color: #f8f9fa; border-radius: 5px;">
            💡 <strong>팁:</strong> URL을 붙여넣고 '요약해줘', 이미지를 업로드하고 '분석해줘', 또는 자유롭게 질문해보세요!
        </div>
        """, unsafe_allow_html=True)
                
    except Exception as e:
        st.error(f"❌ 오류 발생: {e}")
else:
    # API 키가 없을 때 더 친근한 안내
    st.markdown("""
    <div style="text-align: center; padding: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 15px; margin: 20px 0;">
        <h2>🚀 Gemini AI와 대화해보세요!</h2>
        <p style="font-size: 18px; margin: 20px 0;">강력한 AI 어시스턴트가 여러분을 기다리고 있습니다.</p>
        <p style="font-size: 16px;">🔑 왼쪽 사이드바에서 API 키를 입력하고 시작해보세요!</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🎯 주요 기능")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **🌐 웹 컨텐츠 분석**
        - 웹페이지 요약
        - 유튜브 영상 요약
        - PDF 문서 분석
        
        **🤖 AI 대화**
        - 자연스러운 대화
        - 창의적 질문 응답
        - 문제 해결 도움
        """)
    
    with col2:
        st.markdown("""
        **📸 이미지 분석**
        - 이미지 내용 설명
        - 텍스트 추출
        - 시각적 요소 분석
        
        **🌍 다국어 지원**
        - 한국어/영어 자동 감지
        - 언어별 최적화된 응답
        """)
    
    st.markdown("---")
    st.info("🔗 **API 키 발급**: [Google AI Studio](https://aistudio.google.com/app/apikey)에서 무료로 발급받을 수 있습니다!")