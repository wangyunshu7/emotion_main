from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

EMOTIONS = {
    "happy": "开心",
    "calm": "平静",
    "sad": "低落",
    "anxious": "紧张",
    "angry": "生气",
    "tired": "疲惫",
}
TAGS = {
    "study": "学习",
    "work": "工作",
    "family": "家庭",
    "relationship": "人际",
    "sleep": "睡眠",
    "physical": "身体状态",
    "other": "其他",
}
ActivityType = Literal["mindfulness", "music", "movement", "writing", "daily_care"]
Scene = Literal["home", "office", "outdoor", "any"]
Score = Annotated[StrictInt, Field(ge=1, le=5)]
Version = Annotated[StrictInt, Field(ge=1)]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class Tag(Schema):
    code: str = Field(max_length=30)
    label: str = Field(min_length=1, max_length=20)


def normalize_tags(items, choices):
    result, seen = [], set()
    for item in items:
        if item.code != "custom" and item.code not in choices:
            raise ValueError("不支持的情绪或标签")
        label = item.label.strip() if item.code == "custom" else choices[item.code]
        if not label:
            raise ValueError("自定义名称不能为空")
        key = (item.code, label)
        if key not in seen:
            result.append(Tag(code=item.code, label=label))
            seen.add(key)
    return result


class Register(Schema):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=12, max_length=128)
    nickname: str | None = Field(default=None, max_length=30)
    adult_confirmed: Literal[True]
    terms_version: Literal["v1"]
    privacy_version: Literal["v1"]

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, v):
        return v.strip().lower() if isinstance(v, str) else v


class Login(Schema):
    email: EmailStr
    password: str = Field(max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, v):
        return v.strip().lower() if isinstance(v, str) else v


class UserOut(Schema):
    id: UUID
    email: str
    nickname: str | None
    timezone: str
    ai_enabled: bool
    adult_confirmed_at: datetime
    created_at: datetime


class SessionOut(Schema):
    user: UserOut | None
    csrf_token: str


class ProfilePatch(Schema):
    nickname: str | None = Field(default=None, max_length=30)
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, v):
        if v is None:
            raise ValueError("时区不可为空")
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("无效的 IANA 时区") from None
        return v

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set:
            raise ValueError("至少修改一个字段")
        return self


class ConsentIn(Schema):
    enabled: bool
    policy_version: Literal["v1"]


class ConsentOut(Schema):
    ai_enabled: bool
    consent_version: int


class DeleteAccount(Schema):
    password: str = Field(max_length=128)
    confirmation: Literal["DELETE_MY_ACCOUNT"]


class JournalFields(Schema):
    mood_score: Score
    emotions: list[Tag] = Field(min_length=1, max_length=5)
    body: str = Field(default="", max_length=10000)
    event_tags: list[Tag] = Field(default_factory=list, max_length=5)
    occurred_at: AwareDatetime

    @field_validator("emotions")
    @classmethod
    def emotions_valid(cls, v):
        return normalize_tags(v, EMOTIONS)

    @field_validator("event_tags")
    @classmethod
    def tags_valid(cls, v):
        return normalize_tags(v, TAGS)

    @field_validator("occurred_at")
    @classmethod
    def valid_time(cls, v):
        if v > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("发生时间不能晚于当前时间 5 分钟")
        return v.astimezone(timezone.utc)


class JournalCreate(JournalFields):
    client_request_id: UUID


class JournalPatch(Schema):
    version: Version
    mood_score: Score | None = None
    emotions: list[Tag] | None = Field(default=None, min_length=1, max_length=5)
    body: str | None = Field(default=None, max_length=10000)
    event_tags: list[Tag] | None = Field(default=None, max_length=5)
    occurred_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def nonnull(self):
        if len(self.model_fields_set) < 2 or any(
            getattr(self, k) is None for k in self.model_fields_set
        ):
            raise ValueError("修改字段不能为空")
        return self


class JournalOut(Schema):
    id: UUID
    client_request_id: UUID
    mood_score: int
    emotions: list[Tag]
    body: str
    event_tags: list[Tag]
    occurred_at: datetime
    version: int
    created_at: datetime
    updated_at: datetime


class JournalSummary(Schema):
    id: UUID
    mood_score: int
    emotions: list[Tag]
    event_tags: list[Tag]
    occurred_at: datetime
    version: int
    body_preview: str


T = TypeVar("T")


class Page(Schema, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int


class FactorPatch(Schema):
    review_status: Literal["unreviewed", "matches", "partial", "rejected"]
    user_text: str | None = Field(default=None, max_length=300)


class FactorOut(FactorPatch):
    id: UUID
    label: str
    hypothesis: str
    evidence_quote: str


class AnalysisOut(Schema):
    id: UUID
    journal_id: UUID
    journal_version: int
    summary: str
    reflection_question: str | None
    factors: list[FactorOut]
    created_at: datetime


class AnalysisRequest(Schema):
    journal_version: Version


class JobReceipt(Schema):
    job_id: UUID
    status: str
    poll_after_ms: int = 2000


class ReusedAnalysis(Schema):
    analysis_id: UUID
    reused: Literal[True] = True


class ReusedReview(Schema):
    review_id: UUID
    reused: Literal[True] = True


class JobResult(Schema):
    type: Literal["analysis", "weekly_review"]
    id: UUID


class JobOut(Schema):
    id: UUID
    kind: str
    status: str
    attempt: int
    error_code: str | None
    result: JobResult | None


class Step(Schema):
    order: Annotated[int, Field(ge=1)]
    text: str = Field(min_length=1, max_length=1000)


class ActivitySummary(Schema):
    id: UUID
    title: str
    type: ActivityType
    duration_minutes: int
    scenes: list[Scene]
    suitability_note: str


class ActivityOut(ActivitySummary):
    version: int
    steps: list[Step]
    audio_url: str | None = None
    source_name: str
    source_url: str | None
    license_note: str


class RecommendationIn(Schema):
    available_minutes: Annotated[StrictInt, Field(ge=1, le=60)]
    scene: Scene
    excluded_types: list[ActivityType] = Field(default_factory=list)
    journal_id: UUID | None = None


class RecommendationItem(Schema):
    activity: ActivitySummary
    reason: str


class RecommendationOut(Schema):
    items: list[RecommendationItem]
    reason_source: Literal["rules"] = "rules"
    empty_reason: str | None


class CareCreate(Schema):
    client_request_id: UUID
    activity_id: UUID
    journal_id: UUID | None = None
    before_score: Score | None = None


class CareState(Schema):
    version: Version
    status: Literal["running", "paused", "completed", "stopped"]
    elapsed_seconds: Annotated[StrictInt, Field(ge=0)]


class Feedback(Schema):
    version: Version
    before_score: Score | None = None
    after_score: Score | None = None
    helpfulness: Literal["helpful", "neutral", "not_suitable"] | None = None
    feedback_note: str | None = Field(default=None, max_length=500)


class CareOut(Schema):
    id: UUID
    activity_id: UUID
    activity_snapshot: dict
    journal_id: UUID | None
    status: str
    version: int
    elapsed_seconds: int
    started_at: datetime
    ended_at: datetime | None
    before_score: int | None
    after_score: int | None
    helpfulness: str | None
    feedback_note: str | None


class DayStat(Schema):
    date: date
    entry_count: int
    mean_score: float | None


class Distribution(Schema):
    code: str
    label: str
    entry_count: int
    ratio: float | None = None


class CareStat(Schema):
    completed_count: int
    feedback_count: int
    helpful_count: int


class InsightsOut(Schema):
    timezone: str
    start_date: date
    end_date: date
    entry_count: int
    recorded_days: int
    mean_score: float | None
    days: list[DayStat]
    emotion_distribution: list[Distribution]
    tag_distribution: list[Distribution]
    care_summary: CareStat


class ReviewRequest(Schema):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def weekly(self):
        if (self.end_date - self.start_date).days != 6:
            raise ValueError("周回顾必须覆盖连续 7 天")
        return self


class Evidence(Schema):
    journal_id: UUID | None = None
    quote: str | None = None
    stat_path: str | None = None


class Observation(Schema):
    text: str = Field(min_length=1, max_length=300)
    evidence: list[Evidence] = Field(min_length=1)


class ReviewOut(Schema):
    id: UUID
    start_date: date
    end_date: date
    timezone: str
    statistics: InsightsOut
    insight_eligible: bool
    narrative: str | None
    observations: list[Observation]
    ai_status: str
    created_at: datetime


class ModelFactor(Schema):
    label: str = Field(min_length=1, max_length=100)
    hypothesis: str = Field(min_length=1, max_length=300)
    evidence_quote: str = Field(min_length=1, max_length=300)


class ModelAnalysis(Schema):
    summary: str = Field(min_length=1, max_length=300)
    factors: list[ModelFactor] = Field(max_length=3)
    reflection_question: str | None = Field(max_length=150)


class ModelReview(Schema):
    narrative: str = Field(min_length=1, max_length=1000)
    observations: list[Observation] = Field(max_length=5)


class ActivityImport(Schema):
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")
    version: Version = 1
    title: str = Field(min_length=1, max_length=100)
    type: ActivityType
    duration_minutes: Annotated[StrictInt, Field(ge=1, le=60)]
    scenes: list[Scene] = Field(min_length=1)
    steps: list[Step] = Field(min_length=1)
    audio_asset_key: str | None = None
    suitability_note: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: str | None = None
    license_note: str = Field(min_length=1)
    reviewer: str | None = None
    reviewed_at: AwareDatetime | None = None
    review_due_at: AwareDatetime | None = None
    status: Literal["draft", "published", "archived"] = "draft"

    @field_validator("source_url")
    @classmethod
    def safe_url(cls, value):
        from urllib.parse import urlsplit

        if value and (
            urlsplit(value).scheme not in {"https", "http"} or not urlsplit(value).netloc
        ):
            raise ValueError("来源必须为有效的 HTTP(S) 地址")
        return value

    @model_validator(mode="after")
    def reviewed(self):
        if self.audio_asset_key:
            raise ValueError("首版仅支持文字活动；音频须完成资源域名及授权配置后接入")
        if self.status == "published" and not all(
            (self.reviewer, self.reviewed_at, self.review_due_at)
        ):
            raise ValueError("发布需要完整审核信息")
        if self.reviewed_at and self.review_due_at and self.review_due_at <= self.reviewed_at:
            raise ValueError("复核期限必须晚于审核时间")
        return self


class SupportImport(Schema):
    region_code: str = Field(min_length=1, max_length=16)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    contact_text: str | None = Field(default=None, max_length=200)
    url: str | None = None
    source_url: str
    verified_by: str = Field(min_length=1, max_length=200)
    verified_at: AwareDatetime
    review_due_at: AwareDatetime
    status: Literal["draft", "published", "archived"] = "draft"

    @field_validator("url", "source_url")
    @classmethod
    def safe_url(cls, value):
        return ActivityImport.safe_url(value)

    @model_validator(mode="after")
    def ordered(self):
        if self.review_due_at <= self.verified_at:
            raise ValueError("复核期限必须晚于核验时间")
        return self


class ConsentEventOut(Schema):
    action: str
    policy_version: str
    provider_key: str
    purpose: str
    occurred_at: datetime


class ConsentHistory(ConsentOut):
    events: list[ConsentEventOut]


class MetadataOut(Schema):
    emotions: list[Tag]
    event_tags: list[Tag]
    scores: list[str]
    terms_version: str
    privacy_version: str
    ai_policy_version: str
    ai_available: bool
    ai_mode: str
    ai_description: str


class SupportOut(Schema):
    id: UUID
    title: str
    description: str
    contact_text: str | None
    url: str | None
    source_url: str
    verified_at: datetime


class SupportList(Schema):
    items: list[SupportOut]
    generic_support_text: str


class FieldError(Schema):
    path: str
    message: str


class ErrorInfo(Schema):
    code: str
    message: str
    fields: list[FieldError]
    request_id: str


class ErrorOut(Schema):
    error: ErrorInfo
