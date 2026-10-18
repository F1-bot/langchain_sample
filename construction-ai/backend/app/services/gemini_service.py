"""
Робота із зображеннями: розпізнавання тексту й аналіз.

ЩО ТУТ БУЛО НЕ ТАК
────────────────────────────────────────────────────────────────────
1. Модель створювалась у __init__, а об'єкт сервісу — на рівні
   модуля. Тобто при імпорті застосунку. Тепер ліниво.

2. Промпти лишились від МЕДИЧНОГО шаблону, з якого робили цей
   проєкт: модель просили видобути «Patient information»,
   «Doctor's notes», «Prescriptions», а у відповіді за замовчуванням
   стояло «Consult with a healthcare professional». На фото
   будівельного креслення це давало безглузду відповідь.

   Урок той самий, що й у лекції: промпт — це теж код, і копіювати
   його з чужого шаблону треба так само уважно.
"""
import base64
import json

from langchain_core.messages import HumanMessage

from app.config import load_google_vision_llm

EXTRACTION_PROMPT = """You are a construction document text extractor.
Extract ALL text from this construction document.

Include:
- Document title, number and revision
- Project, object and contractor names
- Materials, grades and specifications
- Quantities, dimensions and units
- Dates, signatures and stamps
- Any handwritten notes

Format the output clearly and preserve the structure.
If text is unclear, indicate with [unclear].

Extract all text now:"""

ANALYSIS_PROMPTS = {
    "en": """Analyze this construction document image and provide analysis
in JSON format with these keys:
- summary: Brief overview of what the document is
- key_findings: List of important technical findings
- recommendations: Practical recommendations for the construction team
- next_steps: Suggested actions

Respond ONLY with valid JSON.""",
    "fr": """Analysez cette image de document de construction et fournissez
une analyse au format JSON avec ces clés:
- summary: Bref aperçu du document
- key_findings: Liste des constats techniques importants
- recommendations: Recommandations pratiques pour l'équipe de chantier
- next_steps: Actions suggérées

Répondez UNIQUEMENT en JSON valide.""",
}


def _image_message(prompt: str, image_bytes: bytes) -> HumanMessage:
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    return HumanMessage(content=[
        {"type": "text", "text": prompt},
        {"type": "image_url",
         "image_url": f"data:image/jpeg;base64,{image_b64}"},
    ])


class GeminiService:
    """Модель створюється при першому зверненні, а не на імпорті."""

    @property
    def vision_llm(self):
        return load_google_vision_llm()      # всередині @lru_cache

    def extract_text_from_image(self, image_bytes: bytes):
        try:
            response = self.vision_llm.invoke(
                [_image_message(EXTRACTION_PROMPT, image_bytes)])
            return response.text
        except Exception as e:
            raise Exception(f"Image text extraction error: {str(e)}")

    def analyze_image_directly(self, image_bytes: bytes, language: str = "en"):
        prompt = ANALYSIS_PROMPTS.get(language, ANALYSIS_PROMPTS["en"])
        try:
            response = self.vision_llm.invoke(
                [_image_message(prompt, image_bytes)])
        except Exception as e:
            raise Exception(f"Image analysis error: {str(e)}")

        text = response.text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Модель відповіла текстом, а не JSON. Віддаємо що є, але
            # чесно позначаємо, що структурованого розбору не вийшло.
            return {
                "summary": text[:500],
                "key_findings": ["Модель відповіла не у форматі JSON"],
                "recommendations": ["Перевірте якість зображення та спробуйте ще раз"],
                "next_steps": ["Звіртеся з профільним фахівцем"],
            }


gemini_service = GeminiService()   # об'єкт легкий, модель не створює
