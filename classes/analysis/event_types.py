# classes/analysis/event_types.py
class EventTypeConfig:
    """
    Centralise les types d’événements autorisés pour l’estimation d’impact de maintenance.
    """
    def __init__(self, allowed_types):
        self.allowed_types = set(allowed_types)

    def is_allowed(self, event_name: str) -> bool:
        return event_name in self.allowed_types
