# -*- coding: utf-8 -*-
"""
Gemini Quiz Adapter.

Implements QuizPort using Google Gemini API.
"""

import json

from google import genai
from google.genai import types

from src.application.ports.learning import (
    QuizPort,
    QuizDTO,
    QuizQuestionDTO,
    QuizChoiceDTO,
)
from src.core.config import get_settings, GeminiModels


class GeminiQuizAdapter(QuizPort):
    """QuizPort implementation using Google Gemini.

    This adapter directly interacts with Gemini API to generate
    quizzes from document stores.

    Example:
        adapter = GeminiQuizAdapter()
        quiz = adapter.generate_quiz("channel-123", count=10, quiz_type="mixed")
    """

    def __init__(self, client: genai.Client | None = None):
        """Initialize adapter with Gemini client.

        Args:
            client: Optional Gemini client instance.
                   Creates one if not provided.
        """
        if client:
            self._client = client
        else:
            settings = get_settings()
            self._client = genai.Client(api_key=settings.google_api_key)

    def generate_quiz(
        self,
        store_name: str,
        count: int = 5,
        quiz_type: str = "mixed",
        difficulty: str = "medium",
        include_explanations: bool = True,
        model: str = GeminiModels.DEFAULT,
    ) -> QuizDTO:
        """Generate a quiz using Gemini.

        Args:
            store_name: The document store to analyze
            count: Number of questions to generate (1-20)
            quiz_type: Type of questions (multiple_choice, short_answer, true_false, mixed)
            difficulty: Target difficulty level (easy, medium, hard)
            include_explanations: Whether to include answer explanations
            model: The model to use for generation

        Returns:
            QuizDTO with the generated quiz

        Raises:
            Exception: If quiz generation fails with an error
        """
        difficulty_instruction = {
            "easy": "Create straightforward questions testing basic comprehension.",
            "medium": "Create questions requiring understanding and some analysis.",
            "hard": "Create challenging questions requiring deep understanding and critical thinking.",
        }.get(difficulty, "Create questions requiring understanding and some analysis.")

        type_instruction = {
            "multiple_choice": "All questions must be multiple choice with 4 options (A, B, C, D).",
            "short_answer": "All questions must be short answer requiring brief written responses.",
            "true_false": "All questions must be true/false format.",
            "mixed": "Mix question types: include multiple choice, short answer, and true/false questions.",
        }.get(quiz_type, "Mix question types.")

        explanation_field = ""
        if include_explanations:
            explanation_field = '  - "explanation": Why this is the correct answer (string)'

        prompt = f"""Analyze all documents in this knowledge base and create a quiz with exactly {count} questions.

{difficulty_instruction}
{type_instruction}

Structure your response as a JSON object with these fields:
- "title": A descriptive title for the quiz (string)
- "description": Brief description of what the quiz covers (string)
- "questions": An array of exactly {count} questions, each with:
  - "question": The question text (string)
  - "question_type": One of "multiple_choice", "short_answer", or "true_false" (string)
  - "choices": For multiple choice, array of objects with "label" (A/B/C/D), "text", "is_correct" (boolean). Null for other types.
  - "correct_answer": The correct answer (string)
  - "difficulty": "{difficulty}" (string)
{explanation_field}

Return ONLY the JSON object, no other text.

Example format:
{{
  "title": "Machine Learning Fundamentals Quiz",
  "description": "Test your knowledge of basic ML concepts",
  "questions": [
    {{
      "question": "What is supervised learning?",
      "question_type": "multiple_choice",
      "choices": [
        {{"label": "A", "text": "Learning with labeled data", "is_correct": true}},
        {{"label": "B", "text": "Learning without labels", "is_correct": false}},
        {{"label": "C", "text": "Reinforcement learning", "is_correct": false}},
        {{"label": "D", "text": "Transfer learning", "is_correct": false}}
      ],
      "correct_answer": "A. Learning with labeled data",
      "difficulty": "medium",
      "explanation": "Supervised learning uses labeled training data..."
    }},
    {{
      "question": "Neural networks are inspired by biological neurons.",
      "question_type": "true_false",
      "choices": null,
      "correct_answer": "True",
      "difficulty": "easy",
      "explanation": "Neural networks were designed to mimic..."
    }}
  ]
}}"""

        try:
            response = self._client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=[store_name]
                            )
                        )
                    ],
                ),
            )

            try:
                text = response.text or ""
                start = text.find("{")
                end = text.rfind("}") + 1
                if start != -1 and end > start:
                    quiz = json.loads(text[start:end])
                else:
                    quiz = {}
            except json.JSONDecodeError:
                quiz = {}

            questions = []
            for q in quiz.get("questions", []):
                choices = None
                if q.get("choices"):
                    choices = [
                        QuizChoiceDTO(
                            label=c.get("label", ""),
                            text=c.get("text", ""),
                            is_correct=c.get("is_correct", False),
                        )
                        for c in q.get("choices", [])
                    ]

                questions.append(
                    QuizQuestionDTO(
                        question=q.get("question", ""),
                        question_type=q.get("question_type", "multiple_choice"),
                        correct_answer=q.get("correct_answer", ""),
                        choices=choices,
                        explanation=q.get("explanation"),
                        difficulty=q.get("difficulty", difficulty),
                    )
                )

            return QuizDTO(
                title=quiz.get("title", "Quiz"),
                description=quiz.get("description", ""),
                questions=questions,
            )

        except Exception as e:
            raise Exception(str(e))
