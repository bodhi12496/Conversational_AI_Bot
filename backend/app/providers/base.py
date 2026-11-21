from typing import Protocol

from app.domain.models import ChangeSet, QueryPlan, SemanticModel


class Interpreter(Protocol):
    def propose(self, message: str, model: SemanticModel) -> ChangeSet: ...

    def plan(self, message: str, model: SemanticModel) -> QueryPlan: ...
