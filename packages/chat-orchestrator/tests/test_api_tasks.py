"""Classification of OpenWebUI utility requests.

The prompt fixtures are the DEFAULT TEMPLATES from OpenWebUI's documentation,
reproduced verbatim. Do not replace them with invented strings: the point of
these tests is that the markers survive the real templates.
"""

from chat_orchestrator.api.schemas import MODEL_ID, ChatCompletionRequest
from chat_orchestrator.api.tasks import UTILITY_TASKS, classify_task


def _req(messages, **overrides):
    body = {"model": MODEL_ID, "messages": messages}
    body.update(overrides)
    return ChatCompletionRequest(**body)


USER = {"role": "user", "content": "ciao"}
ASSISTANT = {"role": "assistant", "content": "risposta"}


# --- Verbatim default templates from OpenWebUI docs -------------------------

TITLE_PROMPT = """### Task:
Generate a concise title summarizing the chat history.
### Guidelines:
- The title should clearly represent the main theme or subject of the conversation.
- Keep it short: 2-4 words is best.
- Do not use emojis, quotation marks, or special formatting.
- Write the title in the chat's primary language; default to English if multilingual.
- Prioritize accuracy over creativity.
- Your entire response must consist solely of the JSON object, without any introductory or concluding text.
- The output must be a single, raw JSON object, without any markdown code fences or other encapsulating text.
- Ensure no conversational text, affirmations, or explanations precede or follow the raw JSON output, as this will cause direct parsing failure.
### Output:
JSON format: { "title": "your concise title here" }
### Examples:
- { "title": "Stock Trends" },
- { "title": "Chocolate Chip Cookies" },
- { "title": "Music Streaming" },
- { "title": "Remote Work" }
### Chat History:
<chat_history>
{{MESSAGES:END:2}}
</chat_history>"""

TAGS_PROMPT = """### Task:
Generate 1-3 broad tags categorizing the main themes of the chat history, along with 1-3 more specific subtopic tags.

### Guidelines:
- Start with high-level domains (e.g., Science, Technology, Philosophy, Arts, Politics, Business, Health, Sports, Entertainment, Education)
- Consider including relevant subfields/subdomains if they are strongly represented throughout the conversation
- If content is too short (less than 3 messages) or too diverse, use only ["General"]
- Use the chat's primary language; default to English if multilingual
- Prioritize accuracy over specificity

### Output:
JSON format: { "tags": ["tag1", "tag2", "tag3"] }

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>"""

FOLLOW_UP_PROMPT = """### Task:
Suggest 3-5 relevant follow-up questions or prompts that the user might naturally ask next in this conversation as a **user**, based on the chat history, to help continue or deepen the discussion.

### Guidelines:
- Write all follow-up questions from the user's point of view, directed to the assistant.
- Make questions concise, clear, and directly related to the discussed topic(s).
- Only suggest follow-ups that make sense given the chat content and do not repeat what was already covered.
- If the conversation is very short or not specific, suggest more general (but relevant) follow-ups the user might ask.
- Use the conversation's primary language; default to English if multilingual.
- Response must be a JSON array of strings, no extra text or formatting.

### Output:
JSON format: { "follow_ups": ["Question 1?", "Question 2?", "Question 3?"] }

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>"""

AUTOCOMPLETE_PROMPT = """### Task:
You are an autocompletion system. Continue the text in `<text>` based on the **completion type** in `<type>` and the given language.

### **Instructions**:
1. Analyze `<text>` for context and meaning.
2. Use `<type>` to guide your output:
   - **General**: Provide a natural, concise continuation.
   - **Search Query**: Complete as if generating a realistic search query.
3. Start as if you are directly continuing `<text>`. Do **not** repeat, paraphrase, or respond as a model. Simply complete the text.

### **Output Rules**:
- Respond only in JSON format: `{ "text": "<your_completion>" }`.

### Context:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>
<type>{{TYPE}}</type>
<text>{{PROMPT}}</text>

#### Output:"""


class TestVerbatimTemplates:
    """The markers must survive the real templates, not invented ones."""

    def test_title_template_is_detected(self):
        assert classify_task(_req([{"role": "user", "content": TITLE_PROMPT}])) == "title_generation"

    def test_tags_template_is_detected(self):
        assert classify_task(_req([{"role": "user", "content": TAGS_PROMPT}])) == "tags_generation"

    def test_follow_up_template_is_detected(self):
        assert classify_task(_req([{"role": "user", "content": FOLLOW_UP_PROMPT}])) == "follow_up_generation"

    def test_autocomplete_template_is_detected(self):
        assert classify_task(_req([{"role": "user", "content": AUTOCOMPLETE_PROMPT}])) == "autocomplete_generation"


class TestExplicitMetadata:
    def test_reads_metadata_task(self):
        req = _req([USER], metadata={"task": "title_generation"})
        assert classify_task(req) == "title_generation"

    def test_ignores_blank_metadata_task(self):
        req = _req([USER], metadata={"task": ""})
        assert classify_task(req) is None

    def test_ignores_non_string_metadata_task(self):
        req = _req([USER], metadata={"task": 123})
        assert classify_task(req) is None

    def test_unknown_task_name_is_still_returned(self):
        """An unrecognised task is still a utility request, not a chat."""
        req = _req([USER], metadata={"task": "custom_task"})
        assert classify_task(req) == "custom_task"


class TestPromptShape:
    def test_plain_message_is_not_a_task(self):
        assert classify_task(_req([USER])) is None

    def test_task_marker_without_prefix_is_not_a_task(self):
        """The prefix is required; the words alone must not trigger it."""
        req = _req([{"role": "user", "content": 'Generate a concise title. {"title": "x"}'}])
        assert classify_task(req) is None

    def test_guidelines_rewording_does_not_break_detection(self):
        """Administrators can edit the prose; the Output JSON key is the anchor."""
        reworded = TITLE_PROMPT.replace(
            "Generate a concise title summarizing the chat history.",
            "Invent a very short label for this thread.",
        )
        assert classify_task(_req([{"role": "user", "content": reworded}])) == "title_generation"


class TestShortMessagesAreRealChats:
    """No follow-up heuristic: short messages are action authorisations here.

    The reference implementation treats a short third-turn message as a
    conversational follow-up. In this domain that is wrong: after the assistant
    offers to generate a homily, "si" or "ok" mean "generate it now", which
    requires the graph and the liturgical tools.
    """

    def test_italian_yes_is_a_real_chat(self):
        req = _req([USER, ASSISTANT, {"role": "user", "content": "sì"}])
        assert classify_task(req) is None

    def test_ok_is_a_real_chat(self):
        req = _req([USER, ASSISTANT, {"role": "user", "content": "ok"}])
        assert classify_task(req) is None

    def test_vai_is_a_real_chat(self):
        req = _req([USER, ASSISTANT, {"role": "user", "content": "vai"}])
        assert classify_task(req) is None

    def test_grazie_is_a_real_chat(self):
        """Even a purely conversational turn runs the graph; one extra LLM call is cheap."""
        req = _req([USER, ASSISTANT, {"role": "user", "content": "grazie"}])
        assert classify_task(req) is None


class TestUtilityTaskSet:
    def test_contains_every_detected_task(self):
        assert {
            "title_generation",
            "tags_generation",
            "follow_up_generation",
            "autocomplete_generation",
            "query_generation",
            "context_compaction",
        } <= UTILITY_TASKS
