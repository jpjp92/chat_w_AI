import requests
import urllib.parse
import logging

logger = logging.getLogger(__name__)

class DrugAPI:
    def __init__(self, api_key, cache_handler, cache_ttl=86400):
        self.api_key = api_key
        self.cache = cache_handler
        self.cache_ttl = cache_ttl
        self.base_url = 'http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList'
    
    def get_drug_info(self, drug_query):
        """의약품 정보를 검색하고 반환합니다."""
        drug_name = drug_query.replace("약품검색", "").strip()
        cache_key = f"drug:{drug_name}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        params = {
            'serviceKey': self.api_key,
            'pageNo': '1',
            'numOfRows': '1',
            'itemName': urllib.parse.quote(drug_name),
            'type': 'json'
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=3)
            response.raise_for_status()
            data = response.json()
            
            if 'body' in data and 'items' in data['body'] and data['body']['items']:
                item = data['body']['items'][0]
                result = self._format_drug_info(item)
                self.cache.setex(cache_key, self.cache_ttl, result)
                return result
            
            return f"'{drug_name}'의 공식 정보를 찾을 수 없습니다."
            
        except Exception as e:
            logger.error(f"약품 API 오류: {str(e)}")
            return f"'{drug_name}'의 정보를 가져오는 중 문제가 발생했습니다. 😓"
    
    def _format_drug_info(self, item):
        """의약품 정보를 포맷팅하여 반환합니다."""
        # 전체 내용 및 요약 내용 저장
        efcy_full = item.get('efcyQesitm', '정보 없음')
        efcy_summary = efcy_full[:150] + ("..." if len(efcy_full) > 150 else "")
        
        use_method_full = item.get('useMethodQesitm', '정보 없음')
        use_method_summary = use_method_full[:150] + ("..." if len(use_method_full) > 150 else "")
        
        atpn_full = item.get('atpnQesitm', '정보 없음')
        atpn_summary = atpn_full[:150] + ("..." if len(atpn_full) > 150 else "")
        
        # 마크다운에서 details/summary 태그를 사용하여 접었다 펼치는 효과 구현
        result = (
            f"💊 **의약품 정보** 💊\n\n"
            f"✅ **약품명**: {item.get('itemName', '정보 없음')}\n\n"
            f"✅ **제조사**: {item.get('entpName', '정보 없음')}\n\n"
            f"✅ **효능**: {efcy_summary}\n"
            f"<details><summary>**전체 내용 보기**</summary>\n{efcy_full}\n</details>\n\n"
            f"✅ **용법용량**: {use_method_summary}\n"
            f"<details><summary>**전체 내용 보기**</summary>\n{use_method_full}\n</details>\n\n"
            f"✅ **주의사항**: {atpn_summary}\n"
            f"<details><summary>**전체 내용 보기**</summary>\n{atpn_full}\n</details>\n\n"
            f"더 궁금한 점 있나요? 😊"
        )
        return result