import streamlit as st
from g4f.client import Client

st.title("스트리밍 챗봇")

client = Client()

if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "assistant", "content": "안녕하세요! 질문해주세요."}]

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("질문을 입력하세요"):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=st.session_state["messages"],
            web_search=False,
            stream=True
        )
        챗봇_응답 = ""
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            for chunk in response:
                if hasattr(chunk, 'choices') and len(chunk.choices) > 0 and hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                    content = chunk.choices[0].delta.content
                    if content is not None:
                        챗봇_응답 += content
                        message_placeholder.markdown(챗봇_응답 + "▌")
                else:
                    print(f"경고: 예상치 못한 청크 구조: {chunk}") # 디버깅용
            message_placeholder.markdown(챗봇_응답)
        st.session_state["messages"].append({"role": "assistant", "content": 챗봇_응답})

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
