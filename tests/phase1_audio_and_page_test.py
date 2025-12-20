# -*- coding: utf-8 -*-
"""
Phase 1 추가 검증
- Audio Overview (TTS) 가능 여부
- PDF rag_chunk 페이지 정보 확인
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

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

load_dotenv()


def get_client():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")
    return genai.Client(api_key=api_key)


def test_tts():
    """TTS (Text-to-Speech) 테스트"""
    print("\n" + "="*60)
    print("[테스트] Audio Overview (TTS)")
    print("="*60)

    client = get_client()

    # 테스트할 텍스트
    text_to_speak = """
    Welcome to the NotebookLM clone project overview.
    This project aims to build a document-based AI assistant using Gemini File Search API.
    The main features include document upload, search, and intelligent summarization.
    """

    print(f"\n[입력 텍스트]\n{text_to_speak.strip()}")

    try:
        # TTS 모델 사용 시도
        print("\n[TTS 생성 시도]")

        # 방법 1: gemini-2.5-flash-preview-tts 모델 사용
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text_to_speak,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="Kore"
                        )
                    )
                )
            )
        )

        print("  → TTS 모델 호출 성공!")

        # 오디오 데이터 확인
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and candidate.content:
                for part in candidate.content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        audio_data = part.inline_data.data
                        mime_type = part.inline_data.mime_type
                        print(f"  → 오디오 데이터 생성됨!")
                        print(f"     MIME Type: {mime_type}")
                        print(f"     데이터 크기: {len(audio_data)} bytes")

                        # 파일로 저장
                        output_path = Path(__file__).parent / "samples" / "tts_output.wav"
                        with open(output_path, "wb") as f:
                            f.write(audio_data)
                        print(f"  → 저장됨: {output_path}")
                        return True

        print("  → 오디오 데이터 없음")
        return False

    except Exception as e:
        print(f"  → TTS 실패: {type(e).__name__}")
        print(f"     {str(e)[:200]}")

        # 지원되는 TTS 모델 목록 확인
        print("\n[사용 가능한 모델 확인]")
        try:
            models = client.models.list()
            tts_models = [m.name for m in models if 'tts' in m.name.lower()]
            if tts_models:
                print(f"  TTS 관련 모델: {tts_models}")
            else:
                print("  TTS 모델을 찾을 수 없음")
        except Exception as e2:
            print(f"  모델 목록 조회 실패: {e2}")

        return False


def test_pdf_rag_chunk():
    """PDF rag_chunk에서 페이지 정보 확인"""
    print("\n" + "="*60)
    print("[테스트] PDF rag_chunk 페이지 정보")
    print("="*60)

    client = get_client()
    store = None
    samples_dir = Path(__file__).parent / "samples"
    pdf_path = samples_dir / "test_document.pdf"

    try:
        # Store 생성
        store = client.file_search_stores.create(config={"display_name": "pdf-page-test"})
        print(f"\n[Store] {store.name}")

        # PDF 업로드
        print(f"[업로드] {pdf_path.name}")
        operation = client.file_search_stores.upload_to_file_search_store(
            file=str(pdf_path),
            file_search_store_name=store.name
        )
        while not operation.done:
            time.sleep(2)
            operation = client.operations.get(operation)
        print("  → 완료")

        time.sleep(5)

        # 검색
        print("\n[질문] What is discussed on Page 2?")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="What is on Page 2? Please mention the page number in your answer.",
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

        # rag_chunk 상세 분석
        print("\n[rag_chunk 상세 분석]")
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                gm = candidate.grounding_metadata
                if hasattr(gm, 'grounding_chunks') and gm.grounding_chunks:
                    for i, chunk in enumerate(gm.grounding_chunks):
                        print(f"\n  [Chunk {i}]")
                        ctx = chunk.retrieved_context

                        # 모든 속성과 값 출력
                        for attr in dir(ctx):
                            if not attr.startswith('_') and not callable(getattr(ctx, attr, None)):
                                try:
                                    val = getattr(ctx, attr, None)
                                    if val is not None and attr not in ['model_config', 'model_fields', 'model_fields_set', 'model_computed_fields']:
                                        val_str = str(val)[:100] if len(str(val)) > 100 else str(val)
                                        print(f"    {attr}: {val_str}")
                                except:
                                    pass

                        # rag_chunk 특별히 확인
                        if hasattr(ctx, 'rag_chunk') and ctx.rag_chunk:
                            print(f"\n    [rag_chunk 내용]")
                            rag = ctx.rag_chunk
                            for attr in dir(rag):
                                if not attr.startswith('_') and not callable(getattr(rag, attr, None)):
                                    try:
                                        val = getattr(rag, attr, None)
                                        if val is not None and attr not in ['model_config', 'model_fields', 'model_fields_set', 'model_computed_fields']:
                                            val_str = str(val)[:100] if len(str(val)) > 100 else str(val)
                                            print(f"      {attr}: {val_str}")
                                    except:
                                        pass

        return True

    except Exception as e:
        print(f"\n[에러] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        if store:
            api_key = os.getenv("GOOGLE_API_KEY")
            url = f"https://generativelanguage.googleapis.com/v1beta/{store.name}?force=true&key={api_key}"
            requests.delete(url)
            print("\n[Store 삭제 완료]")


if __name__ == "__main__":
    print("="*60)
    print(" Phase 1 추가 검증: TTS & PDF 페이지")
    print("="*60)

    test_tts()
    test_pdf_rag_chunk()
