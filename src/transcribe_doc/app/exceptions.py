"""Custom exceptions for scaffolded runtime contracts."""


class TranscribeDocError(Exception):
    """Base application error."""


class ConfigurationError(TranscribeDocError):
    """Raised when configuration cannot be loaded or validated."""


class ExternalDependencyError(TranscribeDocError):
    """Raised when a required local binary or library is unavailable."""


class CommandNotImplementedError(TranscribeDocError):
    """Raised by CLI placeholders for commands planned in later milestones."""
