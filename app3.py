import streamlit as st
from datetime import datetime
import uuid
import threading
import logging
from supabase import create_client, Client
from config.env import SUPABASE_URL, SUPABASE_KEY  # 환경 변수에서 Supabase 정보 가져오기
import pandas as pd
import time

# Supabase 클라이언트 초기화
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 세션 상태 초기화
def init_session_state():
    if "is_logged_in" not in st.session_state:
        st.session_state.is_logged_in = False
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "chat_history" not in st.session_state:
        if st.session_state.user_id:
            # Supabase에서 사용자별 채팅 기록 가져오기
            response = supabase.table("chat_history").select("*").eq("user_id", st.session_state.user_id).order("created_at", desc=True).limit(10).execute()
            st.session_state.chat_history = []
            for r in response.data:
                if r["question"]:
                    st.session_state.chat_history.append({"role": "user", "content": r["question"]})
                if r["answer"]:
                    # answer가 JSON 문자열일 경우 파싱 시도
                    try:
                        import json
                        answer_content = json.loads(r["answer"]) if isinstance(r["answer"], str) and r["answer"].startswith("{") else r["answer"]
                        if isinstance(answer_content, dict) and "table" in answer_content:
                            answer_content["table"] = pd.DataFrame(answer_content["table"])
                        st.session_state.chat_history.append({"role": "assistant", "content": answer_content})
                    except:
                        st.session_state.chat_history.append({"role": "assistant", "content": r["answer"]})
        else:
            st.session_state.chat_history = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

# 사용자 생성 또는 조회
def create_or_get_user(nickname):
    try:
        # id는 자동 증가로 설정되어 있으므로 명시적으로 제공하지 않음
        response = supabase.table("users").upsert(
            {"nickname": nickname, "created_at": datetime.now().isoformat()},
            on_conflict="nickname"
        ).execute()
        if not response.data or "id" not in response.data[0]:
            raise ValueError("Invalid response from Supabase: missing 'id'")
        logger.info(f"User created/fetched: {response.data[0]}")
        return response.data[0]["id"], len(response.data) > 1
    except Exception as e:
        logger.error(f"Error creating/getting user: {str(e)}")
        raise

# 채팅 기록 저장
def save_chat_history(user_id, session_id, question, answer, time_taken):
    try:
        if isinstance(answer, dict) and "table" in answer and isinstance(answer["table"], pd.DataFrame):
            answer_to_save = {
                "header": answer["header"],
                "table": answer["table"].to_dict(orient="records"),
                "footer": answer["footer"]
            }
        else:
            answer_to_save = answer
        
        supabase.table("chat_history").insert({
            "user_id": user_id,
            "session_id": session_id,
            "question": question,
            "answer": answer_to_save,
            "time_taken": time_taken,
            "created_at": datetime.now().isoformat()
        }).execute()
        logger.info(f"Chat saved: {question} -> {answer}")
    except Exception as e:
        logger.error(f"Failed to save chat history: {str(e)}")

# 비동기 저장
def async_save_chat_history(user_id, session_id, question, answer, time_taken):
    threading.Thread(target=save_chat_history, args=(user_id, session_id, question, answer, time_taken)).start()

# 검색 필요 여부 판단
def needs_search(query):
    query_lower = query.strip().lower().replace(" ", "")
    if "mbti" in query_lower:
        return "mbti"
    if "다중지능" in query_lower or "multi_iq" in query_lower:
        return "multi_iq"
    return "conversation"

# 쿼리 처리
@st.cache_data
def process_query(query):
    query_type = needs_search(query)
    query_lower = query.strip().lower()
    
    if query_type == "mbti":
        return (
            "MBTI 검사를 원하시나요? ✨ 아래 사이트에서 무료로 성격 유형 검사를 할 수 있어요! 😊\n"
            "[16Personalities MBTI 검사](https://www.16personalities.com/ko/%EB%AC%B4%EB%A3%8C-%EC%84%B1%EA%B2%A9-%EC%9C%A0%ED%98%95-%EA%B2%80%EC%82%AC) 🌟\n"
            "이 사이트는 16가지 성격 유형을 기반으로 한 테스트를 제공하며, 결과에 따라 성격 설명과 인간관계 조언 등을 확인할 수 있어요! 🧠💡"
        )
    elif query_type == "multi_iq":
        return (
            "다중지능 검사를 원하시나요? 🎉 아래 사이트에서 무료로 다중지능 테스트를 해볼 수 있어요! 😄\n"
            "[Multi IQ Test](https://multiiqtest.com/) 🚀\n"
            "이 사이트는 하워드 가드너의 다중지능 이론을 기반으로 한 테스트를 제공하며, 다양한 지능 영역을 평가해줍니다! 📚✨"
        )
    else:
        return "현재는 MBTI와 다중지능 검색만 지원합니다. 'MBTI' 또는 '다중지능'을 입력해보세요! 😊"

# 대시보드 표시
def show_chat_dashboard():
    st.title("AI 챗봇 🤖")
    
    if st.button("도움말 ℹ️"):
        st.info(
            "챗봇 사용법:\n"
            "1. **MBTI 검사** ✨: 'MBTI' (예: MBTI 검사)\n"
            "2. **다중지능 검사** 🎉: '다중지능' (예: 다중지능 검사)\n\n"
            "다른 기능은 현재 비활성화 상태입니다. 😊"
        )
    
    for msg in st.session_state.chat_history[-10:]:
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
                async_save_chat_history(st.session_state.user_id, st.session_state.session_id, user_prompt, response, time_taken)
            
            except Exception as e:
                placeholder.empty()
                error_msg = f"응답을 준비하다 문제가 생겼어요: {str(e)} 😓"
                logger.error(f"오류 발생: {str(e)}", exc_info=True)
                st.markdown(error_msg, unsafe_allow_html=True)
                st.session_state.chat_history.append({"role": "assistant", "content": error_msg})

# 로그인 페이지
def show_login_page():
    st.title("로그인 🤗")
    with st.form("login_form"):
        nickname = st.text_input("닉네임", placeholder="예: 사용자")
        submit_button = st.form_submit_button("시작하기 🚀")
        
        if submit_button and nickname:
            try:
                user_id, existed = create_or_get_user(nickname)
                st.session_state.user_id = user_id
                st.session_state.is_logged_in = True
                st.session_state.chat_history = []
                st.session_state.session_id = str(uuid.uuid4())
                st.toast(f"환영합니다, {nickname}님! 🎉")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.toast(f"로그인 중 오류: {str(e)}", icon="❌")

# 메인 함수
def main():
    init_session_state()
    if not st.session_state.is_logged_in:
        show_login_page()
    else:
        show_chat_dashboard()

if __name__ == "__main__":
    st.set_page_config(page_title="AI 챗봇", page_icon="🤖")
    main()
