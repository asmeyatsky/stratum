from domain.entities.commit import Commit
from domain.entities.author import Author
from domain.entities.file_change import FileChange
from domain.entities.dependency import Dependency
from domain.entities.vulnerability import Vulnerability
from domain.entities.risk_report import RiskReport, ComponentRisk, FileHotspot
from domain.entities.jira_issue import JiraIssue

__all__ = [
    "Commit",
    "Author",
    "FileChange",
    "Dependency",
    "Vulnerability",
    "RiskReport",
    "ComponentRisk",
    "FileHotspot",
    "JiraIssue",
]
