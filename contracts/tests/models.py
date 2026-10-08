"""Independent consumer expectations; never import producer state models here."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, StrictStr, model_validator
from typing_extensions import NotRequired, TypedDict

Nonblank = Annotated[StrictStr, Field(pattern=r"\S")]
ISODate = Annotated[StrictStr, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
Occasion = Literal["mass", "marriage", "baptism", "funeral"]
Ritual = Literal["marriage", "baptism", "funeral"]


class ConsumerModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadingContract(ConsumerModel):
    reference: Nonblank
    text: Nonblank
    type: Literal["First", "Second", "Gospel", "Psalm", "Alleluia"]


class MetadataContract(ConsumerModel):
    date: ISODate
    occasion: Occasion
    season: Nonblank
    color: Nonblank
    year_cycle: Literal["A", "B", "C"]
    sunday_or_weekday: Literal["Sunday", "Weekday"]


class DailyMassDataContract(ConsumerModel):
    date: ISODate
    occasion: Literal["mass"]
    metadata: MetadataContract
    first_reading: ReadingContract
    psalm: ReadingContract
    second_reading: ReadingContract | None = None
    gospel: ReadingContract
    alleluia_verse: ReadingContract | None = None
    cached_at: datetime
    source: Nonblank

    @model_validator(mode="after")
    def require_sunday_second(self):
        if self.metadata.sunday_or_weekday == "Sunday" and self.second_reading is None:
            raise ValueError("Sunday Mass requires a second reading")
        return self


class DailyMassResultContract(ConsumerModel):
    status: Literal["success"]
    data: DailyMassDataContract
    source: Literal["web", "cache"]


class RitualReadingContract(ReadingContract):
    id: Annotated[int, Field(gt=0)]
    theme: Nonblank


class RitualCollectionContract(ConsumerModel):
    occasion_name: Nonblank
    general_readings: list[RitualReadingContract]


class LectionaryDataContract(RootModel[dict[Ritual, RitualCollectionContract]]):
    @model_validator(mode="after")
    def require_one_ritual(self):
        if len(self.root) != 1:
            raise ValueError("Lectionary must contain exactly one ritual collection")
        return self


class RitualReadingsResultContract(ConsumerModel):
    status: Literal["success"]
    data: LectionaryDataContract
    source: Literal["lectionary"]


class LectionaryResultContract(ConsumerModel):
    occasion: Ritual
    lectionary: LectionaryDataContract
    readings_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def verify_collection(self):
        collection = self.lectionary.root.get(self.occasion)
        if collection is None or self.readings_count != len(collection.general_readings):
            raise ValueError("Lectionary occasion/count does not match its collection")
        return self


class ReadingsErrorContract(ConsumerModel):
    status: Literal["error"]
    error: Nonblank
    message: Nonblank | None = None


class ReadingsRequestContract(ConsumerModel):
    occasion: Literal["sunday", "mass", "weekday", "daily", "marriage", "baptism", "funeral"]
    date: ISODate | None = None


class LectionaryRequestContract(ConsumerModel):
    occasion: Ritual


class PreferencesContract(ConsumerModel):
    target_audience: Literal["adults", "youth", "children", "mixed"] = "adults"
    tone: Literal["formal", "conversational", "poetic", "consolatory", "celebratory"] = "formal"
    length: Literal["short", "medium", "long"] = "medium"
    themes: list[StrictStr] | None = None
    metaphors: list[StrictStr] | None = None
    analogies: list[StrictStr] | None = None
    parables: list[StrictStr] | None = None


class HomilyMetadataInput(TypedDict):
    date: ISODate
    occasion: NotRequired[Occasion]
    season: StrictStr
    color: StrictStr
    year_cycle: Literal["A", "B", "C"]
    sunday_or_weekday: Literal["Sunday", "Weekday"]


class HomilyReadingInput(TypedDict):
    date: ISODate
    occasion: NotRequired[Occasion]
    metadata: NotRequired[HomilyMetadataInput]
    first_reading: ReadingContract
    psalm: NotRequired[ReadingContract | None]
    second_reading: NotRequired[ReadingContract | None]
    gospel: ReadingContract
    alleluia_verse: NotRequired[ReadingContract | None]
    cached_at: NotRequired[datetime]
    source: NotRequired[StrictStr]


class GenerateRequestContract(ConsumerModel):
    liturgical_data: HomilyReadingInput
    occasion: Occasion = "mass"
    preferences: PreferencesContract = Field(default_factory=PreferencesContract)


class RefineRequestContract(GenerateRequestContract):
    existing_draft: Nonblank


class HomilySectionContract(ConsumerModel):
    title: Nonblank
    content: Nonblank


class GeneratedHomilyContract(ConsumerModel):
    introduction: HomilySectionContract
    reading_reflection: HomilySectionContract
    practical_application: HomilySectionContract
    conclusion: HomilySectionContract
    occasion: Occasion
    liturgical_date: ISODate


class HomilyDataContract(ConsumerModel):
    homily: GeneratedHomilyContract
    sources: list[StrictStr]


class HomilySuccessContract(ConsumerModel):
    status: Literal["success"]
    data: HomilyDataContract


class PingRequestContract(ConsumerModel):
    pass


class PingResultContract(ConsumerModel):
    status: Literal["pong"]
    agent: Literal["liturgy_agent", "homily_agent"]
    version: Nonblank


def inline_schema(model: type[BaseModel]) -> dict:
    """Expand local model references for the existing custom contract format."""
    schema = model.model_json_schema()
    definitions = schema.pop("$defs", {})

    def expand(value):
        if isinstance(value, list):
            return [expand(item) for item in value]
        if isinstance(value, dict):
            if "$ref" in value:
                return expand(definitions[value["$ref"].split("/")[-1]])
            return {key: expand(item) for key, item in value.items() if not (key == "title" and isinstance(item, str))}
        return value

    return expand(schema)
