from homily_agent.state import HomilyAgentState, GeneratedHomily, HomilySection
from homily_agent.agent import HomilyAgent
from homily_agent.graph import GraphState


class TestValidateNode:
    def test_validate_sets_validation_on_state(self):
        agent = HomilyAgent()
        section = HomilySection(title="x", content="y")
        homily = GeneratedHomily(
            introduction=section,
            reading_reflection=section,
            practical_application=section,
            conclusion=section,
            occasion="mass",
            liturgical_date="2026-05-19",
        )
        state = HomilyAgentState(generated_homily=homily)
        graph_state: GraphState = {"homily_state": state}

        from homily_agent.graph import _validate_node

        result = _validate_node(graph_state, agent)
        homily_state = result["homily_state"]

        assert homily_state.validation is not None
        assert homily_state.validation["valid"] is True

    def test_validate_detects_missing_homily(self):
        agent = HomilyAgent()
        state = HomilyAgentState()
        graph_state: GraphState = {"homily_state": state}

        from homily_agent.graph import _validate_node

        result = _validate_node(graph_state, agent)
        homily_state = result["homily_state"]

        assert homily_state.validation["valid"] is False
        assert "No homily to validate" in homily_state.validation["issues"]
