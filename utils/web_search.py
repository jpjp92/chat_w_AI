import urllib.request
import urllib.parse
import json
import re
import logging
from datetime import datetime
import uuid
import streamlit as st

logger = logging.getLogger(__name__)

class WebSearchAPI:
    def __init__(self, client_id, client_secret, cache_handler, cache_ttl=3600, daily_limit=25000):
        self.client_id = client_id
        self.client_secret = client_secret
        self.cache = cache_handler
        self.cache_ttl = cache_ttl
        self.daily_limit = daily_limit
        self.request_count = 0
        self.base_url = "https://openapi.naver.com/v1/search/webkr"
    
    def get_request_count(self):
        """현재 요청 횟수를 반환합니다."""
        return self.request_count
    
    def increment_request_count(self):
        """요청 횟수를 증가시킵니다."""
        self.request_count += 1
    
    def is_over_limit(self):
        """일일 한도 초과 여부를 확인합니다."""
        return self.request_count >= self.daily_limit
    
    def search_web(self, query, display=5, sort="date"):
        """Naver API를 사용하여 웹 검색을 수행합니다."""
        cache_key = f"naver:{query}:{display}:{sort}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        if self.is_over_limit():
            return "검색 한도 초과로 결과를 가져올 수 없습니다. 😓"
        
        try:
            enc_text = urllib.parse.quote(query)
            url = f"{self.base_url}?query={enc_text}&display={display}&sort={sort}"
            
            request = urllib.request.Request(url)
            request.add_header("X-Naver-Client-Id", self.client_id)
            request.add_header("X-Naver-Client-Secret", self.client_secret)
            
            response = urllib.request.urlopen(request, timeout=3)
            self.increment_request_count()
            
            if response.getcode() == 200:
                data = json.loads(response.read().decode('utf-8'))
                results = data.get('items', [])
                
                if not results:
                    return "검색 결과가 없습니다. 😓"
                
                formatted_result = self.format_search_results(results)
                self.cache.setex(cache_key, self.cache_ttl, formatted_result)
                return formatted_result
            else:
                return f"검색 API 오류 (코드: {response.getcode()}) 😓"
                
        except Exception as e:
            logger.error(f"Naver API 오류: {str(e)}")
            return "검색 중 오류가 발생했습니다. 😓"
    
    def format_search_results(self, results):
        """검색 결과를 포맷팅합니다."""
        response_text = "🌐 **웹 검색 결과** \n\n"
        
        formatted_results = []
        for i, item in enumerate(results, 1):
            # HTML 태그 제거
            clean_title = re.sub(r'<b>|</b>', '', item.get('title', '제목 없음'))
            clean_description = re.sub(r'<b>|</b>', '', item.get('description', '내용 없음'))
            
            # 설명 길이 제한
            description_preview = clean_description[:100] + "..." if len(clean_description) > 100 else clean_description
            
            formatted_result = (
                f"**결과 {i}**\n\n"
                f"📄 **제목**: {clean_title}\n\n"
                f"📝 **내용**: {description_preview}\n\n"
                f"🔗 **링크**: {item.get('link', '')}"
            )
            formatted_results.append(formatted_result)
        
        response_text += "\n\n".join(formatted_results)
        response_text += "\n\n더 궁금한 점 있나요? 😊"
        
        return response_text
    
    def search_and_create_context(self, query, session_state=None):
        """검색을 수행하고 컨텍스트를 생성합니다."""
        # 쿼리에서 '검색' 키워드 제거
        clean_query = query.lower().replace("검색", "").strip()
        
        # 검색 수행
        search_result = self.search_web(clean_query)
        
        # 세션 상태가 있는 경우 컨텍스트 저장
        if session_state and hasattr(session_state, 'search_contexts'):
            context_id = str(uuid.uuid4())
            session_state.search_contexts[context_id] = {
                "type": "naver_search",
                "query": clean_query,
                "result": search_result,
                "timestamp": datetime.now().isoformat()
            }
            session_state.current_context = context_id
            
            # 로그 추가
            logger.info(f"검색 컨텍스트 저장 완료: {context_id}")
            logger.info(f"저장된 컨텍스트 수: {len(session_state.search_contexts)}")
        else:
            logger.warning("세션 상태가 없거나 search_contexts가 없습니다.")
        
        # 멀티턴 대화를 위한 안내 추가
        enhanced_result = search_result + "\n\n💡 검색 결과에 대해 더 질문하시면 답변해드릴게요. 예를 들어:\n"
        enhanced_result += "- '검색 결과를 요약해'\n"
        enhanced_result += "- '첫 번째 결과에 대해 자세히 설명해줘'\n"
        enhanced_result += "- '3번째 링크 요약해줘' (해당 순서 웹페이지 전체 내용 요약)\n"
        enhanced_result += "- 'URL 요약해줘' (특정 링크의 전체 내용 확인)"
        
        return enhanced_result
    
    def get_search_stats(self):
        """검색 통계를 반환합니다."""
        return {
            "request_count": self.request_count,
            "daily_limit": self.daily_limit,
            "remaining": self.daily_limit - self.request_count,
            "usage_percentage": round((self.request_count / self.daily_limit) * 100, 2)
        }
    
    def reset_daily_count(self):
        """일일 카운트를 초기화합니다."""
        self.request_count = 0
        logger.info("Naver API 일일 요청 카운트가 초기화되었습니다.")