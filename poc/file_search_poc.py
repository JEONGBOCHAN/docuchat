# -*- coding: utf-8 -*-
"""
Gemini File Search API POC
- Store 생성
- 파일 업로드
- 검색 쿼리 테스트
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

from src.core.config import GeminiModels

# Windows 콘솔 UTF-8 출력 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# .env에서 API 키 로드
load_dotenv()


def get_api_key():
    """API 키 가져오기"""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY가 .env에 설정되지 않았습니다")
    return api_key


def create_client():
    """Gemini 클라이언트 생성"""
    return genai.Client(api_key=get_api_key())


def create_store(client, name: str):
    """File Search Store 생성"""
    print(f"[1/4] Store 생성 중: {name}")
    store = client.file_search_stores.create(
        config={"display_name": name}
    )
    print(f"      Store 생성 완료: {store.name}")
    return store


def upload_file(client, store, file_path: str):
    """파일을 Store에 업로드"""
    print(f"[2/4] 파일 업로드 중: {Path(file_path).name}")

    operation = client.file_search_stores.upload_to_file_search_store(
        file=file_path,
        file_search_store_name=store.name
    )

    # 업로드 완료 대기
    wait_count = 0
    while not operation.done:
        wait_count += 1
        print(f"      대기 중... ({wait_count * 3}초)")
        time.sleep(3)
        operation = client.operations.get(operation)

    print("      파일 업로드 완료")
    return operation


def search_and_answer(client, store, question: str):
    """Store에서 검색하고 답변 생성"""
    print(f"[3/4] 질문: {question}")

    response = client.models.generate_content(
        model=GeminiModels.DEFAULT,
        contents=question,
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

    print("[4/4] 답변:")
    print("-" * 50)
    print(response.text)
    print("-" * 50)

    return response


def cleanup_store(store_name: str):
    """Store 삭제 (REST API 직접 호출, force=true)"""
    print("\n[정리] Store 삭제 중...")

    api_key = get_api_key()
    url = f"https://generativelanguage.googleapis.com/v1beta/{store_name}?force=true&key={api_key}"

    response = requests.delete(url)

    if response.status_code == 200:
        print("      Store 삭제 완료")
    else:
        print(f"      Store 삭제 실패: {response.status_code} - {response.text}")


def run_poc(file_path: str, question: str):
    """POC 전체 실행"""
    print("=" * 50)
    print("Gemini File Search API POC")
    print("=" * 50)

    # 파일 존재 확인
    if not Path(file_path).exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    print(f"파일: {Path(file_path).name}")
    print(f"크기: {Path(file_path).stat().st_size / 1024:.1f} KB")
    print("=" * 50)

    client = create_client()
    store = None

    try:
        # 1. Store 생성
        store = create_store(client, "poc-test-store")

        # 2. 파일 업로드
        upload_file(client, store, file_path)

        # 3. 검색 및 답변
        response = search_and_answer(client, store, question)

        print("\n[완료] POC 성공!")
        return response

    except Exception as e:
        print(f"\n[에러] {type(e).__name__}: {e}")
        raise

    finally:
        # 4. 정리 (Store 삭제)
        if store:
            cleanup_store(store.name)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용법: python file_search_poc.py <파일경로> <질문>")
        print("예시: python file_search_poc.py ./sample.pdf '이 논문의 주요 내용은?'")
        sys.exit(1)

    file_path = sys.argv[1]
    question = sys.argv[2]

    run_poc(file_path, question)
