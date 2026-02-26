"""Orchestrator for chaining agents in the Redline AI pipeline."""

import asyncio
import logging
from typing import Any, Dict, Optional

from ..agents.base import BaseAgent
from ..plugins.registry import PluginRegistry
from ..core.schemas import (
    Transcript,
    EmotionAnalysis,
    ReasoningOutput,
    SeverityAssessment,
    SafetyOutput,
    DispatchReport,
)

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orchestrator that chains agents in the emergency response pipeline.

    The pipeline follows: STT → Emotion → Reasoning → Severity → Safety → Dispatch
    """

    def __init__(self, plugin_registry: PluginRegistry):
        self.plugin_registry = plugin_registry
        self.agents: Dict[str, BaseAgent] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the orchestrator and load agents."""
        if self._initialized:
            return

        # Load agents from plugins
        await self._load_agents()
        self._initialized = True
        logger.info("Orchestrator initialized")

    async def _load_agents(self) -> None:
        """Load and initialize agents from available plugins."""
        # For each stage, load the corresponding agent
        stages = ['stt', 'emotion', 'reasoning', 'severity', 'safety', 'dispatch']

        for stage in stages:
            # For now, assume we have one plugin per stage
            # In production, this would be configurable
            plugin_name = f"mock_{stage}"  # e.g., mock_stt
            plugin = self.plugin_registry.get_plugin(plugin_name)

            if plugin and hasattr(plugin, 'create_agent'):
                agent = await plugin.create_agent()
                self.agents[stage] = agent
                logger.info(f"Loaded agent for stage: {stage}")
            else:
                logger.warning(f"No plugin found for stage: {stage}")

    async def process_emergency_call(self, audio_data: bytes) -> Optional[DispatchReport]:
        """Process an emergency call through the entire pipeline.

        Args:
            audio_data: Raw audio data of the emergency call.

        Returns:
            Dispatch report if processing succeeds, None otherwise.
        """
        try:
            # Step 1: STT - Convert audio to transcript
            transcript = await self._execute_stage('stt', audio_data)
            if not transcript:
                logger.error("STT stage failed")
                return None

            # Step 2: Emotion - Analyze emotions in audio
            # Pass original audio_data to get real acoustic features
            emotion_analysis = await self._execute_stage('emotion', audio_data)
            if not emotion_analysis:
                logger.error("Emotion stage failed")
                return None
            
            # Link transcript and emotion for reasoning
            if hasattr(emotion_analysis, 'text_segments'):
                emotion_analysis.text_segments = [transcript.text]

            # Step 3: Reasoning - Apply reasoning to emotion analysis
            reasoning_output = await self._execute_stage('reasoning', emotion_analysis)
            if not reasoning_output:
                logger.error("Reasoning stage failed")
                return None

            # Step 4: Severity - Assess severity based on reasoning
            severity_assessment = await self._execute_stage('severity', reasoning_output)
            if not severity_assessment:
                logger.error("Severity stage failed")
                return None

            # Step 5: Safety - Apply safety checks
            safety_output = await self._execute_stage('safety', severity_assessment)
            if not safety_output:
                logger.error("Safety stage failed")
                return None

            # Step 6: Dispatch - Generate dispatch report
            dispatch_report = await self._execute_stage('dispatch', safety_output)
            if not dispatch_report:
                logger.error("Dispatch stage failed")
                return None

            logger.info("Emergency call processed successfully")
            return dispatch_report

        except Exception as e:
            logger.error(f"Error processing emergency call: {e}")
            return None

    async def _execute_stage(self, stage_name: str, input_data: Any) -> Any:
        """Execute a single stage in the pipeline.

        Args:
            stage_name: Name of the stage to execute.
            input_data: Input data for the stage.

        Returns:
            Output from the stage, or None if failed.
        """
        agent = self.agents.get(stage_name)
        if not agent:
            logger.error(f"No agent available for stage: {stage_name}")
            return None

        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                agent.process(input_data),
                timeout=30.0  # Configurable timeout
            )
            logger.debug(f"Stage {stage_name} completed successfully")
            return result
        except asyncio.TimeoutError:
            logger.error(f"Stage {stage_name} timed out")
            return None
        except Exception as e:
            logger.error(f"Stage {stage_name} failed: {e}")
            return None

    def get_pipeline_status(self) -> Dict[str, bool]:
        """Get the status of each pipeline stage.

        Returns:
            Dictionary mapping stage names to availability status.
        """
        return {stage: stage in self.agents for stage in
                ['stt', 'emotion', 'reasoning', 'severity', 'safety', 'dispatch']}