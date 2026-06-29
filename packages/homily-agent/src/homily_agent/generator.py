"""
Homily generation logic.

Handles the generation of homilies based on liturgical data and user preferences.
"""

import logging
from typing import Optional
from .state import (
    HomilyAgentState,
    GeneratedHomily,
    HomilySection,
    UserPreferences,
    LiturgicalReading,
)
from .rag import RetrievalService

logger = logging.getLogger(__name__)


class HomilyGenerator:
    """
    Generates homilies based on liturgical readings and user preferences.
    
    Attributes:
        retrieval_service: Service for retrieving theological content
    """
    
    def __init__(self, retrieval_service: Optional[RetrievalService] = None):
        """
        Initialize the homily generator.
        
        Args:
            retrieval_service: Service for RAG retrieval
        """
        self.retrieval_service = retrieval_service
        
    def generate(
        self,
        liturgical_data: LiturgicalReading,
        occasion: str,
        preferences: UserPreferences,
        existing_draft: Optional[str] = None
    ) -> tuple[GeneratedHomily, list[str]]:
        """
        Generate a homily based on liturgical data and preferences.
        
        Args:
            liturgical_data: The liturgical readings
            occasion: Type of occasion (mass, marriage, baptism, funeral)
            preferences: User preferences
            existing_draft: Optional existing draft to refine
            
        Returns:
            Tuple of (GeneratedHomily, list of theological sources)
        """
        logger.info(f"Generating homily for occasion: {occasion}")
        
        theme_query = self._build_theme_query(liturgical_data, occasion, preferences)
        rag_results = self._retrieve_theological_content(theme_query)
        
        introduction = self._generate_introduction(
            liturgical_data, occasion, preferences, rag_results
        )
        reading_reflection = self._generate_reading_reflection(
            liturgical_data, occasion, preferences, rag_results
        )
        practical_application = self._generate_practical_application(
            liturgical_data, occasion, preferences, rag_results
        )
        conclusion = self._generate_conclusion(
            liturgical_data, occasion, preferences, rag_results
        )
        
        sources = [r.source for r in rag_results] if rag_results else []
        
        homily = GeneratedHomily(
            introduction=introduction,
            reading_reflection=reading_reflection,
            practical_application=practical_application,
            conclusion=conclusion,
            occasion=occasion,  # type: ignore
            liturgical_date=liturgical_data.date
        )
        
        return homily, sources
    
    def _build_theme_query(
        self,
        liturgical_data: LiturgicalReading,
        occasion: str,
        preferences: UserPreferences
    ) -> str:
        """
        Build a query for retrieving relevant theological content.
        
        Args:
            liturgical_data: The liturgical readings
            occasion: Type of occasion
            preferences: User preferences
            
        Returns:
            Search query string
        """
        themes = []
        
        themes.append(f"{occasion} homily")
        themes.append(liturgical_data.metadata.season)
        
        gospel_ref = liturgical_data.gospel.reference
        themes.append(f"Gospel {gospel_ref}")
        
        if preferences.themes:
            themes.extend(preferences.themes)
            
        if preferences.parables:
            themes.extend(preferences.parables)
            
        tone_themes = {
            "consolatory": "consolation hope resurrection",
            "celebratory": "joy celebration love",
            "poetic": "beauty spirit poetic",
        }
        if preferences.tone in tone_themes:
            themes.append(tone_themes[preferences.tone])
            
        return " ".join(themes)
    
    def _retrieve_theological_content(self, query: str) -> list:
        """
        Retrieve relevant theological content using RAG.
        
        Args:
            query: Search query
            
        Returns:
            List of retrieved documents
        """
        if self.retrieval_service is None:
            logger.warning("No retrieval service configured, using empty results")
            return []
            
        try:
            results = self.retrieval_service.retrieve(query)
            logger.info(f"Retrieved {len(results)} documents for query")
            return results
        except Exception as e:
            logger.error(f"Error retrieving content: {e}")
            return []
    
    def _generate_introduction(
        self,
        liturgical_data: LiturgicalReading,
        occasion: str,
        preferences: UserPreferences,
        rag_results: list
    ) -> HomilySection:
        """
        Generate the introduction section.
        
        Args:
            liturgical_data: The liturgical readings
            occasion: Type of occasion
            preferences: User preferences
            rag_results: Retrieved theological content
            
        Returns:
            Introduction section
        """
        content = self._build_section_content(
            liturgical_data,
            occasion,
            preferences,
            rag_results,
            "introduction"
        )
        
        return HomilySection(
            title=self._get_introduction_title(occasion),
            content=content
        )
    
    def _generate_reading_reflection(
        self,
        liturgical_data: LiturgicalReading,
        occasion: str,
        preferences: UserPreferences,
        rag_results: list
    ) -> HomilySection:
        """
        Generate the reading reflection section.
        
        Args:
            liturgical_data: The liturgical readings
            occasion: Type of occasion
            preferences: User preferences
            rag_results: Retrieved theological content
            
        Returns:
            Reading reflection section
        """
        content = self._build_section_content(
            liturgical_data,
            occasion,
            preferences,
            rag_results,
            "reflection"
        )
        
        return HomilySection(
            title="Riflessione sulle letture",
            content=content
        )
    
    def _generate_practical_application(
        self,
        liturgical_data: LiturgicalReading,
        occasion: str,
        preferences: UserPreferences,
        rag_results: list
    ) -> HomilySection:
        """
        Generate the practical application section.
        
        Args:
            liturgical_data: The liturgical readings
            occasion: Type of occasion
            preferences: User preferences
            rag_results: Retrieved theological content
            
        Returns:
            Practical application section
        """
        content = self._build_section_content(
            liturgical_data,
            occasion,
            preferences,
            rag_results,
            "application"
        )
        
        return HomilySection(
            title="Applicazione pratica",
            content=content
        )
    
    def _generate_conclusion(
        self,
        liturgical_data: LiturgicalReading,
        occasion: str,
        preferences: UserPreferences,
        rag_results: list
    ) -> HomilySection:
        """
        Generate the conclusion section.
        
        Args:
            liturgical_data: The liturgical readings
            occasion: Type of occasion
            preferences: User preferences
            rag_results: Retrieved theological content
            
        Returns:
            Conclusion section
        """
        content = self._build_section_content(
            liturgical_data,
            occasion,
            preferences,
            rag_results,
            "conclusion"
        )
        
        return HomilySection(
            title="Conclusione",
            content=content
        )
    
    def _build_section_content(
        self,
        liturgical_data: LiturgicalReading,
        occasion: str,
        preferences: UserPreferences,
        rag_results: list,
        section_type: str
    ) -> str:
        """
        Build content for a section based on templates and RAG results.
        
        This is a placeholder that would normally use an LLM for actual generation.
        For now, it builds structured content based on the readings and occasion.
        
        Args:
            liturgical_data: The liturgical readings
            occasion: Type of occasion
            preferences: User preferences
            rag_results: Retrieved theological content
            section_type: Type of section (introduction, reflection, application, conclusion)
            
        Returns:
            Generated content
        """
        gospel = liturgical_data.gospel
        season = liturgical_data.metadata.season
        year = liturgical_data.metadata.year_cycle
        
        if section_type == "introduction":
            return self._build_introduction_content(gospel, occasion, preferences, season, liturgical_data.metadata.year_cycle)
        elif section_type == "reflection":
            return self._build_reflection_content(liturgical_data, occasion, preferences)
        elif section_type == "application":
            return self._build_application_content(occasion, preferences, rag_results)
        else:
            return self._build_conclusion_content(occasion, preferences, rag_results)
    
    def _build_introduction_content(
        self,
        gospel,
        occasion: str,
        preferences: UserPreferences,
        season: str,
        year: str = "A"
    ) -> str:
        """Build introduction content based on occasion."""
        
        templates = {
            "mass": f"Oggi, in questa domenica dell'{season} dell'anno {year}, la Parola di Dio ci invita a meditare sul Vangelo di {gospel.reference}. Questo brano ci conduce al cuore del messaggio di Cristo.",
            "marriage": f"In questo giorno di gioia per {preferences.themes[0] if preferences.themes else 'gli sposi'}, la Parola di Dio ci mostra il piano divino per l'amore e il matrimonio.",
            "baptism": "In questo giorno di grazia, la Parola di Dio ci introduce al mistero della nuova vita in Cristo.",
            "funeral": "In questo momento di dolcezza e speranza, la Parola di Dio ci offre consolazione e ci ricorda la promessa della vita eterna."
        }
        
        return templates.get(occasion, templates["mass"])
    
    def _build_reflection_content(
        self,
        liturgical_data: LiturgicalReading,
        occasion: str,
        preferences: UserPreferences
    ) -> str:
        """Build reflection content based on readings."""
        
        first = liturgical_data.first_reading
        gospel = liturgical_data.gospel
        
        content = f"La prima lettura da {first.reference} ci presenta un messaggio profondo."
        
        if preferences.metaphors:
            content += f" Come {preferences.metaphors[0]}, questo passaggio risuona nella nostra vita."
            
        content += f" Il Vangelo di {gospel.reference} ci invita ad accogliere questa Parola nel cuore."
        
        return content
    
    def _build_application_content(
        self,
        occasion: str,
        preferences: UserPreferences,
        rag_results: list
    ) -> str:
        """Build practical application content."""
        
        base = "Come fedeli, siamo chiamati a vivere concretamente questa verità nella nostra vita quotidiana."
        
        if preferences.analogies:
            base += f" Proprio come {preferences.analogies[0]}, possiamo trovare forza nella nostra fede."
            
        return base
    
    def _build_conclusion_content(
        self,
        occasion: str,
        preferences: UserPreferences,
        rag_results: list
    ) -> str:
        """Build conclusion content."""
        
        templates = {
            "mass": "Preghiamo affinché questa Parola ci accompagni durante la settimana e ci guiderà a vivere come discepoli di Cristo.",
            "marriage": "Auguriamo agli sposi che il loro amore cresca sempre più nell'immagine dell'amore divino.",
            "baptism": "Accogliamo nella nostra comunità questo nuovo membro e preghiamo per lui.",
            "funeral": "La nostra fede ci assicura che la vita non finisce: Cristo è risorto e ci ha aperto la porta del cielo."
        }
        
        return templates.get(occasion, templates["mass"])
    
    def _get_introduction_title(self, occasion: str) -> str:
        """Get the appropriate title for the introduction based on occasion."""
        
        titles = {
            "mass": "Introduzione",
            "marriage": "Introduzione al Matrimonio",
            "baptism": "Accoglienza del nuovo battezzato",
            "funeral": "Parola di consolazione"
        }
        
        return titles.get(occasion, "Introduzione")