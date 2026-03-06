# bookings_service/app/constants/service_periods.py
SERVICE_PERIODS = {
    "lunch": {
        "start": "11:00",
        "end": "15:00",
        "last_order": "14:45",
    },
    "dinner": {
        "start": "15:00",
        "end": "19:00",
        "last_order": "18:45",
    },
}

# 0=Monday, 6=Sunday
LUNCH_DAYS = [0, 1, 2, 3, 4, 5, 6]   # Mon-Sun
DINNER_DAYS = [3, 4, 5, 6]            # Thu-Sun