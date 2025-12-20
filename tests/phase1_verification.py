# -*- coding: utf-8 -*-
"""
Phase 1 검증 스크립트
- 출처 인용 (Grounding)
- 여러 파일 크로스 검색
- 요약 생성
"""

import io
import os
import sys
import time
import json
from pathlib import Path

import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Windows 콘솔 UTF-8 출력 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# .env에서 API 키 로드
load_dotenv()

def get_client():
    """Gemini 클라이언트 생성"""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY가 .env에 설정되지 않았습니다")
    return genai.Client(api_key=api_key)


def create_store(client, name: str):
    """Store 생성"""
    print(f"\n[Store 생성] {name}")
    store = client.file_search_stores.create(
        config={"display_name": name}
    )
    print(f"  → 완료: {store.name}")
    return store


def upload_file(client, store, file_path: str):
    """파일 업로드"""
    print(f"  [업로드] {Path(file_path).name}")

    operation = client.file_search_stores.upload_to_file_search_store(
        file=file_path,
        file_search_store_name=store.name
    )

    while not operation.done:
        time.sleep(2)
        operation = client.operations.get(operation)

    print(f"    → 완료")
    return operation


def search_with_grounding(client, store, question: str):
    """검색 및 응답 (grounding 정보 포함)"""
    print(f"\n[질문] {question}")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
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

    return response


def cleanup_store(store_name: str):
    """Store 삭제"""
    print(f"\n[정리] Store 삭제 중...")
    api_key = os.getenv("GOOGLE_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/{store_name}?force=true&key={api_key}"
    response = requests.delete(url)
    if response.status_code == 200:
        print("  → Store 삭제 완료")
    else:
        print(f"  → 삭제 실패: {response.status_code}")


def print_response_details(response, test_name: str):
    """응답 상세 정보 출력"""
    print(f"\n{'='*60}")
    print(f"[{test_name}] 결과")
    print('='*60)

    # 기본 응답 텍스트
    print("\n[답변]")
    print(response.text[:500] if len(response.text) > 500 else response.text)

    # Grounding 메타데이터 확인
    print("\n[Grounding 메타데이터 확인]")

    # candidates 확인
    if hasattr(response, 'candidates') and response.candidates:
        candidate = response.candidates[0]

        # grounding_metadata 확인
        if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
            print("  ✓ grounding_metadata 존재!")
            gm = candidate.grounding_metadata
            print(f"  → {gm}")
        else:
            print("  ✗ grounding_metadata 없음")

        # content.parts 확인
        if hasattr(candidate, 'content') and candidate.content:
            for i, part in enumerate(candidate.content.parts):
                print(f"\n  [Part {i}]")
                if hasattr(part, 'text'):
                    print(f"    text: {part.text[:100]}...")
                if hasattr(part, 'file_data'):
                    print(f"    file_data: {part.file_data}")
                if hasattr(part, 'inline_data'):
                    print(f"    inline_data: {part.inline_data}")

        # 기타 속성 확인
        print(f"\n  [Candidate 속성들]")
        for attr in dir(candidate):
            if not attr.startswith('_'):
                val = getattr(candidate, attr, None)
                if val and not callable(val):
                    print(f"    {attr}: {type(val).__name__}")

    print('='*60)


def run_verification():
    """검증 실행"""
    print("\n" + "="*60)
    print(" Phase 1 검증: NotebookLM 핵심 기능 테스트")
    print("="*60)

    client = get_client()
    store = None
    samples_dir = Path(__file__).parent / "samples"

    try:
        # 1. Store 생성
        store = create_store(client, "phase1-verification-store")

        # 2. 여러 파일 업로드
        print("\n" + "-"*40)
        print("[테스트 1] 여러 파일 업로드")
        print("-"*40)

        files = list(samples_dir.glob("*.txt"))
        print(f"  업로드할 파일: {len(files)}개")

        for f in files:
            upload_file(client, store, str(f))

        print("\n  ✓ 여러 파일 업로드 성공!")

        # 잠시 대기 (인덱싱 시간)
        print("\n  인덱싱 대기 중 (5초)...")
        time.sleep(5)

        # 3. 출처 인용 (Grounding) 테스트
        print("\n" + "-"*40)
        print("[테스트 2] 출처 인용 (Grounding)")
        print("-"*40)

        response1 = search_with_grounding(
            client, store,
            "딥러닝이란 무엇인가요? 출처와 함께 답변해주세요."
        )
        print_response_details(response1, "Grounding 테스트")

        # 4. 크로스 검색 테스트
        print("\n" + "-"*40)
        print("[테스트 3] 크로스 검색 (여러 문서)")
        print("-"*40)

        response2 = search_with_grounding(
            client, store,
            "이 프로젝트에서 사용하는 기술 스택은 무엇인가요? Python과 관련된 라이브러리도 알려주세요."
        )
        print_response_details(response2, "크로스 검색 테스트")

        # 5. 요약 테스트
        print("\n" + "-"*40)
        print("[테스트 4] 요약 생성")
        print("-"*40)

        response3 = search_with_grounding(
            client, store,
            "업로드된 모든 문서의 내용을 종합하여 요약해주세요."
        )
        print_response_details(response3, "요약 테스트")

        # 결과 요약
        print("\n" + "="*60)
        print(" 검증 결과 요약")
        print("="*60)
        print(f"  [1] 여러 파일 업로드: ✓ 성공 ({len(files)}개)")
        print(f"  [2] 출처 인용: 위 결과 참조")
        print(f"  [3] 크로스 검색: 위 결과 참조")
        print(f"  [4] 요약 생성: 위 결과 참조")
        print("="*60)

    except Exception as e:
        print(f"\n[에러] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if store:
            cleanup_store(store.name)


if __name__ == "__main__":
    run_verification()
