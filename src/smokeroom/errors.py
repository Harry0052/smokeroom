"""Actionable contract errors for fixture and configuration checks."""


class ContractError(Exception):
    """A fixture or configuration failed a named check.

    ``category`` is a stable machine token. ``message`` states the field,
    the offending value, and the required unit or bound.
    """

    def __init__(self, category: str, message: str) -> None:
        self.category = category
        self.message = message
        super().__init__(f"{category}: {message}")
