"""Testy vlastních výjimek z modulu cashier_app.errors."""

import pytest
from cashier_app.errors import (
    MultipleRowsAffectedError,
    NoRowsAffectedError,
    ForbiddenError,
    CanNotMakeNewEventIfNotCopyingEventError,
    NoValidEmployeesToCopyError,
    NoPasteToUndoError,
    NoPasteToRedoError,
    NoChangeToUndoError,
    NoChangeToRedoError,
    UndoTargetDeletedError,
    CanNotDeleteLastAdminError,
    InsufficientBalanceError,
    IdempotencyKeyDataConflict,
    UnexpectedError,
    PgTryAdvisoryLockError,
    ConflictingExistingEmployeeRoles,
)


class TestCustomExceptions:
    """Ověření, že všechny vlastní výjimky lze vyvolat a zachytit."""

    def test_multiple_rows_affected(self):
        with pytest.raises(MultipleRowsAffectedError):
            raise MultipleRowsAffectedError()

    def test_no_rows_affected(self):
        with pytest.raises(NoRowsAffectedError):
            raise NoRowsAffectedError()

    def test_forbidden(self):
        with pytest.raises(ForbiddenError):
            raise ForbiddenError()

    def test_cannot_make_new_event_if_not_copying(self):
        with pytest.raises(CanNotMakeNewEventIfNotCopyingEventError):
            raise CanNotMakeNewEventIfNotCopyingEventError()

    def test_no_valid_employees_to_copy(self):
        with pytest.raises(NoValidEmployeesToCopyError):
            raise NoValidEmployeesToCopyError()

    def test_no_paste_to_undo(self):
        with pytest.raises(NoPasteToUndoError):
            raise NoPasteToUndoError()

    def test_no_paste_to_redo(self):
        with pytest.raises(NoPasteToRedoError):
            raise NoPasteToRedoError()

    def test_no_change_to_undo(self):
        with pytest.raises(NoChangeToUndoError):
            raise NoChangeToUndoError()

    def test_no_change_to_redo(self):
        with pytest.raises(NoChangeToRedoError):
            raise NoChangeToRedoError()

    def test_undo_target_deleted(self):
        with pytest.raises(UndoTargetDeletedError):
            raise UndoTargetDeletedError("target was deleted")

    def test_cannot_delete_last_admin(self):
        with pytest.raises(CanNotDeleteLastAdminError):
            raise CanNotDeleteLastAdminError()

    def test_insufficient_balance(self):
        with pytest.raises(InsufficientBalanceError):
            raise InsufficientBalanceError()

    def test_idempotency_key_conflict(self):
        with pytest.raises(IdempotencyKeyDataConflict):
            raise IdempotencyKeyDataConflict()

    def test_unexpected_error(self):
        with pytest.raises(UnexpectedError):
            raise UnexpectedError()

    def test_pg_advisory_lock_error(self):
        with pytest.raises(PgTryAdvisoryLockError):
            raise PgTryAdvisoryLockError()

    def test_conflicting_employee_roles(self):
        with pytest.raises(ConflictingExistingEmployeeRoles):
            raise ConflictingExistingEmployeeRoles()

    def test_all_inherit_from_exception(self):
        exceptions = [
            MultipleRowsAffectedError,
            NoRowsAffectedError,
            ForbiddenError,
            InsufficientBalanceError,
            IdempotencyKeyDataConflict,
            UnexpectedError,
            CanNotDeleteLastAdminError,
            PgTryAdvisoryLockError,
            ConflictingExistingEmployeeRoles,
        ]
        for exc_class in exceptions:
            assert issubclass(exc_class, Exception)

    def test_undo_target_deleted_has_message(self):
        e = UndoTargetDeletedError("entity was deleted")
        assert "entity was deleted" in str(e)
