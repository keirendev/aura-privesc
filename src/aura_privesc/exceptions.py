"""Custom exception hierarchy for aura-privesc."""


class AuraError(Exception):
    """Base exception for all aura-privesc errors."""


class DiscoveryError(AuraError):
    """Failed to discover Aura endpoint or context."""


class ClientOutOfSyncError(AuraError):
    """Server returned aura:clientOutOfSync — fwuid mismatch."""

    def __init__(self, new_fwuid: str | None = None):
        self.new_fwuid = new_fwuid
        super().__init__(f"Client out of sync, new fwuid: {new_fwuid}")


class InvalidSessionError(AuraError):
    """Token is expired or invalid."""


class AuraRequestError(AuraError):
    """Generic Aura request failure."""

    def __init__(self, message: str, status_code: int | None = None, raw: str | None = None):
        self.status_code = status_code
        self.raw = raw
        super().__init__(message)


class ReconError(AuraError):
    """Salesforce CLI recon operation failed."""
