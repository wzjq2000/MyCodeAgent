from langgraph.checkpoint.memory import InMemorySaver
from langgraph.constants import START, END
from langgraph.graph import StateGraph
from langgraph.types import interrupt, Command
from pydantic import BaseModel

from my_code_agent.agent.state import NodeName


class EmailState(BaseModel):
    email_content: str
    response_text: str | None = None



def human_review(state: EmailState):
    interrupt(
        {
            "approved": False,
            "edited_response": state.response_text or ""
        }
    )
    return {"response_text": "placeholder"}


app = (
    StateGraph(EmailState)
    .add_node(NodeName.HUMAN_REVIEW, human_review)
    .add_edge(START, NodeName.HUMAN_REVIEW)
    .add_edge(NodeName.HUMAN_REVIEW, END)
    .compile(checkpointer = InMemorySaver())
)


initial_state = EmailState(
    email_content="I was charged twice for my subscription! This is urgent!",
    response_text="Draft response",
)


config = {"configurable": {"thread_id":"customer_123"}}
stream = app.stream_events(initial_state, config, version="v3")
_ = stream.output

print(f"human review interrupt:{stream.interrupts}")
human_response = Command(
    resume={
        "approved": True,
        "edited_response": "We sincerely apologize for the double charge. I've initiated an immediate refund...",
    }
)

resumed = app.stream_events(human_response, config, version="v3")
final_state = resumed.output
print("Email Sent!")


