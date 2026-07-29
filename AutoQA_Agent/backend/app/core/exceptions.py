class AutoQAException(Exception):
    """Base exception for AutoQA Agent."""


class InvalidRepositoryUrlException(AutoQAException):
    """Raised when GitHub URL is invalid."""


class RepositoryCloneException(AutoQAException):
    """Raised when repository clone fails."""


class AnalysisNotFoundException(AutoQAException):
    """Raised when analysis report is not found."""
