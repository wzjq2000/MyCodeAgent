import os
from typing import Literal, cast

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.constants import END

from my_code_agent.agent.state import EmailAgentState, EmailClassification, Intent, NodeName, Urgency
from langchain_core.messages import HumanMessage

from langgraph.types import interrupt, Command, RetryPolicy

load_dotenv(override=True)
llm = init_chat_model(
    model_provider="deepseek",
    model="deepseek-v4-flash",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_API_BASE"),
    extra_body={"thinking": {"type": "disabled"}},
)


def read_email(state: EmailAgentState) -> dict:
    return {
        "messages": [HumanMessage(content=f"Processing email: {state.email_content}")]
    }


def classify_intent(state: EmailAgentState) -> Command[Literal[
    NodeName.SEARCH_DOCUMENT, NodeName.HUMAN_REVIEW, NodeName.BUG_TRACKING, NodeName.DRAFT_RESPONSE
]]:
    structured_llm = llm.with_structured_output(EmailClassification)

    classification_prompt = f"""
    Analyze this customer's email and classify it:

    Email: {state.email_content}
    From: {state.sender_email}

    Provide classification including intent, urgency, topic and summary.
    """

    classification = cast(EmailClassification, structured_llm.invoke(classification_prompt))

    # determine next node based on classification
    if classification.intent == Intent.BILLING or classification.urgency == Urgency.CRITICAL:
        goto = NodeName.HUMAN_REVIEW
    elif classification.intent in [Intent.QUESTION, Intent.FEATURE]:
        goto = NodeName.SEARCH_DOCUMENT
    elif classification.intent == Intent.BUG:
        goto = NodeName.BUG_TRACKING
    else:
        goto = NodeName.DRAFT_RESPONSE

    # store classification as a dict in state
    return Command(
        update={"classification": classification}, goto=goto
    )


def search_document(state: EmailAgentState) -> Command[Literal[NodeName.DRAFT_RESPONSE]]:
    classification = state.classification or EmailClassification()
    query = f'{classification.intent or ''} {classification.topic or ''}'
    search_results = [f"Search temporarily unavailable"]
    try:
        search_results = [
            "Reset password via Settings > Security > Change Password",
            "Password must be at least 12 characters",
            "Include uppercase, lowercase, numbers, and symbols"
        ]
        # except SearchAPIError as e:
        # # For recoverable search errors, store error and continue
        # search_results = [f"Search temporarily unavailable: {str(e)}"]
    except:
        print("wrong")
    return Command(update={"search_results": search_results}, goto=NodeName.DRAFT_RESPONSE)


def bug_tracking(state: EmailAgentState) -> Command[Literal[NodeName.DRAFT_RESPONSE]]:
    ticket_id = "BUG-12345"
    return Command(update={"search_results": [f"Bug ticket {ticket_id} created"], "current_step": "bug_tracked"},
                   goto=NodeName.DRAFT_RESPONSE)


def draft_response(state: EmailAgentState) -> Command[Literal[NodeName.HUMAN_REVIEW, NodeName.SEND_REPLY]]:
    classification = state.classification or EmailClassification()

    # format context from raw data on demand
    context_sections = []

    if state.search_results:
        formatted_docs = "\n".join([f"- {doc}" for doc in state.search_results])
        context_sections.append(f"Relevant documents: {formatted_docs}")

    if state.customer_history:
        context_sections.append(f"Customer tier: {state.customer_history.get('tier', 'standard')}")

    # build the prompt with formatted context
    draft_prompt = f"""
    Draft a response to this customer email:
    {state.sender_email}
    
    Email Intent: {classification.intent or 'unknown'}
    Urgency Level: {classification.urgency or 'medium'}
    
    {'\n'.join(context_sections)}
    
    Guidelines:
    - Be professional and helpful
    - Address their specific concern
    - Use the provided documents when relevant.
    """

    response = llm.invoke(draft_prompt)

    # determine if human review needed based on urgency and intent
    needs_review = (
            classification.intent == 'complex' or classification.urgency in [Urgency.CRITICAL, Urgency.HIGH]
    )

    # route to appropriate next node
    goto = NodeName.HUMAN_REVIEW if needs_review else NodeName.SEND_REPLY

    return Command(update={"draft_response": response.content}, goto=goto)


def human_review(state: EmailAgentState) -> Command[Literal[NodeName.SEND_REPLY, END]]:
    classification = state.classification or EmailClassification()

    human_decision = interrupt({
        "email_id": state.email_id,
        "original_email": state.sender_email,
        "draft_response": state.draft_response,
        "urgency": classification.urgency,
        "intent": classification.intent,
        "action": "Please review and approve/edit this response"
    })

    if human_decision.get("approved"):
        return Command(
            update={"draft_response": human_decision.get("edited_response", state.draft_response)},
            goto=NodeName.SEND_REPLY
        )

    else:
        return Command(
            update={}, goto=END
        )


def send_reply(state: EmailAgentState) -> dict:
    print(f"sending reply: {state.draft_response}")
    return {}
