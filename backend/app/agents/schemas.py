"""Validated tool inputs, provider evidence and structured workflow outputs."""
from datetime import date
from typing import Annotated, Literal, TypedDict
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, StringConstraints, field_validator

Workflow = Literal['pull_request', 'sprint_summary', 'blockers', 'priorities']
IssueKey = Annotated[str, StringConstraints(pattern=r'^[A-Z][A-Z0-9_]*-[0-9]+$', max_length=100)]
Text = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
Count = Annotated[int, Field(ge=0, strict=True)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ProjectContext(StrictModel):
    id: int = Field(gt=0)
    organization_id: int = Field(gt=0)
    github_repository: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}$')
    jira_key: str = Field(pattern=r'^[A-Z][A-Z0-9_]*$')
    jira_board_id: int = Field(gt=0)

    @field_validator('github_repository')
    @classmethod
    def reject_path_segments(cls, value):
        if value.split('/')[-1] in {'.', '..'}:
            raise ValueError('Invalid repository path')
        return value


class Analysis(StrictModel):
    summary: str = Field(min_length=1, max_length=4000)
    risks: list[Text] = Field(default_factory=list, max_length=30)
    testing: list[Text] = Field(default_factory=list, max_length=30)
    recommendations: list[Text] = Field(default_factory=list, max_length=30)


class PRPayload(StrictModel):
    number: int = Field(gt=0, strict=True)


class SprintPayload(StrictModel):
    number: int | None = Field(default=None, gt=0, strict=True)
    issue_key: IssueKey | None = None


class RoutingInput(BaseModel):
    event_type: Workflow
    payload: dict


class ChangedFile(StrictModel):
    filename: str = Field(min_length=1, max_length=1024)
    additions: Count
    deletions: Count


class Commit(StrictModel):
    sha: str = Field(min_length=1, max_length=100)
    message: str = Field(max_length=50000)


class PREvidence(StrictModel):
    number: int = Field(gt=0, strict=True)
    repository: str
    title: str = Field(min_length=1, max_length=2000)
    body: str = Field(max_length=1000000)
    files: list[ChangedFile] = Field(max_length=3000)
    commits: list[Commit] = Field(max_length=3000)
    url: AnyHttpUrl
    linked_issues: list[IssueKey] = Field(default_factory=list)


class Issue(StrictModel):
    key: IssueKey
    summary: Text
    status: str = Field(min_length=1, max_length=100)
    priority: str = Field(min_length=1, max_length=100)
    severity: int = Field(ge=0, le=10, strict=True)
    due_date: date | None
    dependencies: list[IssueKey]
    sprint: bool
    updated: date


class SprintEvidence(StrictModel):
    id: str = Field(min_length=1, max_length=200)
    name: Text
    issues: list[Issue] = Field(max_length=10000)
    reference_date: date

    @field_validator('issues')
    @classmethod
    def unique_keys(cls, issues):
        if len({issue.key for issue in issues}) != len(issues):
            raise ValueError('Duplicate Jira issue keys')
        return issues


class BlockerFinding(StrictModel):
    issue_key: IssueKey
    kind: Literal['explicit', 'dependency', 'stalled', 'overdue']
    certainty: Literal['definite', 'potential']
    evidence: Text
    recommendation: Text
    pull_requests: list[AnyHttpUrl] = Field(default_factory=list)


class RankedIssue(Issue):
    score: Count
    components: dict[str, Count]
    explanation: Text


class PRResult(StrictModel):
    provider_id: str
    analysis: Analysis
    evidence: PREvidence


class SprintResult(StrictModel):
    provider_id: str
    analysis: Analysis
    distribution: dict[str, Count]
    progress: float = Field(ge=0, le=1)
    evidence: SprintEvidence


class BlockerResult(StrictModel):
    provider_id: str
    analysis: Analysis
    items: list[BlockerFinding]
    evidence: SprintEvidence


class PriorityResult(StrictModel):
    provider_id: str
    analysis: Analysis
    items: list[RankedIssue]
    evidence: SprintEvidence


class State(TypedDict, total=False):
    event_type: Workflow
    payload: dict
    project: ProjectContext
    reference_date: str
    evidence: dict
    output: dict
