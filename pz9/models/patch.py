from pydantic import BaseModel, ConfigDict, model_validator


class PatchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="before")
    @classmethod
    def reject_nulls(cls, data):
        if isinstance(data, dict):
            for name, value in data.items():
                if value is None and name not in {"middle_name", "sip_extension"}:
                    raise ValueError(f"Поле {name} не может быть null")
        return data
