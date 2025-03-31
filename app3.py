import streamlit as st
from datetime import datetime
import uuid
import pandas as pd
import time

# MBTI 유형별 설명 딕셔너리
mbti_descriptions = {
    "ISTJ": "(현실주의자) 🏛️📚🧑‍⚖️: 원칙을 중시하며 꼼꼼한 계획으로 목표를 달성!",
    "ISFJ": "(따뜻한 수호자) 🛡️🧸💖: 타인을 배려하며 헌신적인 도움을 주는 성격!",
    "INFJ": "(신비로운 조언자) 🌿🔮📖: 깊은 통찰력으로 사람들에게 영감을 주는 이상주의자!",
    "INTJ": "(전략가) 🧠♟️📈: 미래를 설계하며 목표를 향해 나아가는 마스터마인드!",
    "ISTP": "(만능 재주꾼) 🔧🕶️🏍️: 문제를 실질적으로 해결하는 실용적인 모험가!",
    "ISFP": "(예술가) 🎨🎵🦋: 감성을 표현하며 자유로운 삶을 추구하는 예술가!",
    "INFP": "(이상주의자) 🌌📜🕊️: 내면의 가치를 중시하며 세상을 더 나은 곳으로 만드는 몽상가!",
    "INTP": "(논리적인 철학자) 🤔📖⚙️: 호기심 많고 논리적으로 세상을 탐구하는 사색가!",
    "ESTP": "(모험가) 🏎️🔥🎤: 순간을 즐기며 도전과 모험을 사랑하는 활동가!",
    "ESFP": "(사교적인 연예인) 🎭🎤🎊: 사람들과 함께하며 분위기를 띄우는 파티의 중심!",
    "ENFP": "(자유로운 영혼) 🌈🚀💡: 창의적인 아이디어로 세상을 밝히는 열정적인 영혼!",
    "ENTP": "(토론가) 🗣️⚡♟️: 새로운 아이디어를 탐구하며 논쟁을 즐기는 혁신가!",
    "ESTJ": "(엄격한 관리자) 🏗️📊🛠️: 체계적으로 목표를 달성하는 리더십의 대가!",
    "ESFJ": "(친절한 외교관) 💐🤗🏡: 사람들을 연결하며 따뜻한 공동체를 만드는 외교관!",
    "ENFJ": "(열정적인 리더) 🌟🎤🫶: 타인을 이끌며 긍정적인 변화를 만드는 카리스마 리더!",
    "ENTJ": "(야망가) 👑📈🔥: 목표를 향해 돌진하며 큰 그림을 그리는 지휘관!"
}

# 다중지능 유형별 설명 및 직업 딕셔너리
multi_iq_descriptions = {
    "언어지능": {
        "description": "📝📚📢: 말과 글을 통해 생각을 표현하는 데 탁월!",
        "jobs": "소설가, 시인, 작가, 논설 / 동화 작가, 방송작가, 영화대본작가, 웹툰 작가 / 아나운서, 리포터, 성우 / 교사, 교수, 강사, 독서 지도사 / 언어치료사, 심리치료사, 구연동화가"
    },
    "논리수학지능": {
        "description": "🧮📊🧠: 분석적 사고와 문제 해결 능력이 뛰어남!",
        "jobs": "과학자, 물리학자, 수학자 / 의료공학, 전자공학, 컴퓨터 공학, 항공우주공학 / 애널리스트, 경영 컨설팅, 회계사, 세무사 / 투자분석가, M&A 전문가 / IT 컨설팅, 컴퓨터 프로그래머, web 개발 / 통신 신호처리, 통계학, AI 개발, 정보처리, 빅데이터 업무 / 은행원, 금융기관, 강사, 비평가, 논설 / 변호사, 변리사, 검사, 판사 / 의사, 건축가, 설계사"
    },
    "시각공간지능": {
        "description": "🎨📸🏛️: 그림과 디자인으로 공간을 아름답게 표현!",
        "jobs": "사진사, 촬영기사, 만화가, 애니메이션, 화가, 아티스트 / 건축 설계, 인테리어, 디자이너 / 지도 제작, 엔지니어, 발명가 / 전자공학, 기계공학, 통신공학, 산업공학, 로봇 개발 / 영화감독, 방송 피디, 푸드스타일리스트 / 광고 제작, 인쇄 업무"
    },
    "음악지능": {
        "description": "🎶🎧🎸: 소리와 리듬을 느끼고 창조하는 음악적 재능!",
        "jobs": "음악교사, 음향사, 작곡가, 작사가, 편곡가, 가수, 성악가 / 악기 연주 / 동시통역사, 성우 / 뮤지컬 배우 / 발레, 무용 / 음향 부문, 연예 기획사 / DJ, 개인 음악 방송, 가수 매니지먼트"
    },
    "신체운동지능": {
        "description": "🏀🤸‍♂️🏆: 몸을 활용해 스포츠와 움직임에서 두각!",
        "jobs": "외과의사, 치기공사, 한의사, 수의사, 간호사, 대체의학 / 물리치료사, 작업치료사 / 악기 연주, 성악가, 가수, 무용, 연극 / 스포츠, 체육교사, 모델 / 경찰, 경호원, 군인, 소방관 / 농업, 임업, 수산업, 축산업 / 공예, 액세서리 제작, 가구 제작"
    },
    "대인관계지능": {
        "description": "🤝🗣️💬: 사람들과 소통하며 관계를 잘 맺는 능력!",
        "jobs": "변호사, 검사, 판사, 법무사 / 교사, 교수, 강사 / 홍보 업무, 마케팅 / 지배인, 비서, 승무원, 판매업무 / 기자, 리포터, 보험서비스 / 외교관, 국제공무원, 경찰 / 병원코디네이터, 간호사 / 호텔리어, 학습지 교사, 웨딩플래너, 웃음치료사, 성직자"
    },
    "개인내적지능": {
        "description": "🧘‍♂️💭📖: 자신을 깊이 이해하고 성찰하는 내면의 힘!",
        "jobs": "변호사, 검사, 판사, 변리사, 평론가, 논설 / 교사, 교수, 심리상담사 / 스포츠 감독, 코치, 심판, 스포츠 해설가 / 협상가, CEO, CTO, 컨설팅, 마케팅, 회사 경영 / 기자, 아나운서, 요리사, 심사위원 / 의사, 제약 분야 연구원 / 성직자, 철학자, 투자분석가, 자산관리 / 영화감독, 작가, 건축가"
    },
    "자연탐구지능": {
        "description": "🌿🐦🌍: 자연과 동물을 사랑하며 환경에 민감한 재능!",
        "jobs": "의사, 간호사, 물리치료, 임상병리 / 수의사, 동물 사육, 곤충 사육 / 건축 설계, 감리, 측량사, 조경 디자인 / 천문학자, 지질학자 / 생명공학, 기계 공학, 생물공학, 전자공학 / 의사, 간호사, 약제사, 임상병리 / 특수작물 재배, 농업, 임업, 축산업, 원예, 플로리스트"
    }
}

# MBTI 전체 설명 (변경 없음)
mbti_full_description = """
### 📝 MBTI 유형별 한 줄 설명
#### 🔥 외향형 (E) vs ❄️ 내향형 (I)  
- **E (외향형)** 🎉🗣️🚀🌞: 사람들과 어울리며 에너지를 얻는 사교적인 성격!  
- **I (내향형)** 📚🛋️🌙🤫: 혼자만의 시간을 즐기며 내면에 집중하는 성격!  
#### 📊 직관형 (N) vs 🧐 감각형 (S)  
- **N (직관형)** 💡✨🎨🔮: 창의적이고 큰 그림을 보며 아이디어를 중시!  
- **S (감각형)** 🔎📏🛠️🍽️: 현실적이고 구체적인 정보를 바탕으로 행동!  
#### 🤝 감정형 (F) vs ⚖️ 사고형 (T)  
- **F (감정형)** ❤️🥰🌸🫂: 공감과 사람 중심으로 따뜻한 결정을 내림!  
- **T (사고형)** 🧠⚙️📊📏: 논리와 객관적 판단으로 문제를 해결!  
#### ⏳ 판단형 (J) vs 🌊 인식형 (P)  
- **J (계획형)** 📅📌📝✅: 체계적이고 계획적으로 일을 처리하는 스타일!  
- **P (즉흥형)** 🎭🎢🌪️🌍: 유연하고 변화에 잘 적응하는 자유로운 스타일!  
#### 🎭 MBTI 유형별 한 줄 설명  
- ✅ **ISTJ** (현실주의자) 🏛️📚🧑‍⚖️: 원칙을 중시하며 꼼꼼한 계획으로 목표를 달성!  
- ✅ **ISFJ** (따뜻한 수호자) 🛡️🧸💖: 타인을 배려하며 헌신적인 도움을 주는 성격!  
- ✅ **INFJ** (신비로운 조언자) 🌿🔮📖: 깊은 통찰력으로 사람들에게 영감을 주는 이상주의자!  
- ✅ **INTJ** (전략가) 🧠♟️📈: 미래를 설계하며 목표를 향해 나아가는 마스터마인드!  
- ✅ **ISTP** (만능 재주꾼) 🔧🕶️🏍️: 문제를 실질적으로 해결하는 실용적인 모험가!  
- ✅ **ISFP** (예술가) 🎨🎵🦋: 감성을 표현하며 자유로운 삶을 추구하는 예술가!  
- ✅ **INFP** (이상주의자) 🌌📜🕊️: 내면의 가치를 중시하며 세상을 더 나은 곳으로 만드는 몽상가!  
- ✅ **INTP** (논리적인 철학자) 🤔📖⚙️: 호기심 많고 논리적으로 세상을 탐구하는 사색가!  
- ✅ **ESTP** (모험가) 🏎️🔥🎤: 순간을 즐기며 도전과 모험을 사랑하는 활동가!  
- ✅ **ESFP** (사교적인 연예인) 🎭🎤🎊: 사람들과 함께하며 분위기를 띄우는 파티의 중심!  
- ✅ **ENFP** (자유로운 영혼) 🌈🚀💡: 창의적인 아이디어로 세상을 밝히는 열정적인 영혼!  
- ✅ **ENTP** (토론가) 🗣️⚡♟️: 새로운 아이디어를 탐구하며 논쟁을 즐기는 혁신가!  
- ✅ **ESTJ** (엄격한 관리자) 🏗️📊🛠️: 체계적으로 목표를 달성하는 리더십의 대가!  
- ✅ **ESFJ** (친절한 외교관) 💐🤗🏡: 사람들을 연결하며 따뜻한 공동체를 만드는 외교관!  
- ✅ **ENFJ** (열정적인 리더) 🌟🎤🫶: 타인을 이끌며 긍정적인 변화를 만드는 카리스마 리더!  
- ✅ **ENTJ** (야망가) 👑📈🔥: 목표를 향해 돌진하며 큰 그림을 그리는 지휘관!
"""

# 다중지능 전체 설명
multi_iq_descriptions = {
    "언어지능": {
        "description": "📝📚📢: 말과 글을 통해 생각을 표현하는 데 탁월!\n",
        "jobs": "소설가, 시인, 작가, 논설 / 동화 작가, 방송작가, 영화대본작가, 웹툰 작가 / 아나운서, 리포터, 성우 / 교사, 교수, 강사, 독서 지도사 / 언어치료사, 심리치료사, 구연동화가"
    },
    "논리수학지능": {
        "description": "🧮📊🧠: 분석적 사고와 문제 해결 능력이 뛰어남!\n",
        "jobs": "과학자, 물리학자, 수학자 / 의료공학, 전자공학, 컴퓨터 공학, 항공우주공학 / 애널리스트, 경영 컨설팅, 회계사, 세무사 / 투자분석가, M&A 전문가 / IT 컨설팅, 컴퓨터 프로그래머, web 개발 / 통신 신호처리, 통계학, AI 개발, 정보처리, 빅데이터 업무 / 은행원, 금융기관, 강사, 비평가, 논설 / 변호사, 변리사, 검사, 판사 / 의사, 건축가, 설계사"
    },
    "시각공간지능": {
        "description": "🎨📸🏛️: 그림과 디자인으로 공간을 아름답게 표현!\n",
        "jobs": "사진사, 촬영기사, 만화가, 애니메이션, 화가, 아티스트 / 건축 설계, 인테리어, 디자이너 / 지도 제작, 엔지니어, 발명가 / 전자공학, 기계공학, 통신공학, 산업공학, 로봇 개발 / 영화감독, 방송 피디, 푸드스타일리스트 / 광고 제작, 인쇄 업무"
    },
    "음악지능": {
        "description": "🎶🎧🎸: 소리와 리듬을 느끼고 창조하는 음악적 재능!\n",
        "jobs": "음악교사, 음향사, 작곡가, 작사가, 편곡가, 가수, 성악가 / 악기 연주 / 동시통역사, 성우 / 뮤지컬 배우 / 발레, 무용 / 음향 부문, 연예 기획사 / DJ, 개인 음악 방송, 가수 매니지먼트"
    },
    "신체운동지능": {
        "description": "🏀🤸‍♂️🏆: 몸을 활용해 스포츠와 움직임에서 두각!\n",
        "jobs": "외과의사, 치기공사, 한의사, 수의사, 간호사, 대체의학 / 물리치료사, 작업치료사 / 악기 연주, 성악가, 가수, 무용, 연극 / 스포츠, 체육교사, 모델 / 경찰, 경호원, 군인, 소방관 / 농업, 임업, 수산업, 축산업 / 공예, 액세서리 제작, 가구 제작"
    },
    "대인관계지능": {
        "description": "🤝🗣️💬: 사람들과 소통하며 관계를 잘 맺는 능력!\n",
        "jobs": "변호사, 검사, 판사, 법무사 / 교사, 교수, 강사 / 홍보 업무, 마케팅 / 지배인, 비서, 승무원, 판매업무 / 기자, 리포터, 보험서비스 / 외교관, 국제공무원, 경찰 / 병원코디네이터, 간호사 / 호텔리어, 학습지 교사, 웨딩플래너, 웃음치료사, 성직자"
    },
    "개인내적지능": {
        "description": "🧘‍♂️💭📖: 자신을 깊이 이해하고 성찰하는 내면의 힘!\n",
        "jobs": "변호사, 검사, 판사, 변리사, 평론가, 논설 / 교사, 교수, 심리상담사 / 스포츠 감독, 코치, 심판, 스포츠 해설가 / 협상가, CEO, CTO, 컨설팅, 마케팅, 회사 경영 / 기자, 아나운서, 요리사, 심사위원 / 의사, 제약 분야 연구원 / 성직자, 철학자, 투자분석가, 자산관리 / 영화감독, 작가, 건축가"
    },
    "자연탐구지능": {
        "description": "🌿🐦🌍: 자연과 동물을 사랑하며 환경에 민감한 재능!\n",
        "jobs": "의사, 간호사, 물리치료, 임상병리 / 수의사, 동물 사육, 곤충 사육 / 건축 설계, 감리, 측량사, 조경 디자인 / 천문학자, 지질학자 / 생명공학, 기계 공학, 생물공학, 전자공학 / 의사, 간호사, 약제사, 임상병리 / 특수작물 재배, 농업, 임업, 축산업, 원예, 플로리스트"
    }
}
# multi_iq_full_description = """
# ### 🎨 다중지능 유형별 한 줄 설명 및 추천 직업  
# - 📖 **언어 지능** 📝📚📢: 말과 글을 통해 생각을 표현하는 데 탁월!\n  
#     - **추천 직업**: 소설가, 시인, 작가, 논설 / 동화 작가, 방송작가, 영화대본작가, 웹툰 작가 / 아나운서, 리포터, 성우 / 교사, 교수, 강사, 독서 지도사 / 언어치료사, 심리치료사, 구연동화가\n  
# - 🔢 **논리-수학 지능** 🧮📊🧠: 분석적 사고와 문제 해결 능력이 뛰어남!\n  
#     - **추천 직업**: 과학자, 물리학자, 수학자 / 의료공학, 전자공학, 컴퓨터 공학, 항공우주공학 / 애널리스트, 경영 컨설팅, 회계사, 세무사 / 투자분석가, M&A 전문가 / IT 컨설팅, 컴퓨터 프로그래머, web 개발 / 통신 신호처리, 통계학, AI 개발, 정보처리, 빅데이터 업무 / 은행원, 금융기관, 강사, 비평가, 논설 / 변호사, 변리사, 검사, 판사 / 의사, 건축가, 설계사 \n  
# - 🎨 **시각-공간 지능** 🎨📸🏛️: 그림과 디자인으로 공간을 아름답게 표현!\n  
#     - **추천 직업**: 사진사, 촬영기사, 만화가, 애니메이션, 화가, 아티스트 / 건축 설계, 인테리어, 디자이너 / 지도 제작, 엔지니어, 발명가 / 전자공학, 기계공학, 통신공학, 산업공학, 로봇 개발 / 영화감독, 방송 피디, 푸드스타일리스트 / 광고 제작, 인쇄 업무  
# - 🎵 **음악 지능** 🎶🎧🎸: 소리와 리듬을 느끼고 창조하는 음악적 재능!  
#     - **추천 직업**: 음악교사, 음향사, 작곡가, 작사가, 편곡가, 가수, 성악가 / 악기 연주 / 동시통역사, 성우 / 뮤지컬 배우 / 발레, 무용 / 음향 부문, 연예 기획사 / DJ, 개인 음악 방송, 가수 매니지먼트  
# - 🏃 **신체-운동 지능** 🏀🤸‍♂️🏆: 몸을 활용해 스포츠와 움직임에서 두각!  
#     - **추천 직업**: 외과의사, 치기공사, 한의사, 수의사, 간호사, 대체의학 / 물리치료사, 작업치료사 / 악기 연주, 성악가, 가수, 무용, 연극 / 스포츠, 체육교사, 모델 / 경찰, 경호원, 군인, 소방관 / 농업, 임업, 수산업, 축산업 / 공예, 액세서리 제작, 가구 제작  
# - 🤝 **대인관계 지능** 🤝🗣️💬: 사람들과 소통하며 관계를 잘 맺는 능력!  
#     - **추천 직업**: 변호사, 검사, 판사, 법무사 / 교사, 교수, 강사 / 홍보 업무, 마케팅 / 지배인, 비서, 승무원, 판매업무 / 기자, 리포터, 보험서비스 / 외교관, 국제공무원, 경찰 / 병원코디네이터, 간호사 / 호텔리어, 학습지 교사, 웨딩플래너, 웃음치료사, 성직자  
# - 🧘 **개인 내적 지능** 🧘‍♂️💭📖: 자신을 깊이 이해하고 성찰하는 내면의 힘!  
#     - **추천 직업**: 변호사, 검사, 판사, 변리사, 평론가, 논설 / 교사, 교수, 심리상담사 / 스포츠 감독, 코치, 심판, 스포츠 해설가 / 협상가, CEO, CTO, 컨설팅, 마케팅, 회사 경영 / 기자, 아나운서, 요리사, 심사위원 / 의사, 제약 분야 연구원 / 성직자, 철학자, 투자분석가, 자산관리 / 영화감독, 작가, 건축가  
# - 🌱 **자연 탐구 지능** 🌿🐦🌍: 자연과 동물을 사랑하며 환경에 민감한 재능!  
#     - **추천 직업**: 의사, 간호사, 물리치료, 임상병리 / 수의사, 동물 사육, 곤충 사육 / 건축 설계, 감리, 측량사, 조경 디자인 / 천문학자, 지질학자 / 생명공학, 기계 공학, 생물공학, 전자공학 / 의사, 간호사, 약제사, 임상병리 / 특수작물 재배, 농업, 임업, 축산업, 원예, 플로리스트  
# """

# 세션 상태 초기화
def init_session_state():
    if "is_logged_in" not in st.session_state:
        st.session_state.is_logged_in = False
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

# 검색 필요 여부 판단
def needs_search(query):
    query_lower = query.strip().lower().replace(" ", "")
    if "mbti" in query_lower:
        if "유형" in query_lower or "설명" in query_lower:
            return "mbti_types"
        return "mbti"
    if "다중지능" in query_lower or "multi_iq" in query_lower:
        if "유형" in query_lower or "설명" in query_lower:
            return "multi_iq_types"
        if "직업" in query_lower or "추천" in query_lower:
            return "multi_iq_jobs"
        return "multi_iq"
    return "conversation"

# 쿼리 처리
@st.cache_data
def process_query(query):
    query_type = needs_search(query)
    query_lower = query.strip().lower().replace(" ", "")
    
    if query_type == "mbti":
        return (
            "MBTI 검사를 원하시나요? ✨ 아래 사이트에서 무료로 성격 유형 검사를 할 수 있어요! 😊\n"
            "[16Personalities MBTI 검사](https://www.16personalities.com/ko/%EB%AC%B4%EB%A3%8C-%EC%84%B1%EA%B2%A9-%EC%9C%A0%ED%98%95-%EA%B2%80%EC%82%AC) 🌟\n"
            "이 사이트는 16가지 성격 유형을 기반으로 한 테스트를 제공하며, 결과에 따라 성격 설명과 인간관계 조언 등을 확인할 수 있어요! 💡"
        )
    elif query_type == "mbti_types":
        specific_type = query_lower.replace("mbti", "").replace("유형", "").replace("설명", "").strip().upper()
        if specific_type in mbti_descriptions:
            return f"### 🎭 {specific_type} 한 줄 설명\n- ✅ **{specific_type}** {mbti_descriptions[specific_type]}"
        return mbti_full_description
    elif query_type == "multi_iq":
        return (
            "다중지능 검사를 원하시나요? 🎉 아래 사이트에서 무료로 다중지능 테스트를 해볼 수 있어요! 😄\n"
            "[Multi IQ Test](https://multiiqtest.com/) 🚀\n"
            "이 사이트는 하워드 가드너의 다중지능 이론을 기반으로 한 테스트를 제공하며, 다양한 지능 영역을 평가해줍니다! 📚✨"
        )
    elif query_type == "multi_iq_types":
        specific_type = query_lower.replace("다중지능", "").replace("multi_iq", "").replace("유형", "").replace("설명", "").strip().replace(" ", "")
        if specific_type in multi_iq_descriptions:
            return f"### 🎨 {specific_type.replace('지능', ' 지능')} 한 줄 설명\n- 📖 **{specific_type.replace('지능', ' 지능')}** {multi_iq_descriptions[specific_type]['description']}"
        return multi_iq_full_description
    elif query_type == "multi_iq_jobs":
        specific_type = query_lower.replace("다중지능", "").replace("multi_iq", "").replace("직업", "").replace("추천", "").strip().replace(" ", "")
        if specific_type in multi_iq_descriptions:
            return f"### 🎨 {specific_type.replace('지능', ' 지능')} 추천 직업\n- 📖 **{specific_type.replace('지능', ' 지능')}**: {multi_iq_descriptions[specific_type]['description']}\n- **추천 직업**: {multi_iq_descriptions[specific_type]['jobs']}"
        return multi_iq_full_description
    else:
        return "현재는 MBTI와 다중지능 검색만 지원합니다. 'MBTI' 또는 '다중지능'을 입력해보세요! 😊\n유형별 설명을 보려면 'MBTI 유형' 또는 '다중지능 유형'을 입력해 보세요!"

# 대시보드 표시
def show_chat_dashboard():
    st.title("MBTI/다중지능 🎨")
    
    if st.button("도움말 ℹ️"):
        st.info(
            """
            **📌 사용방법**  
            1. **MBTI 검사** ✨: 'MBTI' (예: MBTI 검사)  
            2. **다중지능 검사** 🎉: '다중지능' (예: 다중지능 검사)  
            3. **유형 설명 보기** 📖: 'MBTI 유형' 또는 '다중지능 유형' 입력   
            """
        )
    
    # 최근 5개 메시지만 표시 (메모리 최적화)
    for msg in st.session_state.chat_history[-5:]:
        with st.chat_message(msg['role']):
            if isinstance(msg['content'], dict) and "table" in msg['content']:
                st.markdown(msg['content']['header'], unsafe_allow_html=True)
                st.dataframe(msg['content']['table'])
                st.markdown(msg['content']['footer'], unsafe_allow_html=True)
            else:
                st.markdown(msg['content'], unsafe_allow_html=True)
    
    if user_prompt := st.chat_input("질문해 주세요!"):
        st.chat_message("user").markdown(user_prompt)
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("응답을 준비 중이에요.. ⏳")
            try:
                start_time = time.time()
                response = process_query(user_prompt)
                time_taken = round(time.time() - start_time, 2)
                
                placeholder.empty()
                if isinstance(response, dict) and "table" in response:
                    st.markdown(response['header'], unsafe_allow_html=True)
                    st.dataframe(response['table'])
                    st.markdown(response['footer'], unsafe_allow_html=True)
                else:
                    st.markdown(response, unsafe_allow_html=True)
                
                st.session_state.chat_history.append({"role": "assistant", "content": response})
            
            except Exception as e:
                placeholder.empty()
                error_msg = f"응답을 준비하다 문제가 생겼어요: {str(e)} 😓"
                st.markdown(error_msg, unsafe_allow_html=True)
                st.session_state.chat_history.append({"role": "assistant", "content": error_msg})

# 로그인 페이지
def show_login_page():
    st.title("로그인 🤗")
    with st.form("login_form"):
        nickname = st.text_input("닉네임", placeholder="예: 박해피")
        submit_button = st.form_submit_button("시작하기 🚀")
        
        if submit_button and nickname:
            st.session_state.user_id = nickname  # Supabase 대신 닉네임 사용
            st.session_state.is_logged_in = True
            st.session_state.chat_history = []
            st.session_state.session_id = str(uuid.uuid4())
            st.toast(f"환영합니다, {nickname}님! 🎉")
            time.sleep(1)
            st.rerun()

# 메인 함수
def main():
    init_session_state()
    if not st.session_state.is_logged_in:
        show_login_page()
    else:
        show_chat_dashboard()

if __name__ == "__main__":
    st.set_page_config(page_title="MBTI/다중지능", page_icon="📊")
    main()
