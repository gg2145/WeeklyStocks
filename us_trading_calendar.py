import datetime as dt
import pytz
import holidays

NY = pytz.timezone("America/New_York")

def is_us_trading_day(date_: dt.date) -> bool:
    # Monday-Friday and not a US holiday
    if date_.weekday() >= 5:
        return False
    us_h = holidays.UnitedStates(years=range(date_.year-1, date_.year+2))
    return date_ not in us_h

def next_us_trading_day(date_: dt.date) -> dt.date:
    d = date_
    while not is_us_trading_day(d):
        d += dt.timedelta(days=1)
    return d

def next_monday_trading_date(ref_dt: dt.datetime) -> dt.date:
    ref_dt = ref_dt.astimezone(NY)
    # find next Monday (today if Monday & still before close)
    days_ahead = (0 - ref_dt.weekday()) % 7
    monday = (ref_dt + dt.timedelta(days=days_ahead)).date()
    if not is_us_trading_day(monday):
        # roll forward until a trading day
        monday = next_us_trading_day(monday + dt.timedelta(days=1))
        # ensure it's a Monday-equivalent start (first trading day of week)
    return monday

def friday_of_week(monday_date: dt.date) -> dt.date:
    # Friday; if holiday, step back to previous trading day in that week
    f = monday_date + dt.timedelta(days=4)
    while not is_us_trading_day(f) or f.weekday() < 0 or f.weekday() > 4:
        f -= dt.timedelta(days=1)
    return f

def ny_datetime(date_: dt.date, hour: int, minute: int) -> dt.datetime:
    return NY.localize(dt.datetime(date_.year, date_.month, date_.day, hour, minute))
