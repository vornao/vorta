"""Human-friendly text for dates, counts and the backup schedule."""

from datetime import datetime, timedelta
from typing import Optional

from PyQt6.QtCore import QCoreApplication, QDateTime, QLocale

from vorta.i18n import get_locale
from vorta.scheduler import ScheduleStatusType

CONTEXT = 'OverviewPage'


def _qdatetime(time: datetime) -> QDateTime:
    return QDateTime.fromMSecsSinceEpoch(int(time.timestamp() * 1000))


def long_datetime(time: datetime) -> str:
    return get_locale().toString(_qdatetime(time), QLocale.FormatType.LongFormat)


def _clock(time: datetime) -> str:
    return get_locale().toString(_qdatetime(time).time(), QLocale.FormatType.ShortFormat)


def plural(singular: str, plural_form: str, n: int, context: str = CONTEXT) -> str:
    """
    Translate a count, e.g. ``plural('%n archive', '%n archives', 3)``.

    Translators get Qt's ``%n`` plural source (the plural form); without a translation
    the English singular or plural is used.
    """
    translated = QCoreApplication.translate(context, plural_form, '', n)
    if translated != plural_form.replace('%n', str(n)):
        return translated
    return (singular if n == 1 else plural_form).replace('%n', str(n))


def relative_time(time: datetime, now: Optional[datetime] = None) -> str:
    """'just now', '5 minutes ago', '3 hours ago', 'yesterday at 14:02', or a short date."""
    now = now or datetime.now()
    seconds = (now - time).total_seconds()
    if seconds < 60:
        return QCoreApplication.translate(CONTEXT, 'just now')
    if seconds < 3600:
        return plural('%n minute ago', '%n minutes ago', int(seconds // 60))
    if seconds < 6 * 3600 or time.date() == now.date():
        return plural('%n hour ago', '%n hours ago', int(seconds // 3600))
    if (now.date() - time.date()).days == 1:
        return QCoreApplication.translate(CONTEXT, 'yesterday at %1').replace('%1', _clock(time))
    return get_locale().toString(_qdatetime(time), QLocale.FormatType.ShortFormat)


def friendly_datetime(time: datetime, now: Optional[datetime] = None) -> str:
    """'today at 14:36', 'tomorrow at 03:42' or a short date with time, for upcoming events."""
    now = now or datetime.now()
    if time.date() == now.date():
        return QCoreApplication.translate(CONTEXT, 'today at %1').replace('%1', _clock(time))
    if time.date() == (now + timedelta(days=1)).date():
        return QCoreApplication.translate(CONTEXT, 'tomorrow at %1').replace('%1', _clock(time))
    return get_locale().toString(_qdatetime(time), QLocale.FormatType.ShortFormat)


def _schedule_tr(text: str) -> str:
    # Same context as the strings had in SchedulePage, so existing translations apply.
    return QCoreApplication.translate('SchedulePage', text)


def next_backup_text(scheduler, profile_id: int) -> str:
    """Human-readable description of the next scheduled backup of a profile."""
    status = scheduler.next_job_for_profile(profile_id)
    if status.type == ScheduleStatusType.SCHEDULED:
        return friendly_datetime(status.time)
    if status.type == ScheduleStatusType.PAUSED:
        return _schedule_tr('Paused until %s') % friendly_datetime(status.time)
    if status.type == ScheduleStatusType.NO_PREVIOUS_BACKUP:
        return _schedule_tr('Run a manual backup first')
    return _schedule_tr('None scheduled')


def next_backup_tooltip(scheduler, profile_id: int) -> str:
    status = scheduler.next_job_for_profile(profile_id)
    return long_datetime(status.time) if status.time else ''
