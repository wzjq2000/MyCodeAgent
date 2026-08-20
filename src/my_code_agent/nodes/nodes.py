import os
from typing import Any

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

from my_code_agent.agent.agent_state import CodeAgentState
from my_code_agent.constants.node_constants import NodeNameEnum
from my_code_agent.schemas.schema import NodeDispatchResult
from my_code_agent.tools.file_read_tool import read_file as read_file_tool

load_dotenv(override=True)
llm = init_chat_model(
    model_provider="deepseek",
    model="deepseek-v4-flash",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_API_BASE"),
    extra_body={"thinking": {"type": "disabled"}},
)

def collect_context(state: CodeAgentState):
    pass


def dispatch_task(state: CodeAgentState) -> dict[str, Any]:
    prompt = f"""
    You are an intelligent task planner for a code assistant agent. Your job is to understand the user's request and decide which action to take next in order to solve their problem.

    You have access to the following information:
    - **User query**: {state["user_query"]}
    - **Current context**: {state["context"]}
    - **Last output**: {state["output"]}
    - **Last error**: {state["err_msg"]}
    - **Current retry count**: {state["retry"]} / max retries: {state["max_retry"]}

    Based on the above, choose the MOST appropriate next step from the options below:

    ### Available Actions
    - **{NodeNameEnum.DIRECT_REPLY}**: Answer the user directly. Use this for:
        - Conversational questions, explanations, or general inquiries
        - When the user's request does not require reading/writing files or running commands
        - When all necessary context is already available and you can provide a complete answer

    - **{NodeNameEnum.READ_FILE}**: Read one or more files from disk. Use this for:
        - The user asks to read, view, or inspect a file's content
        - You need to understand existing code before making changes
        - Gathering context or investigating a bug in the codebase

    - **{NodeNameEnum.WRITE_FILE}**: Write or modify files on disk. Use this for:
        - The user asks you to create a new file
        - The user asks you to modify, edit, or fix code in an existing file
        - You have already read and understood the target file(s)

    - **{NodeNameEnum.EXECUTE_SHELL}**: Run a shell command. Use this for:
        - The user asks to run tests, build, install dependencies, or execute scripts
        - You need to run git commands (status, diff, log, etc.)
        - Any terminal operation that reads or mutates system state

    - **{NodeNameEnum.OBSERVE_RESULT}**: Observe and analyze the result of the last action. Use this for:
        - After a READ_FILE, WRITE_FILE, or EXECUTE_SHELL has just completed
        - You need to check whether the last operation succeeded or produced the expected output
        - Deciding whether to retry, continue, or report back to the user

    - **{NodeNameEnum.VERIFY_RESULT}**: Verify the correctness of the last action's output. Use this for:
        - After writing code — does the change look correct and consistent with the codebase?
        - After running a shell command — did it succeed with the expected output?
        - When the retry count is > 0 and you suspect a previous attempt failed

    ### Decision Guidelines
    1. If the user is just chatting or asking a question → **{NodeNameEnum.DIRECT_REPLY}**
    2. If you need file content to proceed → **{NodeNameEnum.READ_FILE}**
    3. If you know what to write and have enough context → **{NodeNameEnum.WRITE_FILE}**
    4. If you need to run a command → **{NodeNameEnum.EXECUTE_SHELL}**
    5. After any file/shell operation completes → **{NodeNameEnum.OBSERVE_RESULT}**
    6. If you need to confirm an operation's correctness → **{NodeNameEnum.VERIFY_RESULT}**
    7. If an error occurred and retries remain → consider going back to the step that failed
    8. If max retries exceeded → **{NodeNameEnum.DIRECT_REPLY}** with an explanation of what went wrong

    Output the next action to take and the info needed for that action.
    """
    structured_llm = llm.with_structured_output(NodeDispatchResult)
    decision: NodeDispatchResult = structured_llm.invoke(prompt)
    return {"node_dispatch_result": decision}


def read_file(state: CodeAgentState) -> dict[str, Any]:
    """READ_FILE node: read a file via the @tool-decorated read_file tool."""
    args = state["node_dispatch_result"].read_node
    result = read_file_tool.invoke(
        {
            "file_path": args.file_path,
            "offset": args.offset,
            "limit": args.limit,
        }
    )
    return {"file_read_result": result}
