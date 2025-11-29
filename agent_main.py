# agent_main.py
import os
import sys
from dotenv import load_dotenv

# load .env from project root
load_dotenv()

from langchain_groq import ChatGroq
from tools.db_tools import create_heart_tool, create_cancer_tool, create_diabetes_tool
from tools.web_search_tool import MedicalWebSearchTool

# Keywords to route between DB tools and web tool
DATA_KEYWORDS = [
    "count", "average", "mean", "median", "sum", "how many",
    "statistics", "distribution", "correlation", "age", "bps",
    "cholesterol", "glucose", "diagnosis", "patients", "rate"
]
WEB_KEYWORDS = [
    "define", "definition", "symptom", "symptoms", "treatment",
    "cure", "how to treat", "what is", "side effects"
]

def choose_tool(text: str):
    txt = text.lower()
    if any(w in txt for w in WEB_KEYWORDS):
        return "web"
    if any(w in txt for w in DATA_KEYWORDS) or "show" in txt or "list" in txt:
        if "heart" in txt or "cardio" in txt:
            return "heart"
        if "cancer" in txt or "tumor" in txt or "tumour" in txt:
            return "cancer"
        if "diabetes" in txt or "blood sugar" in txt or "glucose" in txt:
            return "diabetes"
        return "heart"
    return "web"

def main_loop():
    # Read Groq API key from environment (loaded via python-dotenv)
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        print("ERROR: GROQ_API_KEY not found. Please add it to your .env or environment variables.")
        print("Add a line like: GROQ_API_KEY=your_key_here")
        sys.exit(1)

    # Instantiate the Groq LLM
    # NOTE: replace the model with one you have access to in your Groq account.
    # Common example: "mixtral-8x7b-32768"
    llm = ChatGroq(
        groq_api_key=groq_api_key,
        model="openai/gpt-oss-20b",
        temperature=0,
    )

    # Create tools (these expect the llm for SQL generation)
    heart_tool = create_heart_tool(llm)
    cancer_tool = create_cancer_tool(llm)
    diabetes_tool = create_diabetes_tool(llm)
    web_tool = MedicalWebSearchTool(provider="serpapi")

    print("Multi-tool medical agent (Groq) ready. Type 'quit' to exit.")
    while True:
        try:
            q = input("\nUser> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if not q:
            continue
        if q.lower() in ("quit", "exit"):
            break

        tool_choice = choose_tool(q)
        print(f"[Routing to: {tool_choice}]")

        if tool_choice == "web":
            out = web_tool.run(q)
        elif tool_choice == "heart":
            out = heart_tool.run(q)
        elif tool_choice == "cancer":
            out = cancer_tool.run(q)
        elif tool_choice == "diabetes":
            out = diabetes_tool.run(q)
        else:
            out = "No tool found."

        print("\n=== Agent response ===\n")
        print(out)
        print("\n======================\n")

if __name__ == "__main__":
    main_loop()
