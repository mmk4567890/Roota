from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, model_validator


class FieldSpec(BaseModel):
    name: str
    type: Literal["enum", "number", "boolean"]
    values: list[str] | None = None
    unit: str | None = None
    description: str
    ask: str


class FieldCondition(BaseModel):
    model_config = {"extra": "ignore"}

    field: str
    op: Literal["eq", "ne", "in", "gt", "gte", "lt", "lte"]
    value: str | float | bool | list[str | float | bool]


class AllCondition(BaseModel):
    model_config = {"extra": "ignore"}

    all: list[Condition]


class AnyCondition(BaseModel):
    model_config = {"extra": "ignore"}

    any: list[Condition]


Condition = FieldCondition | AllCondition | AnyCondition

# Rebuild recursive models once Condition is defined.
AllCondition.model_rebuild()
AnyCondition.model_rebuild()


class Source(BaseModel):
    model_config = {"extra": "ignore"}

    doc_id: str
    section: str
    page: int | None = None


class Check(BaseModel):
    id: str
    instruction: str
    reason: str
    collects: list[str]
    source: Source


class Cause(BaseModel):
    id: str
    name: str
    priority: int
    checks: list[str]
    ruled_out_when: Condition | None = None
    confirmed_when: Condition | None = None
    promote_when: Condition | None = None
    corrective_action: str
    action_source: Source


class FaultGraph(BaseModel):
    fault_id: str
    equipment: str
    display_name: str
    fault_codes: list[str]
    description: str
    fields: list[FieldSpec]
    checks: list[Check]
    causes: list[Cause]

    @model_validator(mode="after")
    def validate_graph_integrity(self) -> FaultGraph:
        field_names = [field.name for field in self.fields]
        check_ids = [check.id for check in self.checks]
        cause_ids = [cause.id for cause in self.causes]

        _reject_duplicates(field_names, "field")
        _reject_duplicates(check_ids, "check")
        _reject_duplicates(cause_ids, "cause")

        field_by_name = {field.name: field for field in self.fields}

        for field in self.fields:
            if field.type == "enum":
                if not field.values:
                    raise ValueError(
                        f"enum field '{field.name}' must declare a non-empty values list"
                    )
                if "unclear" not in field.values:
                    raise ValueError(
                        f"enum field '{field.name}' values must include 'unclear'"
                    )

        for check in self.checks:
            for field_name in check.collects:
                if field_name not in field_by_name:
                    raise ValueError(
                        f"check '{check.id}' collects unknown field '{field_name}'"
                    )

        for cause in self.causes:
            for check_id in cause.checks:
                if check_id not in check_ids:
                    raise ValueError(
                        f"cause '{cause.id}' references unknown check '{check_id}'"
                    )
            for condition in (
                cause.ruled_out_when,
                cause.confirmed_when,
                cause.promote_when,
            ):
                if condition is not None:
                    _validate_condition(condition, field_by_name)

        return self


def _reject_duplicates(ids: list[str], kind: str) -> None:
    seen: set[str] = set()
    for item_id in ids:
        if item_id in seen:
            raise ValueError(f"duplicate {kind} id '{item_id}'")
        seen.add(item_id)


def _validate_condition(
    condition: FieldCondition | AllCondition | AnyCondition,
    field_by_name: dict[str, FieldSpec],
) -> None:
    if isinstance(condition, AllCondition):
        for child in condition.all:
            _validate_condition(child, field_by_name)
        return
    if isinstance(condition, AnyCondition):
        for child in condition.any:
            _validate_condition(child, field_by_name)
        return

    field = field_by_name.get(condition.field)
    if field is None:
        raise ValueError(f"condition references unknown field '{condition.field}'")

    if field.type == "enum":
        assert field.values is not None
        values_to_check: list[Any]
        if condition.op == "in":
            if not isinstance(condition.value, list):
                raise ValueError(
                    f"condition on enum field '{field.name}' with op 'in' requires a list value"
                )
            values_to_check = list(condition.value)
        else:
            values_to_check = [condition.value]

        for value in values_to_check:
            if not isinstance(value, str) or value not in field.values:
                raise ValueError(
                    f"condition value {value!r} is not in enum field "
                    f"'{field.name}' values {field.values}"
                )
