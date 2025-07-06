import requests
import xml.etree.ElementTree as ET
import random
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class CultureEventAPI:
    def __init__(self, api_key, cache_handler, cache_ttl=3600):
        self.api_key = api_key
        self.cache = cache_handler
        self.cache_ttl = cache_ttl
        self.base_url = "http://openapi.seoul.go.kr:8088"
    
    def fetch_xml(self):
        """API 키를 사용하여 XML 데이터를 가져옵니다."""
        cache_key = f"culture_xml:{self.api_key}"
        cached = self.cache.get(cache_key)
        if cached:
            try:
                return ET.fromstring(cached)
            except ET.ParseError:
                pass
        
        url = f"{self.base_url}/{self.api_key}/xml/culturalEventInfo/1/100/"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            xml_content = response.content.decode('utf-8')
            
            # XML 캐싱 (30분)
            self.cache.setex(cache_key, 1800, xml_content)
            
            root = ET.fromstring(xml_content)
            return root
        except requests.exceptions.RequestException as e:
            logger.error(f"문화행사 API 호출 실패: {e}")
            return None
        except ET.ParseError as e:
            logger.error(f"XML 파싱 실패: {e}")
            return None
    
    def select_target_district(self, root, target_district=""):
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
    
    def extract_event_date(self, date_str):
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
    
    def get_future_events(self, target_district="", max_events=10):
        """API 키와 target_district(빈 문자열이면 랜덤 선택)를 받아 미래 행사를 반환합니다."""
        cache_key = f"culture_events:{target_district}:{max_events}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        root = self.fetch_xml()
        if not root:
            return "문화행사 정보를 가져올 수 없습니다. 😓"
        
        today = datetime.today().date()
        selected_district = self.select_target_district(root, target_district)
        
        if not selected_district:
            return "구 정보가 없습니다."
        
        events = []
        for row in root.findall('.//row'):
            district = row.findtext('GUNAME', default='정보 없음')
            date_str = row.findtext('DATE', default='정보 없음')
            event_date = self.extract_event_date(date_str)
            
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
        
        result = events[:max_events]  # 최대 지정된 개수만 반환
        
        # 결과 캐싱 (1시간)
        self.cache.setex(cache_key, self.cache_ttl, result)
        
        return result
    
    def format_events_response(self, events):
        """이벤트 목록을 포맷팅된 문자열로 변환합니다."""
        if isinstance(events, str):  # 에러 메시지인 경우
            return events
        
        if not events:  # 결과가 없을 경우
            return "해당 조건에 맞는 문화 행사가 없습니다."
        
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
        return result
    
    def search_cultural_events(self, query):
        """문화행사 검색 메인 함수"""
        # "문화행사" 키워드 제거하여 지역구 추출
        target_district = query.replace("문화행사", "").strip()
        
        # 이벤트 가져오기
        events = self.get_future_events(target_district)
        
        # 응답 포맷팅
        return self.format_events_response(events)