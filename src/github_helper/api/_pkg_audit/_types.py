
from typing import Literal, TypedDict


class Ignore(TypedDict):
    type: str
    action: Literal["ignore"]
class Error(TypedDict):
    error: str
    value: str
class Audit(TypedDict):
    name: str
    action: Literal["resolved"]

ReturnMessages = Ignore | Error | Audit
