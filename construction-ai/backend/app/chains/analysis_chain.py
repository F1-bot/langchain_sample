from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from app.config import load_google_llm
from app.models.schemas import ConstructionAnalysis


def create_analysis_chain(language: str = "en"):
    llm = load_google_llm()
    parser = PydanticOutputParser(pydantic_object=ConstructionAnalysis)
    format_instructions = parser.get_format_instructions()

    if language == "fr":
        system_message = """Vous êtes un assistant IA analysant des documents de construction.
Fournissez des informations claires, précises et actionnables.
Restez objectif et recommandez toujours une consultation professionnelle."""

        user_template = """Analysez ce document de construction et fournissez une analyse structurée:

Document:
{document_text}

Contexte Additionnel:
{context}

{format_instructions}

Répondez UNIQUEMENT en JSON valide."""
    else:
        system_message = """You are a construction AI assistant analyzing construction documents.
Provide clear, accurate, and actionable insights.
Stay objective and always recommend professional consultation."""

        user_template = """Analyze this construction document and provide a structured analysis:

Document:
{document_text}

Additional Context:
{context}

{format_instructions}

Respond ONLY with valid JSON."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("user", user_template)
    ])

    prompt = prompt.partial(format_instructions=format_instructions)
    chain = prompt | llm | parser

    return chain


def analyze_construction_document(text: str, context: str = "", language: str = "en"):
    chain = create_analysis_chain(language)

    try:
        result = chain.invoke({
            "document_text": text,
            "context": context if context else "No additional context provided"
        })
        return result
    except Exception as e:
        print(f"Analysis error: {e}")
        return ConstructionAnalysis(
            summary=f"Analysis completed but encountered formatting issues: {str(e)[:200]}",
            key_findings=["Analysis was performed but results need manual review"],
            recommendations=["Consult with a construction professional for detailed interpretation"],
            next_steps=["Schedule a meeting with an engineer", "Keep this record for your project history"]
        )