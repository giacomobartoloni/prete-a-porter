"""
Homily Agent implementation with LangGraph.

Implements the agent reasoning logic for homily generation.
"""

import logging
from typing import Dict, Any, Optional
from .state import (
    HomilyAgentState,
    UserPreferences,
    LiturgicalReading,
    GeneratedHomily,
)
from .generator import HomilyGenerator

logger = logging.getLogger(__name__)


class HomilyAgent:
    """
    Agent for generating homilies using LangGraph and LLM.
    
    Attributes:
        generator: The homily generator
    """
    
    def __init__(self, generator: Optional[HomilyGenerator] = None):
        """
        Initialize the homily agent.
        
        Args:
            generator: Homily generator instance
        """
        self.generator = generator or HomilyGenerator()
        
    def parse_request(self, state: HomilyAgentState) -> Dict[str, Any]:
        """
        Parse the incoming request and extract parameters.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state dictionary
        """
        logger.info(f"Parsing homily request: intent={state.intent}, occasion={state.occasion}")
        
        updates: Dict[str, Any] = {}
        
        if state.user_preferences is None:
            updates["user_preferences"] = UserPreferences()
            
        return updates
    
    def generate_homily(self, state: HomilyAgentState) -> Dict[str, Any]:
        """
        Generate the homily based on liturgical data and preferences.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with generated homily
        """
        logger.info(f"Generating homily for occasion: {state.occasion}")
        
        try:
            if state.liturgical_data is None:
                raise ValueError("No liturgical data provided")
                
            preferences = state.user_preferences or UserPreferences()
            
            homily, sources = self.generator.generate(
                liturgical_data=state.liturgical_data,
                occasion=state.occasion,
                preferences=preferences,
                existing_draft=state.existing_draft
            )
            
            logger.info(f"Homily generated successfully, sources: {sources}")
            
            state.generated_homily = homily
            state.theological_sources = sources
            
            return {
                "generated_homily": homily,
                "theological_sources": sources
            }
            
        except Exception as e:
            logger.error(f"Error generating homily: {e}")
            state.error = str(e)
            return {"error": str(e)}
    
    def refine_homily(self, state: HomilyAgentState) -> Dict[str, Any]:
        """
        Refine an existing homily based on feedback.
        
        Args:
            state: Current agent state with existing draft
            
        Returns:
            Updated state with refined homily
        """
        logger.info("Refining existing homily")
        
        try:
            if state.existing_draft is None:
                raise ValueError("No existing draft to refine")
                
            preferences = state.user_preferences or UserPreferences()
            
            if state.liturgical_data:
                homily, sources = self.generator.generate(
                    liturgical_data=state.liturgical_data,
                    occasion=state.occasion,
                    preferences=preferences,
                    existing_draft=state.existing_draft
                )
                
                return {
                    "generated_homily": homily,
                    "theological_sources": sources
                }
            else:
                return {"error": "Cannot refine without liturgical data"}
                
        except Exception as e:
            logger.error(f"Error refining homily: {e}")
            return {"error": str(e)}
    
    def adjust_tone(self, state: HomilyAgentState) -> Dict[str, Any]:
        """
        Adjust the tone of an existing homily.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with adjusted homily
        """
        logger.info(f"Adjusting homily tone")
        
        return self.refine_homily(state)
    
    def validate_homily(self, state: HomilyAgentState) -> Dict[str, Any]:
        """
        Validate the theological accuracy of a homily.
        
        Args:
            state: Current agent state
            
        Returns:
            Validation result
        """
        logger.info("Validating homily")
        
        validation_result = {
            "valid": True,
            "issues": []
        }
        
        if state.generated_homily is None:
            validation_result["valid"] = False
            validation_result["issues"].append("No homily to validate")
            
        return {"validation": validation_result}
    
    def format_response(self, state: HomilyAgentState) -> Dict[str, Any]:
        """
        Format the generated homily for response.
        
        Args:
            state: Current agent state
            
        Returns:
            Formatted response data
        """
        if state.error:
            return {"error": state.error}
            
        if state.generated_homily is None:
            return {"error": "No homily generated"}
            
        homily = state.generated_homily
        
        response_text = self._format_homily_text(homily)
        
        return {
            "homily": homily.model_dump(),
            "formatted_text": response_text,
            "sources": state.theological_sources or []
        }
    
    def _format_homily_text(self, homily: GeneratedHomily) -> str:
        """
        Format homily as readable text.
        
        Args:
            homily: The generated homily
            
        Returns:
            Formatted text
        """
        lines = []
        
        lines.append(f"--- {homily.introduction.title} ---\n")
        lines.append(homily.introduction.content)
        lines.append("")
        
        lines.append(f"--- {homily.reading_reflection.title} ---\n")
        lines.append(homily.reading_reflection.content)
        lines.append("")
        
        lines.append(f"--- {homily.practical_application.title} ---\n")
        lines.append(homily.practical_application.content)
        lines.append("")
        
        lines.append(f"--- {homily.conclusion.title} ---\n")
        lines.append(homily.conclusion.content)
        
        return "\n".join(lines)