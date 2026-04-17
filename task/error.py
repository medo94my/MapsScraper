class ScraperError(Exception):
    """Base class for scraper-related errors."""


class MissingPromptFile(ScraperError):
    """Raised when the provided prompt file path does not exist."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        super().__init__(f"Prompt file {file_path} is missing")


class WrongPromptFile(ScraperError):
    """Raised when the prompt file has no usable prompt lines."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        super().__init__(f"Prompt file {file_path} is empty or has invalid format")
