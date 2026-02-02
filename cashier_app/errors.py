class MultipleRowsAffectedError(Exception):
    pass

class NoRowsAffectedError(Exception):
    pass

class ForbiddenError(Exception):
    pass

class CanNotMakeNewEventIfNotCopyingEventError(Exception):
    pass

class NoValidEmployeesToCopyError(Exception):
    pass

class NoPasteToUndoError(Exception):
    pass

class NoPasteToRedoError(Exception):
    pass

class NoChangeToUndoError(Exception):
    pass

class NoChangeToRedoError(Exception):
    pass

class UndoTargetDeletedError(Exception):
    """Raised when trying to undo an UPDATE but the target entity was deleted by another user."""
    pass

class CanNotDeleteLastAdminError(Exception):
    pass

class InsufficientBalanceError(Exception):
    pass

class IdempotencyKeyDataConflict(Exception):
    pass

class UnexpectedError(Exception):
    pass

class PgTryAdvisoryLockError(Exception):
    pass

class ConflictingExistingEmployeeRoles(Exception):
    pass