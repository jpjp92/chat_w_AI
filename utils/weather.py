import requests
import logging
import re
from requests.adapters import HTTPAdapter, Retry
from functools import lru_cache
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)

class WeatherAPI:
    def __init__(self, cache_handler, WEATHER_API_KEY, cache_ttl=600):
        self.cache = cache_handler
        self.cache_ttl = cache_ttl
        self.WEATHER_API_KEY = WEATHER_API_KEY
        self.base_url = "https://api.openweathermap.org/data/2.5"
        self.geo_url = "https://api.openweathermap.org/geo/1.0"

    def fetch_weather(self, url, params):
        session = requests.Session()
        retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        try:
            response = session.get(url, params=params, timeout=3)
            response.raise_for_status()
            return response.json()
        except:
            return self.cache.get(f"weather:{params.get('q', '')}") or "날씨 정보를 불러올 수 없습니다."

    @lru_cache(maxsize=100)
    def get_city_info(self, city_name):
        cache_key = f"city_info:{city_name}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        url = "http://api.openweathermap.org/geo/1.0/direct"
        params = {'q': city_name, 'limit': 1, 'appid': self.WEATHER_API_KEY}
        data = self.fetch_weather(url, params)
        if data and isinstance(data, list) and len(data) > 0:
            city_info = {"name": data[0]["name"], "lat": data[0]["lat"], "lon": data[0]["lon"]}
            self.cache.setex(cache_key, 86400, city_info)
            return city_info
        return None

    def search_city_by_name(self, city_name):
        """OpenWeatherMap Geocoding API로 도시 검색"""
        cache_key = f"city_search:{city_name}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            # OpenWeatherMap Geocoding API 사용
            url = f"{self.geo_url}/direct"
            params = {
                "q": city_name,
                "limit": 1,
                "appid": self.WEATHER_API_KEY
            }
            
            response = requests.get(url, params=params, timeout=3)
            response.raise_for_status()
            
            results = response.json()
            if results:
                result = results[0]
                city_info = {
                    "name": result.get("name"),
                    "country": result.get("country"),
                    "lat": result.get("lat"),
                    "lon": result.get("lon"),
                    "local_names": result.get("local_names", {}),
                    "search_name": f"{result.get('name')},{result.get('country')}"
                }
                
                self.cache.setex(cache_key, 86400, city_info)  # 24시간 캐싱
                return city_info
            
        except Exception as e:
            logger.error(f"City search error for '{city_name}': {str(e)}")
        
        return None
    
    def get_city_weather(self, city_input):
        """도시 날씨를 가져옵니다 (자동 지명 검색)"""
        cache_key = f"weather:{city_input}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            # 1. 도시 검색 (한국어/영어 자동 처리)
            city_info = self.search_city_by_name(city_input)
            if not city_info:
                return f"'{city_input}' 도시를 찾을 수 없습니다. 도시명을 다시 확인해주세요. 😓"
            
            # 2. 좌표로 날씨 조회 (더 정확함)
            url = f"{self.base_url}/weather"
            params = {
                "lat": city_info["lat"],
                "lon": city_info["lon"],
                "appid": self.WEATHER_API_KEY,
                "units": "metric",
                "lang": "kr"
            }
            
            response = requests.get(url, params=params, timeout=3)
            response.raise_for_status()
            
            data = response.json()
            
            # 3. 날씨 데이터 포맷팅
            result = self.format_weather_data(data, city_input, city_info)
            
            self.cache.setex(cache_key, 1800, result)  # 30분 캐싱
            return result
            
        except Exception as e:
            logger.error(f"날씨 API 오류 for '{city_input}': {str(e)}")
            return f"'{city_input}'의 날씨 정보를 가져올 수 없습니다. 😓"
    
    def get_forecast_by_day(self, city_input, days=1):
        """도시의 일기예보를 가져옵니다"""
        cache_key = f"forecast:{city_input}:{days}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            # 1. 도시 검색
            city_info = self.search_city_by_name(city_input)
            if not city_info:
                return f"'{city_input}' 도시를 찾을 수 없습니다. 😓"
            
            # 2. 5일 예보 API 호출
            url = f"{self.base_url}/forecast"
            params = {
                "lat": city_info["lat"],
                "lon": city_info["lon"],
                "appid": self.WEATHER_API_KEY,
                "units": "metric",
                "lang": "kr"
            }
            
            response = requests.get(url, params=params, timeout=3)
            response.raise_for_status()
            
            data = response.json()
            
            # 3. 예보 데이터 포맷팅
            result = self.format_forecast_data(data, city_input, city_info, days)
            
            self.cache.setex(cache_key, 3600, result)  # 1시간 캐싱
            return result
            
        except Exception as e:
            logger.error(f"예보 API 오류 for '{city_input}': {str(e)}")
            return f"'{city_input}'의 날씨 예보를 가져올 수 없습니다. 😓"
    
    def format_weather_data(self, data, original_input, city_info):
        """날씨 데이터를 포맷팅합니다"""
        # 표시명 결정: 한국어 입력이면 한국어 유지, 영어면 영어 유지
        if self.is_korean(original_input):
            display_name = original_input
        else:
            display_name = city_info["name"]
        
        weather_desc = data['weather'][0]['description']
        temp = data['main']['temp']
        feels_like = data['main']['feels_like']
        humidity = data['main']['humidity']
        wind_speed = data['wind']['speed']
        
        # 날씨 이모지
        weather_emoji = self.get_weather_emoji(data['weather'][0]['icon'])
        
        return (
            f"현재 {display_name} 날씨 {weather_emoji}\n"
            f"날씨: {weather_desc}\n"
            f"온도: {temp}°C\n"
            f"체감: {feels_like}°C\n"
            f"습도: {humidity}%\n"
            f"풍속: {wind_speed}m/s\n"
            f"더 궁금한 점 있나요? 😊"
        )
    
    def format_forecast_data(self, data, original_input, city_info, days):
        """예보 데이터를 포맷팅합니다"""
        if self.is_korean(original_input):
            display_name = original_input
        else:
            display_name = city_info["name"]
        
        # 내일 예보 추출 (24시간 후 데이터)
        tomorrow_forecast = data['list'][8] if len(data['list']) > 8 else data['list'][0]
        
        weather_desc = tomorrow_forecast['weather'][0]['description']
        temp_max = tomorrow_forecast['main']['temp_max']
        temp_min = tomorrow_forecast['main']['temp_min']
        humidity = tomorrow_forecast['main']['humidity']
        wind_speed = tomorrow_forecast['wind']['speed']
        
        weather_emoji = self.get_weather_emoji(tomorrow_forecast['weather'][0]['icon'])
        
        return (
            f"내일 {display_name} 날씨 {weather_emoji}\n"
            f"날씨: {weather_desc}\n"
            f"최고: {temp_max}°C\n"
            f"최저: {temp_min}°C\n"
            f"습도: {humidity}%\n"
            f"풍속: {wind_speed}m/s\n"
            f"더 궁금한 점 있나요? 😊"
        )
    
    def is_korean(self, text):
        """한국어 포함 여부 확인"""
        return bool(re.search(r'[가-힣]', text))
    
    def get_weather_emoji(self, icon_code):
        """날씨 아이콘 코드에 따른 이모지 반환"""
        emoji_map = {
            '01d': '☀️', '01n': '🌙',
            '02d': '⛅', '02n': '☁️',
            '03d': '☁️', '03n': '☁️',
            '04d': '☁️', '04n': '☁️',
            '09d': '🌧️', '09n': '🌧️',
            '10d': '🌦️', '10n': '🌧️',
            '11d': '⛈️', '11n': '⛈️',
            '13d': '❄️', '13n': '❄️',
            '50d': '🌫️', '50n': '🌫️'
        }
        return emoji_map.get(icon_code, '🌤️')