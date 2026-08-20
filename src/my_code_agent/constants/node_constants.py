from enum import StrEnum, auto


class NodeNameEnum(StrEnum):
    COLLECT_CONTEXT = auto()
    DISPATCH_TASK = auto()
    READ_FILE = auto()
    WRITE_FILE = auto()
    EXECUTE_SHELL = auto()
    DIRECT_REPLY = auto()
    VERIFY_RESULT = auto()
    OBSERVE_RESULT = auto()