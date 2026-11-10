"""Explicit deterministic model for TEST_MODE contract fixtures, never production."""

import json

from langchain_core.messages import AIMessage

from homily_agent.composition import SECTION_NAMES


class FixtureHomilyModel:
    """Exercise request parsing and graph transport without external LLM access."""

    def invoke(self, messages):
        request = json.loads(messages[-1].content)
        count = request["target_word_count"]
        payload = {}
        for index, key in enumerate(SECTION_NAMES):
            words = count // 4 + (1 if index < count % 4 else 0)
            payload[key] = {"title": key, "content": " ".join(["fixture"] * words)}
        return AIMessage(content=json.dumps(payload | {"used_source_ids": []}))
