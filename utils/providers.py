# utils/providers.py
from config.imports import *
import logging

logger = logging.getLogger("HybridChat")

def select_best_provider_with_priority():
    """
    우선순위에 따라 가장 적합한 프로바이더를 선택합니다.
    """
    providers = ["GeekGpt", "Liaobots", "Raycast", "Phind"]  # 우선순위 설정
    for provider in providers:
        try:
            client = Client(include_providers=[provider])
            # 테스트 요청 (챗봇의 역할에 맞는 메시지 사용)
            client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "당신은 친절한 AI 챗봇입니다. 사용자의 질문에 적절히 응답하세요."},
                ]
            )
            logger.info(f"선택된 프로바이더: {provider}")
            return client
        except Exception as e:
            logger.warning(f"{provider} 프로바이더를 사용할 수 없습니다: {str(e)}")
    raise RuntimeError("사용 가능한 프로바이더가 없습니다.")

def select_random_available_provider():
    providers = ["GeekGpt", "Liaobots", "Raycast"]
    random.shuffle(providers)  # 랜덤 순서로 섞기
    for provider in providers:
        try:
            client = Client(include_providers=[provider])
            # 실제로 간단한 테스트 요청
            client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "system", "content": "테스트 메시지입니다."}]
            )
            logger.info(f"선택된 프로바이더(랜덤): {provider}")
            return client, provider
        except Exception as e:
            logger.warning(f"{provider} 프로바이더를 사용할 수 없습니다: {str(e)}")
    raise RuntimeError("사용 가능한 프로바이더가 없습니다.")

def get_client():
    global _client_instance
    if _client_instance is None:
        client, provider_name = select_random_available_provider()
        _client_instance = client
        # 세션 상태가 사용 가능한 컨텍스트에서만 업데이트
        if hasattr(st, 'session_state'):
            st.session_state.provider_name = provider_name
    return _client_instance

_client_instance = None
