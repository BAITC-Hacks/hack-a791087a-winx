"""Human-readable Russian names for official indicator and measure IDs."""

INDICATOR_NAMES = {
    "T1": "разгрузка дорог",
    "T2": "доступность общественного транспорта",
    "E1": "озеленение",
    "E2": "качество воздуха",
    "S1": "школы и детсады",
    "S2": "поликлиники и первичная медпомощь",
    "B1": "безопасность улиц",
    "B2": "безопасность дорожного движения",
    "C1": "надёжность ЖКХ",
    "C2": "скорость решения обращений жителей",
}

MEASURE_NAMES = {
    "M1": "выделенные полосы для автобусов",
    "M2": "умные светофоры",
    "M3": "линия ЛРТ / расширение",
    "M4": "парк / сквер",
    "M5": "перевод частного сектора на чистое топливо",
    "M6": "городская программа озеленения и ветрозащитных полос",
    "M7": "школа + детсад",
    "M8": "центр семейного здоровья / поликлиника",
    "M9": "дворовые спорт-хабы",
    "M10": "освещение и камеры",
    "M11": "безопасные переходы и школьные зоны",
    "M12": "единая цифровая платформа обращений",
    "M13": "модернизация тепло- и водосетей",
    "M14": "аварийные бригады ЖКХ + раннее оповещение",
}


def indicator_name(indicator_id: str) -> str:
    """Return an official indicator name, preserving unknown IDs for diagnostics."""
    return INDICATOR_NAMES.get(indicator_id, indicator_id)


def measure_name(measure_id: str) -> str:
    """Return an official measure name, preserving unknown IDs for diagnostics."""
    return MEASURE_NAMES.get(measure_id, measure_id)
