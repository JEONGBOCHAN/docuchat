# -*- coding: utf-8 -*-
"""
Phase 1 추가 검증
- 파일 삭제/관리
- Store 정보 조회
- 스트리밍 응답
- Flashcards/Quiz 생성 (프롬프트)
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


def test_store_management():
    """Store 및 파일 관리 기능 테스트"""
    print("\n" + "="*60)
    print("[테스트] Store 및 파일 관리")
    print("="*60)

    client = get_client()
    api_key = os.getenv("GOOGLE_API_KEY")
    samples_dir = Path(__file__).parent / "samples"

    try:
        # 1. Store 생성
        print("\n[1] Store 생성")
        store = client.file_search_stores.create(config={"display_name": "management-test"})
        print(f"  → {store.name}")

        # 2. 파일 업로드
        print("\n[2] 파일 업로드 (2개)")
        files_to_upload = [
            samples_dir / "ai_basics.txt",
            samples_dir / "python_guide.txt"
        ]

        for f in files_to_upload:
            print(f"  업로드: {f.name}")
            op = client.file_search_stores.upload_to_file_search_store(
                file=str(f),
                file_search_store_name=store.name
            )
            while not op.done:
                time.sleep(2)
                op = client.operations.get(op)
            print(f"    → 완료")

        # 3. Store 정보 조회
        print("\n[3] Store 정보 조회")
        try:
            store_info = client.file_search_stores.get(name=store.name)
            print(f"  이름: {store_info.display_name}")
            print(f"  ID: {store_info.name}")

            # Store의 속성들 확인
            for attr in dir(store_info):
                if not attr.startswith('_') and not callable(getattr(store_info, attr, None)):
                    try:
                        val = getattr(store_info, attr, None)
                        if val is not None and attr not in ['model_config', 'model_fields', 'model_fields_set', 'model_computed_fields']:
                            print(f"  {attr}: {val}")
                    except:
                        pass
        except Exception as e:
            print(f"  조회 실패: {e}")

        # 4. Store 내 파일 목록 조회 시도
        print("\n[4] Store 내 파일 목록 조회")
        try:
            # REST API로 직접 시도
            url = f"https://generativelanguage.googleapis.com/v1beta/{store.name}/files?key={api_key}"
            resp = requests.get(url)
            if resp.status_code == 200:
                files = resp.json()
                print(f"  파일 목록: {files}")
            else:
                print(f"  API 응답: {resp.status_code} - {resp.text[:100]}")
        except Exception as e:
            print(f"  목록 조회 실패: {e}")

        # 5. 개별 파일 삭제 시도
        print("\n[5] 개별 파일 삭제 시도")
        try:
            # SDK로 파일 삭제 메서드가 있는지 확인
            methods = [m for m in dir(client.file_search_stores) if not m.startswith('_')]
            print(f"  file_search_stores 메서드: {methods}")

            # REST API로 삭제 시도
            # 파일 ID를 알아야 하는데, 목록 조회가 안되면 어려움
        except Exception as e:
            print(f"  삭제 시도 실패: {e}")

        return store

    except Exception as e:
        print(f"\n[에러] {e}")
        return None


def test_streaming():
    """스트리밍 응답 테스트"""
    print("\n" + "="*60)
    print("[테스트] 스트리밍 응답")
    print("="*60)

    client = get_client()

    try:
        print("\n[스트리밍 생성 시도]")

        # 스트리밍으로 긴 응답 생성
        response_stream = client.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents="Explain machine learning in 5 paragraphs."
        )

        print("  스트리밍 응답:")
        chunk_count = 0
        for chunk in response_stream:
            chunk_count += 1
            if hasattr(chunk, 'text') and chunk.text:
                print(f"  [{chunk_count}] {chunk.text[:50]}..." if len(chunk.text) > 50 else f"  [{chunk_count}] {chunk.text}")

        print(f"\n  → 총 {chunk_count}개 청크 수신")
        return True

    except Exception as e:
        print(f"  스트리밍 실패: {e}")
        return False


def test_flashcards_quiz():
    """Flashcards/Quiz 생성 (프롬프트 기반)"""
    print("\n" + "="*60)
    print("[테스트] Flashcards/Quiz 생성 (프롬프트)")
    print("="*60)

    client = get_client()
    store = None
    samples_dir = Path(__file__).parent / "samples"

    try:
        # Store 생성 및 파일 업로드
        store = client.file_search_stores.create(config={"display_name": "flashcard-test"})
        print(f"\n[Store] {store.name}")

        op = client.file_search_stores.upload_to_file_search_store(
            file=str(samples_dir / "ai_basics.txt"),
            file_search_store_name=store.name
        )
        while not op.done:
            time.sleep(2)
            op = client.operations.get(op)

        time.sleep(3)

        # Flashcards 생성
        print("\n[Flashcards 생성]")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="""Based on the uploaded documents, create 3 flashcards.
            Format each flashcard as:
            Q: [question]
            A: [answer]
            """,
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
        print(f"\n{response.text}")

        # Quiz 생성
        print("\n[Quiz 생성]")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="""Based on the uploaded documents, create a 3-question multiple choice quiz.
            Format:
            1. [Question]
               a) [option]
               b) [option]
               c) [option]
               d) [option]
               Answer: [correct letter]
            """,
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
        print(f"\n{response.text}")

        return True

    except Exception as e:
        print(f"  실패: {e}")
        return False

    finally:
        if store:
            api_key = os.getenv("GOOGLE_API_KEY")
            url = f"https://generativelanguage.googleapis.com/v1beta/{store.name}?force=true&key={api_key}"
            requests.delete(url)


def cleanup_store(store):
    if store:
        api_key = os.getenv("GOOGLE_API_KEY")
        url = f"https://generativelanguage.googleapis.com/v1beta/{store.name}?force=true&key={api_key}"
        requests.delete(url)
        print(f"\n[Store 삭제 완료]")


if __name__ == "__main__":
    print("="*60)
    print(" Phase 1 추가 검증")
    print("="*60)

    store = test_store_management()
    test_streaming()
    test_flashcards_quiz()

    if store:
        cleanup_store(store)
