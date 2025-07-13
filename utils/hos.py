import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import logging
import re
import pytz

logger = logging.getLogger(__name__)

class SeoulHospitalAPI:
    """
    서울시 병의원 운영 정보 API 모듈 (수정버전)
    """

    BASE_URL = "http://openapi.seoul.go.kr:8088"

    def __init__(self, api_key, cache_handler=None):
        self.api_key = api_key
        self.cache_handler = cache_handler

    def search_hospitals(self, query, limit=100):
        """
        병의원 검색 및 정보 조회 (수정버전)
        """
        try:
            logger.info(f"병원 검색 요청: '{query}'")
            page = self._extract_page_number(query)
            cache_key = f"hospital:{query}:{limit}:{page}"
            
            if self.cache_handler:
                cached = self.cache_handler.get(cache_key)
                if cached:
                    logger.info("캐시에서 병원 정보 반환")
                    return cached

            district = self._extract_district(query)
            hospital_name = self._extract_hospital_name(query)
            hospital_type = self._extract_hospital_type(query)

            logger.info(f"추출된 지역구: {district}")
            logger.info(f"추출된 병원명: {hospital_name}")
            logger.info(f"추출된 병원종류: {hospital_type}")
            logger.info(f"추출된 페이지: {page}")

            # limit*5가 1000을 넘지 않도록 제한
            fetch_limit = min(limit * 5, 1000)
            result = self._fetch_hospital_data(fetch_limit)
            if result["status"] == "error":
                return result["message"]

            # 클라이언트 측에서 필터링 적용
            filtered_hospitals = self._apply_filters(
                result["hospitals"], 
                district, 
                hospital_name, 
                hospital_type,
                query  # 원본 쿼리도 전달
            )

            total_filtered = len(filtered_hospitals)

            # 페이지네이션
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            page_hospitals = filtered_hospitals[start_idx:end_idx]
            total_pages = (total_filtered + limit - 1) // limit
            has_next = page < total_pages
            has_prev = page > 1

            paginated_result = {
                "status": "success",
                "total_count": total_filtered,
                "hospitals": page_hospitals,
                "pagination": {
                    "current_page": page,
                    "total_pages": total_pages,
                    "has_next": has_next,
                    "has_prev": has_prev,
                    "per_page": limit
                }
            }

            formatted_result = self._format_hospital_results(paginated_result, district, hospital_type)
            if self.cache_handler:
                self.cache_handler.setex(cache_key, 1800, formatted_result)
            return formatted_result

        except Exception as e:
            logger.error(f"병원 검색 중 오류: {str(e)}")
            return f"병원 정보를 가져오는 중 오류가 발생했습니다: {str(e)} 😓"

    def _apply_filters(self, hospitals, district, hospital_name, hospital_type, original_query):
        """
        클라이언트 측에서 필터링 적용 (수정버전)
        """
        filtered = hospitals

        # 지역구 필터링
        if district:
            filtered = [h for h in filtered if district in h.get("address", "")]
            logger.info(f"지역구 필터링 후: {len(filtered)}개")

        # 병원명 필터링 (비활성화)
        # if hospital_name:
        #     filtered = [h for h in filtered if hospital_name in h.get("name", "")]
        #     logger.info(f"병원명 필터링 후: {len(filtered)}개")

        # 병원 종류 필터링 (수정된 로직)
        if hospital_type:
            original_count = len(filtered)
            
            # "지역구 병원" 형태의 쿼리는 모든 의료기관 포함
            if self._is_general_hospital_query(original_query):
                logger.info(f"일반 병원 검색으로 판단: '{original_query}' - 모든 의료기관 포함")
                # 병원 종류 필터링 건너뛰기
                pass
            else:
                # 구체적인 병원 종류 필터링
                if hospital_type == "병원":
                    # "병원"만 검색할 때는 일반병원과 종합병원만
                    filtered = [h for h in filtered if any(keyword in h.get("type", "") for keyword in ["병원", "종합병원"]) and "의원" not in h.get("type", "")]
                elif hospital_type == "의원":
                    # "의원"만 검색할 때는 의원과 한의원만
                    filtered = [h for h in filtered if any(keyword in h.get("type", "") for keyword in ["의원", "한의원"])]
                elif hospital_type == "종합병원":
                    # "종합병원"만 검색
                    filtered = [h for h in filtered if "종합병원" in h.get("type", "")]
                elif hospital_type == "한의원":
                    # "한의원"만 검색
                    filtered = [h for h in filtered if "한의원" in h.get("type", "")]
                else:
                    # 기타 구체적인 종류 검색
                    filtered = [h for h in filtered if hospital_type in h.get("type", "") or h.get("type", "") in hospital_type]
                
                logger.info(f"병원 종류 필터링 후: {len(filtered)}개 ('{hospital_type}' 검색, {original_count}개에서 필터링)")

        return filtered

    def _is_general_hospital_query(self, query):
        """
        일반적인 병원 검색 쿼리인지 판단 (모든 의료기관 포함해야 하는지)
        """
        # 지역구 + "병원" 형태의 일반 검색
        district = self._extract_district(query)
        if district and "병원" in query:
            # 구체적인 병원 종류가 없는 경우 (종합병원, 치과병원, 한방병원 등)
            specific_types = ["종합병원", "치과병원", "한방병원", "한의원"]
            if not any(t in query for t in specific_types):
                return True
        return False

    def _extract_page_number(self, query):
        page_patterns = [
            r'(\d+)페이지',
            r'(\d+)번째',
            r'페이지\s*(\d+)',
            r'(\d+)p',
            r'(\d+)$'
        ]
        for pattern in page_patterns:
            match = re.search(pattern, query)
            if match:
                page_num = int(match.group(1))
                return max(1, page_num)
        return 1

    def _extract_district(self, query):
        districts = [
            "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구",
            "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구",
            "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"
        ]
        for district in districts:
            if district in query:
                return district
        return None

    def _extract_hospital_type(self, query):
        """
        병원 종류 추출 (개선된 로직)
        """
        # 더 구체적인 타입을 우선 검색
        specific_types = ["종합병원", "치과병원", "한방병원", "한의원"]
        for t in specific_types:
            if t in query:
                return t
        
        # 일반적인 타입 검색
        general_types = ["병원", "의원"]
        for t in general_types:
            if t in query:
                return t
        
        return None

    def _extract_hospital_name(self, query):
        keywords_to_remove = ["병원", "의원", "치과", "한방", "한의원", "종합병원", "병원명", "병원검색", "병원정보", "서울시", "검색"]
        cleaned_query = query
        for keyword in keywords_to_remove:
            cleaned_query = cleaned_query.replace(keyword, "")
        cleaned_query = cleaned_query.strip()
        
        district = self._extract_district(query)
        if district:
            cleaned_query = cleaned_query.replace(district, "")
        
        hospital_type = self._extract_hospital_type(query)
        if hospital_type:
            cleaned_query = cleaned_query.replace(hospital_type, "")
        
        cleaned_query = cleaned_query.strip()
        if len(cleaned_query) < 2:
            return None
        return cleaned_query

    def _fetch_hospital_data(self, limit=100):
        """
        서울시 병원 데이터 조회 (필터링 제거)
        """
        url = f"{self.BASE_URL}/{self.api_key}/xml/TbHospitalInfo/1/{limit}/"
        try:
            logger.info(f"API 호출: {url}")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            
            # 결과 코드 확인
            result_code = root.find(".//CODE")
            result_msg = root.find(".//MESSAGE")
            if result_code is not None:
                result_code_text = result_code.text
                result_msg_text = result_msg.text if result_msg is not None else "알 수 없는 오류"
                if result_code_text != "INFO-000":
                    logger.error(f"API 오류: {result_msg_text} (코드: {result_code_text})")
                    return {"status": "error", "message": f"API 오류: {result_msg_text} (코드: {result_code_text})"}
            
            # 전체 카운트
            total_count_elem = root.find(".//list_total_count")
            total_count = total_count_elem.text if total_count_elem is not None else "0"
            
            hospitals = []
            day_names = ["월", "화", "수", "목", "금", "토", "일", "공휴일"]

            # 한국 시간으로 현재 요일 계산
            now = datetime.now(pytz.timezone("Asia/Seoul"))
            weekday = now.weekday()  # 0:월요일, 6:일요일
            current_day = day_names[weekday]

            for row in root.findall(".//row"):
                hospital_id = row.findtext("HPID", "")
                name = row.findtext("DUTYNAME", "정보 없음")
                addr = row.findtext("DUTYADDR", "정보 없음")
                tel = row.findtext("DUTYTEL1", "정보 없음")
                emergency_tel = row.findtext("DUTYTEL3", "")
                hospital_type_val = row.findtext("DUTYDIVNAM", "정보 없음")
                emergency_status = row.findtext("DUTYEMCLSNAME", "정보 없음")
                emergency_room = "응급실 운영" if row.findtext("DUTYERYN", "") == "1" else "응급실 미운영"
                description = row.findtext("DUTYINF", "")
                note = row.findtext("DUTYETC", "")
                
                # 운영시간 파싱
                operation_hours = {}
                for i in range(1, 9):
                    day_key = day_names[i-1]
                    start_time = row.findtext(f"DUTYTIME{i}S", "")
                    close_time = row.findtext(f"DUTYTIME{i}C", "")
                    if start_time and len(start_time) == 4:
                        start_time = f"{start_time[:2]}:{start_time[2:]}"
                    else:
                        start_time = "정보 없음"
                    if close_time and len(close_time) == 4:
                        close_time = f"{close_time[:2]}:{close_time[2:]}"
                    else:
                        close_time = "정보 없음"
                    operation_hours[day_key] = {
                        "start": start_time,
                        "end": close_time
                    }
                
                hospital_info = {
                    "id": hospital_id,
                    "name": name,
                    "type": hospital_type_val,
                    "address": addr,
                    "tel": tel,
                    "emergency_tel": emergency_tel,
                    "emergency_status": emergency_status,
                    "emergency_room": emergency_room,
                    "description": description,
                    "note": note,
                    "hours": operation_hours,
                    "current_day": current_day
                }
                hospitals.append(hospital_info)
            
            logger.info(f"총 {len(hospitals)}개 병원 데이터 조회 완료")
            return {
                "status": "success",
                "total_count": total_count,
                "hospitals": hospitals
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"데이터 요청 오류: {str(e)}")
            return {"status": "error", "message": f"데이터 요청 오류: {str(e)}"}
        except ET.ParseError as e:
            logger.error(f"XML 파싱 오류: {str(e)}")
            return {"status": "error", "message": f"XML 파싱 오류: {str(e)}"}
        except Exception as e:
            logger.error(f"예상치 못한 오류: {str(e)}")
            return {"status": "error", "message": f"오류 발생: {str(e)}"}

    def _filter_by_district(self, result, target_district):
        """
        지역구별 필터링 (사용하지 않음 - 호환성 유지)
        """
        if result["status"] != "success":
            return result
        
        filtered = [h for h in result["hospitals"] if target_district in h["address"]]
        return {
            "status": "success",
            "total_count": len(filtered),
            "hospitals": filtered
        }

    def _format_hospital_results(self, result, searched_district=None, searched_type=None):
        """
        병원 검색 결과 포맷팅
        """
        if result["status"] == "error":
            return result["message"]
        
        hospitals = result["hospitals"]
        total_count = result["total_count"]
        pagination = result.get("pagination", {})
        
        if not hospitals:
            district_msg = f" ({searched_district})" if searched_district else ""
            return f"검색 조건에 맞는 병의원을 찾을 수 없습니다{district_msg}. 😓\n\n💡 **검색 팁**:\n- 지역구명을 정확히 입력해주세요 (예: 강남구)\n- 병원명을 정확히 입력해주세요"
        
        # 헤더
        district_info = f" ({searched_district})" if searched_district else ""
        type_info = f" [{searched_type}]" if searched_type else ""
        header = f"## 🏥 서울시 병의원 정보 검색 결과{district_info}{type_info}\n\n"
        header += f"✅ **총 {total_count}개 병의원**을 찾았습니다.\n\n"
        
        # 페이지네이션 정보
        if pagination:
            current_page = pagination.get("current_page", 1)
            total_pages = pagination.get("total_pages", 1)
            per_page = pagination.get("per_page", 10)
            start_num = (current_page - 1) * per_page + 1
            end_num = min(start_num + len(hospitals) - 1, total_count)
            header += f"📄 **현재 페이지**: {current_page}/{total_pages} ({start_num}-{end_num}번 병의원)\n\n"
        
        # 병원 목록
        hospital_list = ""
        start_num = ((pagination.get("current_page", 1) - 1) * pagination.get("per_page", 10)) + 1
        
        for i, hospital in enumerate(hospitals, start_num):
            hospital_list += f"### {i}. 🏥 {hospital['name']} ({hospital['type']})\n\n"
            hospital_list += f"📍 **주소**: {hospital['address']}\n\n"
            hospital_list += f"📞 **전화**: {hospital['tel']}\n\n"
            
            if hospital['emergency_tel']:
                hospital_list += f"🚑 **응급실 전화**: {hospital['emergency_tel']}\n\n"
            
            hospital_list += f"🚨 **응급의료기관 분류**: {hospital['emergency_status']}\n\n"
            hospital_list += f"🏥 **응급실 운영여부**: {hospital['emergency_room']}\n\n"
            
            if hospital['note']:
                hospital_list += f"📝 **비고**: {hospital['note']}\n\n"
            
            if hospital['description']:
                desc = hospital['description']
                if len(desc) > 100:
                    desc = desc[:100] + "..."
                hospital_list += f"ℹ️ **기관 설명**: {desc}\n\n"
            
            # 오늘 운영시간
            current_hours = hospital["hours"][hospital["current_day"]]
            hospital_list += f"⏰ **오늘({hospital['current_day']}) 운영시간**: {current_hours['start']}~{current_hours['end']}\n\n"
            
            # 영업 중 여부
            now_time = datetime.now().strftime("%H:%M")
            if current_hours["start"] != "정보 없음" and current_hours["end"] != "정보 없음":
                if current_hours["start"] <= now_time <= current_hours["end"]:
                    hospital_list += f"🟢 **현재 진료 중**\n\n"
                else:
                    hospital_list += f"🔴 **현재 진료 종료**\n\n"
            
            # 전체 운영시간
            hospital_list += "📅 **전체 운영시간:**\n"
            for day, hours in hospital["hours"].items():
                day_mark = "✅" if day == hospital["current_day"] else ""
                hospital_list += f"  - {day}: {hours['start']}~{hours['end']} {day_mark}\n"
            hospital_list += "\n---\n\n"
        
        # 페이지네비게이션
        navigation = ""
        if pagination:
            has_prev = pagination.get("has_prev", False)
            has_next = pagination.get("has_next", False)
            current_page = pagination.get("current_page", 1)
            
            if has_prev or has_next:
                navigation += "\n🔄 **더 보기**:\n"
                if has_prev:
                    navigation += f"- 이전 페이지: \"{searched_district or ''} 병원 {current_page - 1}페이지\"\n"
                if has_next:
                    navigation += f"- 다음 페이지: \"{searched_district or ''} 병원 {current_page + 1}페이지\"\n"
                navigation += "\n"
        
        # 푸터
        footer = "\n💡 **이용 안내**:\n"
        footer += "- 운영시간은 변경될 수 있으니 방문 전 전화 확인을 권장합니다\n"
        footer += "- 공휴일 및 특별한 날에는 운영시간이 다를 수 있습니다\n"
        footer += "- 더 정확한 정보는 병원에 직접 문의해주세요 😊\n"
        footer += "- 🔴 **진료 종료 병원도 정보를 확인할 수 있습니다**"
        
        return header + hospital_list + navigation + footer