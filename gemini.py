# import streamlit as st
# import google.generativeai as genai
# import os
# from datetime import datetime
# import json
# import requests
# from bs4 import BeautifulSoup
# import re
# import logging
# from youtube_transcript_api import YouTubeTranscriptApi
# from urllib.parse import urlparse, parse_qs
# from pypdf import PdfReader
# import io

# # 로깅 설정
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # --- 페이지 설정 ---
# st.set_page_config(
#     page_title="Chat with Gemini",
#     page_icon="🚀",
#     layout="wide"
# )

# # --- 유튜브 처리 함수들 ---
# def extract_video_id(url):
#     """유튜브 URL에서 비디오 ID 추출"""
#     try:
#         # 다양한 유튜브 URL 형식 지원
#         if 'youtu.be/' in url:
#             return url.split('youtu.be/')[1].split('?')[0]
#         elif 'youtube.com/watch' in url:
#             parsed_url = urlparse(url)
#             return parse_qs(parsed_url.query)['v'][0]
#         elif 'youtube.com/embed/' in url:
#             return url.split('embed/')[1].split('?')[0]
#         else:
#             return None
#     except:
#         return None

# def get_youtube_transcript(video_id):
#     """유튜브 비디오의 자막 가져오기"""
#     try:
#         # 한국어 자막 우선 시도
#         try:
#             transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko'])
#         except:
#             # 한국어 자막이 없으면 영어 자막 시도
#             try:
#                 transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
#             except:
#                 # 자동 생성 자막 포함하여 시도
#                 transcript = YouTubeTranscriptApi.get_transcript(video_id)
        
#         # 자막 텍스트 합치기
#         full_text = ' '.join([entry['text'] for entry in transcript])
        
#         # 텍스트 길이 제한 (토큰 수 제한을 위해)
#         max_chars = 15000  # 약 3000-4000 토큰 정도
#         if len(full_text) > max_chars:
#             full_text = full_text[:max_chars] + "\n\n... (자막이 길어서 일부만 표시됩니다)"
        
#         return full_text
        
#     except Exception as e:
#         logger.error(f"유튜브 자막 추출 오류: {str(e)}")
#         return None

# def is_youtube_url(url):
#     """유튜브 URL인지 확인"""
#     youtube_domains = ['youtube.com', 'youtu.be', 'www.youtube.com']
#     try:
#         parsed_url = urlparse(url)
#         return any(domain in parsed_url.netloc for domain in youtube_domains)
#     except:
#         return False

# def extract_urls_from_text(text):
#     """텍스트에서 URL을 추출"""
#     url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
#     urls = re.findall(url_pattern, text)
#     return urls

# def is_youtube_summarization_request(query):
#     """유튜브 요약 요청인지 확인"""
#     urls = extract_urls_from_text(query)
#     if urls:
#         for url in urls:
#             if is_youtube_url(url):
#                 summary_keywords = ['요약', '정리', '내용', '설명', '알려줘', '분석', '해석', '리뷰', '정보']
#                 for keyword in summary_keywords:
#                     if keyword in query:
#                         return True, url
#     return False, None

# def summarize_youtube_with_gemini(url, user_query, chat_session, detected_lang):
#     """유튜브 비디오를 Gemini로 요약"""
#     try:
#         # 비디오 ID 추출
#         video_id = extract_video_id(url)
#         if not video_id:
#             return "❌ 유효하지 않은 유튜브 URL입니다."
        
#         # 자막 가져오기
#         with st.spinner("📺 유튜브 자막을 가져오는 중..."):
#             transcript = get_youtube_transcript(video_id)
        
#         if not transcript:
#             return "❌ 이 유튜브 비디오의 자막을 가져올 수 없습니다. 자막이 없거나 비공개 비디오일 수 있습니다."
        
#         # 언어별 시스템 프롬프트 추가
#         system_prompt = get_system_prompt(detected_lang)
        
#         # 언어별 요약 프롬프트
#         if detected_lang == "ko":
#             prompt = f"""{system_prompt}

# 다음 유튜브 비디오의 자막 내용을 한국어로 요약해주세요.

# 유튜브 URL: {url}
# 사용자 질문: {user_query}

# 비디오 자막 내용:
# {transcript}

# 요약 지침:
# 1. 비디오의 주요 내용을 5-7개 포인트로 정리
# 2. 중요한 정보나 핵심 메시지를 포함
# 3. 시간 순서대로 내용 구성
# 4. 사용자가 특정 질문을 했다면 그에 맞춰 요약
# 5. 이모지를 적절히 사용하여 가독성 향상
# 6. 출처 URL도 함께 제공
# 7. 반드시 한국어로만 답변하세요

# 형식:
# 🎬 **유튜브 비디오 요약**

# 🔗 **출처**: {url}

# 📝 **주요 내용**:
# - 핵심 포인트 1
# - 핵심 포인트 2
# - 핵심 포인트 3
# - 핵심 포인트 4
# - 핵심 포인트 5

# 💡 **결론**: 비디오의 핵심 메시지나 결론

# ⏱️ **예상 시청 시간**: 대략적인 비디오 길이 정보 (가능한 경우)
# """
#         else:
#             prompt = f"""{system_prompt}

# Please summarize the following YouTube video transcript in English.

# YouTube URL: {url}
# User Query: {user_query}

# Video Transcript:
# {transcript}

# Summary Guidelines:
# 1. Organize main content into 5-7 key points
# 2. Include important information and key messages
# 3. Structure content chronologically
# 4. Focus on user's specific question if provided
# 5. Use appropriate emojis for readability
# 6. Include source URL
# 7. Respond only in English

# Format:
# 🎬 **YouTube Video Summary**

# 🔗 **Source**: {url}

# 📝 **Key Points**:
# - Main point 1
# - Main point 2
# - Main point 3
# - Main point 4
# - Main point 5

# 💡 **Conclusion**: Key message or conclusion from the video

# ⏱️ **Estimated Watch Time**: Approximate video length (if available)
# """
        
#         # Gemini로 요약 생성
#         with st.spinner("🤖 Gemini가 유튜브 내용을 요약하는 중..."):
#             response = chat_session.send_message(prompt)
#             return response.text
        
#     except Exception as e:
#         logger.error(f"유튜브 요약 중 오류: {str(e)}")
#         return f"❌ 유튜브 요약 중 오류가 발생했습니다: {str(e)}"

# # --- 웹페이지 처리 함수들 ---
# def is_url_summarization_request(query):
#     """URL 요약 요청인지 확인 (유튜브 제외)"""
#     urls = extract_urls_from_text(query)
#     if urls:
#         for url in urls:
#             if not is_youtube_url(url):  # 유튜브가 아닌 URL만 처리
#                 summary_keywords = ['요약', '정리', '내용', '설명', '알려줘', '분석', '해석', '리뷰', '정보']
#                 for keyword in summary_keywords:
#                     if keyword in query:
#                         return True, url
#     return False, None

# def fetch_webpage_content(url):
#     """일반 웹페이지 HTML 내용 추출"""
#     try:
#         # User-Agent 헤더 설정 (봇 차단 방지)
#         headers = {
#             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
#         }
        
#         # HTTP 요청
#         response = requests.get(url, headers=headers, timeout=15)
#         response.raise_for_status()
        
#         # BeautifulSoup으로 HTML 파싱
#         soup = BeautifulSoup(response.content, 'html.parser')
        
#         # 불필요한 태그 제거
#         for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'advertisement']):
#             tag.decompose()
        
#         # 메인 콘텐츠 추출 (우선순위 순서로 시도)
#         main_content = (
#             soup.find('main') or                                                    # HTML5 main 태그
#             soup.find('article') or                                                # HTML5 article 태그
#             soup.find('div', class_=re.compile(r'content|main|post|article', re.I)) or  # content 관련 class
#             soup.find('div', id=re.compile(r'content|main|post|article', re.I))         # content 관련 id
#         )
        
#         # 메인 콘텐츠가 있으면 해당 부분에서 텍스트 추출
#         if main_content:
#             text = main_content.get_text(strip=True, separator='\n')
#         else:
#             # 메인 콘텐츠를 못 찾으면 전체 body에서 텍스트 추출
#             body = soup.find('body')
#             if body:
#                 text = body.get_text(strip=True, separator='\n')
#             else:
#                 # body도 없으면 전체 HTML에서 텍스트 추출
#                 text = soup.get_text(strip=True, separator='\n')
        
#         # 텍스트 정리 (빈 줄 제거, 공백 정리)
#         lines = [line.strip() for line in text.split('\n') if line.strip()]
#         clean_text = '\n'.join(lines)
        
#         # 텍스트 길이 제한 (너무 긴 내용은 일부만 반환)
#         if len(clean_text) > 8000:
#             clean_text = clean_text[:8000] + "\n\n... (내용이 길어서 일부만 표시됩니다)"
        
#         return clean_text
        
#     except requests.RequestException as e:
#         logger.error(f"웹페이지 요청 오류: {str(e)}")
#         return f"❌ '{url}' 웹페이지에 접근할 수 없습니다. 네트워크 오류: {str(e)}"
#     except Exception as e:
#         logger.error(f"웹페이지 내용 추출 오류: {str(e)}")
#         return f"❌ '{url}' 내용을 가져올 수 없습니다. 오류: {str(e)}"

# def summarize_webpage_with_gemini(url, user_query, chat_session, detected_lang):
#     """웹페이지 내용을 Gemini로 요약"""
#     try:
#         # 웹페이지 내용 추출
#         with st.spinner("🌐 웹페이지 내용을 가져오는 중..."):
#             content = fetch_webpage_content(url)
        
#         # 오류 메시지인 경우 그대로 반환
#         if content.startswith("❌"):
#             return content
        
#         # 언어별 시스템 프롬프트 추가
#         system_prompt = get_system_prompt(detected_lang)
        
#         # 언어별 요약 프롬프트
#         if detected_lang == "ko":
#             prompt = f"""{system_prompt}

# 다음 웹페이지의 내용을 한국어로 요약해주세요.

# 웹페이지 URL: {url}
# 사용자 질문: {user_query}

# 웹페이지 내용:
# {content}

# 요약 지침:
# 1. 주요 핵심 내용을 3-5개 포인트로 정리
# 2. 중요한 정보나 수치가 있다면 포함
# 3. 사용자가 특정 질문을 했다면 그에 맞춰 요약
# 4. 이모지를 적절히 사용하여 가독성 향상
# 5. 출처 URL도 함께 제공
# 6. 반드시 한국어로만 답변하세요

# 형식:
# 📄 **웹페이지 요약**

# 🔗 **출처**: {url}

# 📝 **주요 내용**:
# - 핵심 포인트 1
# - 핵심 포인트 2
# - 핵심 포인트 3

# 💡 **결론**: 간단한 결론이나 핵심 메시지
# """
#         else:
#             prompt = f"""{system_prompt}

# Please summarize the following webpage content in English.

# Webpage URL: {url}
# User Query: {user_query}

# Webpage Content:
# {content}

# Summary Guidelines:
# 1. Organize main points into 3-5 key bullets
# 2. Include important information or numbers if present
# 3. Focus on user's specific question if provided
# 4. Use appropriate emojis for readability
# 5. Include source URL
# 6. Respond only in English

# Format:
# 📄 **Webpage Summary**

# 🔗 **Source**: {url}

# 📝 **Key Points**:
# - Main point 1
# - Main point 2
# - Main point 3

# 💡 **Conclusion**: Brief conclusion or key message
# """
        
#         # Gemini로 요약 생성
#         with st.spinner("🤖 Gemini가 내용을 요약하는 중..."):
#             response = chat_session.send_message(prompt)
#             return response.text
        
#     except Exception as e:
#         logger.error(f"웹페이지 요약 중 오류: {str(e)}")
#         return f"❌ 웹페이지 요약 중 오류가 발생했습니다: {str(e)}"

# # --- PDF 처리 함수들 ---
# def fetch_pdf_text(url, max_chars=8000):
#     """PDF 파일에서 텍스트 추출 (arXiv 등 논문 PDF 지원)"""
#     try:
#         response = requests.get(url, timeout=20)
#         response.raise_for_status()
#         pdf_file = io.BytesIO(response.content)
#         reader = PdfReader(pdf_file)
#         text = ""
#         for page in reader.pages:
#             text += page.extract_text() or ""
#             if len(text) > max_chars:
#                 text = text[:max_chars] + "\n\n... (내용이 길어서 일부만 표시됩니다)"
#                 break
#         return text.strip()
#     except Exception as e:
#         return f"❌ PDF 파일을 처리할 수 없습니다: {e}"

# def is_pdf_url(url):
#     return url.lower().endswith('.pdf') or '/pdf/' in url

# def is_pdf_summarization_request(query):
#     urls = extract_urls_from_text(query)
#     if urls:
#         for url in urls:
#             if is_pdf_url(url):
#                 summary_keywords = ['요약', '정리', '내용', '설명', '알려줘', '분석', '해석', '리뷰', '정보']
#                 for keyword in summary_keywords:
#                     if keyword in query:
#                         return True, url
#     return False, None

# def summarize_pdf_with_gemini(url, user_query, chat_session, detected_lang):
#     try:
#         with st.spinner("📄 논문 PDF를 읽는 중..."):
#             content = fetch_pdf_text(url)
#         if content.startswith("❌"):
#             return content
#         system_prompt = get_system_prompt(detected_lang)
#         if detected_lang == "ko":
#             prompt = f"""{system_prompt}

# 다음 논문 PDF의 내용을 한국어로 요약해주세요.

# 논문 URL: {url}
# 사용자 질문: {user_query}

# 논문 내용:
# {content}

# 요약 지침:
# 1. 주요 핵심 내용을 3-5개 포인트로 정리
# 2. 중요한 정보나 수치가 있다면 포함
# 3. 사용자가 특정 질문을 했다면 그에 맞춰 요약
# 4. 이모지를 적절히 사용하여 가독성 향상
# 5. 출처 URL도 함께 제공
# 6. 반드시 한국어로만 답변하세요

# 형식:
# 📄 **논문 요약**

# 🔗 **출처**: {url}

# 📝 **주요 내용**:
# - 핵심 포인트 1
# - 핵심 포인트 2
# - 핵심 포인트 3

# 💡 **결론**: 간단한 결론이나 핵심 메시지
# """
#         else:
#             prompt = f"""{system_prompt}

# Please summarize the following PDF document in English.

# PDF URL: {url}
# User Query: {user_query}

# PDF Content:
# {content}

# Summary Guidelines:
# 1. Organize main points into 3-5 key bullets
# 2. Include important information or numbers if present
# 3. Focus on user's specific question if provided
# 4. Use appropriate emojis for readability
# 5. Include source URL
# 6. Respond only in English

# Format:
# 📄 **PDF Summary**

# 🔗 **Source**: {url}

# 📝 **Key Points**:
# - Main point 1
# - Main point 2
# - Main point 3

# 💡 **Conclusion**: Brief conclusion or key message
# """
#         with st.spinner("🤖 Gemini가 논문을 요약하는 중..."):
#             response = chat_session.send_message(prompt)
#             return response.text
#     except Exception as e:
#         return f"❌ 논문 요약 중 오류가 발생했습니다: {e}"

# # --- 사용량 추적 함수 ---
# def get_usage_count():
#     """일일 사용량 추적"""
#     today = datetime.now().strftime("%Y-%m-%d")
    
#     # 세션 상태 초기화 (한 번만)
#     if "usage_data" not in st.session_state:
#         st.session_state.usage_data = {"date": today, "count": 0}
    
#     # 날짜가 바뀌면 카운트 초기화
#     if st.session_state.usage_data["date"] != today:
#         st.session_state.usage_data = {"date": today, "count": 0}
    
#     return st.session_state.usage_data["count"]

# def increment_usage():
#     """사용량 증가"""
#     if "usage_data" in st.session_state:
#         st.session_state.usage_data["count"] += 1
#     else:
#         # 만약 usage_data가 없으면 초기화
#         today = datetime.now().strftime("%Y-%m-%d")
#         st.session_state.usage_data = {"date": today, "count": 1}

# def detect_language(text):
#     """텍스트에서 URL을 제외하고 언어 감지"""
#     import re
#     # URL 패턴 제거
#     url_pattern = r'https?://[^\s]+'
#     urls = re.findall(url_pattern, text)
#     for url in urls:
#         text = text.replace(url, '')
#     text = text.strip()
#     if not text:
#         return "ko"  # 기본값
#     korean_chars = sum(1 for char in text if '\uac00' <= char <= '\ud7af')
#     total_chars = len(text.replace(' ', ''))
#     korean_ratio = korean_chars / total_chars if total_chars > 0 else 0
#     return "ko" if korean_ratio > 0.3 else "en"

# def get_system_prompt(language):
#     """언어별 시스템 프롬프트"""
#     if language == "ko":
#         return """당신은 친근하고 도움이 되는 AI 어시스턴트입니다. 
#         다음 규칙을 따라주세요:
#         - 한국어로만 답변하세요
#         - 친근하고 자연스러운 톤을 사용하세요
#         - 이모지를 적절히 활용하세요
#         - 웹페이지 및 유튜브 요약 기능을 제공할 수 있습니다
#         - 답변은 간결하면서도 유용하게 작성하세요"""
#     else:
#         return """You are a friendly and helpful AI assistant.
#         Please follow these rules:
#         - Respond only in English
#         - Use a friendly and natural tone
#         - Use appropriate emojis
#         - You can provide webpage and YouTube summarization features
#         - Keep responses concise yet useful"""

# # --- 사이드바 ---
# with st.sidebar:
#     st.markdown("## ⚙️ 설정")
    
#     # API 키 입력
#     api_key = st.text_input("🔑 Gemini API 키", type="password", help="Google AI Studio에서 발급받은 API 키를 입력하세요")
    
#     if api_key:
#         try:
#             genai.configure(api_key=api_key)
#             st.success("✅ API 키 연결 완료!")
#         except Exception as e:
#             st.error(f"❌ API 키 오류: {e}")
    
#     st.markdown("---")
    
#     # 사용량 표시 (실시간 업데이트)
#     usage_count = get_usage_count()
#     free_limit = 100  # 무료 티어 일일 한도
    
#     st.markdown("### 📊 오늘의 사용량")
#     progress = min(usage_count / free_limit, 1.0)
#     st.progress(progress)
#     st.markdown(f"**{usage_count}/{free_limit}** 회 사용")
    
#     if usage_count >= free_limit:
#         st.error("⚠️ 일일 무료 한도를 초과했습니다!")
#     elif usage_count >= free_limit * 0.8:
#         st.warning("⚠️ 일일 한도에 가까워지고 있습니다!")
    
#     st.markdown("---")
    
#     # 사용 가이드
#     st.markdown("### 💡 사용 가이드")
#     st.markdown("""
#     1. 🔗 [Google AI Studio](https://aistudio.google.com/app/apikey)에서 API 키 발급
#     2. 🔑 위의 입력창에 API 키 입력
#     3. 💬 아래 채팅창에서 대화 시작
#     4. 🌐 웹페이지 URL 요약 기능 지원
#     5. 📺 유튜브 비디오 요약 기능 지원
#     """)
    
#     st.markdown("---")
    
#     # 웹페이지 요약 가이드
#     st.markdown("### 🌐 웹페이지 요약 기능")
#     st.markdown("""
#     **사용법:**
#     - URL과 함께 '요약', '정리', '내용' 등의 키워드 입력
#     - 예: "https://example.com 이 페이지 요약해줘"
#     - 한국어/영어 자동 감지하여 해당 언어로 요약
#     """)
    
#     st.markdown("---")
    
#     # 유튜브 요약 가이드 추가
#     st.markdown("### 📺 유튜브 요약 기능")
#     st.markdown("""
#     **사용법:**
#     - 유튜브 URL과 함께 '요약', '정리', '내용' 등의 키워드 입력
#     - 예: "https://youtube.com/watch?v=... 이 영상 요약해줘"
#     - 자막이 있는 비디오만 요약 가능
#     - 토큰 절약을 위해 자막 길이 제한 (약 15,000자)
#     """)
    
#     st.markdown("---")
    
#     # 새 대화 시작 버튼
#     if st.button("🔄 새 대화 시작", use_container_width=True):
#         st.session_state.messages = []
#         if "chat_session" in st.session_state:
#             del st.session_state.chat_session
#         st.rerun()

# # --- 메인 화면 ---
# st.markdown("# 🚀 Chat with Gemini")

# # --- 채팅 기록 초기화 ---
# if "messages" not in st.session_state:
#     st.session_state.messages = []

# # --- 모델 및 채팅 세션 초기화 ---
# if "chat_session" not in st.session_state:
#     if api_key:
#         try:
#             model = genai.GenerativeModel('gemini-2.5-flash')
#             st.session_state.chat_session = model.start_chat(history=[])
#         except Exception as e:
#             st.error(f"❌ 모델 초기화 오류: {e}")
#             st.stop()
#     else:
#         st.info("👈 사이드바에서 API 키를 먼저 입력해주세요!")
#         st.stop()

# # --- 채팅 기록 표시 ---
# if not st.session_state.messages:
#     st.markdown("💡 **팁**: 한국어 또는 영어로 질문하시면 해당 언어로 답변해드립니다.")
#     st.markdown("🌐 **웹페이지 요약**: URL과 함께 '요약', '정리' 등의 키워드를 사용하면 해당 페이지를 요약해드립니다.")
#     st.markdown("📺 **유튜브 요약**: 유튜브 URL과 함께 '요약', '정리' 등의 키워드를 사용하면 해당 영상을 요약해드립니다.")

# for message in st.session_state.messages:
#     with st.chat_message(message["role"], avatar="🧑‍💻" if message["role"] == "user" else "🤖"):
#         st.markdown(message["content"])

# # --- 사용자 입력 처리 ---
# if prompt := st.chat_input("💬 메시지를 입력하세요. (예시: 웹페이지/유튜브 요약: URL + '요약해줘')"):
#     # 사용량 체크 (API 요청 전에 미리 체크)
#     current_usage = get_usage_count()
#     if current_usage >= free_limit:
#         st.error("⚠️ 일일 무료 사용량을 초과했습니다. 내일 다시 시도해주세요!")
#         st.stop()
    
#     # 언어 감지
#     detected_lang = detect_language(prompt)
    
#     # 사용자 메시지 기록 및 표시
#     st.session_state.messages.append({"role": "user", "content": prompt})
#     with st.chat_message("user", avatar="🧑‍💻"):
#         st.markdown(prompt)

#     # 요약 요청 유형 확인
#     is_youtube_request, youtube_url = is_youtube_summarization_request(prompt)
#     is_webpage_request, webpage_url = is_url_summarization_request(prompt)
#     is_pdf_request, pdf_url = is_pdf_summarization_request(prompt)
    
#     try:
#         if is_youtube_request:
#             # 유튜브 요약 처리
#             response_text = summarize_youtube_with_gemini(youtube_url, prompt, st.session_state.chat_session, detected_lang)
#             increment_usage()
            
#         elif is_webpage_request:
#             # 웹페이지 요약 처리
#             response_text = summarize_webpage_with_gemini(webpage_url, prompt, st.session_state.chat_session, detected_lang)
#             increment_usage()
            
#         elif is_pdf_request:
#             # PDF 요약 처리
#             response_text = summarize_pdf_with_gemini(pdf_url, prompt, st.session_state.chat_session, detected_lang)
#             increment_usage()
            
#         else:
#             # 일반 채팅 처리
#             with st.spinner("🤖 Gemini가 답변을 생성하는 중..."):
#                 # 시스템 프롬프트와 함께 메시지 전송
#                 system_prompt = get_system_prompt(detected_lang)
#                 full_prompt = f"{system_prompt}\n\nUser: {prompt}"
                
#                 response = st.session_state.chat_session.send_message(full_prompt)
#                 response_text = response.text
                
#                 # API 요청 성공 시에만 사용량 증가
#                 increment_usage()
        
#         # 응답 표시
#         with st.chat_message("assistant", avatar="🤖"):
#             st.markdown(response_text)
        
#         # 모델 응답 기록
#         st.session_state.messages.append({"role": "assistant", "content": response_text})
        
#         # 사용량 업데이트를 위해 페이지 새로고침
#         st.rerun()

#     except Exception as e:
#         st.error(f"❌ 메시지 전송 중 오류가 발생했습니다: {e}")
#         if "quota" in str(e).lower():
#             st.error("💡 **팁**: API 할당량을 초과했을 수 있습니다. 잠시 후 다시 시도해주세요.")
#         # API 요청 실패 시에는 사용량을 증가시키지 않음

# # --- 푸터 ---
# st.markdown("---")
# st.markdown(
#     """
#     <div style='text-align: center; color: #666; padding: 1rem;'>
#         <small>
#             🚀 Powered by Google Gemini AI + BeautifulSoup + YouTube Transcript API
#         </small>
#     </div>
#     """, 
#     unsafe_allow_html=True
# )


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

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 페이지 설정 ---
st.set_page_config(
    page_title="Chat with Gemini",
    page_icon="🚀",
    layout="wide"
)

# --- 유튜브 처리 함수들 ---
def extract_video_id(url):
    """유튜브 URL에서 비디오 ID 추출"""
    try:
        if 'youtu.be/' in url:
            return url.split('youtu.be/')[1].split('?')[0]
        elif 'youtube.com/watch' in url:
            parsed_url = urlparse(url)
            return parse_qs(parsed_url.query)['v'][0]
        elif 'youtube.com/embed/' in url:
            return url.split('embed/')[1].split('?')[0]
        else:
            return None
    except:
        return None

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

def is_youtube_url(url):
    """유튜브 URL인지 확인"""
    youtube_domains = ['youtube.com', 'youtu.be', 'www.youtube.com']
    try:
        parsed_url = urlparse(url)
        return any(domain in parsed_url.netloc for domain in youtube_domains)
    except:
        return False

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

def summarize_youtube_with_gemini(url, user_query, chat_session, detected_lang):
    """유튜브 비디오를 Gemini로 요약"""
    try:
        video_id = extract_video_id(url)
        if not video_id:
            return "❌ 유효하지 않은 유튜브 URL입니다."
        
        with st.spinner("📺 유튜브 자막을 가져오는 중..."):
            transcript = get_youtube_transcript(video_id)
        
        if not transcript:
            return "❌ 이 유튜브 비디오의 자막을 가져올 수 없습니다. 자막이 없거나 비공개 비디오일 수 있습니다."
        
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
- 핵심 포인트 3
- 핵심 포인트 4
- 핵심 포인트 5

💡 **결론**: 비디오의 핵심 메시지나 결론

⏱️ **예상 시청 시간**: 대략적인 비디오 길이 정보 (가능한 경우)
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
- Main point 3
- Main point 4
- Main point 5

💡 **Conclusion**: Key message or conclusion from the video

⏱️ **Estimated Watch Time**: Approximate video length (if available)
"""
        with st.spinner("🤖 Gemini가 유튜브 내용을 요약하는 중..."):
            response = chat_session.send_message(prompt)
            return response.text
    except Exception as e:
        logger.error(f"유튜브 요약 중 오류: {str(e)}")
        return f"❌ 유튜브 요약 중 오류가 발생했습니다: {str(e)}"

# --- 웹페이지 처리 함수들 ---
def is_url_summarization_request(query):
    """URL 요약 요청인지 확인 (유튜브 제외)"""
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
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'advertisement']):
            tag.decompose()
        main_content = (
            soup.find('main') or
            soup.find('article') or
            soup.find('div', class_=re.compile(r'content|main|post|article', re.I)) or
            soup.find('div', id=re.compile(r'content|main|post|article', re.I))
        )
        if main_content:
            text = main_content.get_text(strip=True, separator='\n')
        else:
            body = soup.find('body')
            text = body.get_text(strip=True, separator='\n') if body else soup.get_text(strip=True, separator='\n')
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        clean_text = '\n'.join(lines)
        if len(clean_text) > 8000:
            clean_text = clean_text[:8000] + "\n\n... (내용이 길어서 일부만 표시됩니다)"
        return clean_text
    except requests.RequestException as e:
        logger.error(f"웹페이지 요청 오류: {str(e)}")
        return f"❌ '{url}' 웹페이지에 접근할 수 없습니다. 네트워크 오류: {str(e)}"
    except Exception as e:
        logger.error(f"웹페이지 내용 추출 오류: {str(e)}")
        return f"❌ '{url}' 내용을 가져올 수 없습니다. 오류: {str(e)}"

def summarize_webpage_with_gemini(url, user_query, chat_session, detected_lang):
    """웹페이지 내용을 Gemini로 요약"""
    try:
        with st.spinner("🌐 웹페이지 내용을 가져오는 중..."):
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
- 핵심 포인트 3

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
- Main point 3

💡 **Conclusion**: Brief conclusion or key message
"""
        with st.spinner("🤖 Gemini가 내용을 요약하는 중..."):
            response = chat_session.send_message(prompt)
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
    """PDF 파일에서 텍스트 추출 (arXiv 등 논문 PDF 지원)"""
    try:
        with st.spinner("📥 PDF 파일 다운로드 중..."):
            response = requests.get(url, timeout=20)
            response.raise_for_status()
        with st.spinner("📄 PDF 텍스트 추출 중..."):
            pdf_file = io.BytesIO(response.content)
            reader = PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
                if len(text) > max_chars:
                    text = text[:max_chars] + "\n\n... (내용이 길어서 일부만 표시됩니다)"
                    break
            return text.strip(), reader.metadata
    except Exception as e:
        return f"❌ PDF 파일을 처리할 수 없습니다: {e}", None

def summarize_pdf_with_gemini(url, user_query, chat_session, detected_lang):
    """PDF 내용을 Gemini로 요약"""
    try:
        content, metadata = fetch_pdf_text(url)
        if content.startswith("❌"):
            return content
        metadata_info = {
            "title": metadata.get("/Title", "알 수 없음") if metadata else "알 수 없음",
            "author": metadata.get("/Author", "알 수 없음") if metadata else "알 수 없음",
            "subject": metadata.get("/Subject", "알 수 없음") if metadata else "알 수 없음"
        }
        system_prompt = get_system_prompt(detected_lang)
        if detected_lang == "ko":
            prompt = f"""{system_prompt}

다음 논문 PDF의 내용을 한국어로 요약해주세요.

논문 URL: {url}
논문 제목: {metadata_info["title"]}
사용자 질문: {user_query}

논문 내용:
{content}

요약 지침:
1. 초록(Abstract), 연구 방법, 주요 결과, 결론을 중심으로 3-5개 포인트로 정리
2. 중요한 수치, 데이터, 또는 연구 기여도를 포함
3. 사용자가 특정 질문을 했다면 그에 맞춰 요약
4. 이모지를 적절히 사용하여 가독성 향상
5. 출처 URL과 논문 제목 포함
6. 반드시 한국어로만 답변하세요

형식:
📄 **논문 요약**

🔗 **출처**: {url}
📖 **제목**: {metadata_info["title"]}
📜 **저자**: {metadata_info["author"]}

📝 **주요 내용**:
- 초록 요약
- 연구 방법
- 주요 결과
- 결론

💡 **핵심 기여도**: 연구의 주요 기여나 의의
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
1. Organize main points into 3-5 key bullets focusing on abstract, methodology, results, and conclusion
2. Include important data, numbers, or research contributions
3. Focus on user's specific question if provided
4. Use appropriate emojis for readability
5. Include source URL and document title
6. Respond only in English

Format:
📄 **PDF Summary**

🔗 **Source**: {url}
📖 **Title**: {metadata_info["title"]}
📜 **Author**: {metadata_info["author"]}

📝 **Key Points**:
- Abstract summary
- Methodology
- Main results
- Conclusion

💡 **Key Contribution**: Main contribution or significance of the research
"""
        with st.spinner("🤖 Gemini가 논문을 요약하는 중..."):
            response = chat_session.send_message(prompt)
            return response.text
    except Exception as e:
        logger.error(f"논문 요약 중 오류: {str(e)}")
        return f"❌ 논문 요약 중 오류가 발생했습니다: {str(e)}"

# --- 사용량 추적 함수 ---
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
        - 웹페이지, 유튜브, 논문 PDF 요약 기능을 제공할 수 있습니다
        - 답변은 간결하면서도 유용하게 작성하세요"""
    else:
        return """You are a friendly and helpful AI assistant.
        Please follow these rules:
        - Respond only in English
        - Use a friendly and natural tone
        - Use appropriate emojis
        - You can provide webpage, YouTube, and PDF summarization features
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
    1. 🔗 [Google AI Studio](https://aistudio.google.com/app/apikey)에서 API 키 발급
    2. 🔑 위의 입력창에 API 키 입력
    3. 💬 아래 채팅창에서 대화 시작
    4. 🌐 웹페이지 URL 요약 기능 지원
    5. 📺 유튜브 비디오 요약 기능 지원
    6. 📄 논문 PDF 요약 기능 지원
    """)
    
    st.markdown("---")
    st.markdown("### 🌐 웹페이지 요약 기능")
    st.markdown("""
    **사용법:**
    - URL과 함께 '요약', '정리', '내용' 등의 키워드 입력
    - 예: "https://example.com 이 페이지 요약해줘"
    - 한국어/영어 자동 감지하여 해당 언어로 요약
    """)
    
    st.markdown("---")
    st.markdown("### 📺 유튜브 요약 기능")
    st.markdown("""
    **사용법:**
    - 유튜브 URL과 함께 '요약', '정리', '내용' 등의 키워드 입력
    - 예: "https://youtube.com/watch?v=... 이 영상 요약해줘"
    - 자막이 있는 비디오만 요약 가능
    - 토큰 절약을 위해 자막 길이 제한 (약 15,000자)
    """)
    
    st.markdown("---")
    st.markdown("### 📄 논문 요약 기능")
    st.markdown("""
    **사용법:**
    - PDF URL과 함께 '요약', '정리', '내용' 등의 키워드 입력
    - 예: "https://arxiv.org/pdf/2307.12345.pdf 이 논문 요약해줘"
    - 논문 제목과 저자 정보 포함 (가능한 경우)
    - 한국어/영어 자동 감지하여 해당 언어로 요약
    """)
    
    st.markdown("---")
    if st.button("🔄 새 대화 시작", use_container_width=True):
        st.session_state.messages = []
        if "chat_session" in st.session_state:
            del st.session_state.chat_session
        st.rerun()

# --- 메인 화면 ---
st.markdown("# 🚀 Chat with Gemini")

# --- 채팅 기록 초기화 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 모델 및 채팅 세션 초기화 ---
if "chat_session" not in st.session_state:
    if api_key:
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            st.session_state.chat_session = model.start_chat(history=[])
        except Exception as e:
            st.error(f"❌ 모델 초기화 오류: {e}")
            st.stop()
    else:
        st.info("👈 사이드바에서 API 키를 먼저 입력해주세요!")
        st.stop()

# --- 채팅 기록 표시 ---
if not st.session_state.messages:
    st.markdown("💡 **팁**: 한국어 또는 영어로 질문하시면 해당 언어로 답변해드립니다.")
    st.markdown("🌐 **웹페이지 요약**: URL과 함께 '요약', '정리' 등의 키워드를 사용하면 해당 페이지를 요약해드립니다.")
    st.markdown("📺 **유튜브 요약**: 유튜브 URL과 함께 '요약', '정리' 등의 키워드를 사용하면 해당 영상을 요약해드립니다.")
    st.markdown("📄 **논문 요약**: PDF URL과 함께 '요약', '정리' 등의 키워드를 사용하면 해당 논문을 요약해드립니다.")

for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="🧑‍💻" if message["role"] == "user" else "🤖"):
        st.markdown(message["content"])

# --- 사용자 입력 처리 ---
if prompt := st.chat_input("💬 메시지를 입력하세요. (예시: 웹페이지/유튜브/논문 요약: URL + '요약해줘')"):
    current_usage = get_usage_count()
    if current_usage >= free_limit:
        st.error("⚠️ 일일 무료 사용량을 초과했습니다. 내일 다시 시도해주세요!")
        st.stop()
    
    detected_lang = detect_language(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)

    is_youtube_request, youtube_url = is_youtube_summarization_request(prompt)
    is_webpage_request, webpage_url = is_url_summarization_request(prompt)
    is_pdf_request, pdf_url = is_pdf_summarization_request(prompt)
    
    try:
        if is_youtube_request:
            response_text = summarize_youtube_with_gemini(youtube_url, prompt, st.session_state.chat_session, detected_lang)
            increment_usage()
        elif is_webpage_request:
            response_text = summarize_webpage_with_gemini(webpage_url, prompt, st.session_state.chat_session, detected_lang)
            increment_usage()
        elif is_pdf_request:
            response_text = summarize_pdf_with_gemini(pdf_url, prompt, st.session_state.chat_session, detected_lang)
            increment_usage()
        else:
            with st.spinner("🤖 Gemini가 답변을 생성하는 중..."):
                system_prompt = get_system_prompt(detected_lang)
                full_prompt = f"{system_prompt}\n\nUser: {prompt}"
                response = st.session_state.chat_session.send_message(full_prompt)
                response_text = response.text
                increment_usage()
        
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(response_text)
        st.session_state.messages.append({"role": "assistant", "content": response_text})
        st.rerun()
    except Exception as e:
        st.error(f"❌ 메시지 전송 중 오류가 발생했습니다: {e}")
        if "quota" in str(e).lower():
            st.error("💡 **팁**: API 할당량을 초과했을 수 있습니다. 잠시 후 다시 시도해주세요.")

# --- 푸터 ---
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; padding: 1rem;'>
        <small>
            🚀 Powered by Google Gemini AI + BeautifulSoup + YouTube Transcript API + PyPDF
        </small>
    </div>
    """, 
    unsafe_allow_html=True
)