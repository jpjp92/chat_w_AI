import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import logging
import pytz
import re

logger = logging.getLogger(__name__)

class DrugStoreAPI:
    def __init__(self, api_key, cache_handler=None):
        self.api_key = api_key
        self.cache_handler = cache_handler
        self.base_url = "http://openapi.seoul.go.kr:8088"
    
    def search_pharmacies(self, query, limit=10):
        """약국 검색 및 정보 조회 (페이지네이션)"""
        try:
            logger.info(f"약국 검색 요청: '{query}'")
            
            # 🔴 페이지 번호 추출
            page = self._extract_page_number(query)
            
            # 캐시 확인 (페이지 포함)
            cache_key = f"pharmacy:{query}:{limit}:{page}"
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
            logger.info(f"추출된 페이지: {page}")
            
            # 🔴 전체 데이터 가져오기 (지역구 검색 시 500개)
            result = self._fetch_pharmacy_data(district, pharmacy_name, limit)
            
            if result["status"] == "error":
                return result["message"]
            
            # 🔴 지역구 필터링
            if district:
                result = self._filter_by_district(result, district)
            
            # 🔴 페이지네이션 처리
            all_pharmacies = result["pharmacies"]
            total_filtered = len(all_pharmacies)
            
            # 페이지별 약국 선택
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            page_pharmacies = all_pharmacies[start_idx:end_idx]
            
            # 페이지네이션 정보 계산
            total_pages = (total_filtered + limit - 1) // limit
            has_next = page < total_pages
            has_prev = page > 1
            
            logger.info(f"전체 필터링된 약국: {total_filtered}개")
            logger.info(f"현재 페이지: {page}/{total_pages}")
            logger.info(f"표시할 약국: {len(page_pharmacies)}개")
            
            # 🔴 결과 구조 업데이트
            paginated_result = {
                "status": "success",
                "total_count": total_filtered,
                "pharmacies": page_pharmacies,
                "pagination": {
                    "current_page": page,
                    "total_pages": total_pages,
                    "has_next": has_next,
                    "has_prev": has_prev,
                    "per_page": limit
                }
            }
            
            # 결과 포맷팅
            formatted_result = self._format_pharmacy_results(paginated_result, district)
            
            # 캐시 저장 (30분)
            if self.cache_handler:
                self.cache_handler.setex(cache_key, 1800, formatted_result)
            
            return formatted_result
            
        except Exception as e:
            logger.error(f"약국 검색 중 오류: {str(e)}")
            return f"약국 정보를 가져오는 중 오류가 발생했습니다: {str(e)} 😓"
    
    def _extract_page_number(self, query):
        """쿼리에서 페이지 번호 추출"""
        # "광진구 약국 2페이지", "광진구 약국 3", "광진구 약국 더보기" 등
        page_patterns = [
            r'(\d+)페이지',
            r'(\d+)번째',
            r'페이지\s*(\d+)',
            r'(\d+)p',
            r'(\d+)$'  # 마지막에 숫자만 있는 경우
        ]
        
        for pattern in page_patterns:
            match = re.search(pattern, query)
            if match:
                page_num = int(match.group(1))
                return max(1, page_num)  # 최소 1페이지
        
        return 1  # 기본 1페이지
    
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
            # 🔴 지역구 검색 시 더 많은 데이터 가져오기
            start_index = 1
            if district:
                end_index = 500  # 🔴 지역구 검색 시 500개 가져오기
            else:
                end_index = limit * 5
            
            url = f"{self.base_url}/{self.api_key}/xml/TbPharmacyOperateInfo/{start_index}/{end_index}/"
            
            params = {}
            if name:
                params['DUTYNAME'] = name
            
            logger.info(f"API 호출 URL: {url}")
            logger.info(f"파라미터: {params}")
            logger.info(f"요청 데이터 범위: {start_index}-{end_index}")
            
            response = requests.get(url, params=params, timeout=10)
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
            
            # 🔴 데이터 파싱 (try 블록 안에 포함)
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
            address = pharmacy["address"]
            logger.info(f"약국 주소 확인: '{address}'")
            
            # 🔴 간단한 문자열 포함 검사
            if target_district in address:
                filtered_pharmacies.append(pharmacy)
                logger.info(f"✅ 필터링 통과: {pharmacy['name']} - {address}")
            else:
                logger.info(f"❌ 필터링 제외: {pharmacy['name']} - {address}")
        
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
            
            # 🔴 한국시간 기준으로 요일 계산
            korea_tz = pytz.timezone('Asia/Seoul')
            now_kst = datetime.now(korea_tz)
            weekday = now_kst.weekday()  # 0:월요일, 6:일요일
            day_names = ["월", "화", "수", "목", "금", "토", "일"]
            
            # 오늘 운영시간 (1:월요일 ~ 7:일요일)
            today_idx = weekday + 1
            start_time = row.findtext(f"DUTYTIME{today_idx}S", "")
            end_time = row.findtext(f"DUTYTIME{today_idx}C", "")
            
            # 🔴 운영시간 필드 디버깅
            logger.debug(f"약국 {name} 운영시간 (한국시간 기준):")
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
        """현재 영업 상태 계산 (한국시간 기준)"""
        if start_time == "정보 없음" or end_time == "정보 없음":
            return "정보 없음"
        
        try:
            # 🔴 한국시간(KST) 기준으로 현재 시간 계산
            korea_tz = pytz.timezone('Asia/Seoul')
            now_kst = datetime.now(korea_tz)
            current_time = now_kst.strftime("%H:%M")
            
            logger.info(f"현재 시간(KST): {current_time}, 영업시간: {start_time} - {end_time}")
            
            # 24시간 영업 체크
            if start_time == "00:00" and end_time == "23:59":
                return "🟢 24시간 영업"
            
            # 🔴 시간 비교 로직 수정
            try:
                current_hour, current_min = map(int, current_time.split(':'))
                start_hour, start_min = map(int, start_time.split(':'))
                end_hour, end_min = map(int, end_time.split(':'))
                
                current_minutes = current_hour * 60 + current_min
                start_minutes = start_hour * 60 + start_min
                end_minutes = end_hour * 60 + end_min
                
                logger.info(f"시간 비교(KST) - 현재: {current_minutes}분, 시작: {start_minutes}분, 종료: {end_minutes}분")
                
                # 영업시간 체크
                if start_minutes <= current_minutes <= end_minutes:
                    return "🟢 영업중"
                else:
                    return "🔴 영업종료"
                
            except ValueError:
                logger.error(f"시간 파싱 오류: {start_time}, {end_time}")
                return "정보 없음"
            
        except Exception as e:
            logger.error(f"영업상태 계산 오류: {str(e)}")
            return "정보 없음"
    
    def _format_pharmacy_results(self, result, searched_district=None):
        """약국 검색 결과를 채팅 형태로 포맷팅 (페이지네이션 포함)"""
        if result["status"] == "error":
            return result["message"]
        
        pharmacies = result["pharmacies"]
        total_count = result["total_count"]
        note = result.get("note", "")
        pagination = result.get("pagination", {})
        
        if not pharmacies:
            district_msg = f" ({searched_district})" if searched_district else ""
            return f"검색 조건에 맞는 약국을 찾을 수 없습니다{district_msg}. 😓\n\n💡 **검색 팁**:\n- 지역구명을 정확히 입력해주세요 (예: 강남구)\n- 약국명을 정확히 입력해주세요"
        
        # 헤더
        district_info = f" ({searched_district})" if searched_district else ""
        header = f"## 💊 서울시 약국 정보 검색 결과{district_info}\n\n"
        header += f"✅ **총 {total_count}개 약국**을 찾았습니다.\n\n"
        
        # 🔴 페이지네이션 정보
        if pagination:
            current_page = pagination.get("current_page", 1)
            total_pages = pagination.get("total_pages", 1)
            per_page = pagination.get("per_page", 10)
            
            start_num = (current_page - 1) * per_page + 1
            end_num = min(start_num + len(pharmacies) - 1, total_count)
            
            header += f"📄 **현재 페이지**: {current_page}/{total_pages} ({start_num}-{end_num}번 약국)\n\n"
        
        # 주의사항 표시
        if note:
            header += f"⚠️ **안내**: {note}\n\n"
        
        # 약국 목록
        pharmacy_list = ""
        start_num = ((pagination.get("current_page", 1) - 1) * pagination.get("per_page", 10)) + 1
        
        for i, pharmacy in enumerate(pharmacies, start_num):
            pharmacy_list += f"### {i}. 🏥 {pharmacy['name']}\n\n"
            pharmacy_list += f"📍 **주소**: {pharmacy['address']}\n\n"
            pharmacy_list += f"📞 **전화**: {pharmacy['phone']}\n\n"
            pharmacy_list += f"⏰ **오늘({pharmacy['current_day']}) 운영시간**: {pharmacy['today_hours']}\n\n"
            pharmacy_list += f"🔍 **현재 상태**: {pharmacy['status']}\n\n"
            
            if i < start_num + len(pharmacies) - 1:
                pharmacy_list += "\n---\n\n"
            else:
                pharmacy_list += "\n"
        
        # 🔴 페이지네이션 네비게이션
        navigation = ""
        if pagination:
            has_prev = pagination.get("has_prev", False)
            has_next = pagination.get("has_next", False)
            current_page = pagination.get("current_page", 1)
            
            if has_prev or has_next:
                navigation += "\n🔄 **더 보기**:\n"
                
                if has_prev:
                    navigation += f"- 이전 페이지: \"{searched_district} 약국 {current_page - 1}페이지\"\n"
                
                if has_next:
                    navigation += f"- 다음 페이지: \"{searched_district} 약국 {current_page + 1}페이지\"\n"
                
                navigation += "\n"
        
        # 푸터
        footer = "\n💡 **이용 안내**:\n"
        footer += "- 영업시간은 변경될 수 있으니 방문 전 전화 확인을 권장합니다\n"
        footer += "- 공휴일 및 특별한 날에는 운영시간이 다를 수 있습니다\n"
        footer += "- 더 정확한 정보는 약국에 직접 문의해주세요 😊\n"
        footer += "- 🔴 **영업 종료 약국도 정보를 확인할 수 있습니다**"
        
        return header + pharmacy_list + navigation + footer