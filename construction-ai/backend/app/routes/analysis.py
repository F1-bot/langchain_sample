from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.models.schemas import (
    ChatRequest, ChatResponse,
    AnalysisRequest, AnalysisResponse,
    ImageAnalysisResponse, EstimatorRequest, EstimatorResponse
)
from app.agent import create_agent_executor
from app.chains.analysis_chain import analyze_construction_document
from app.services.gemini_service import gemini_service
from app.agents.estimator_agent import create_estimator_agent
from datetime import datetime
from langchain_core.messages import HumanMessage

router = APIRouter(prefix="/api", tags=["Analysis"])
agent_executor = create_agent_executor()


@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest):
    try:
        config = {"configurable": {"thread_id": request.thread_id}}
        input_message = HumanMessage(content=request.message)
        response = agent_executor.invoke({"messages": [input_message]}, config)
        last_message = response["messages"][-1]

        return ChatResponse(
            response=last_message.content,
            thread_id=request.thread_id,
            language=request.language,
            timestamp=datetime.now()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@router.post("/analyze-text", response_model=AnalysisResponse)
async def analyze_text(request: AnalysisRequest):
    try:
        analysis = analyze_construction_document(
            text=request.text,
            context=request.context,
            language=request.language
        )

        disclaimer = (
            "This analysis is for informational purposes only. "
            "Always consult qualified construction professionals for advice."
        )

        return AnalysisResponse(
            summary=analysis.summary,
            key_findings=analysis.key_findings,
            recommendations=analysis.recommendations,
            next_steps=analysis.next_steps,
            disclaimer=disclaimer,
            language=request.language,
            timestamp=datetime.now()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


@router.post("/analyze-image", response_model=ImageAnalysisResponse)
async def analyze_image(
        file: UploadFile = File(...),
        language: str = Form(default="en"),
        extract_text_only: bool = Form(default=False)
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    try:
        image_bytes = await file.read()
        extracted_text = gemini_service.extract_text_from_image(image_bytes)

        if extract_text_only:
            return ImageAnalysisResponse(
                extracted_text=extracted_text,
                analysis=AnalysisResponse(
                    summary="Text extraction completed",
                    key_findings=[],
                    recommendations=[],
                    next_steps=["Review the extracted text", "Analyze if needed"],
                    disclaimer="Text extraction only - no analysis performed",
                    language=language,
                    timestamp=datetime.now()
                )
            )

        analysis = analyze_construction_document(text=extracted_text, language=language)
        disclaimer = (
            "This analysis is for informational purposes only. "
            "Always consult qualified construction professionals for advice."
        )

        return ImageAnalysisResponse(
            extracted_text=extracted_text,
            analysis=AnalysisResponse(
                summary=analysis.summary,
                key_findings=analysis.key_findings,
                recommendations=analysis.recommendations,
                next_steps=analysis.next_steps,
                disclaimer=disclaimer,
                language=language,
                timestamp=datetime.now()
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image analysis error: {str(e)}")


@router.post("/extract-text")
async def extract_text_from_image(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    try:
        image_bytes = await file.read()
        extracted_text = gemini_service.extract_text_from_image(image_bytes)
        return {
            "extracted_text": extracted_text,
            "timestamp": datetime.now()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text extraction error: {str(e)}")


estimator_agent = create_estimator_agent()


@router.post("/run-estimator", response_model=EstimatorResponse)
async def run_estimator(request: EstimatorRequest):
    try:
        task_message = HumanMessage(content=request.task)
        response = await estimator_agent.ainvoke({"messages": [task_message]})

        final_response_content = response["messages"][-1].content

        # Проста логіка для визначення, чи був створений файл
        artifact_path = "estimate.txt" if "збережено у файл" in final_response_content.lower() else None

        return EstimatorResponse(
            response=final_response_content,
            artifact_path=artifact_path,
            timestamp=datetime.now()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Estimator agent error: {str(e)}")