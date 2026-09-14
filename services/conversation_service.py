import re
from typing import List, Dict, Set, Tuple, Optional, Any
from models.repository_index import (
    RepositoryIndex, FileInfo, Symbol, RetrievedContextPayload,
    ScoredFile, SourceAttribution, ChatResponse
)
from services.retrieval_service import retrieval_engine
from services.groq_service import groq_service

class ConversationService:
    def __init__(self):
        # Session ID -> List of {"role": "user"|"assistant", "content": str}
        self._session_histories: Dict[str, List[Dict[str, str]]] = {}

    def get_history(self, session_id: str = "default") -> List[Dict[str, str]]:
        """Returns multi-turn conversation history for a given session."""
        return self._session_histories.get(session_id, [])

    def add_turn(self, session_id: str, role: str, content: str):
        """Appends a turn to session history, enforcing a maximum history limit of 10 turns."""
        if session_id not in self._session_histories:
            self._session_histories[session_id] = []
        self._session_histories[session_id].append({"role": role, "content": content})
        # Keep last 10 turns max to avoid context pollution
        if len(self._session_histories[session_id]) > 10:
            self._session_histories[session_id] = self._session_histories[session_id][-10:]

    def clear_history(self, session_id: str = "default") -> bool:
        """Clears conversation history for a session."""
        if session_id in self._session_histories:
            del self._session_histories[session_id]
            return True
        return False

    def extract_source_attributions(self, retrieved_payload: RetrievedContextPayload, answer_text: str, repo_index: Optional[RepositoryIndex] = None) -> List[SourceAttribution]:
        """Extracts structured SourceAttribution items connecting answer text to retrieved context."""
        sources: List[SourceAttribution] = []
        seen_keys: Set[Tuple[str, Optional[str]]] = set()

        file_symbol_map = {}
        if repo_index:
            for f in repo_index.files:
                file_symbol_map[f.relative_path] = f.symbols

        for sf in retrieved_payload.scored_files:
            file_rel = sf.relative_path
            
            # Check if file or symbols are cited in answer or scored as primary match
            file_mentioned = (sf.file_name.lower() in answer_text.lower() or 
                              file_rel.lower() in answer_text.lower() or 
                              sf.total_score >= 3.0)

            if file_mentioned:
                symbols_to_cite = sf.matched_symbols if sf.matched_symbols else []
                
                if symbols_to_cite:
                    for sym_str in symbols_to_cite[:3]:
                        clean_sym = sym_str.split("(")[0].split("[")[0].strip()
                        key = (file_rel, clean_sym)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            
                            # Find line number if available
                            line_no = None
                            if file_rel in file_symbol_map:
                                for s in file_symbol_map[file_rel]:
                                    if s.name == clean_sym:
                                        line_no = s.line_number
                                        break
                                        
                            reason = f"Matched via {', '.join(sf.signals[:2])}" if sf.signals else "Retrieved relevant source"
                            sources.append(SourceAttribution(
                                file_path=file_rel,
                                symbol_name=clean_sym,
                                line_number=line_no,
                                relevance_reason=reason
                            ))
                else:
                    key = (file_rel, None)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        reason = sf.expansion_reason if sf.is_expanded_dependency else f"Matched via {', '.join(sf.signals[:2])}"
                        sources.append(SourceAttribution(
                            file_path=file_rel,
                            symbol_name=None,
                            line_number=1,
                            relevance_reason=reason
                        ))

        return sources

    def process_chat(self, question: str, session_id: str = "default", repo_index: Optional[RepositoryIndex] = None) -> ChatResponse:
        """Main Grounded Assistant Pipeline: Retrieve -> Evaluate -> Prompt -> Attribute -> Store History."""
        history = self.get_history(session_id)

        # 1. No repository loaded guardrail
        if not repo_index or not repo_index.files:
            unloaded_answer = (
                "⚠️ **No repository loaded yet.** Please upload or clone a repository first "
                "before asking questions."
            )
            return ChatResponse(
                answer=unloaded_answer,
                sources=[],
                relevant_files=[],
                dependency_paths=[],
                retrieval_metadata={
                    "confidence": 0.0,
                    "has_sufficient_context": False,
                    "files_count": 0,
                    "tokens_used": 0,
                    "error": "no_repository_loaded"
                }
            )

        # 2. Execute Context Retrieval Engine (M3)
        retrieved_payload = retrieval_engine.process_query(
            repo_index=repo_index,
            query=question,
            max_files=8,
            expand_dependencies=True
        )

        relevant_files = [sf.relative_path for sf in retrieved_payload.scored_files if not sf.is_expanded_dependency]
        dependency_paths = [sf.relative_path for sf in retrieved_payload.scored_files if sf.is_expanded_dependency]

        # 3. Evaluate context sufficiency
        max_score = max([sf.total_score for sf in retrieved_payload.scored_files], default=0.0)
        has_sufficient_context = max_score >= 1.5

        # Check for speculative questions (e.g. why Redis/MongoDB/Docker was chosen when not in repo)
        speculative_triggers = ["why does this company", "why did they choose", "why was", "who decided", "why is"]
        is_speculative = any(trig in question.lower() for trig in speculative_triggers)

        if is_speculative and max_score < 5.0:
            has_sufficient_context = False

        # 4. Generate Answer via Groq AI
        if not has_sufficient_context:
            # Fallback when retrieval context is insufficient or question is speculative
            answer_text = (
                f"I couldn't determine the answer from the repository context available. "
                f"I searched the repository index for '{question}', but there isn't enough documentation "
                f"or code evidence in the codebase to answer this question accurately."
            )
        else:
            answer_text = groq_service.chat_with_repository(
                question=question,
                repo_context=retrieved_payload.formatted_context,
                history=history
            )

        # Handle malformed or error string from Groq
        if not answer_text or not isinstance(answer_text, str):
            answer_text = "⚠️ Unable to generate response due to an internal LLM formatting issue."

        # 5. Extract Formal Source Attributions
        sources = self.extract_source_attributions(retrieved_payload, answer_text, repo_index)

        # 6. Store turn in multi-turn history
        self.add_turn(session_id, "user", question)
        self.add_turn(session_id, "assistant", answer_text)

        confidence = round(min(1.0, max_score / 15.0), 2)

        return ChatResponse(
            answer=answer_text,
            sources=sources,
            relevant_files=relevant_files,
            dependency_paths=dependency_paths,
            retrieval_metadata={
                "confidence": confidence,
                "has_sufficient_context": has_sufficient_context,
                "files_count": len(retrieved_payload.scored_files),
                "estimated_tokens": retrieved_payload.estimated_tokens,
                "query_tokens": retrieved_payload.query_analysis.normalized_terms
            }
        )

conversation_service = ConversationService()
