"""cce: a hands-on playground for GitHub Copilot CLI customisation.

The package prepares one git worktree per scenario on top of a public docs
repository and overlays Copilot customisation files, so that anyone can explore
when to use repository instructions, Agent Skills or custom agents.
"""

__version__ = "0.1.1"


class CceError(Exception):
    """Base error for every failure ``cce`` reports to the user.

    ``exit_code`` follows the documented contract: 1 runtime failure,
    2 usage error, 3 refused precondition.
    """

    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code
