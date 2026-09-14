import os
import re
from typing import List, Dict, Set, Tuple, Optional, Any
from models.repository_index import (
    RepositoryIndex, FileInfo, Symbol, Dependency,
    IssueAnalysis, ContributionCandidate, ImpactAnalysis, TestImpact, ConfigImpact, ContributionPlan
)
from services.retrieval_service import retrieval_engine, STOP_WORDS
from services.groq_service import groq_service, GROUNDED_SYSTEM_PROMPT

ACTION_VERBS = {
    "add", "create", "support", "configure", "update", "fix", "refactor",
    "implement", "extend", "enable", "allow", "reuse", "remove", "integrate", "build"
}

TECH_KEYWORDS = {
    "postgresql", "postgres", "mysql", "sqlite", "redis", "fastapi", "flask", "express",
    "node", "python", "typescript", "javascript", "docker", "git", "jwt", "orm",
    "pydantic", "groq", "ast", "html", "css", "json", "yaml", "yml"
}

DOMAIN_KEYWORDS = {
    "database": ["db", "connection", "sql", "orm", "pool", "pooling", "schema", "model"],
    "configuration": ["config", "env", "settings", "variable", "environment", "setup"],
    "authentication": ["auth", "login", "jwt", "token", "session", "user", "security"],
    "api": ["endpoint", "route", "router", "server", "http", "rest", "fastapi"],
    "retrieval": ["search", "query", "retriever", "context", "relevance", "score"],
    "graph": ["dependency", "nodes", "edges", "cycle", "circular", "degree"],
    "summary": ["summarize", "guide", "onboarding", "overview"]
}

CONFIG_FILENAMES = {
    "config.py", "settings.py", ".env", ".env.example", "application.yml",
    "application.yaml", "config.json", "package.json", "pyproject.toml", "setup.py"
}

class IssueAnalyzer:
    def analyze(self, title: str, description: str = "") -> IssueAnalysis:
        """Deterministically extracts technical keywords, technologies, actions, and domains from issue title & description."""
        combined_text = f"{title} {description}".lower()
        clean_text = re.sub(r'[^a-z0-9_.\-\s]', ' ', combined_text)
        tokens = [t.strip() for t in clean_text.split() if t.strip()]

        keywords = []
        actions = []
        technologies = []
        domains = set()

        for t in tokens:
            if t in ACTION_VERBS and t not in actions:
                actions.append(t)
            elif t in TECH_KEYWORDS and t not in technologies:
                technologies.append(t)
            elif t not in STOP_WORDS and len(t) > 2 and t not in keywords:
                keywords.append(t)

        for domain, domain_terms in DOMAIN_KEYWORDS.items():
            if any(term in combined_text for term in [domain] + domain_terms):
                domains.add(domain)

        # Build concise summary
        tech_str = f" ({', '.join(technologies)})" if technologies else ""
        act_str = f"{actions[0].capitalize()} " if actions else "Implement "
        summary = f"{act_str}{title.strip()}{tech_str}"

        return IssueAnalysis(
            title=title.strip(),
            summary=summary,
            keywords=keywords[:15],
            technologies=technologies,
            actions=actions,
            domains=sorted(list(domains))
        )

class ContributionRanker:
    def rank_candidates(self, repo_index: RepositoryIndex, issue_analysis: IssueAnalysis, max_files: int = 10) -> List[ContributionCandidate]:
        """Ranks candidate repository files for an issue by extending M3 retrieval scores with contribution signals."""
        query_str = f"{issue_analysis.title} {' '.join(issue_analysis.keywords[:6])}"
        retrieved_payload = retrieval_engine.process_query(
            repo_index=repo_index,
            query=query_str,
            max_files=max_files * 2,
            expand_dependencies=True
        )

        candidates: List[ContributionCandidate] = []
        all_issue_terms = set(issue_analysis.keywords + issue_analysis.technologies + issue_analysis.actions)

        for sf in retrieved_payload.scored_files:
            file_path_lower = sf.relative_path.lower()
            file_name_lower = sf.file_name.lower()
            
            contrib_score = sf.total_score
            explanations = [f"Base M3 retrieval score: +{sf.total_score}"]

            # Issue Term Direct Match
            direct_matches = [t for t in all_issue_terms if t in file_name_lower or t in file_path_lower]
            if direct_matches:
                contrib_score += 4.0
                explanations.append(f"Issue term filename match ({', '.join(direct_matches[:3])}): +4.0")

            # Symbol match bonus
            if sf.matched_symbols:
                contrib_score += 3.0
                explanations.append(f"Implicated symbols match ({', '.join(sf.matched_symbols[:2])}): +3.0")

            # Core module bonus
            if sf.module_category == "core":
                contrib_score += 1.0
                explanations.append("Core foundation module: +1.0")
            elif sf.module_category == "entry_point":
                contrib_score += 1.0
                explanations.append("Entry-point module: +1.0")

            candidates.append(ContributionCandidate(
                file_path=sf.relative_path,
                file_name=sf.file_name,
                base_retrieval_score=sf.total_score,
                contribution_score=round(contrib_score, 2),
                module_category=sf.module_category,
                matched_symbols=sf.matched_symbols,
                scoring_explanations=explanations
            ))

        candidates.sort(key=lambda c: c.contribution_score, reverse=True)
        return candidates[:max_files]

class ChangeImpactAnalyzer:
    def analyze_impact(self, repo_index: RepositoryIndex, candidate_files: List[str], max_depth: int = 2) -> ImpactAnalysis:
        """Determines directly affected files, downstream dependants, upstream dependencies, and dependency chains."""
        directly_affected = candidate_files[:3] # Top 3 candidates treated as directly affected
        downstream_set: Set[str] = set()
        upstream_set: Set[str] = set()
        chains: List[str] = []

        file_info_map = {f.relative_path: f for f in repo_index.files}

        # Find downstream dependants (files importing directly affected files)
        for primary in directly_affected:
            for candidate_rel, candidate_info in file_info_map.items():
                if candidate_rel not in directly_affected:
                    for dep in candidate_info.dependencies:
                        target_rel = dep.resolved_path or dep.target_path
                        if target_rel == primary:
                            downstream_set.add(candidate_rel)
                            chains.append(f"{primary} ➔ {candidate_rel}")

            # Find upstream dependencies (files imported by primary)
            primary_info = file_info_map.get(primary)
            if primary_info:
                for dep in primary_info.dependencies:
                    target_rel = dep.resolved_path or dep.target_path
                    if dep.is_internal and target_rel in file_info_map and target_rel not in directly_affected:
                        upstream_set.add(target_rel)
                        chains.append(f"{primary} depends on ➔ {target_rel}")

        return ImpactAnalysis(
            directly_affected=directly_affected,
            downstream_impact=sorted(list(downstream_set)),
            upstream_context=sorted(list(upstream_set)),
            dependency_chains=sorted(list(set(chains)))[:8]
        )

class TestDetector:
    def detect_tests(self, repo_index: RepositoryIndex, candidate_files: List[str]) -> TestImpact:
        """Identifies directly related and potentially related test files using conventions and import links."""
        directly_related = set()
        potentially_related = set()
        evidence = []

        all_test_files = [
            f.relative_path for f in repo_index.files
            if f.relative_path.startswith("tests/") or "test_" in f.file_name.lower() or "_test" in f.file_name.lower() or ".spec." in f.file_name.lower()
        ]

        file_info_map = {f.relative_path: f for f in repo_index.files}

        for candidate in candidate_files:
            cand_base = os.path.splitext(os.path.basename(candidate))[0].lower()
            
            for tf in all_test_files:
                tf_base = os.path.splitext(os.path.basename(tf))[0].lower()
                
                # Direct naming convention match (e.g. repo_service.py -> test_repo_service.py or test_m1_core.py)
                if cand_base in tf_base or tf_base.replace("test_", "") in cand_base:
                    directly_related.add(tf)
                    evidence.append(f"Test file '{tf}' matches candidate module '{candidate}' name convention.")
                else:
                    # Check if test file imports candidate
                    tf_info = file_info_map.get(tf)
                    if tf_info:
                        for dep in tf_info.dependencies:
                            target_rel = dep.resolved_path or dep.target_path
                            if target_rel == candidate:
                                directly_related.add(tf)
                                evidence.append(f"Test file '{tf}' directly imports candidate '{candidate}'.")
                                break
                    
                    if tf not in directly_related:
                        potentially_related.add(tf)

        return TestImpact(
            directly_related_tests=sorted(list(directly_related)),
            potentially_related_tests=sorted(list(potentially_related))[:5],
            evidence=evidence
        )

class ConfigDetector:
    def detect_config(self, repo_index: RepositoryIndex, issue_analysis: IssueAnalysis) -> ConfigImpact:
        """Identifies project configuration files related to issue requirements."""
        config_files = []
        evidence = []

        for f in repo_index.files:
            base_name = f.file_name.lower()
            if base_name in CONFIG_FILENAMES or "config" in base_name or "setting" in base_name or base_name.endswith(".env"):
                config_files.append(f.relative_path)
                
                # Check for matching terms inside config file
                if any(domain in issue_analysis.domains for domain in ["configuration", "database", "auth"]):
                    evidence.append(f"Configuration file '{f.relative_path}' handles environment/system parameters for {', '.join(issue_analysis.domains)}.")

        return ConfigImpact(
            configuration_files=sorted(list(set(config_files))),
            evidence=evidence
        )

class ContributionService:
    def __init__(self):
        self.issue_analyzer = IssueAnalyzer()
        self.ranker = ContributionRanker()
        self.impact_analyzer = ChangeImpactAnalyzer()
        self.test_detector = TestDetector()
        self.config_detector = ConfigDetector()

    def calculate_confidence(self, candidates: List[ContributionCandidate], impact: ImpactAnalysis, tests: TestImpact, configs: ConfigImpact) -> Tuple[str, List[str]]:
        """Calculates deterministic confidence level (High, Medium, Low) and supporting evidence."""
        evidence = []
        max_score = candidates[0].contribution_score if candidates else 0.0

        score_point = max_score >= 5.0
        impact_point = len(impact.downstream_impact) > 0 or len(impact.upstream_context) > 0
        test_point = len(tests.directly_related_tests) > 0
        config_point = len(configs.configuration_files) > 0

        if candidates:
            evidence.append(f"Top candidate module '{candidates[0].file_path}' scored {candidates[0].contribution_score} points.")
        if impact.dependency_chains:
            evidence.append(f"Dependency impact confirmed across {len(impact.dependency_chains)} path chain(s).")
        if tests.directly_related_tests:
            evidence.append(f"Direct test coverage identified: {', '.join(tests.directly_related_tests[:2])}.")
        if configs.configuration_files:
            evidence.append(f"Configuration file(s) implicated: {', '.join(configs.configuration_files[:2])}.")

        total_points = sum([score_point, impact_point, test_point, config_point])

        if max_score >= 7.0 and total_points >= 3:
            confidence = "High"
        elif max_score >= 3.0 or total_points >= 2:
            confidence = "Medium"
        else:
            confidence = "Low"

        return confidence, evidence

    def generate_plan(self, title: str, description: str = "", session_id: str = "default", repo_index: Optional[RepositoryIndex] = None, max_files: int = 10, max_impact_depth: int = 2) -> ContributionPlan:
        """Main Issue-to-Code Contribution Intelligence Pipeline."""
        # 1. Unloaded repository handling
        if not repo_index or not repo_index.files:
            empty_analysis = IssueAnalysis(
                title=title,
                summary=title,
                keywords=[],
                technologies=[],
                actions=[],
                domains=[]
            )
            return ContributionPlan(
                repo_name="None",
                issue_analysis=empty_analysis,
                relevant_files=[],
                relevant_symbols=[],
                directly_affected_files=[],
                impacted_files=[],
                configuration_files=[],
                test_files=[],
                dependency_paths=[],
                recommended_changes=[],
                risks=[],
                confidence="Low",
                evidence=["No active repository session loaded."],
                plan_narrative="⚠️ **No repository loaded yet.** Please analyze a repository before executing contribution intelligence."
            )

        # 2. Analyze Issue
        issue_analysis = self.issue_analyzer.analyze(title, description)

        # 3. M3 Retrieval & Contribution Ranking
        candidates = self.ranker.rank_candidates(repo_index, issue_analysis, max_files=max_files)
        candidate_paths = [c.file_path for c in candidates]

        # 4. Change Impact Analysis (M2 Dependency Graph)
        impact = self.impact_analyzer.analyze_impact(repo_index, candidate_paths, max_depth=max_impact_depth)

        # 5. Test & Config Detection
        tests = self.test_detector.detect_tests(repo_index, candidate_paths)
        configs = self.config_detector.detect_config(repo_index, issue_analysis)

        # 6. Extract Implicated Symbols
        relevant_symbols = []
        for c in candidates:
            for sym in c.matched_symbols:
                if sym not in relevant_symbols:
                    relevant_symbols.append(sym)

        # 7. Confidence Calculation
        confidence, evidence = self.calculate_confidence(candidates, impact, tests, configs)

        # 8. Grounded Recommendations & Risk Analysis
        recommended_changes = []
        if impact.directly_affected:
            recommended_changes.append(f"Extend/modify primary target module `{impact.directly_affected[0]}` to support requirement.")
        if configs.configuration_files:
            recommended_changes.append(f"Update configuration parameters in `{configs.configuration_files[0]}` if environment variables are needed.")
        if impact.downstream_impact:
            recommended_changes.append(f"Verify downstream consuming modules ({', '.join(impact.downstream_impact[:2])}) compatibility.")
        if tests.directly_related_tests:
            recommended_changes.append(f"Run and add verification unit tests in `{tests.directly_related_tests[0]}`.")

        risks = []
        if impact.downstream_impact:
            risks.append(f"Modification to `{impact.directly_affected[0] if impact.directly_affected else 'core module'}` affects {len(impact.downstream_impact)} dependant module(s).")
        if not tests.directly_related_tests:
            risks.append("No direct unit test suite detected for target module; regression testing is required.")

        # 9. Format Grounded Markdown Narrative Report
        narrative_lines = []
        narrative_lines.append("# 🎯 Issue-to-Code Contribution Intelligence Report\n")
        narrative_lines.append(f"**Issue Title**: {title}")
        narrative_lines.append(f"**Summary**: {issue_analysis.summary}")
        narrative_lines.append(f"**Confidence**: **{confidence.upper()}**\n")

        narrative_lines.append("## 📂 Relevant Modules & Symbols")
        for idx, c in enumerate(candidates[:5], start=1):
            syms_str = f" (Symbols: {', '.join(c.matched_symbols[:3])})" if c.matched_symbols else ""
            narrative_lines.append(f"{idx}. `{c.file_path}` — Score: {c.contribution_score}{syms_str}")
        narrative_lines.append("")

        narrative_lines.append("## 🛠️ Directly Affected Files (Requires Changes)")
        for f in impact.directly_affected:
            narrative_lines.append(f"- `{f}`")
        narrative_lines.append("")

        if impact.downstream_impact:
            narrative_lines.append("## ⚡ Downstream Impacted Modules")
            for f in impact.downstream_impact[:5]:
                narrative_lines.append(f"- `{f}`")
            narrative_lines.append("")

        if impact.dependency_chains:
            narrative_lines.append("## 🔗 Dependency Impact Chains")
            for chain in impact.dependency_chains[:4]:
                narrative_lines.append(f"- `{chain}`")
            narrative_lines.append("")

        if configs.configuration_files:
            narrative_lines.append("## ⚙️ Configuration Files")
            for cfg in configs.configuration_files[:3]:
                narrative_lines.append(f"- `{cfg}`")
            narrative_lines.append("")

        if tests.directly_related_tests or tests.potentially_related_tests:
            narrative_lines.append("## 🧪 Verification & Test Files")
            for t in (tests.directly_related_tests + tests.potentially_related_tests)[:4]:
                narrative_lines.append(f"- `{t}`")
            narrative_lines.append("")

        narrative_lines.append("## 📋 Recommended Implementation Steps")
        for idx, rec in enumerate(recommended_changes, start=1):
            narrative_lines.append(f"{idx}. {rec}")
        narrative_lines.append("")

        if risks:
            narrative_lines.append("## ⚠️ Risks & Considerations")
            for r in risks:
                narrative_lines.append(f"- {r}")
            narrative_lines.append("")

        plan_narrative = "\n".join(narrative_lines)

        return ContributionPlan(
            repo_name=repo_index.repo_name,
            issue_analysis=issue_analysis,
            relevant_files=candidates,
            relevant_symbols=relevant_symbols[:8],
            directly_affected_files=impact.directly_affected,
            impacted_files=impact.downstream_impact,
            configuration_files=configs.configuration_files,
            test_files=tests.directly_related_tests + tests.potentially_related_tests,
            dependency_paths=impact.dependency_chains,
            recommended_changes=recommended_changes,
            risks=risks,
            confidence=confidence,
            evidence=evidence,
            plan_narrative=plan_narrative
        )

contribution_service = ContributionService()
