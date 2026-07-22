class BaseExecutor:
    """
    Abstract Base Class for all Execution Backends in Forge.
    """

    def __init__(self, name: str = "BaseExecutor"):
        self.name = name

    def can_handle(self, action_type: str, step_data: dict) -> bool:
        """Returns True if this executor supports the given action."""
        return True

    def execute(self, action_type: str, step_data: dict) -> tuple[bool, str]:
        """
        Executes the action step.
        Returns: (success: bool, result_message: str)
        """
        raise NotImplementedError("Subclasses must implement execute()")
