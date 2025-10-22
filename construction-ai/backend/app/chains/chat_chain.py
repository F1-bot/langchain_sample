from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.config import load_google_llm


def create_chat_chain(language: str = "en"):
    llm = load_google_llm()

    if language == "fr":
        system_message = """Vous êtes Construction AI, un assistant IA pour l'industrie de la construction.

Vos responsabilités:
- Fournir des informations précises sur la construction
- Expliquer les concepts de construction en termes simples
- Toujours recommander de consulter des professionnels qualifiés

IMPORTANT: Vous n'êtes PAS un ingénieur ou un architecte. Ne donnez jamais de conseils définitifs."""
    else:
        system_message = """You are Construction AI, an AI assistant for the construction industry.

Your responsibilities:
- Provide accurate construction information
- Explain construction concepts in simple terms
- Always recommend consulting qualified professionals

IMPORTANT: You are NOT an engineer or an architect. Never provide definitive advice."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("user", "{user_question}")
    ])

    parser = StrOutputParser()
    chain = prompt | llm | parser

    return chain


def get_chat_response(message: str, language: str = "en"):
    chain = create_chat_chain(language)
    response = chain.invoke({"user_question": message})
    return response