# tools/db_tools.py
import sqlite3
import re
import pandas as pd
import os
from typing import Any, List, Optional
from datetime import timedelta

# Import ChatGroq from langchain_groq
from langchain_groq import ChatGroq

# -------------------------
# Invocation helper
# -------------------------
def _strip_code_fences(text: str) -> str:
    """Remove common code fences like ```sql or ``` from model output."""
    if text is None:
        return ""
    s = text.strip()
    s = re.sub(r"^```(?:sql)?\n", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\n```$", "", s, flags=re.IGNORECASE)
    return s.strip()

def groq_chat_invoke(llm: ChatGroq, system: str, human: str) -> str:
    """
    Robustly invoke a ChatGroq-like LLM instance.
    Tries common invocation patterns and returns plain text result.
    Raises RuntimeError if no invocation method works.
    """
    messages_for_invoke = [("system", system), ("human", human)]
    # 1) Try llm.invoke(messages)
    try:
        if hasattr(llm, "invoke"):
            resp = llm.invoke(messages_for_invoke)
            if resp is None:
                raise RuntimeError("llm.invoke returned None")
            # resp might be AIMessage-like
            if hasattr(resp, "content"):
                return _strip_code_fences(resp.content)
            if isinstance(resp, str):
                return _strip_code_fences(resp)
            # fallback stringify
            return _strip_code_fences(str(resp))
    except Exception as e:
        invoke_err = e

    # 2) Try calling the llm as a callable with a combined prompt
    combined_prompt = f"SYSTEM: {system}\nUSER: {human}"
    try:
        if callable(llm):
            out = llm(combined_prompt)
            if out is None:
                raise RuntimeError("LLM callable returned None")
            if hasattr(out, "content"):
                return _strip_code_fences(out.content)
            if isinstance(out, str):
                return _strip_code_fences(out)
            return _strip_code_fences(str(out))
    except Exception as e:
        callable_err = e

    # 3) Try llm.generate / llm.generate_responses
    try:
        if hasattr(llm, "generate") or hasattr(llm, "generate_responses"):
            # try structured messages first
            try:
                messages = [{"type": "system", "content": system}, {"type":"human","content": human}]
                if hasattr(llm, "generate_responses"):
                    gen = llm.generate_responses(messages)
                else:
                    gen = llm.generate(messages)
                # LangChain-like shape: gen.generations -> list[list[generation]]
                if hasattr(gen, "generations"):
                    first = gen.generations[0][0]
                    if hasattr(first, "text"):
                        return _strip_code_fences(first.text)
                # otherwise fallback to stringify
                return _strip_code_fences(str(gen))
            except Exception:
                # fallback to simpler prompt-based generate
                gen = llm.generate([combined_prompt])
                return _strip_code_fences(str(gen))
    except Exception as e:
        generate_err = e

    # If reached here, nothing worked
    errs = []
    for name in ("invoke_err", "callable_err", "generate_err"):
        if name in locals():
            errs.append(f"{name}: {locals()[name]!r}")
    raise RuntimeError(
        "Could not invoke the provided ChatGroq LLM with any known method. "
        "Tried: llm.invoke(messages), calling llm(...), llm.generate(...). "
        "Make sure you passed a valid langchain_groq.ChatGroq instance (with API key). "
        "Captured errors:\n" + ("\n".join(errs) if errs else "none")
    )

# -------------------------
# SQL execution helper
# -------------------------
def run_safe_sql(db_path: str, sql: str, max_rows: int = 200) -> pd.DataFrame:
    """
    Execute only SELECT statements and enforce a row limit as a safety measure.
    """
    sql_clean = sql.strip().lower()
    if not sql_clean.startswith("select"):
        raise ValueError("Only SELECT queries allowed for safety.")
    # add LIMIT if not present
    if " limit " not in sql_clean:
        sql = sql.rstrip(";") + f" LIMIT {max_rows}"
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(sql, conn)
    finally:
        conn.close()
    return df

# -------------------------
# BaseDBTool
# -------------------------
class BaseDBTool:
    def __init__(self, db_path: str, table_name: str, llm: ChatGroq):
        self.db_path = db_path
        self.table_name = table_name
        self.llm = llm
        self.columns = self._fetch_columns()

    def _fetch_columns(self) -> List[str]:
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info({self.table_name});")
            cols = [row[1] for row in cur.fetchall()]
            conn.close()
            return cols
        except Exception:
            return []

    def _make_system_prompt(self) -> str:
        cols = ", ".join(self.columns) if self.columns else "<unknown_columns>"
        system = (
            "You are a SQL generator. Convert the user question into a single safe SQL SELECT "
            f"query that queries the table named `{self.table_name}`. "
            "Return just the SQL SELECT query and nothing else. Use column names exactly as provided. "
            "If the user requests a limited number of rows, please include a LIMIT clause. "
            "Only generate SELECT statements. The table columns are: " + cols + "."
        )
        return system

    def nl_to_sql(self, user_question: str) -> str:
        system = self._make_system_prompt()
        human = user_question
        sql = groq_chat_invoke(self.llm, system, human).strip()
        sql = re.sub(r"```sql|```", "", sql, flags=re.IGNORECASE).strip()
        # ensure table reference present (simple heuristic)
        if self.table_name not in sql.lower():
            sql = re.sub(r"\bfrom\b", f"FROM {self.table_name}", sql, flags=re.IGNORECASE)
        return sql

    def _apply_date_filter_fallback(self, df: pd.DataFrame, user_question: str) -> pd.DataFrame:
        """
        If the user asked something like 'last 90 days' and the SQL didn't filter
        by date, attempt to find a date-like column and filter in Python.
        """
        text = user_question.lower()
        if "last 90" not in text and "last 90 days" not in text:
            return df

        # find candidates for date columns
        candidates = [c for c in df.columns if "date" in c.lower() or "admit" in c.lower() or "time" in c.lower()]
        # try to coerce object columns that look like dates
        for c in df.columns:
            if c not in candidates and df[c].dtype == object:
                try:
                    conv = pd.to_datetime(df[c], errors="coerce")
                    if conv.notna().any():
                        candidates.append(c)
                        df[c] = conv
                except Exception:
                    pass

        if not candidates:
            return df

        # pick first candidate and filter
        date_col = candidates[0]
        try:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=90)
            df = df[df[date_col] >= cutoff]
        except Exception:
            # if conversion fails, just return original df
            return df
        return df

    def _apply_sorting_fallback(self, df: pd.DataFrame, user_question: str) -> pd.DataFrame:
        """
        If the user asked to sort by age but SQL didn't include it, apply sorting here.
        """
        text = user_question.lower()
        if "sort" in text or "sorted" in text or "order by" in text:
            if "age" in text and "age" in df.columns:
                try:
                    df = df.sort_values(by="age")
                except Exception:
                    pass
        return df

    def _format_table(self, df: pd.DataFrame, max_rows_preview: int = 10) -> str:
        # try to use to_markdown (requires tabulate); fallback to to_string
        try:
            table = df.head(max_rows_preview).to_markdown(index=False)
        except Exception:
            table = df.head(max_rows_preview).to_string(index=False)
        return table

    def _build_summary(self, df: pd.DataFrame) -> str:
        parts = []
        # numeric summary
        try:
            num_summary = df.describe(include="number").to_string()
            parts.append("Numeric summary:\n" + num_summary)
        except Exception:
            pass
        # categorical/text summary
        try:
            obj_summary = df.describe(include="object").to_string()
            parts.append("Categorical summary:\n" + obj_summary)
        except Exception:
            pass
        # datetime columns: min/max/count
        try:
            dt_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
            # detect object columns that look like datetimes and coerce
            for c in df.columns:
                if c not in dt_cols and df[c].dtype == object:
                    try:
                        conv = pd.to_datetime(df[c], errors="coerce")
                        if conv.notna().any():
                            df[c] = conv
                            dt_cols.append(c)
                    except Exception:
                        pass
            if dt_cols:
                dt_lines = []
                for c in dt_cols:
                    col = df[c].dropna()
                    if not col.empty:
                        dt_lines.append(f"{c}: min={col.min()}, max={col.max()}, count={len(col)}")
                    else:
                        dt_lines.append(f"{c}: all null")
                parts.append("Datetime columns:\n" + "\n".join(dt_lines))
        except Exception:
            pass

        return "\n\n".join(parts) if parts else "No summary available."

    def run(self, user_question: str) -> str:
        """
        Convert NL -> SQL via LLM, execute safely, post-process (date/sort fallbacks),
        and return a human-friendly response.
        """
        try:
            sql = self.nl_to_sql(user_question)
        except Exception as e:
            return f"Error generating SQL from question: {e}"

        try:
            df = run_safe_sql(self.db_path, sql)
        except Exception as e:
            return f"Error executing SQL: {e}"

        # Post-processing fallbacks: date filter (e.g., last 90 days), sorting
        try:
            df = self._apply_date_filter_fallback(df, user_question)
            df = self._apply_sorting_fallback(df, user_question)
        except Exception:
            # non-fatal: continue with original df
            pass

        # If df is empty, return friendly message
        if df.empty:
            return f"Executed SQL:\n```sql\n{sql}\n```\n\nQuery returned no results."

        # If many rows, return summary + head
        try:
            if len(df) > 10:
                summary = self._build_summary(df)
                table = self._format_table(df, max_rows_preview=10)
                return (
                    f"Executed SQL:\n```sql\n{sql}\n```\n\n"
                    f"Summary:\n{summary}\n\n"
                    f"First 10 rows:\n{table}"
                )
            else:
                table = self._format_table(df, max_rows_preview=len(df))
                return (
                    f"Executed SQL:\n```sql\n{sql}\n```\n\n"
                    f"Results:\n{table}"
                )
        except Exception as e:
            return f"Error while formatting results: {e}"

# -------------------------
# Factory functions
# -------------------------
def create_heart_tool(llm: ChatGroq) -> BaseDBTool:
    return BaseDBTool("db/heart_disease.db", "heart_disease", llm)

def create_cancer_tool(llm: ChatGroq) -> BaseDBTool:
    return BaseDBTool("db/cancer.db", "cancer", llm)

def create_diabetes_tool(llm: ChatGroq) -> BaseDBTool:
    return BaseDBTool("db/diabetes.db", "diabetes", llm)
