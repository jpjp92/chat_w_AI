import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class DrugStoreAPI:
    def __init__(self, api_key, cache_handler=None):
        self.api_key = api_key
        self.cache_handler = cache_handler
        self.base_url = f"http://openapi.seoul.go.kr:8088/{api_key}/xml/TbPharmacyOperateInfo"
    
    def search_pharmacies(self, query, limit=10):
        """약국 검색 및 정보 조회"""
        try:
            # 캐시 확인
            cache_key = f"pharmacy:{query}:{limit}"
            if self.cache_handler:
                cached = self.cache_handler.get(cache_key)
                if cached:
                    return cached
            
            # 지역구 또는 약국명 추출
            district = self._extract_district(query)
            pharmacy_name = self._extract_pharmacy_name(query)
            
            # API 호출
            result = self._fetch_pharmacy_data(district, pharmacy_name, limit)
            
            if result["status"] == "error":
                return result["message"]
            
            # 결과 포맷팅
            formatted_result = self._format_pharmacy_results(result)
            
            # 캐시 저장 (30분)
            if self.cache_handler:
                self.cache_handler.setex(cache_key, 1800, formatted_result)
            
            return formatted_result
            
        except Exception as e:
            logger.error(f"약국 검색 중 오류: {str(e)}")
            return f"약국 정보를 가져오는 중 오류가 발생했습니다: {str(e)} 😓"
    
    def _extract_district(self, query):
        """쿼리에서 지역구 추출"""
        districts = [
            "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구",
            "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구",
            "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"
        ]
        
        for district in districts:
            if district in query:
                return district
        return None
    
    def _extract_pharmacy_name(self, query):
        """쿼리에서 약국명 추출"""
        # "약국", "약국명", "약국검색" 등의 키워드 제거
        keywords_to_remove = ["약국", "약국명", "약국검색", "약국정보", "서울시", "검색"]
        
        cleaned_query = query
        for keyword in keywords_to_remove:
            cleaned_query = cleaned_query.replace(keyword, "")
        
        cleaned_query = cleaned_query.strip()
        
        # 지역구 제거
        district = self._extract_district(query)
        if district:
            cleaned_query = cleaned_query.replace(district, "")
        
        cleaned_query = cleaned_query.strip()
        
        # 너무 짧거나 의미없는 경우 None 반환
        if len(cleaned_query) < 2:
            return None
        
        return cleaned_query
    
    def _fetch_pharmacy_data(self, district=None, name=None, limit=10):
        """서울시 약국 API 호출"""
        try:
            url = f"{self.base_url}/1/{limit}/"
            
            # 선택적 파라미터
            params = {}
            if district:
                params['DUTYADDR'] = district
            if name:
                params['DUTYNAME'] = name
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            
            # API 응답 코드 확인
            result_code = root.find(".//CODE")
            if result_code is None:
                return {"status": "error", "message": "API 응답 형식 오류"}
            
            result_code = result_code.text
            if result_code != "INFO-000":
                result_msg = root.find(".//MESSAGE")
                msg = result_msg.text if result_msg is not None else "알 수 없는 오류"
                return {"status": "error", "message": f"API 오류: {msg}"}
            
            # 데이터 파싱
            pharmacies = []
            for row in root.findall(".//row"):
                pharmacy = self._parse_pharmacy_row(row)
                if pharmacy:
                    pharmacies.append(pharmacy)
            
            total_count_elem = root.find(".//list_total_count")
            total_count = total_count_elem.text if total_count_elem is not None else len(pharmacies)
            
            return {
                "status": "success",
                "total_count": total_count,
                "pharmacies": pharmacies
            }
            
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": f"네트워크 오류: {str(e)}"}
        except ET.ParseError as e:
            return {"status": "error", "message": f"데이터 파싱 오류: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": f"알 수 없는 오류: {str(e)}"}
    
    def _parse_pharmacy_row(self, row):
        """약국 데이터 파싱"""
        try:
            name = row.findtext("DUTYNAME", "정보 없음")
            addr = row.findtext("DUTYADDR", "정보 없음")
            tel = row.findtext("DUTYTEL1", "정보 없음")
            
            # 운영 시간 정보
            now = datetime.now()
            weekday = now.weekday()  # 0:월요일, 6:일요일
            day_names = ["월", "화", "수", "목", "금", "토", "일", "공휴일"]
            
            # 오늘 운영시간
            today_idx = weekday + 1  # API는 1부터 시작
            start_time = row.findtext(f"DUTYTIME{today_idx}S", "")
            end_time = row.findtext(f"DUTYTIME{today_idx}C", "")
            
            # 시간 포맷팅
            if start_time and len(start_time) == 4:
                start_time = f"{start_time[:2]}:{start_time[2:]}"
            else:
                start_time = "정보 없음"
                
            if end_time and len(end_time) == 4:
                end_time = f"{end_time[:2]}:{end_time[2:]}"
            else:
                end_time = "정보 없음"
            
            # 현재 영업 상태
            current_status = "정보 없음"
            if start_time != "정보 없음" and end_time != "정보 없음":
                current_time = now.strftime("%H:%M")
                if start_time <= current_time <= end_time:
                    current_status = "🟢 영업중"
                else:
                    current_status = "🔴 영업종료"
            
            return {
                "name": name,
                "address": addr,
                "phone": tel,
                "today_hours": f"{start_time} - {end_time}",
                "status": current_status,
                "current_day": day_names[weekday]
            }
            
        except Exception as e:
            logger.error(f"약국 데이터 파싱 오류: {str(e)}")
            return None
    
    def _format_pharmacy_results(self, result):
        """약국 검색 결과를 채팅 형태로 포맷팅"""
        if result["status"] == "error":
            return result["message"]
        
        pharmacies = result["pharmacies"]
        total_count = result["total_count"]
        
        if not pharmacies:
            return "검색 조건에 맞는 약국을 찾을 수 없습니다. 😓\n\n💡 **검색 팁**:\n- 지역구명을 정확히 입력해주세요 (예: 강남구)\n- 약국명을 정확히 입력해주세요"
        
        # 헤더
        header = f"## 💊 서울시 약국 정보 검색 결과\n\n"
        header += f"✅ **총 {total_count}개 약국** 중 **{len(pharmacies)}개**를 표시합니다.\n\n"
        
        # 약국 목록
        pharmacy_list = ""
        for i, pharmacy in enumerate(pharmacies, 1):
            pharmacy_list += f"### {i}. 🏥 {pharmacy['name']}\n"
            pharmacy_list += f"📍 **주소**: {pharmacy['address']}\n"
            pharmacy_list += f"📞 **전화**: {pharmacy['phone']}\n"
            pharmacy_list += f"⏰ **오늘({pharmacy['current_day']}) 운영시간**: {pharmacy['today_hours']}\n"
            pharmacy_list += f"🔍 **현재 상태**: {pharmacy['status']}\n"
            
            # 지도 링크 (간단한 구글맵 검색)
            map_query = f"{pharmacy['name']} {pharmacy['address']}"
            map_url = f"https://www.google.com/maps/search/?api=1&query={map_query}"
            pharmacy_list += f"🗺️ [지도에서 보기]({map_url})\n\n"
            
            if i < len(pharmacies):
                pharmacy_list += "---\n\n"
        
        # 푸터
        footer = "\n💡 **이용 안내**:\n"
        footer += "- 영업시간은 변경될 수 있으니 방문 전 전화 확인을 권장합니다\n"
        footer += "- 공휴일 및 특별한 날에는 운영시간이 다를 수 있습니다\n"
        footer += "- 더 정확한 정보는 약국에 직접 문의해주세요 😊"
        
        return header + pharmacy_list + footer

def extract_pharmacy_query_info(query):
    """쿼리에서 약국 검색 정보 추출"""
    query_lower = query.lower().replace(" ", "")
    
    # 약국 검색 키워드 확인
    pharmacy_keywords = ["약국", "약국정보", "약국검색", "약국운영", "약국시간"]
    
    for keyword in pharmacy_keywords:
        if keyword in query_lower:
            return True
    
    return False