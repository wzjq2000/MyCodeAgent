from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.types import Command, RetryPolicy

from my_code_agent.agent.state import EmailAgentState, NodeName
from my_code_agent.nodes.agent_node import *

if __name__ == "__main__":
    workflow = StateGraph(EmailAgentState)
    workflow.add_node(NodeName.READ_EMAIL, read_email)
    workflow.add_node(NodeName.CLASSIFY_INTENT, classify_intent)

    # add retry policy for nodes that may have transient failures
    workflow.add_node(
        NodeName.SEARCH_DOCUMENT, search_document, retry_policy=RetryPolicy(max_attempts=3)
    )

    workflow.add_node(NodeName.BUG_TRACKING, bug_tracking)
    workflow.add_node(NodeName.DRAFT_RESPONSE, draft_response)
    workflow.add_node(NodeName.HUMAN_REVIEW, human_review)
    workflow.add_node(NodeName.SEND_REPLY, send_reply)

    workflow.add_edge(START, NodeName.READ_EMAIL)
    workflow.add_edge(NodeName.READ_EMAIL, NodeName.CLASSIFY_INTENT)
    workflow.add_edge(NodeName.SEND_REPLY, END)

    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    initial_state = EmailAgentState(
        sender_email="customer@example.com",
        email_content="I was charged twice for my subscription! This is urgent!",
        email_id="email-001",
        classification=None,
        search_results=None,
        customer_history=None,
        draft_response=None,
        message=None,
    )

    config = {"configurable": {"thread_id": "customer_123"}}

    # --- First invoke: run the graph until it hits an interrupt ---
    res1 = app.invoke(initial_state, config=config)

    # Check if the graph was interrupted (human_review node called interrupt())
    interrupt_list = res1.get("__interrupt__", [])

    if interrupt_list:
        # Extract the interrupt value(s)
        for interrupt_item in interrupt_list:
            review_data = interrupt_item.value
            print(f"\n[Interrupt triggered]")
            print(f"Email ID: {review_data['email_id']}")
            print(f"Intent: {review_data['intent']}")
            print(f"Urgency: {review_data['urgency']}")
            print(f"Draft: {review_data['draft_response']}")

            # --- Read user input to resume ---
            print("\n" + "=" * 50)
            approved = input("Approve this response? (y/n): ").strip().lower() == "y"

            if approved:
                edited = input("Enter edits (or press Enter to keep as-is): ").strip()
                human_decision = {
                    "approved": True,
                    "edited_response": edited if edited else None,
                }
            else:
                human_decision = {"approved": False}

            print("\nResuming graph with decision:", human_decision)

            # --- Resume the graph with the human decision ---
            res2 = app.invoke(
                Command(resume=human_decision),
                config=config,
            )
            print("\nFinal result:", res2)
    else:
        print("Final result (no interrupt):", res1)
