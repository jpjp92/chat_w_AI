import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)

class SeoulHospitalAPI:
    """
    서울시 병의원 운영 정보 API 모듈 (지도 정보 제외, drug_store.py 스타일 포맷 적용)
    """

    BASE_URL = "http://openapi.seoul.go.kr:8088"

    def __init__(self, api_key, cache_handler=None):
        self.api_key = api_key
        self.cache_handler = cache_handler

    def search_hospitals(self, query, limit=10000):
        """
        병의원 검색 및 정보 조회 (drug_store.py 스타일, 페이지네이션 포함)
        :param query: 검색 쿼리 (지역구, 병원명 등 포함 가능)
        :param limit: 페이지당 병원 수
        :return: 포맷된 결과(str) 또는 에러 메시지(str)
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

            # API 호출
            result = self._fetch_hospital_data(district, hospital_name, hospital_type, limit*5)
            if result["status"] == "error":
                return result["message"]

            # 지역구 필터링
            if district:
                result = self._filter_by_district(result, district)

            all_hospitals = result["hospitals"]
            total_filtered = len(all_hospitals)

            # 페이지네이션
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            page_hospitals = all_hospitals[start_idx:end_idx]
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
        types = ["종합병원", "병원", "의원", "치과병원", "한방병원", "한의원"]
        for t in types:
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

    def _fetch_hospital_data(self, district=None, name=None, hospital_type=None, limit=100):
        url = f"{self.BASE_URL}/{self.api_key}/xml/TbHospitalInfo/1/{limit}/"
        params = {}
        if district:
            params['DUTYADDR'] = district
        if name:
            params['DUTYNAME'] = name
        if hospital_type:
            params['DUTYDIVNAM'] = hospital_type
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            result_code = root.find(".//CODE").text
            result_msg = root.find(".//MESSAGE").text
            if result_code != "INFO-000":
                return {"status": "error", "message": f"API 오류: {result_msg} (코드: {result_code})"}
            total_count = root.find(".//list_total_count").text
            hospitals = []
            day_names = ["월", "화", "수", "목", "금", "토", "일", "공휴일"]
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
                now = datetime.now()
                weekday = now.weekday()
                current_day = day_names[weekday]
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
                if district and district not in addr:
                    continue
                if name and name not in hospital_info["name"]:
                    continue
                if hospital_type and hospital_type != hospital_info["type"]:
                    continue
                hospitals.append(hospital_info)
            return {
                "status": "success",
                "total_count": total_count,
                "hospitals": hospitals
            }
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": f"데이터 요청 오류: {str(e)}"}
        except ET.ParseError as e:
            return {"status": "error", "message": f"XML 파싱 오류: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": f"오류 발생: {str(e)}"}

    def _filter_by_district(self, result, target_district):
        if result["status"] != "success":
            return result
        filtered = [h for h in result["hospitals"] if target_district in h["address"]]
        return {
            "status": "success",
            "total_count": len(filtered),
            "hospitals": filtered
        }

    def _format_hospital_results(self, result, searched_district=None, searched_type=None):
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