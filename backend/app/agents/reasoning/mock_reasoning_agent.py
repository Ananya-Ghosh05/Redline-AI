import asyncio
import json
import logging
from typing import Any, Dict
from groq import Groq
from ...core.config import settings
from ..base import BaseAgent
from ...core.schemas import ReasoningOutput, EmotionAnalysis

logger = logging.getLogger("redline_ai.reasoning")

class MockReasoningAgent(BaseAgent):
    """Reasoning Agent using Groq (LLM) or Mock fallback."""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.client = None
        if settings.GROQ_API_KEY:
            try:
                self.client = Groq(api_key=settings.GROQ_API_KEY)
                logger.info("Groq client initialized for reasoning")
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {e}")

    async def process(self, input_data: EmotionAnalysis) -> ReasoningOutput:
        """Process emotion analysis and return reasoning output.

        Args:
            input_data: Emotion analysis from previous stage.

        Returns:
            Real reasoning from Groq or mock output.
        """
        if self.client:
            return await self._process_with_groq(input_data)
        
        # Fallback to Mock Logic
        await asyncio.sleep(0.1)
        return self._fallback_mock(input_data)

    async def _process_with_groq(self, input_data: EmotionAnalysis) -> ReasoningOutput:
        prompt = f"""
        Analyze the following emergency call emotion data and provide a structured JSON response.
        Primary Emotion: {input_data.primary_emotion.value}
        Intensity: {input_data.intensity}
        
        Respond ONLY with a JSON object in this format:
        {{
            "key_insights": ["list", "of", "3", "insights"],
            "risk_factors": ["list", "of", "risk", "factors"],
            "context_summary": "one sentence summary",
            "confidence": 0.9
        }}
        """
        
        try:
            # Run in executor since the groq client is sync (for now)
            loop = asyncio.get_running_loop()
            completion = await loop.run_in_executor(
                None, 
                lambda: self.client.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
            )
            
            data = json.loads(completion.choices[0].message.content)
            return ReasoningOutput(
                key_insights=data.get("key_insights", []),
                risk_factors=data.get("risk_factors", []),
                context_summary=data.get("context_summary", ""),
                confidence=data.get("confidence", 0.8),
                metadata={"engine": "groq", "model": "llama3-70b-8192"}
            )
        except Exception as e:
            logger.error(f"Groq reasoning failed: {e}")
            return self._fallback_mock(input_data)

    def _fallback_mock(self, input_data: EmotionAnalysis) -> ReasoningOutput:
        if input_data.primary_emotion == input_data.primary_emotion.FEAR:
            insights = ["[Mock] High emotional distress detected", "[Mock] Potential emergency situation"]
            risk_factors = ["[Mock] Emotional crisis", "[Mock] Possible immediate danger"]
            context = "[Mock] Caller appears to be in distress and may need immediate assistance"
        else:
            insights = ["[Mock] Normal emotional state"]
            risk_factors = []
            context = "[Mock] No immediate concerns detected"

        return ReasoningOutput(
            key_insights=insights,
            risk_factors=risk_factors,
            context_summary=context,
            confidence=0.5,
            metadata={"engine": "mock"}
        )

    def get_input_schema(self):
        """Return input schema."""
        return EmotionAnalysis

    def get_output_schema(self):
        """Return output schema."""
        return ReasoningOutput