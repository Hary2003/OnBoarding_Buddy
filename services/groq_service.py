import json
import requests
from typing import List, Dict, Optional
from config import settings

try:
    from groq import Groq
    GROQ_SDK_AVAILABLE = True
except ImportError:
    GROQ_SDK_AVAILABLE = False

VALID_FALLBACK_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant"
]

MODEL_ALIAS_MAP = {
    "gpt-oss-120b": "openai/gpt-oss-120b",
    "gpt-oss-20b": "openai/gpt-oss-20b",
    "groq/compound": "openai/gpt-oss-120b",
    "groq/compound-mini": "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama-3.3-70b": "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b": "qwen/qwen3.8-27b",
    "qwen-2.5-coder-32b": "qwen/qwen3.8-27b"
}

GROUNDED_SYSTEM_PROMPT = (
    "You are OnBoarding Buddy, an authoritative AI software architecture & repository assistant.\n"
    "Your core objective is to answer developer questions GROUNDED STRICTLY in the provided repository context.\n\n"
    "CRITICAL GROUNDING RULES:\n"
    "1. USE SUPPLIED CONTEXT ONLY: Rely strictly on the provided source code, symbols, dependencies, and file metadata.\n"
    "2. NO HALLUCINATIONS: Never invent or assume non-existent files, functions, classes, or architecture choices that are not present in the supplied context.\n"
    "3. DISTINGUISH FACTS FROM INFERENCE: State clear empirical facts from code. Label any logical inference as an inference.\n"
    "4. INSUFFICIENT CONTEXT: If the supplied context does NOT contain enough evidence to answer a question (such as speculative questions like 'Why was Redis chosen?'), EXPLICITLY state that the context is insufficient (e.g. 'I couldn't determine the reason from the repository context available. I found usage in X, but there isn't enough documentation or code evidence to establish why X was chosen.').\n"
    "5. CONCRETE CITATIONS: Prefer concrete code references (e.g. `services/repo_service.py` or `RepoService.extract_dependencies()`)."
)

class GroqService:
    GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

    def _call_groq_api_messages(self, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
        """Call Groq API with a list of messages (system prompt, conversation history, user turn)."""
        if not settings.is_groq_configured:
            return "⚠️ **Groq API Key missing.** Please set `GROQ_API_KEY` in your `.env` file to enable AI insights."

        configured_model = (settings.GROQ_MODEL or "groq/compound").strip()
        target_model = MODEL_ALIAS_MAP.get(configured_model, configured_model)
        models_to_try = [target_model] + [m for m in VALID_FALLBACK_MODELS if m != target_model]

        last_error = ""

        for model_name in models_to_try:
            # 1. Try official Groq SDK
            if GROQ_SDK_AVAILABLE:
                try:
                    client = Groq(api_key=settings.GROQ_API_KEY)
                    chat_completion = client.chat.completions.create(
                        messages=messages,
                        model=model_name,
                        temperature=temperature,
                        max_tokens=2048
                    )
                    return chat_completion.choices[0].message.content
                except Exception as e:
                    err_str = str(e)
                    if "401" in err_str or "Invalid API Key" in err_str:
                        return "❌ **Invalid Groq API Key.** Please check `GROQ_API_KEY` in `.env`."
                    last_error = err_str

            # 2. Try HTTP REST fallback
            headers = {
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 2048
            }

            try:
                response = requests.post(self.GROQ_URL, headers=headers, json=payload, timeout=30)
                if response.status_code == 401:
                    return "❌ **Invalid Groq API Key.** Please verify your key in `.env`."
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                last_error = response.text
            except Exception as e:
                last_error = str(e)

        return f"❌ **Groq API Error**: Could not complete request. Details: {last_error}"

    def _call_groq_api(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return self._call_groq_api_messages(messages, temperature=temperature)

    def summarize_code(self, file_path: str, code_content: str) -> dict:
        """Summarizes a code file using Groq LLM."""
        truncated_code = code_content[:8000] if len(code_content) > 8000 else code_content
        
        system_prompt = (
            "You are a senior software architect creating developer onboarding documentation. "
            "Analyze the provided source code file and provide a structured, clean Markdown summary with:\n"
            "1. 📌 **Purpose & Core Responsibility** (1-2 clear sentences)\n"
            "2. ⚙️ **Key Functions & Classes** (bullet points with descriptions)\n"
            "3. 🔗 **Dependencies & Imports**\n"
            "4. ⚠️ **Important Architectural Notes or Gotchas** (if any)"
        )
        
        user_prompt = f"File Path: {file_path}\n\nSource Code:\n```\n{truncated_code}\n```"
        
        summary_markdown = self._call_groq_api(system_prompt, user_prompt, temperature=0.1)
        return {
            "file_path": file_path,
            "summary": summary_markdown
        }

    def generate_onboarding_guide(self, repo_name: str, file_tree_structure: str, key_files: list) -> str:
        """Generates a complete ONBOARDING_GUIDE.md for the repository."""
        system_prompt = (
            "You are a Lead Software Engineer generating an official ONBOARDING_GUIDE.md for a new software developer. "
            "Your output must be well-structured, inspiring, clear, and written in professional Github Markdown."
        )
        
        user_prompt = (
            f"Repository Name: {repo_name}\n\n"
            f"Key Active Files:\n{json.dumps(key_files, indent=2)}\n\n"
            f"Directory Structure Summary:\n{file_tree_structure[:3000]}\n\n"
            "Please generate an Onboarding Guide with the following sections:\n"
            "# 🚀 Developer Onboarding Guide\n"
            "## 1. Executive Summary & Architecture Overview\n"
            "## 2. Recommended Reading & Exploration Order (Where to start)\n"
            "## 3. Core Component Breakdown\n"
            "## 4. Key Entry Points & Workflow Execution\n"
            "## 5. Pro-tips & Best Practices for New Contributors"
        )
        
        return self._call_groq_api(system_prompt, user_prompt, temperature=0.3)

    def chat_with_repository(self, question: str, repo_context: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        """Answers developer questions about the repository using grounded system prompt and history."""
        messages = [{"role": "system", "content": GROUNDED_SYSTEM_PROMPT}]
        
        # Append limited history (last 6 turns) if provided
        if history:
            for turn in history[-6:]:
                messages.append({"role": turn.get("role", "user"), "content": turn.get("content", "")})

        user_turn_content = f"Supplied Repository Context:\n{repo_context}\n\nDeveloper Question: {question}"
        messages.append({"role": "user", "content": user_turn_content})

        return self._call_groq_api_messages(messages, temperature=0.2)

    def generate_architecture_insight(self, repo_name: str, total_files: int, total_lines: int, entry_points: list, core_modules: list, leaf_modules: list, circular_count: int, languages: dict) -> str:
        """Generates LLM-backed executive architectural summary based on dependency graph analysis."""
        system_prompt = (
            "You are a Principal Software Architect analyzing dependency graphs and codebase structures. "
            "Provide a concise, executive architectural overview in markdown with:\n"
            "1. 🏛️ **Architecture Pattern & System Design**\n"
            "2. 🚀 **Primary Entry Points & Flow**\n"
            "3. 🧩 **Core Foundation & Utility Hubs**\n"
            "4. ⚠️ **Graph Health & Dependency Risk Assessment**"
        )
        
        user_prompt = (
            f"Repository: {repo_name}\n"
            f"Total Files: {total_files} ({total_lines} lines)\n"
            f"Languages: {json.dumps(languages)}\n"
            f"Entry Points: {json.dumps(entry_points)}\n"
            f"Core Hub Modules (high in-degree): {json.dumps(core_modules)}\n"
            f"Leaf / Utility Modules: {json.dumps(leaf_modules)}\n"
            f"Circular Dependency Loops: {circular_count}\n"
        )
        
        return self._call_groq_api(system_prompt, user_prompt, temperature=0.2)

groq_service = GroqService()
