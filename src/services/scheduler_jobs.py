# -*- coding: utf-8 -*-
"""Scheduled job implementations.

This module contains the actual job functions that are executed
by the scheduler service.
"""

import logging
from datetime import datetime, UTC

from src.core.database import SessionLocal
from src.services.channel_repository import ChannelRepository
from src.services.lifecycle_policy import LifecyclePolicy, ChannelState
from src.services.gemini import GeminiService
from src.services.trash_repository import TrashRepository

logger = logging.getLogger(__name__)


def scan_inactive_channels():
    """Scan for inactive channels and log warnings.

    This job runs periodically to identify channels that are approaching
    or have exceeded inactivity thresholds.
    """
    logger.info("Starting inactive channel scan...")

    db = SessionLocal()
    try:
        repo = ChannelRepository(db)
        policy = LifecyclePolicy()

        # Get all channels
        channels = repo.get_all()
        stats = {
            "total": len(channels),
            "active": 0,
            "idle": 0,
            "inactive": 0,
        }

        for channel in channels:
            state_info = policy.get_status(channel)

            if state_info.state == ChannelState.ACTIVE:
                stats["active"] += 1
            elif state_info.state == ChannelState.IDLE:
                stats["idle"] += 1
                logger.warning(
                    f"Channel {channel.gemini_store_id} is idle. "
                    f"Days since access: {state_info.days_since_access}"
                )
            elif state_info.state == ChannelState.INACTIVE:
                stats["inactive"] += 1
                logger.warning(
                    f"Channel {channel.gemini_store_id} is INACTIVE and eligible for cleanup. "
                    f"Days since access: {state_info.days_since_access}"
                )

        logger.info(
            f"Scan complete. Total: {stats['total']}, "
            f"Active: {stats['active']}, Idle: {stats['idle']}, Inactive: {stats['inactive']}"
        )

        return stats

    except Exception as e:
        logger.error(f"Error during inactive channel scan: {e}")
        raise
    finally:
        db.close()


def cleanup_inactive_channels(dry_run: bool = True):
    """Clean up inactive channels.

    This job removes channels that have been inactive beyond the threshold.

    Args:
        dry_run: If True, only log what would be deleted without actually deleting
    """
    logger.info(f"Starting inactive channel cleanup (dry_run={dry_run})...")

    db = SessionLocal()
    try:
        repo = ChannelRepository(db)
        policy = LifecyclePolicy()
        gemini = GeminiService()

        # Get all channels and filter inactive ones
        all_channels = repo.get_all()
        inactive_with_status = policy.get_channels_by_state(all_channels, ChannelState.INACTIVE)
        inactive_channels = [ch for ch, _ in inactive_with_status]

        if not inactive_channels:
            logger.info("No inactive channels to clean up")
            return {"deleted": 0, "failed": 0}

        deleted = 0
        failed = 0

        for channel in inactive_channels:
            channel_id = channel.gemini_store_id

            if dry_run:
                logger.info(f"[DRY RUN] Would delete channel: {channel_id}")
                deleted += 1
            else:
                try:
                    # Delete from Gemini
                    success = gemini.delete_store(channel_id)
                    if success:
                        # Delete from local DB
                        repo.delete(channel_id)
                        logger.info(f"Deleted inactive channel: {channel_id}")
                        deleted += 1
                    else:
                        logger.error(f"Failed to delete channel from Gemini: {channel_id}")
                        failed += 1
                except Exception as e:
                    logger.error(f"Error deleting channel {channel_id}: {e}")
                    failed += 1

        logger.info(f"Cleanup complete. Deleted: {deleted}, Failed: {failed}")
        return {"deleted": deleted, "failed": failed}

    except Exception as e:
        logger.error(f"Error during channel cleanup: {e}")
        raise
    finally:
        db.close()


def update_channel_statistics():
    """Update channel statistics from Gemini API.

    This job syncs file counts and sizes from Gemini to local DB.
    """
    logger.info("Starting channel statistics update...")

    db = SessionLocal()
    try:
        repo = ChannelRepository(db)
        gemini = GeminiService()

        channels = repo.get_all()
        updated = 0

        for channel in channels:
            try:
                files = gemini.list_store_files(channel.gemini_store_id)
                file_count = len(files)
                total_size = sum(f.get("size_bytes", 0) for f in files)

                repo.update_stats(
                    gemini_store_id=channel.gemini_store_id,
                    file_count=file_count,
                    total_size_bytes=total_size,
                )
                updated += 1

            except Exception as e:
                logger.warning(
                    f"Failed to update stats for {channel.gemini_store_id}: {e}"
                )

        logger.info(f"Statistics update complete. Updated: {updated}/{len(channels)}")
        return {"updated": updated, "total": len(channels)}

    except Exception as e:
        logger.error(f"Error during statistics update: {e}")
        raise
    finally:
        db.close()


def cleanup_expired_trash(retention_days: int = 30):
    """Clean up expired items in trash.

    Permanently deletes channels and notes that have been in the trash
    for longer than the retention period.

    Args:
        retention_days: Number of days to retain items in trash (default: 30)
    """
    logger.info(f"Starting expired trash cleanup (retention_days={retention_days})...")

    db = SessionLocal()
    try:
        trash_repo = TrashRepository(db)
        gemini = GeminiService()

        # Get trashed channels that will be deleted for Gemini cleanup
        from src.models.db_models import ChannelMetadata
        from datetime import timedelta

        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        expired_channels = db.query(ChannelMetadata).filter(
            ChannelMetadata.deleted_at.isnot(None),
            ChannelMetadata.deleted_at < cutoff,
        ).all()

        # Delete from Gemini first
        gemini_deleted = 0
        gemini_failed = 0
        for channel in expired_channels:
            try:
                gemini.delete_store(channel.gemini_store_id, force=True)
                gemini_deleted += 1
            except Exception as e:
                logger.warning(
                    f"Failed to delete from Gemini: {channel.gemini_store_id}: {e}"
                )
                gemini_failed += 1

        # Then delete from DB
        deleted_channels, deleted_notes = trash_repo.cleanup_expired_trash(retention_days)

        logger.info(
            f"Expired trash cleanup complete. "
            f"Channels: {deleted_channels} (Gemini: {gemini_deleted} ok, {gemini_failed} failed), "
            f"Notes: {deleted_notes}"
        )

        return {
            "deleted_channels": deleted_channels,
            "deleted_notes": deleted_notes,
            "gemini_deleted": gemini_deleted,
            "gemini_failed": gemini_failed,
        }

    except Exception as e:
        logger.error(f"Error during expired trash cleanup: {e}")
        raise
    finally:
        db.close()
