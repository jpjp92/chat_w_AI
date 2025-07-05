import requests
from requests.adapters import HTTPAdapter, Retry
from functools import lru_cache
from datetime import datetime, timedelta
import pytz

class WeatherAPI:
    def __init__(self, cache_handler, WEATHER_API_KEY, cache_ttl=600):
        self.cache = cache_handler
        self.cache_ttl = cache_ttl
        self.WEATHER_API_KEY = WEATHER_API_KEY

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

    def get_city_weather(self, city_name):
        cache_key = f"weather:{city_name}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        city_info = self.get_city_info(city_name)
        if not city_info:
            return f"'{city_name}'의 날씨 정보를 가져올 수 없습니다."
        
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {'lat': city_info["lat"], 'lon': city_info["lon"], 'appid': self.WEATHER_API_KEY, 'units': 'metric', 'lang': 'kr'}
        data = self.fetch_weather(url, params)
        if isinstance(data, str):
            return data
        weather_emojis = {'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Snow': '❄️', 'Thunderstorm': '⛈️', 'Drizzle': '🌦️', 'Mist': '🌫️'}
        weather_emoji = weather_emojis.get(data['weather'][0]['main'], '🌤️')
        result = (
            f"현재 {data['name']}, {data['sys']['country']} 날씨 {weather_emoji}\n"
            f"날씨: {data['weather'][0]['description']}\n"
            f"온도: {data['main']['temp']}°C\n"
            f"체감: {data['main']['feels_like']}°C\n"
            f"습도: {data['main']['humidity']}%\n"
            f"풍속: {data['wind']['speed']}m/s\n"
            f"더 궁금한 점 있나요? 😊"
        )
        self.cache.setex(cache_key, self.cache_ttl, result)
        return result

    def get_forecast_by_day(self, city_name, days_from_today=1):
        cache_key = f"forecast:{city_name}:{days_from_today}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        city_info = self.get_city_info(city_name)
        if not city_info:
            return f"'{city_name}'의 날씨 예보를 가져올 수 없습니다."
        
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {'lat': city_info["lat"], 'lon': city_info["lon"], 'appid': self.WEATHER_API_KEY, 'units': 'metric', 'lang': 'kr'}
        data = self.fetch_weather(url, params)
        if isinstance(data, str):
            return data
        target_date = (datetime.now() + timedelta(days=days_from_today)).strftime('%Y-%m-%d')
        forecast_text = f"{city_info['name']}의 {target_date} 날씨 예보 🌤️\n\n"
        weather_emojis = {'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Snow': '❄️', 'Thunderstorm': '⛈️', 'Drizzle': '🌦️', 'Mist': '🌫️'}
        
        found = False
        for forecast in data['list']:
            dt = datetime.fromtimestamp(forecast['dt']).strftime('%Y-%m-%d')
            if dt == target_date:
                found = True
                time_only = datetime.fromtimestamp(forecast['dt']).strftime('%H:%M')
                weather_emoji = weather_emojis.get(forecast['weather'][0]['main'], '🌤️')
                forecast_text += (
                    f"⏰ {time_only} {forecast['weather'][0]['description']} {weather_emoji} "
                    f"{forecast['main']['temp']}°C 💧{forecast['main']['humidity']}% 🌬️{forecast['wind']['speed']}m/s\n\n"
                )
        
        result = forecast_text + "더 궁금한 점 있나요? 😊" if found else f"'{city_name}'의 {target_date} 날씨 예보를 찾을 수 없습니다."
        self.cache.setex(cache_key, self.cache_ttl, result)
        return result

    def get_weekly_forecast(self, city_name):
        cache_key = f"weekly_forecast:{city_name}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        city_info = self.get_city_info(city_name)
        if not city_info:
            return f"'{city_name}'의 주간 예보를 가져올 수 없습니다."
        
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {'lat': city_info["lat"], 'lon': city_info["lon"], 'appid': self.WEATHER_API_KEY, 'units': 'metric', 'lang': 'kr'}
        data = self.fetch_weather(url, params)
        if isinstance(data, str):
            return data
        today = datetime.now().date()
        week_end = today + timedelta(days=6)
        daily_forecast = {}
        weekdays_kr = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        today_weekday = today.weekday()
        
        for forecast in data['list']:
            dt = datetime.fromtimestamp(forecast['dt']).date()
            if today <= dt <= week_end:
                dt_str = dt.strftime('%Y-%m-%d')
                if dt_str not in daily_forecast:
                    weekday_idx = (today_weekday + (dt - today).days) % 7
                    daily_forecast[dt_str] = {
                        'weekday': weekdays_kr[weekday_idx],
                        'temp_min': forecast['main']['temp_min'],
                        'temp_max': forecast['main']['temp_max'],
                        'weather': forecast['weather'][0]['description']
                    }
                else:
                    daily_forecast[dt_str]['temp_min'] = min(daily_forecast[dt_str]['temp_min'], forecast['main']['temp_min'])
                    daily_forecast[dt_str]['temp_max'] = max(daily_forecast[dt_str]['temp_max'], forecast['main']['temp_max'])
        
        today_str = today.strftime('%Y-%m-%d')
        today_weekday_str = weekdays_kr[today_weekday]
        forecast_text = f"{today_str}({today_weekday_str}) 기준 {city_info['name']}의 주간 날씨 예보 🌤️\n"
        weather_emojis = {'Clear': '☀️', 'Clouds': '☁️', 'Rain': '🌧️', 'Snow': '❄️', 'Thunderstorm': '⛈️', 'Drizzle': '🌦️', 'Mist': '🌫️'}
        
        for date, info in daily_forecast.items():
            weather_emoji = weather_emojis.get(info['weather'].split()[0], '🌤️')
            forecast_text += (
                f"\n{info['weekday']}: {info['weather']} {weather_emoji} "
                f"최저 {info['temp_min']}°C 최고 {info['temp_max']}°C\n\n"
            )
        
        result = forecast_text + "\n더 궁금한 점 있나요? 😊"
        self.cache.setex(cache_key, self.cache_ttl, result)
        return result