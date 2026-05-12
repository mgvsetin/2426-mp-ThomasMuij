"""Vlastní výjimky používané v aplikaci pokladního systému."""

class MultipleRowsAffectedError(Exception):
    """Vyvolána, když operace ovlivní více řádků, než se očekávalo."""
    pass

class NoRowsAffectedError(Exception):
    """Vyvolána, když operace neovlivní žádný řádek, ačkoli se očekával alespoň jeden."""
    pass

class ForbiddenError(Exception):
    """Vyvolána, když uživatel nemá oprávnění k provedení požadované akce."""
    pass

class CanNotMakeNewEventIfNotCopyingEventError(Exception):
    """Vyvolána při pokusu o vytvoření nové události, pokud se nekopíruje existující událost."""
    pass

class NoValidEmployeesToCopyError(Exception):
    """Vyvolána, když nejsou k dispozici žádní platní zaměstnanci ke kopírování."""
    pass

class NoPasteToUndoError(Exception):
    """Vyvolána, když neexistuje žádné vložení, které by bylo možné vrátit zpět."""
    pass

class NoPasteToRedoError(Exception):
    """Vyvolána, když neexistuje žádné vložení, které by bylo možné znovu provést."""
    pass

class NoChangeToUndoError(Exception):
    """Vyvolána, když neexistuje žádná změna, kterou by bylo možné vrátit zpět."""
    pass

class NoChangeToRedoError(Exception):
    """Vyvolána, když neexistuje žádná změna, kterou by bylo možné znovu provést."""
    pass

class UndoTargetDeletedError(Exception):
    """Vyvolána při pokusu o vrácení aktualizace, ale cílová entita byla smazána jiným uživatelem."""
    pass

class CanNotDeleteLastAdminError(Exception):
    """Vyvolána při pokusu o smazání posledního administrátora."""
    pass

class InsufficientBalanceError(Exception):
    """Vyvolána, když je na účtu nedostatečný zůstatek pro provedení transakce."""
    pass

class IdempotencyKeyDataConflict(Exception):
    """Vyvolána, když dojde ke konfliktu dat u klíče idempotence."""
    pass

class UnexpectedError(Exception):
    """Vyvolána při výskytu neočekávané chyby."""
    pass

class PgTryAdvisoryLockError(Exception):
    """Vyvolána, když se nepodaří získat poradní zámek v PostgreSQL."""
    pass

class ConflictingExistingEmployeeRoles(Exception):
    """Vyvolána, když existují konfliktní role u stávajícího zaměstnance."""
    pass
