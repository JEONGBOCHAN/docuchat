# -*- coding: utf-8 -*-
"""
Phase 1 확장 검증 스크립트
- PDF 페이지 인용
- Word 파일 업로드
- 이미지 소스
- 웹페이지 URL 소스
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

load_dotenv()


def get_client():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")
    return genai.Client(api_key=api_key)


def create_store(client, name: str):
    print(f"\n[Store 생성] {name}")
    store = client.file_search_stores.create(config={"display_name": name})
    print(f"  → {store.name}")
    return store


def upload_file(client, store, file_path: str):
    fname = Path(file_path).name
    print(f"  [업로드] {fname}")
    try:
        operation = client.file_search_stores.upload_to_file_search_store(
            file=file_path,
            file_search_store_name=store.name
        )
        while not operation.done:
            time.sleep(2)
            operation = client.operations.get(operation)
        print(f"    → 성공")
        return True
    except Exception as e:
        print(f"    → 실패: {e}")
        return False


def search(client, store, question: str):
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


def analyze_grounding(response, test_name: str):
    """Grounding 메타데이터 분석"""
    print(f"\n{'='*60}")
    print(f"[{test_name}]")
    print('='*60)

    # 답변
    print(f"\n[답변]\n{response.text[:400]}..." if len(response.text) > 400 else f"\n[답변]\n{response.text}")

    # Grounding 분석
    result = {"has_grounding": False, "has_page_info": False, "sources": []}

    if hasattr(response, 'candidates') and response.candidates:
        candidate = response.candidates[0]
        if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
            gm = candidate.grounding_metadata
            result["has_grounding"] = True

            if hasattr(gm, 'grounding_chunks') and gm.grounding_chunks:
                print(f"\n[출처 정보]")
                for i, chunk in enumerate(gm.grounding_chunks):
                    if hasattr(chunk, 'retrieved_context') and chunk.retrieved_context:
                        ctx = chunk.retrieved_context
                        title = getattr(ctx, 'title', 'Unknown')
                        text_preview = getattr(ctx, 'text', '')[:100]

                        # 페이지 정보 확인
                        page = getattr(ctx, 'page', None)
                        uri = getattr(ctx, 'uri', None)

                        source_info = f"  [{i+1}] {title}"
                        if page:
                            source_info += f" (Page {page})"
                            result["has_page_info"] = True
                        if uri:
                            source_info += f" - {uri}"
                        print(source_info)

                        result["sources"].append({
                            "title": title,
                            "page": page,
                            "uri": uri
                        })

                        # 모든 속성 출력 (디버깅용)
                        print(f"      속성: {[a for a in dir(ctx) if not a.startswith('_')]}")

    print(f"\n[결과] Grounding: {'✓' if result['has_grounding'] else '✗'} | 페이지정보: {'✓' if result['has_page_info'] else '✗'}")
    return result


def cleanup_store(store_name: str):
    print(f"\n[정리] Store 삭제...")
    api_key = os.getenv("GOOGLE_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/{store_name}?force=true&key={api_key}"
    response = requests.delete(url)
    print(f"  → {'성공' if response.status_code == 200 else '실패'}")


def test_url_source(client, store):
    """웹페이지 URL 소스 테스트"""
    print(f"\n{'='*60}")
    print("[테스트] 웹페이지 URL 소스")
    print('='*60)

    # 방법 1: URL 직접 업로드 시도
    test_url = "https://en.wikipedia.org/wiki/Python_(programming_language)"
    print(f"\n  URL 직접 업로드 시도: {test_url}")

    try:
        # file_search_stores API가 URL을 지원하는지 확인
        operation = client.file_search_stores.upload_to_file_search_store(
            file=test_url,
            file_search_store_name=store.name
        )
        while not operation.done:
            time.sleep(2)
            operation = client.operations.get(operation)
        print("    → URL 업로드 성공!")
        return True
    except Exception as e:
        print(f"    → URL 직접 업로드 실패: {type(e).__name__}")
        print(f"       {str(e)[:100]}")
        return False


def run_extended_verification():
    print("\n" + "="*60)
    print(" Phase 1 확장 검증: PDF, Word, 이미지, URL")
    print("="*60)

    client = get_client()
    store = None
    samples_dir = Path(__file__).parent / "samples"

    results = {}

    try:
        store = create_store(client, "phase1-extended-verification")

        # 1. PDF 업로드 및 페이지 인용 테스트
        print("\n" + "-"*40)
        print("[테스트 1] PDF 업로드 및 페이지 인용")
        print("-"*40)

        pdf_path = samples_dir / "test_document.pdf"
        pdf_uploaded = upload_file(client, store, str(pdf_path))

        if pdf_uploaded:
            time.sleep(5)  # 인덱싱 대기
            response = search(client, store, "What is discussed on Page 2 about neural network architecture?")
            results["pdf"] = analyze_grounding(response, "PDF 페이지 인용")

        # 2. Word 업로드 테스트
        print("\n" + "-"*40)
        print("[테스트 2] Word 파일 업로드")
        print("-"*40)

        docx_path = samples_dir / "test_document.docx"
        docx_uploaded = upload_file(client, store, str(docx_path))

        if docx_uploaded:
            time.sleep(3)
            response = search(client, store, "What are the three types of cloud services mentioned?")
            results["word"] = analyze_grounding(response, "Word 파일")

        # 3. 이미지 업로드 테스트
        print("\n" + "-"*40)
        print("[테스트 3] 이미지 파일 업로드")
        print("-"*40)

        img_path = samples_dir / "test_image.png"
        img_uploaded = upload_file(client, store, str(img_path))

        if img_uploaded:
            time.sleep(3)
            response = search(client, store, "What API endpoints are shown in the image?")
            results["image"] = analyze_grounding(response, "이미지 파일")
        else:
            results["image"] = {"has_grounding": False, "error": "업로드 실패"}

        # 4. URL 소스 테스트
        print("\n" + "-"*40)
        print("[테스트 4] 웹페이지 URL 소스")
        print("-"*40)

        url_result = test_url_source(client, store)
        results["url"] = {"supported": url_result}

        # 결과 요약
        print("\n" + "="*60)
        print(" 확장 검증 결과 요약")
        print("="*60)

        print(f"\n  [1] PDF 업로드: {'✓' if pdf_uploaded else '✗'}")
        if "pdf" in results:
            print(f"      페이지 인용: {'✓' if results['pdf'].get('has_page_info') else '✗ (페이지 번호 미포함)'}")

        print(f"\n  [2] Word 업로드: {'✓' if docx_uploaded else '✗'}")
        if "word" in results:
            print(f"      Grounding: {'✓' if results['word'].get('has_grounding') else '✗'}")

        print(f"\n  [3] 이미지 업로드: {'✓' if img_uploaded else '✗'}")
        if "image" in results and results["image"].get("has_grounding"):
            print(f"      Grounding: ✓")
        else:
            print(f"      Grounding: ✗ (이미지 OCR 미지원 가능성)")

        print(f"\n  [4] URL 소스: {'✓' if results.get('url', {}).get('supported') else '✗ (직접 지원 안함)'}")

        print("="*60)

    except Exception as e:
        print(f"\n[에러] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if store:
            cleanup_store(store.name)

    return results


if __name__ == "__main__":
    run_extended_verification()
