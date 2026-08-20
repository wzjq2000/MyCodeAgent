import operator
from typing import Annotated, TypedDict

from langgraph.graph import MessagesState

from my_code_agent.schemas.schema import NodeDispatchResult, FileReadResult


class CodeAgentState(MessagesState):
    user_query: str = ""
    context: str = ""
    code: str = ""
    output: str = ""
    err_msg: str = ""
    max_retry: int = 3
    retry: Annotated[int, operator.add] = 0
    node_dispatch_result: NodeDispatchResult
    file_read_result: str





