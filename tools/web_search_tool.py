# tools/web_search_tool.py
import os
import time
import requests
from typing import Optional, Dict

DEFAULT_TIMEOUT = 10
DEFAULT_NUM_RESULTS = 3

class MedicalWebSearchTool:
    """
    Simple web search tool for medical definitions/symptoms/treatments.
    Supports SerpAPI (default) and Bing (fallback).
    """

    def __init__(self, provider: str = "serpapi", enable_cache: bool = True, max_retries: int = 2):
        self.provider = provider.lower()
        self.serp_api_key = os.getenv("SERPAPI_API_KEY")
        self.bing_key = os.getenv("BING_SUBSCRIPTION_KEY")
        self._cache: Dict[str, str] = {} if enable_cache else None
        self.max_retries = int(max_retries)

    def run(self, query: str, num_results: int = DEFAULT_NUM_RESULTS) -> str:
        query = (query or "").strip()
        if not query:
            return "No query provided."

        # Check cache
        if self._cache is not None and query in self._cache:
            return self._cache[query]

        if self.provider == "serpapi":
            result = self._safe_call(self._serpapi_search, query, num_results=num_results)
        else:
            result = self._safe_call(self._bing_search, query, num_results=num_results)

        # store cache
        if self._cache is not None:
            self._cache[query] = result

        return result

    def _safe_call(self, func, *args, **kwargs) -> str:
        last_exc = None
        for attempt in range(1, self.max_retries + 2):  # e.g. max_retries=2 -> attempts 1..3
            try:
                return func(*args, **kwargs)
            except requests.RequestException as e:
                last_exc = e
                # exponential backoff
                time.sleep(0.5 * attempt)
            except Exception as e:
                # non-network error -> bubble up as nice message
                return f"Error during web search: {e}"
        # if we exhausted retries
        return f"Network error while contacting search provider: {last_exc}"

    def _serpapi_search(self, query: str, num_results: int = DEFAULT_NUM_RESULTS) -> str:
        if not self.serp_api_key:
            return "SerpAPI key not configured. Set SERPAPI_API_KEY in your environment or .env."

        params = {
            "q": query,
            "engine": "google",
            "api_key": self.serp_api_key,
            "num": max(1, int(num_results)),
        }

        resp = requests.get("https://serpapi.com/search", params=params, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        snippets = []

        # Prefer direct answer/answer_box if present
        if "answer_box" in data:
            ab = data["answer_box"]
            # pick the most descriptive field available
            for field in ("answer", "snippet", "snippet_highlighted_words"):
                if ab.get(field):
                    text = ab.get(field)
                    snippets.append(f"Direct answer:\n{text}")
                    break

        # organic_results (common)
        organic = data.get("organic_results", [])
        for i, r in enumerate(organic[:num_results], start=1):
            title = r.get("title") or r.get("position") or f"Result {i}"
            snippet = r.get("snippet") or r.get("snippet_text") or r.get("rich_snippet", {}).get("top", "")
            link = r.get("link") or r.get("displayed_link") or r.get("url")
            if not (title or snippet or link):
                continue
            snippet_text = f"{i}. {title}\n{snippet}\n{link}"
            snippets.append(snippet_text)

        # fallback: 'top' or 'related_questions'
        if not snippets:
            # try related_questions or knowledge_graph
            if data.get("related_questions"):
                for i, q in enumerate(data["related_questions"][:num_results], start=1):
                    snippets.append(f"{i}. {q.get('question')}\n{q.get('answer')}\n")
            elif data.get("knowledge_graph"):
                kg = data["knowledge_graph"]
                snippets.append(f"Knowledge graph: {kg.get('title')}\n{kg.get('description')}")

        if not snippets:
            return "No results found for that query."

        # join results into a human-friendly string
        result = "Web search results:\n\n" + "\n\n".join(snippets)
        return result

