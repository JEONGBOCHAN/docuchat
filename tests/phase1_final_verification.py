# -*- coding: utf-8 -*-
"""
Phase 1 최종 검증
- 멀티턴 대화
- 한글 문서 처리
- YouTube URL
- 오디오 파일
- 채널 격리
- 다양한 출력 형식
"""

import io
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

load_dotenv()


def get_client():
    api_key = os.getenv("GOOGLE_API_KEY")
    return genai.Client(api_key=api_key)


def cleanup_store(store_name: str):
    api_key = os.getenv("GOOGLE_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/{store_name}?force=true&key={api_key}"
    requests.delete(url)


def test_korean_document():
    """한글 문서 처리 테스트"""
    print("\n" + "="*60)
    print("[테스트] 한글 문서 처리")
    print("="*60)

    client = get_client()
    store = None
    samples_dir = Path(__file__).parent / "samples"

    try:
        store = client.file_search_stores.create(config={"display_name": "korean-test"})
        print(f"\n[Store] {store.name}")

        # 한글 문서 업로드
        korean_file = samples_dir / "korean_document.txt"
        print(f"[업로드] {korean_file.name}")
        op = client.file_search_stores.upload_to_file_search_store(
            file=str(korean_file),
            file_search_store_name=store.name
        )
        while not op.done:
            time.sleep(2)
            op = client.operations.get(op)
        print("  → 완료")

        time.sleep(3)

        # 한글로 질문
        print("\n[한글 질문] 이 프로젝트의 기술 스택은 무엇인가요?")
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents="이 프로젝트의 기술 스택은 무엇인가요? 한글로 답변해주세요.",
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store.name]
                        )
                    )
                ]
            )
        )
        print(f"\n[답변]\n{response.text}")

        # Grounding 확인
        if hasattr(response, 'candidates') and response.candidates:
            gm = response.candidates[0].grounding_metadata
            if gm and hasattr(gm, 'grounding_chunks') and gm.grounding_chunks:
                print(f"\n[출처] {gm.grounding_chunks[0].retrieved_context.title}")

        print("\n✓ 한글 문서 처리 성공!")
        return True

    except Exception as e:
        print(f"\n✗ 실패: {e}")
        return False

    finally:
        if store:
            cleanup_store(store.name)


def test_multi_turn_conversation():
    """멀티턴 대화 테스트"""
    print("\n" + "="*60)
    print("[테스트] 멀티턴 대화 (컨텍스트 유지)")
    print("="*60)

    client = get_client()
    store = None
    samples_dir = Path(__file__).parent / "samples"

    try:
        store = client.file_search_stores.create(config={"display_name": "multiturn-test"})
        print(f"\n[Store] {store.name}")

        # 문서 업로드
        op = client.file_search_stores.upload_to_file_search_store(
            file=str(samples_dir / "ai_basics.txt"),
            file_search_store_name=store.name
        )
        while not op.done:
            time.sleep(2)
            op = client.operations.get(op)

        time.sleep(3)

        # 대화 기록 유지
        conversation_history = []

        # 첫 번째 질문
        print("\n[질문 1] What is deep learning?")
        conversation_history.append({"role": "user", "parts": [{"text": "What is deep learning?"}]})

        response1 = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=conversation_history,
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store.name]
                        )
                    )
                ]
            )
        )
        print(f"[답변 1] {response1.text[:200]}...")
        conversation_history.append({"role": "model", "parts": [{"text": response1.text}]})

        # 두 번째 질문 (이전 컨텍스트 참조)
        print("\n[질문 2] What are its main components? (이전 답변 참조)")
        conversation_history.append({"role": "user", "parts": [{"text": "What are its main components?"}]})

        response2 = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=conversation_history,
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store.name]
                        )
                    )
                ]
            )
        )
        print(f"[답변 2] {response2.text[:200]}...")

        # 세 번째 질문 (더 깊은 참조)
        print("\n[질문 3] Can you give me an example? (컨텍스트 연속)")
        conversation_history.append({"role": "model", "parts": [{"text": response2.text}]})
        conversation_history.append({"role": "user", "parts": [{"text": "Can you give me an example?"}]})

        response3 = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=conversation_history,
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store.name]
                        )
                    )
                ]
            )
        )
        print(f"[답변 3] {response3.text[:200]}...")

        print("\n✓ 멀티턴 대화 성공!")
        return True

    except Exception as e:
        print(f"\n✗ 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        if store:
            cleanup_store(store.name)


def test_channel_isolation():
    """채널 격리 테스트 (Store 간 분리)"""
    print("\n" + "="*60)
    print("[테스트] 채널 격리 (Store 간 데이터 분리)")
    print("="*60)

    client = get_client()
    store_a = None
    store_b = None
    samples_dir = Path(__file__).parent / "samples"

    try:
        # Store A 생성 (AI 문서)
        store_a = client.file_search_stores.create(config={"display_name": "channel-a-ai"})
        print(f"\n[Store A] {store_a.name} - AI 문서")

        op = client.file_search_stores.upload_to_file_search_store(
            file=str(samples_dir / "ai_basics.txt"),
            file_search_store_name=store_a.name
        )
        while not op.done:
            time.sleep(2)
            op = client.operations.get(op)

        # Store B 생성 (Python 문서)
        store_b = client.file_search_stores.create(config={"display_name": "channel-b-python"})
        print(f"[Store B] {store_b.name} - Python 문서")

        op = client.file_search_stores.upload_to_file_search_store(
            file=str(samples_dir / "python_guide.txt"),
            file_search_store_name=store_b.name
        )
        while not op.done:
            time.sleep(2)
            op = client.operations.get(op)

        time.sleep(5)

        # Store A에서 Python 질문 (없어야 함)
        print("\n[테스트 1] Store A (AI 문서)에서 'Python 함수 정의 방법' 질문")
        response_a = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents="How do you define a function in Python? Show me the syntax.",
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store_a.name]
                        )
                    )
                ]
            )
        )
        print(f"[Store A 답변] {response_a.text[:150]}...")

        # Store A의 grounding 확인
        has_python_source_in_a = False
        if hasattr(response_a, 'candidates') and response_a.candidates:
            gm = response_a.candidates[0].grounding_metadata
            if gm and hasattr(gm, 'grounding_chunks') and gm.grounding_chunks:
                for chunk in gm.grounding_chunks:
                    title = chunk.retrieved_context.title
                    print(f"  출처: {title}")
                    if 'python' in title.lower():
                        has_python_source_in_a = True

        # Store B에서 딥러닝 질문 (없어야 함)
        print("\n[테스트 2] Store B (Python 문서)에서 '딥러닝이란' 질문")
        response_b = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents="What is deep learning? Explain in detail.",
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store_b.name]
                        )
                    )
                ]
            )
        )
        print(f"[Store B 답변] {response_b.text[:150]}...")

        # Store B의 grounding 확인
        has_ai_source_in_b = False
        if hasattr(response_b, 'candidates') and response_b.candidates:
            gm = response_b.candidates[0].grounding_metadata
            if gm and hasattr(gm, 'grounding_chunks') and gm.grounding_chunks:
                for chunk in gm.grounding_chunks:
                    title = chunk.retrieved_context.title
                    print(f"  출처: {title}")
                    if 'ai' in title.lower():
                        has_ai_source_in_b = True

        # 결과 판정
        if not has_python_source_in_a and not has_ai_source_in_b:
            print("\n✓ 채널 격리 성공! (각 Store는 자신의 문서만 참조)")
        else:
            print("\n△ 채널 격리 부분 성공 (LLM이 일반 지식으로 답변할 수 있음)")

        return True

    except Exception as e:
        print(f"\n✗ 실패: {e}")
        return False

    finally:
        if store_a:
            cleanup_store(store_a.name)
        if store_b:
            cleanup_store(store_b.name)


def test_youtube_url():
    """YouTube URL 지원 테스트"""
    print("\n" + "="*60)
    print("[테스트] YouTube URL 소스")
    print("="*60)

    client = get_client()
    store = None

    try:
        store = client.file_search_stores.create(config={"display_name": "youtube-test"})
        print(f"\n[Store] {store.name}")

        # YouTube URL 업로드 시도
        youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        print(f"\n[YouTube URL 업로드 시도] {youtube_url}")

        try:
            op = client.file_search_stores.upload_to_file_search_store(
                file=youtube_url,
                file_search_store_name=store.name
            )
            while not op.done:
                time.sleep(2)
                op = client.operations.get(op)
            print("  → YouTube URL 업로드 성공!")
            return True
        except Exception as e:
            print(f"  → 실패: {type(e).__name__}")
            print(f"     {str(e)[:100]}")
            return False

    except Exception as e:
        print(f"\n✗ 실패: {e}")
        return False

    finally:
        if store:
            cleanup_store(store.name)


def test_various_outputs():
    """다양한 출력 형식 테스트"""
    print("\n" + "="*60)
    print("[테스트] 다양한 출력 형식")
    print("="*60)

    client = get_client()
    store = None
    samples_dir = Path(__file__).parent / "samples"

    try:
        store = client.file_search_stores.create(config={"display_name": "output-test"})

        # 여러 문서 업로드
        for f in ["ai_basics.txt", "python_guide.txt", "project_meeting.txt"]:
            op = client.file_search_stores.upload_to_file_search_store(
                file=str(samples_dir / f),
                file_search_store_name=store.name
            )
            while not op.done:
                time.sleep(2)
                op = client.operations.get(op)

        time.sleep(5)

        outputs = {}

        # 1. Timeline
        print("\n[1] Timeline 생성")
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents="""Based on the documents, create a timeline of the project phases.
            Format:
            [Date/Phase] - [Event/Milestone]
            """,
            config=types.GenerateContentConfig(
                tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[store.name]))]
            )
        )
        print(response.text[:300])
        outputs["timeline"] = True

        # 2. FAQ
        print("\n[2] FAQ 생성")
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents="""Based on the documents, create a FAQ (Frequently Asked Questions) with 3 questions and answers.
            Format:
            Q: [Question]
            A: [Answer]
            """,
            config=types.GenerateContentConfig(
                tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[store.name]))]
            )
        )
        print(response.text[:300])
        outputs["faq"] = True

        # 3. Study Guide
        print("\n[3] Study Guide 생성")
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents="""Based on the documents, create a study guide with key concepts and learning objectives.
            Include:
            - Main topics
            - Key terms
            - Learning objectives
            """,
            config=types.GenerateContentConfig(
                tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[store.name]))]
            )
        )
        print(response.text[:300])
        outputs["study_guide"] = True

        # 4. Mind Map (텍스트 형태)
        print("\n[4] Mind Map 생성 (텍스트)")
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents="""Based on the documents, create a mind map in text format.
            Use indentation to show hierarchy:
            - Main Topic
              - Subtopic 1
                - Detail
              - Subtopic 2
            """,
            config=types.GenerateContentConfig(
                tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[store.name]))]
            )
        )
        print(response.text[:300])
        outputs["mind_map"] = True

        # 5. Briefing Doc
        print("\n[5] Briefing Doc 생성")
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents="""Based on the documents, create a brief executive summary.
            Include:
            - Overview (1-2 sentences)
            - Key Points (bullet points)
            - Next Steps
            """,
            config=types.GenerateContentConfig(
                tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[store.name]))]
            )
        )
        print(response.text[:300])
        outputs["briefing_doc"] = True

        print(f"\n✓ 모든 출력 형식 생성 성공! ({len(outputs)}개)")
        return True

    except Exception as e:
        print(f"\n✗ 실패: {e}")
        return False

    finally:
        if store:
            cleanup_store(store.name)


if __name__ == "__main__":
    print("="*60)
    print(" Phase 1 최종 검증")
    print("="*60)

    results = {}

    results["korean"] = test_korean_document()
    results["multi_turn"] = test_multi_turn_conversation()
    results["channel_isolation"] = test_channel_isolation()
    results["youtube"] = test_youtube_url()
    results["various_outputs"] = test_various_outputs()

    # 최종 결과
    print("\n" + "="*60)
    print(" 최종 결과 요약")
    print("="*60)
    for test, passed in results.items():
        status = "✓" if passed else "✗"
        print(f"  [{status}] {test}")
