from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

# "unclear" is the parser's "mentioned but ambiguous" value; the engine treats it as unknown.
UNCLEAR = "unclear"

# FiniteFloat: json.loads accepts NaN / Infinity, and a NaN threshold never
# compares true, so a cause using it could never be ruled out or confirmed.
ConditionScalar = bool | FiniteFloat | str
ConditionValue = ConditionScalar | list[ConditionScalar]

_OPS_BY_FIELD_TYPE: dict[str, set[str]] = {
    "enum": {"eq", "ne", "in"},
    "number": {"eq", "ne", "in", "gt", "gte", "lt", "lte"},
    "boolean": {"eq", "ne"},
}


class GraphModel(BaseModel):
    """Base for every graph object.

    Unknown keys are rejected so a typo in a graph file (e.g. ``ruled_out_whn``)
    fails loudly instead of silently dropping a rule. ``_todo`` is the one
    allowed annotation key, since JSON has no comments.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    todo: str | None = Field(default=None, alias="_todo")


class FieldSpec(GraphModel):
    name: str
    type: Literal["enum", "number", "boolean"]
    values: list[str] | None = None
    unit: str | None = None
    description: str
    ask: str


class FieldCondition(GraphModel):
    field: str
    op: Literal["eq", "ne", "in", "gt", "gte", "lt", "lte"]
    value: ConditionValue


class AllCondition(GraphModel):
    all: list[Condition] = Field(min_length=1)


class AnyCondition(GraphModel):
    any: list[Condition] = Field(min_length=1)


Condition = FieldCondition | AllCondition | AnyCondition

# Rebuild recursive models once Condition is defined.
AllCondition.model_rebuild()
AnyCondition.model_rebuild()


class Source(GraphModel):
    doc_id: str
    section: str
    page: int | None = None


class Check(GraphModel):
    id: str
    instruction: str
    reason: str
    collects: list[str] = Field(min_length=1)
    source: Source


class Cause(GraphModel):
    id: str
    name: str
    priority: int
    checks: list[str] = Field(min_length=1)
    ruled_out_when: Condition | None = None
    confirmed_when: Condition | None = None
    promote_when: Condition | None = None
    corrective_action: str
    action_source: Source

    def conditions(self) -> list[tuple[str, Condition]]:
        named = (
            ("ruled_out_when", self.ruled_out_when),
            ("confirmed_when", self.confirmed_when),
            ("promote_when", self.promote_when),
        )
        return [(name, condition) for name, condition in named if condition is not None]


class FaultGraph(GraphModel):
    fault_id: str
    equipment: str
    display_name: str
    fault_codes: list[str]
    description: str
    fields: list[FieldSpec] = Field(min_length=1)
    checks: list[Check] = Field(min_length=1)
    causes: list[Cause] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_graph_integrity(self) -> FaultGraph:
        _reject_duplicates([field.name for field in self.fields], "field")
        _reject_duplicates([check.id for check in self.checks], "check")
        _reject_duplicates([cause.id for cause in self.causes], "cause")
        # Priority is the investigation order; ties would make it ambiguous.
        _reject_duplicates([str(cause.priority) for cause in self.causes], "cause priority")

        field_by_name = {field.name: field for field in self.fields}
        check_by_id = {check.id: check for check in self.checks}

        for field in self.fields:
            _validate_field_spec(field)

        for check in self.checks:
            for field_name in check.collects:
                if field_name not in field_by_name:
                    raise ValueError(
                        f"check '{check.id}' collects unknown field '{field_name}'"
                    )

        for cause in self.causes:
            for check_id in cause.checks:
                if check_id not in check_by_id:
                    raise ValueError(
                        f"cause '{cause.id}' references unknown check '{check_id}'"
                    )
            # The engine can only obtain a field by recommending a check that collects it,
            # so every field a cause's conditions depend on must come from that cause's checks.
            collectable = {
                field_name
                for check_id in cause.checks
                for field_name in check_by_id[check_id].collects
            }
            for condition_name, condition in cause.conditions():
                _validate_condition(condition, field_by_name)
                for field_name in _condition_fields(condition):
                    if field_name not in collectable:
                        raise ValueError(
                            f"cause '{cause.id}' {condition_name} uses field '{field_name}', "
                            "which none of the cause's checks collect"
                        )

        return self


def _reject_duplicates(ids: list[str], kind: str) -> None:
    seen: set[str] = set()
    for item_id in ids:
        if item_id in seen:
            raise ValueError(f"duplicate {kind} id '{item_id}'")
        seen.add(item_id)


def _validate_field_spec(field: FieldSpec) -> None:
    if field.type == "enum":
        if not field.values:
            raise ValueError(f"enum field '{field.name}' must declare a non-empty values list")
        if UNCLEAR not in field.values:
            raise ValueError(f"enum field '{field.name}' values must include '{UNCLEAR}'")
        if len(set(field.values)) != len(field.values):
            raise ValueError(f"enum field '{field.name}' has duplicate values")
    elif field.values is not None:
        raise ValueError(f"{field.type} field '{field.name}' must not declare values")


def _condition_fields(condition: Condition) -> set[str]:
    if isinstance(condition, AllCondition):
        return set().union(*(_condition_fields(child) for child in condition.all))
    if isinstance(condition, AnyCondition):
        return set().union(*(_condition_fields(child) for child in condition.any))
    return {condition.field}


def _validate_condition(condition: Condition, field_by_name: dict[str, FieldSpec]) -> None:
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

    if condition.op not in _OPS_BY_FIELD_TYPE[field.type]:
        raise ValueError(
            f"op '{condition.op}' is not valid for {field.type} field '{field.name}'"
        )

    if condition.op == "in":
        if not isinstance(condition.value, list) or not condition.value:
            raise ValueError(
                f"condition on '{field.name}' with op 'in' requires a non-empty list value"
            )
        values = list(condition.value)
    else:
        if isinstance(condition.value, list):
            raise ValueError(
                f"condition on '{field.name}' with op '{condition.op}' requires a single value"
            )
        values = [condition.value]

    for value in values:
        if value == UNCLEAR:
            raise ValueError(
                f"condition on '{field.name}' must not test for '{UNCLEAR}'; "
                "the engine treats it as unknown"
            )
        if field.type == "enum":
            if not isinstance(value, str) or value not in (field.values or []):
                raise ValueError(
                    f"condition value {value!r} is not in enum field "
                    f"'{field.name}' values {field.values}"
                )
        elif field.type == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(
                    f"condition value {value!r} on number field '{field.name}' must be a number"
                )
        elif not isinstance(value, bool):
            raise ValueError(
                f"condition value {value!r} on boolean field '{field.name}' must be true or false"
            )
