"""Custom exceptions for scaffolded runtime contracts."""


class MnemaError(Exception):
    """Base application error."""


class ConfigurationError(MnemaError):
    """Raised when configuration cannot be loaded or validated."""


class ExternalDependencyError(MnemaError):
    """Raised when a required local binary or library is unavailable."""


class CommandNotImplementedError(MnemaError):
    """Raised by CLI placeholders for commands planned in later milestones."""


# Compatibility for integrations migrating from the old Python namespace.
TranscribeDocError = MnemaError
