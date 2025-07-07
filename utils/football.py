import requests
import time
import pandas as pd

class FootballAPI:
    def __init__(self, api_key, cache_handler, cache_ttl=600):
        self.api_key = api_key
        self.base_url = "https://api.football-data.org/v4/competitions"
        self.cache = cache_handler
        self.cache_ttl = cache_ttl

    def fetch_league_standings(self, league_code, league_name):
        cache_key = f"league_standings:{league_code}"
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            return cached_data

        url = f"{self.base_url}/{league_code}/standings"
        headers = {'X-Auth-Token': self.api_key}
        
        try:
            time.sleep(1)
            response = requests.get(url, headers=headers, timeout=2)
            response.raise_for_status()
            data = response.json()
            
            standings = data['standings'][0]['table'] if league_code not in ["CL"] else data['standings']
            if league_code in ["CL"]:
                standings_data = []
                for group in standings:
                    for team in group['table']:
                        standings_data.append({
                            '순위': team['position'],
                            '그룹': group['group'],
                            '팀': team['team']['name'],
                            '경기': team['playedGames'],
                            '승': team['won'],
                            '무': team['draw'],
                            '패': team['lost'],
                            '득점': team['goalsFor'],
                            '실점': team['goalsAgainst'],
                            '득실차': team['goalsFor'] - team['goalsAgainst'],
                            '포인트': team['points']
                        })
                df = pd.DataFrame(standings_data)
            else:
                df = pd.DataFrame([
                    {
                        '순위': team['position'],
                        '팀': team['team']['name'],
                        '경기': team['playedGames'],
                        '승': team['won'],
                        '무': team['draw'],
                        '패': team['lost'],
                        '득점': team['goalsFor'],
                        '실점': team['goalsAgainst'],
                        '득실차': team['goalsFor'] - team['goalsAgainst'],
                        '포인트': team['points']
                    } for team in standings
                ])
            
            result = {"league_name": league_name, "data": df}
            self.cache.setex(cache_key, self.cache_ttl, result)
            return result
        
        except requests.exceptions.RequestException as e:
            return {"league_name": league_name, "error": f"{league_name} 리그 순위를 가져오는 중 문제가 발생했습니다: {str(e)} 😓"}

    def fetch_league_scorers(self, league_code, league_name):
        cache_key = f"league_scorers:{league_code}"
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            return cached_data

        url = f"{self.base_url}/{league_code}/scorers"
        headers = {'X-Auth-Token': self.api_key}
        
        try:
            time.sleep(1)
            response = requests.get(url, headers=headers, timeout=2)
            response.raise_for_status()
            data = response.json()
            
            scorers = [{"순위": i+1, "선수": s['player']['name'], "팀": s['team']['name'], "득점": s['goals']} 
                       for i, s in enumerate(data['scorers'][:10])]
            df = pd.DataFrame(scorers)
            result = {"league_name": league_name, "data": df}
            self.cache.setex(cache_key, self.cache_ttl, result)
            return result
        
        except requests.exceptions.RequestException as e:
            return {"league_name": league_name, "error": f"{league_name} 리그 득점순위 정보를 가져오는 중 문제가 발생했습니다: {str(e)} 😓"}

    def fetch_championsleague_knockout_matches(self):
        url = f"{self.base_url}/CL/matches"
        headers = {'X-Auth-Token': self.api_key}
        KNOCKOUT_STAGES = {
            "LAST_16": "16강",
            "QUARTER_FINALS": "8강",
            "SEMI_FINALS": "준결승",
            "FINAL": "결승",
            "THIRD_PLACE": "3위 결정전"
        }
        try:
            response = requests.get(url, headers=headers, timeout=3)
            response.raise_for_status()
            data = response.json()
            
            knockout_matches = [
                m for m in data['matches']
                if m.get('stage') in KNOCKOUT_STAGES
            ]
            results = []
            for m in knockout_matches:
                home = m.get('homeTeam', {}).get('name', '미정')
                away = m.get('awayTeam', {}).get('name', '미정')
                
                score_home = m.get('score', {}).get('fullTime', {}).get('home')
                score_away = m.get('score', {}).get('fullTime', {}).get('away')
                
                if score_home is None or score_away is None:
                    score_home = m.get('score', {}).get('halfTime', {}).get('home')
                    score_away = m.get('score', {}).get('halfTime', {}).get('away')
                
                if score_home is None or score_away is None:
                    score_home = m.get('score', {}).get('extraTime', {}).get('home')
                    score_away = m.get('score', {}).get('extraTime', {}).get('away')
                
                if score_home is None or score_away is None:
                    score_home = m.get('score', {}).get('penalties', {}).get('home')
                    score_away = m.get('score', {}).get('penalties', {}).get('away')
            
                match_status = m.get('status', '')
                
                if match_status == 'FINISHED':
                    score_str = f"{score_home if score_home is not None else 0} : {score_away if score_away is not None else 0}"
                elif match_status == 'SCHEDULED':
                    score_str = "예정된 경기"
                else:
                    score_str = f"{score_home if score_home is not None else '-'} : {score_away if score_away is not None else '-'}"
                
                stage = KNOCKOUT_STAGES.get(m.get('stage', ''), '미정')
                
                results.append({
                    "라운드": stage,
                    "날짜": m.get('utcDate', '')[:10] if m.get('utcDate') else '미정',
                    "홈팀": home,
                    "원정팀": away,
                    "스코어": score_str,
                    "상태": match_status
                })
            return results
        except Exception as e:
            return f"챔피언스리그 토너먼트 경기 결과를 가져오는 중 오류: {str(e)}"

