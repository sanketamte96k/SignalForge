from enum import Enum


class ValidationStatus(str, Enum):
    """Validation state of an instrument."""

    TESTING = "TESTING"
    VALIDATED = "VALIDATED"
    FAILED = "FAILED"
