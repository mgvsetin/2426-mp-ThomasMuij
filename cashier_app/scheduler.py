"""Periodic background job scheduler.

Uses APScheduler BackgroundScheduler with a file lock to ensure only
one process (across multiple Gunicorn workers) runs the scheduler.
"""

import os
import logging
import atexit

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR
from filelock import FileLock, Timeout
from flask import Flask

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_lock: FileLock | None = None


# ---------------------------------------------------------------------------
# Job wrappers – each pushes Flask app context and catches exceptions
# ---------------------------------------------------------------------------

def _job_delete_expired_sessions(app: Flask):
    with app.app_context():
        from cashier_app.pg_session import delete_expired_sessions
        try:
            count = delete_expired_sessions()
            logger.info("Deleted %d expired session(s)", count)
        except Exception:
            logger.exception("Error in delete_expired_sessions job")


def _job_delete_unused_images(app: Flask):
    with app.app_context():
        from cashier_app.utils.images import delete_unused_images
        try:
            delete_unused_images()
            logger.info("Completed delete_unused_images job")
        except Exception:
            logger.exception("Error in delete_unused_images job")


def _job_delete_disk_orphans(app: Flask):
    with app.app_context():
        from cashier_app.utils.images import delete_disk_orphans
        try:
            delete_disk_orphans()
            logger.info("Completed delete_disk_orphans job")
        except Exception:
            logger.exception("Error in delete_disk_orphans job")


# ---------------------------------------------------------------------------
# APScheduler error listener (defence-in-depth)
# ---------------------------------------------------------------------------

def _on_job_error(event):
    if event.exception:
        logger.error(
            "Scheduler job %s raised an exception",
            event.job_id,
            exc_info=(type(event.exception), event.exception, event.traceback),
        )


# ---------------------------------------------------------------------------
# Public entry point – called from create_app()
# ---------------------------------------------------------------------------

def init_scheduler(app: Flask):
    """Start the background scheduler if enabled and no other process holds the lock."""
    global _scheduler, _lock

    if not app.config.get("SCHEDULER_ENABLED", True):
        logger.info("Scheduler disabled by config")
        return

    lock_path = os.path.join(app.instance_path, ".scheduler.lock")
    _lock = FileLock(lock_path, timeout=0)

    try:
        _lock.acquire()
    except Timeout:
        logger.info(
            "Another process holds the scheduler lock (%s); "
            "skipping scheduler start in this worker",
            lock_path,
        )
        _lock = None
        return

    logger.info("Acquired scheduler lock (%s); starting scheduler", lock_path)

    session_min = app.config.get("SCHEDULER_SESSION_CLEANUP_MINUTES", 60)
    unused_img_min = app.config.get("SCHEDULER_UNUSED_IMAGES_CLEANUP_MINUTES", 180)
    disk_orphan_min = app.config.get("SCHEDULER_DISK_ORPHANS_CLEANUP_MINUTES", 720)

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)

    _scheduler.add_job(
        _job_delete_expired_sessions,
        trigger="interval",
        minutes=session_min,
        args=[app],
        id="delete_expired_sessions",
        name="Delete expired sessions",
        replace_existing=True,
    )

    _scheduler.add_job(
        _job_delete_unused_images,
        trigger="interval",
        minutes=unused_img_min,
        args=[app],
        id="delete_unused_images",
        name="Delete unused images",
        replace_existing=True,
    )

    _scheduler.add_job(
        _job_delete_disk_orphans,
        trigger="interval",
        minutes=disk_orphan_min,
        args=[app],
        id="delete_disk_orphans",
        name="Delete disk orphan images",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        "Scheduler started — sessions=%dm, unused_images=%dm, disk_orphans=%dm",
        session_min,
        unused_img_min,
        disk_orphan_min,
    )

    def _shutdown():
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            logger.info("Scheduler shut down")
        if _lock and _lock.is_locked:
            _lock.release()
            logger.info("Scheduler lock released")

    atexit.register(_shutdown)
