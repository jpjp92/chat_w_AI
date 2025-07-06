import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DrugStoreAPI:
    def __init__(self, api_key, cache_handler=None):
        self.api_key = api_key
        self.cache_handler = cache_handler
        self.base_url = "http://openapi.seoul.go.kr:8088"
    
    def search_pharmacies(self, query, limit=10):
        """약국 검색 및 정보 조회"""
        try:
            logger.info(f"약국 검색 요청: '{query}'")
            
            # 캐시 확인
            cache_key = f"pharmacy:{query}:{limit}"
            if self.cache_handler:
                cached = self.cache_handler.get(cache_key)
                if cached:
                    logger.info("캐시에서 약국 정보 반환")
                    return cached
            
            # 지역구 추출
            district = self._extract_district(query)
            pharmacy_name = self._extract_pharmacy_name(query)
            
            logger.info(f"추출된 지역구: {district}")
            logger.info(f"추출된 약국명: {pharmacy_name}")
            
            # API 호출
            result = self._fetch_pharmacy_data(district, pharmacy_name, limit)
            
            if result["status"] == "error":
                return result["message"]
            
            # 🔴 지역구 필터링 (API 필터링이 완벽하지 않을 경우 수동 필터링)
            if district:
                result = self._filter_by_district(result, district)
            
            # 결과 포맷팅
            formatted_result = self._format_pharmacy_results(result, district)
            
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
            # 🔴 올바른 URL 구조 사용
            start_index = 1
            end_index = limit
            
            # 기본 URL 구성
            url = f"{self.base_url}/{self.api_key}/xml/TbPharmacyOperateInfo/{start_index}/{end_index}/"
            
            # 🔴 선택적 파라미터를 URL에 추가
            if district:
                url += f"{district}"
                if name:
                    url += f"/{name}"
            elif name:
                url += f"/{name}"
            
            logger.info(f"API 호출 URL: {url}")
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            logger.info(f"API 응답 상태 코드: {response.status_code}")
            
            # XML 파싱
            root = ET.fromstring(response.content)
            
            # 🔴 응답 구조 디버깅
            logger.info("API 응답 구조:")
            for elem in root.iter():
                if elem.tag in ['CODE', 'MESSAGE', 'list_total_count']:
                    logger.info(f"  {elem.tag}: {elem.text}")
            
            # 결과 코드 확인
            result_elem = root.find(".//RESULT")
            if result_elem is not None:
                code_elem = result_elem.find("CODE")
                msg_elem = result_elem.find("MESSAGE")
                
                if code_elem is not None:
                    result_code = code_elem.text
                    result_msg = msg_elem.text if msg_elem is not None else "알 수 없는 오류"
                    
                    logger.info(f"API 결과 코드: {result_code}")
                    logger.info(f"API 결과 메시지: {result_msg}")
                    
                    if result_code != "INFO-000":
                        return {"status": "error", "message": f"API 오류: {result_msg}"}
            
            # 데이터 파싱
            pharmacies = []
            rows = root.findall(".//row")
            logger.info(f"찾은 약국 수: {len(rows)}")
            
            for i, row in enumerate(rows):
                pharmacy = self._parse_pharmacy_row(row)
                if pharmacy:
                    pharmacies.append(pharmacy)
                    logger.info(f"약국 {i+1}: {pharmacy['name']} - {pharmacy['address']}")
            
            # 총 개수 확인
            total_count_elem = root.find(".//list_total_count")
            total_count = total_count_elem.text if total_count_elem is not None else str(len(pharmacies))
            
            logger.info(f"총 약국 수: {total_count}, 파싱된 약국 수: {len(pharmacies)}")
            
            return {
                "status": "success",
                "total_count": total_count,
                "pharmacies": pharmacies
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"네트워크 오류: {str(e)}")
            return {"status": "error", "message": f"네트워크 오류: {str(e)}"}
        except ET.ParseError as e:
            logger.error(f"XML 파싱 오류: {str(e)}")
            return {"status": "error", "message": f"데이터 파싱 오류: {str(e)}"}
        except Exception as e:
            logger.error(f"알 수 없는 오류: {str(e)}")
            return {"status": "error", "message": f"알 수 없는 오류: {str(e)}"}
    
    def _filter_by_district(self, result, target_district):
        """지역구별 수동 필터링"""
        logger.info(f"지역구 '{target_district}'로 수동 필터링 시작")
        
        if result["status"] != "success":
            return result
        
        filtered_pharmacies = []
        for pharmacy in result["pharmacies"]:
            if target_district in pharmacy["address"]:
                filtered_pharmacies.append(pharmacy)
        
        logger.info(f"필터링 전: {len(result['pharmacies'])}개")
        logger.info(f"필터링 후: {len(filtered_pharmacies)}개")
        
        return {
            "status": "success",
            "total_count": len(filtered_pharmacies),
            "pharmacies": filtered_pharmacies
        }
    
    def _parse_pharmacy_row(self, row):
        """약국 데이터 파싱"""
        try:
            name = row.findtext("DUTYNAME", "정보 없음")
            addr = row.findtext("DUTYADDR", "정보 없음")
            tel = row.findtext("DUTYTEL1", "정보 없음")
            
            # 🔴 운영 시간 정보 개선
            now = datetime.now()
            weekday = now.weekday()  # 0:월요일, 6:일요일
            day_names = ["월", "화", "수", "목", "금", "토", "일"]
            
            # 오늘 운영시간 (1:월요일 ~ 7:일요일)
            today_idx = weekday + 1
            start_time = row.findtext(f"DUTYTIME{today_idx}S", "")
            end_time = row.findtext(f"DUTYTIME{today_idx}C", "")
            
            # 🔴 운영시간 필드 디버깅
            logger.debug(f"약국 {name} 운영시간:")
            for i in range(1, 9):  # 1-8 (월~일, 공휴일)
                start = row.findtext(f"DUTYTIME{i}S", "")
                end = row.findtext(f"DUTYTIME{i}C", "")
                if start or end:
                    logger.debug(f"  요일{i}: {start} - {end}")
            
            # 시간 포맷팅
            formatted_start = self._format_time(start_time)
            formatted_end = self._format_time(end_time)
            
            # 현재 영업 상태 계산
            current_status = self._calculate_status(formatted_start, formatted_end)
            
            return {
                "name": name,
                "address": addr,
                "phone": tel,
                "today_hours": f"{formatted_start} - {formatted_end}",
                "status": current_status,
                "current_day": day_names[weekday] if weekday < 7 else "일"
            }
            
        except Exception as e:
            logger.error(f"약국 데이터 파싱 오류: {str(e)}")
            return None
    
    def _format_time(self, time_str):
        """시간 포맷팅"""
        if not time_str or len(time_str) < 4:
            return "정보 없음"
        
        try:
            # 4자리 시간 형식 (예: 0900 -> 09:00)
            if len(time_str) == 4:
                return f"{time_str[:2]}:{time_str[2:]}"
            else:
                return time_str
        except:
            return "정보 없음"
    
    def _calculate_status(self, start_time, end_time):
        """현재 영업 상태 계산"""
        if start_time == "정보 없음" or end_time == "정보 없음":
            return "정보 없음"
        
        try:
            current_time = datetime.now().strftime("%H:%M")
            
            # 24시간 영업 체크
            if start_time == "00:00" and end_time == "23:59":
                return "🟢 24시간 영업"
            
            # 일반 영업시간 체크
            if start_time <= current_time <= end_time:
                return "🟢 영업중"
            else:
                return "🔴 영업종료"
        except:
            return "정보 없음"
    
    def _format_pharmacy_results(self, result, searched_district=None):
        """약국 검색 결과를 채팅 형태로 포맷팅"""
        if result["status"] == "error":
            return result["message"]
        
        pharmacies = result["pharmacies"]
        total_count = result["total_count"]
        
        if not pharmacies:
            district_msg = f" ({searched_district})" if searched_district else ""
            return f"검색 조건에 맞는 약국을 찾을 수 없습니다{district_msg}. 😓\n\n💡 **검색 팁**:\n- 지역구명을 정확히 입력해주세요 (예: 강남구)\n- 약국명을 정확히 입력해주세요"
        
        # 헤더
        district_info = f" ({searched_district})" if searched_district else ""
        header = f"## 💊 서울시 약국 정보 검색 결과{district_info}\n\n"
        header += f"✅ **총 {total_count}개 약국**을 찾았습니다.\n\n"
        
        # 약국 목록
        pharmacy_list = ""
        for i, pharmacy in enumerate(pharmacies, 1):
            pharmacy_list += f"### {i}. 🏥 {pharmacy['name']}\n"
            pharmacy_list += f"📍 **주소**: {pharmacy['address']}\n"
            pharmacy_list += f"📞 **전화**: {pharmacy['phone']}\n"
            pharmacy_list += f"⏰ **오늘({pharmacy['current_day']}) 운영시간**: {pharmacy['today_hours']}\n"
            pharmacy_list += f"🔍 **현재 상태**: {pharmacy['status']}\n"
            
            # 지도 링크
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