from dataclasses import dataclass

@dataclass
class MaintenanceType:
    name: str
    cost: float
    downtime_hours: float
    expected_delta_pf: float

class MaintenanceCatalog:
    def __init__(self):
        self._types = {}

    def register(self, m: MaintenanceType):
        self._types[m.name] = m

    def get(self, name: str) -> MaintenanceType:
        return self._types.get(name)

    def list_all(self):
        return list(self._types.values())

    @classmethod
    def from_settings(cls, settings: dict):
        cat = cls()
        for item in settings["economics"]["catalog"]:
            cat.register(MaintenanceType(
                name=item["name"],
                cost=item["cost"],
                downtime_hours=item["downtime_hours"],
                expected_delta_pf=item["expected_delta_pf"]
            ))
        return cat

