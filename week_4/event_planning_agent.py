import os
from typing import TypedDict, Literal, Optional
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import requests
from pprint import pprint


load_dotenv()


llm = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0,
)


# Define event schema structure
# Sample User Prompt: I am organizing an outdoor AI bootcamp networking session tomorrow evening in Lagos, Nigeria for beginner developers and working professionals. Help me prepare a readiness plan.
class EventDetails(BaseModel):
    event_type: str = Field(description="Type of event, e.g. bootcamp class, outdoor meetup, church event")
    city: str = Field(description="City or location where the event will happen")
    country: Optional[str] = Field(default=None, description="Country if provided")
    date_or_time: Optional[str] = Field(default=None, description="Event date or time if provided")
    audience: Optional[str] = Field(default=None, description="Who the event is for")
    is_outdoor: bool = Field(description="Whether weather is likely important for this event")
    missing_info: list[str] = Field(default_factory=list, description="Important missing details")


class ReviewResult(BaseModel):
    score: int = Field(description="Quality score from 1 to 10")
    passed: bool = Field(description="Whether the plan is good enough")
    feedback: str = Field(description="Specific feedback for improvement")


# Define the workflow/graph state
class AgentState(TypedDict):
    user_request: str
    event_details: Optional[EventDetails]
    weather_report: Optional[str]
    plan: Optional[str]
    review: Optional[ReviewResult]
    revision_count: int
    final_answer: Optional[str]


# Define the weather tool
@tool
def check_weather(location: str) -> str:
    """Get the current weather in a given location using OpenWeatherMap."""

    api_key = os.getenv("OPENWEATHER_API_KEY")

    if not api_key:
        return "Weather tool error: OPENWEATHER_API_KEY is missing from the .env file."

    url = "https://api.openweathermap.org/data/2.5/weather"

    params = {
        "q": location,
        "appid": api_key,
        "units": "metric"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
    except requests.RequestException as e:
        return f"Weather tool error: {str(e)}"

    if response.status_code != 200:
        return f"Could not get weather for {location}. Error: {response.text}"

    data = response.json()

    city = data["name"]
    country = data["sys"]["country"]
    temperature = data["main"]["temp"]
    feels_like = data["main"]["feels_like"]
    description = data["weather"][0]["description"]
    humidity = data["main"]["humidity"]
    wind_speed = data["wind"]["speed"]

    return (
        f"Current weather in {city}, {country}: {description}. "
        f"Temperature: {temperature}°C. "
        f"Feels like: {feels_like}°C. "
        f"Humidity: {humidity}%. "
        f"Wind speed: {wind_speed} m/s."
    )


# Node 1: Extract event details in a structured format.
def extract_event_details_node(state: AgentState) -> dict:
    print(f"extract_event_details_node state - user_request: {state["user_request"]}")

    # NOTE for "with_structured_output()":
    # "with_structured_output()" tells the LLM, "Whenever you answer, produce an EventDetails object."
    # LangChain uses the schema to instruct the model to produce structured data.
    # This is a powerful way to control the output format.
    # If not used, the model returns a human-readable output which will be challenging for downstream code to process,
    # you would need to parse the text yourself.
    structured_llm = llm.with_structured_output(EventDetails)

    prompt = f"""
You are an expert event operations assistant.

Extract structured event details from the user's request.

User request:
{state["user_request"]}

Rules:
- Infer only what is reasonable.
- If important details are missing, list them in missing_info.
- Decide if weather matters. Weather usually matters for outdoor events, travel, logistics, or physical attendance.
"""

    details = structured_llm.invoke(prompt)
    print(f"extract_event_details_node state - details: {details}")

    test_response = llm.invoke(state["user_request"])
    print(f"extract_event_details_node state - test_response: {test_response}")

    return {
        "event_details": details
    }


# Conditional router
def route_weather_check(state: AgentState) -> Literal["check_weather", "generate_plan"]:
    details = state["event_details"]

    if details and details.is_outdoor:
        return "check_weather"

    return "generate_plan"


# Node 2: Call weather tool
def check_weather_node(state: AgentState) -> dict:
    details = state["event_details"]

    if not details:
        return {"weather_report": "Weather was not checked because event details were missing."}

    location = details.city

    if details.country:
        location = f"{details.city}, {details.country}"

    """ NOTE:
        When you import tool from LangChain and decorate a function:

        from langchain_core.tools import tool

        @tool
        def check_weather(location: str) -> str:
            ...

        LangChain converts that function into a Tool object (specifically a StructuredTool or similar), 
        which implements the Runnable interface.

        Because tools are Runnables, they automatically get methods such as:

        .invoke()
        .ainvoke()
        .batch()
        .stream()
    """
    weather_report = check_weather.invoke({"location": location})
    print(f"check_weather type: {type(check_weather)}")

    return {
        "weather_report": weather_report
    }


# Node 3 generate the event plan
def generate_plan_node(state: AgentState) -> dict:
    details = state["event_details"]
    weather = state["weather_report"] or "Weather was not required or not available."

    prompt = f"""
You are a senior event operations planner.

Create a practical event readiness plan.

Original user request:
{state["user_request"]}

Structured event details:
{details.model_dump() if details else "No structured details available"}

Weather information:
{weather}

Your plan must include:
1. Event summary
2. Key assumptions
3. Preparation checklist
4. Weather/logistics considerations if relevant
5. Risks and mitigation
6. Final recommendation

Be practical, clear, and suitable for someone organizing the event tomorrow.
"""

    response = llm.invoke(prompt)

    return {
        "plan": response.content
    }


# Node 4: Review the plan
def review_plan_node(state: AgentState) -> dict:
    structured_llm = llm.with_structured_output(ReviewResult)

    prompt = f"""
You are a strict quality reviewer.

Review the event plan below.

User request:
{state["user_request"]}

Plan:
{state["plan"]}

Score the plan from 1 to 10.

The plan should pass only if:
- It answers the user's request clearly
- It is practical
- It includes risks
- It uses weather information when relevant
- It does not make unsupported claims

Return structured review only.
"""

    review = structured_llm.invoke(prompt)

    return {
        "review": review
    }


# Conditional router: Accept or revise?
def route_after_review(state: AgentState) -> Literal["finalize", "revise_plan"]:
    review = state["review"]
    revision_count = state["revision_count"]

    if review and review.passed:
        return "finalize"

    if revision_count >= 1:
        return "finalize"

    return "revise_plan"


# Node 5: Revise the plan
def revise_plan_node(state: AgentState) -> dict:
    review = state["review"]

    prompt = f"""
You are improving an event readiness plan.

Original user request:
{state["user_request"]}

Previous plan:
{state["plan"]}

Reviewer feedback:
{review.feedback if review else "No feedback available"}

Rewrite the plan to address the feedback.
Make it clearer, more practical, and more complete.
"""

    response = llm.invoke(prompt)

    return {
        "plan": response.content,
        "revision_count": state["revision_count"] + 1
    }


# Node 6: Finalize
def finalize_node(state: AgentState) -> dict:
    review = state["review"]

    final_answer = f"""
{state["plan"]}

---

Plan quality score: {review.score if review else "Not reviewed"}/10

Reviewer note:
{review.feedback if review else "No review feedback available."}
"""

    return {
        "final_answer": final_answer
    }


# Build the LangGraph workflow
def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("extract_event_details", extract_event_details_node)
    builder.add_node("check_weather", check_weather_node)
    builder.add_node("generate_plan", generate_plan_node)
    builder.add_node("review_plan", review_plan_node)
    builder.add_node("revise_plan", revise_plan_node)
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "extract_event_details")

    builder.add_conditional_edges(
        "extract_event_details",
        route_weather_check,
        {
            "check_weather": "check_weather",
            "generate_plan": "generate_plan"
        },
    )

    builder.add_edge("check_weather", "generate_plan")
    builder.add_edge("generate_plan", "review_plan")

    builder.add_conditional_edges(
        "review_plan",
        route_after_review,
        {
            "finalize": "finalize",
            "revise_plan": "revise_plan"
        },
    )

    builder.add_edge("revise_plan", "review_plan")
    builder.add_edge("finalize", END)

    return builder


# Compile the graph
graph = build_graph().compile()

# Graph input
inputs = {
    "user_request": """I am organizing an outdoor AI bootcamp networking session tomorrow evening in Lagos, Nigeria for beginner developers and working professionals. Help me prepare a readiness plan.""",
    "event_details": None,
    "weather_report": None,
    "plan": None,
    "review": None,
    "revision_count": 0,
    "final_answer": None
}

# Stream graph execution

for chunk in graph.stream(inputs, stream_mode="updates"):
    print("\n==============================")
    print("GRAPH UPDATE")
    print("==============================")
    # NOTE: each chunk contains the state updates returned by a node, not the entire state and not just the final result.
    # So you get a node-by-node view of the state updates.
    pprint(chunk)

# Get final answer directly
# NOTE: graph.invoke() runs the entire graph to completion and returns the final state.
result = graph.invoke(inputs)

print("\n\nFINAL ANSWER")
print("============")
print(result["final_answer"])
