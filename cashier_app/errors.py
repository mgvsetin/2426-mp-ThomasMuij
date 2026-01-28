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

class CanNotDeleteLastAdminError(Exception):
    pass