"""Organizer dataset, transcribed from docs/DATASET.md; fresh objects per call."""

from citysim.models import Dataset, District, Measure


def load_dataset() -> Dataset:
    keys = ("T1", "T2", "E1", "E2", "S1", "S2", "B1", "B2", "C1", "C2")
    rows = (
        ("esil", "Есиль", .27, (45, 62, 68, 72, 48, 55, 78, 60, 75, 70)),
        ("almaty", "Алматы", .24, (40, 75, 50, 55, 60, 65, 62, 52, 50, 60)),
        ("saryarka", "Сарыарка", .20, (50, 70, 42, 40, 62, 68, 58, 55, 45, 55)),
        ("baikonur", "Байконур", .13, (52, 68, 55, 50, 58, 60, 52, 58, 55, 58)),
        ("nura", "Нура", .16, (55, 40, 45, 65, 38, 35, 55, 50, 60, 50)),
    )
    districts = tuple(
        District(id_, name, pop, dict(zip(keys, values)))
        for id_, name, pop, values in rows
    )
    measures = (
        Measure("M1", "Выделенные полосы для автобусов", "transport", "district", 18, 2, {"T1": 6, "T2": 9}),
        Measure("M2", "Умные светофоры", "transport", "city", 22, 2, {"T1": 4, "B2": 3}),
        Measure("M3", "Линия ЛРТ / расширение", "transport", "district", 30, 4, {"T1": 16, "T2": 20, "E2": 4}),
        Measure("M4", "Парк / сквер", "ecology", "district", 15, 2, {"E1": 12, "E2": 3, "B1": 2}),
        Measure("M5", "Перевод частного сектора на чистое топливо", "ecology", "district", 25, 3, {"E2": 14, "C1": 4}),
        Measure("M6", "Озеленение и ветрозащитные полосы", "ecology", "city", 20, 4, {"E1": 5, "E2": 3}),
        Measure("M7", "Школа + детсад", "social", "district", 24, 3, {"S1": 16}),
        Measure("M8", "Центр семейного здоровья / поликлиника", "social", "district", 20, 3, {"S2": 14}),
        Measure("M9", "Дворовые спорт-хабы", "social", "district", 10, 1, {"S1": 3, "S2": 3, "B1": 3}),
        Measure("M10", "Освещение и камеры", "safety", "district", 12, 1, {"B1": 12, "B2": 2}),
        Measure("M11", "Безопасные переходы и школьные зоны", "safety", "district", 10, 1, {"B2": 12, "T1": -2}),
        Measure("M12", "Единая цифровая платформа обращений", "services", "city", 14, 1, {"C2": 5}),
        Measure("M13", "Модернизация тепло- и водосетей", "services", "district", 28, 4, {"C1": 18, "E2": 2}),
        Measure("M14", "Аварийные бригады ЖКХ + раннее оповещение", "services", "city", 16, 1, {"C1": 5, "C2": 2}),
    )
    return Dataset(districts, measures, dict(zip(keys, (.10, .10, .09, .11, .11, .11, .09, .09, .10, .10))))
