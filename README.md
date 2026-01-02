# 🧠 MultiTool Medical AI Agent
LLM-powered medical assistant with SQL querying, diagnosis support, and external web search.
---

## 🚀 Project Overview

This project implements a specialized medical agent that can intelligently route user questions to multiple tools:

🩺 Medical Dataset SQL Tools (Heart Disease, Diabetes, Cancer).

🌐 Medical Web Search Tool (SerpAPI or Bing).

💬 Groq-powered LLM (ChatGroq).

🧭 Router system that decides which tool to use for each query.

It supports natural-language questions like:

```
“List all patients with cholesterol above 250.”
“Show first 10 rows of the heart disease dataset.”
“Return patients admitted in the last 90 days sorted by age.”
“What are the symptoms of pancreatic cancer?”
```
The system safely converts natural-language queries into SQL (via Groq LLM), runs them against SQLite databases, and returns summaries or result tables.

---

## 🚀 Features (Updated)

### ✔ Robust Groq LLM Integration

Uses ChatGroq from langchain_groq with full API-key authentication.

Also includes multi-mode LLM invocation fallback ensuring compatibility with all Groq model versions.

### ✔ Safe SQL Generation + Execution

NL → SQL conversion using the LLM includes:

- Only allows SELECT statements

- Auto-injects LIMIT if missing

- Automatically corrects missing table names

- Sanitizes code-fences in LLM output

### ✔ Automatic Date-Filtering Fallback

If the user asks:

“in the last 90 days”

and the SQL lacks a date filter, the system:

- Finds possible date-like columns (date, admit, time, etc.)

- Converts them to datetime

- Applies filtering in Python safely

### ✔ Sorting Fallback

If SQL ignores sorting (e.g., "sort by age"), the system performs sorting in Python.

### ✔ Improved Result Summaries

Instead of Pandas’ deprecated datetime_is_numeric, the agent now:

- Builds numeric and categorical summaries separately

- Detects datetime columns manually

- Provides min/max/count for datetime values

### ✔ Tabular Output with Markdown

Uses to_markdown if available or falls back to to_string.

### ✔ Modular Tool Architecture
```
tools/db_tools.py – SQL generation + fallback logic

tools/web_search_tool.py – SerpAPI/Bing

agent_main.py – routing + conversation loop
```

---

## 📦 Requirements

Install Python dependencies:

```
pip install -r requirements.txt
```
Make sure to have:

- langchain

- langchain_groq

- pandas

- tabulate

- requests

- python-dotenv
  
---

🔑 API Keys

Create a .env file:
```
GROQ_API_KEY=your_groq_key_here
SERPAPI_API_KEY=your_serpapi_key_here
BING_SUBSCRIPTION_KEY=your_bing_api_key_here
```

Load them in Python:
```
from dotenv import load_dotenv
load_dotenv()
```

---

## 📁 Project Structure
```
MultiTool_MedicalAI/
│
├── agent_main.py
├── tools/
│   ├── db_tools.py   ← fully updated SQL tool
│   ├── web_search_tool.py
│
├── db/
│   ├── heart_disease.db
│   ├── cancer.db
│   ├── diabetes.db
│
├── .env
├── README.md
└── requirements.txt
```

---

## 🧰 Tools Overview

### 🗄 1. Database Tools

- Three datasets are exposed as tools:

| Dataset        | File Path              | Table Name      |
|----------------|------------------------|-----------------|
| Heart Disease  | db/heart_disease.db    | heart_disease   |
| Cancer         | db/cancer.db           | cancer          |
| Diabetes       | db/diabetes.db         | diabetes        |

Each tool supports:

  - Natural language → SQL conversion

  - Safety checks (only SELECT)

  - Date-filter fallback

  - Sorting fallback

  - Automatic summary + markdown tables

- Example query:
```
"List all patients with cholesterol > 250"
```

### 🌐 2. Medical Web Search Tool

Supports:

- SerpAPI Google Search (recommended)

- Bing Search API

Usage:
```
MedicalWebSearchTool(provider="serpapi")
```

Returns:

- Top N results

- Title + snippet + URL

### 🧭 3. Router Logic

The agent decides whether a question should go to:

-> Heart SQL tool

-> Cancer SQL tool

-> Diabetes SQL tool

-> General web search

-> Direct LLM reasoning

The routing is performed via a Groq LLM using a classification prompt.

---

## ▶ Running the Agent

From project root:
```
python agent_main.py
```

You’ll see:
```
User>
```

Start asking questions like:

“Show first 10 rows of the heart disease table.”

“Which patients have BMI higher than 30?”

“What are early signs of breast cancer?”

“Patients admitted in last 90 days sorted by age.”

“Compare symptoms of type 1 and type 2 diabetes.”

---

## 🧪 Example Queries to Test the Agent

### ✔ Database Queries
```
List all patients with cholesterol higher than 250.
Show me the first 10 rows of the heart disease table.
Patients admitted in the last 90 days sorted by age.
Find diabetic patients aged over 60.
Show cancer dataset summary.
Return patients with fasting blood sugar > 120.
```
### ✔ Web Search Queries
```
What are symptoms of pancreatic cancer?
Latest research on heart disease prevention.
What causes type 2 diabetes?
```

### ✔ Mixed Reasoning
```
Compare heart attack symptoms in men vs women.
Explain the role of insulin in diabetes.
Summarize common cancer screening methods.
```

---
## 🎥 Demo Video:
👉 URL for final overview: https://drive.google.com/file/d/1o5VSHRyjtJnP6A3t85QE9Zpe7bY14Cuo/view?usp=sharing
