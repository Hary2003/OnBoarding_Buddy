import json
import requests
from config import settings

try:
    from groq import Groq
    GROQ_SDK_AVAILABLE = True
except ImportError:
    GROQ_SDK_AVAILABLE = False

class GroqService:
    # Groq OpenAI-compatible fallback endpoint
    GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

    def _call_groq_api(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        """Call Groq API via official Groq SDK or REST fallback."""
        if not settings.is_groq_configured:
            return "⚠️ **Groq API Key missing.** Please set `GROQ_API_KEY` in your `.env` file to enable AI insights."

        model_name = settings.GROQ_MODEL or "groq/compound"

        # Try official Groq SDK first
        if GROQ_SDK_AVAILABLE:
            try:
                client = Groq(api_key=settings.GROQ_API_KEY)
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    model=model_name,
                    temperature=temperature,
                    max_tokens=2048
                )
                return chat_completion.choices[0].message.content
            except Exception as e:
                err_str = str(e)
                if "401" in err_str or "Invalid API Key" in err_str:
                    return "❌ **Invalid Groq API Key.** Please check `GROQ_API_KEY` in `.env`."
                # Fall through to HTTP request fallback if SDK fails

        # HTTP Fallback
        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": 2048
        }
        
        try:
            response = requests.post(self.GROQ_URL, headers=headers, json=payload, timeout=45)
            if response.status_code == 401:
                return "❌ **Invalid Groq API Key.** Please verify your key in `.env`."
            if response.status_code == 404:
                return f"❌ **Groq API Model Error (404).** Model `{model_name}` not found or endpoint unavailable. Try model `llama-3.3-70b-versatile` or `llama-3.1-8b-instant`."
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            return "⚠️ **Groq API timed out.** Please try again."
        except Exception as e:
            return f"❌ **Groq API Error**: {str(e)}"

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

    def chat_with_repository(self, question: str, repo_context: str) -> str:
        """Answers developer questions about the repository using Groq."""
        system_prompt = (
            "You are an AI Onboarding Buddy assisting a developer with understanding this repository. "
            "Answer the user's question accurately using the provided repository context. "
            "If the answer isn't fully in context, provide your best software engineering guidance while stating what is known."
        )
        
        user_prompt = f"Repository Context:\n{repo_context[:4000]}\n\nDeveloper Question: {question}"
        return self._call_groq_api(system_prompt, user_prompt, temperature=0.3)

groq_service = GroqService()
