document.addEventListener("DOMContentLoaded", () => {
    // Application State
    let currentSession = null;
    let selectedFilePath = null;
    let networkGraph = null;
    let currentInspectorNode = null;
    let auditReportCache = null;

    // DOM Elements - Shell & Navigation
    const repoSwitcherBtn = document.getElementById("repo-switcher-btn");
    const currentRepoLabel = document.getElementById("current-repo-label");
    const quickRescanBtn = document.getElementById("quick-rescan-btn");
    const groqStatus = document.getElementById("groq-status");
    const navItems = document.querySelectorAll(".nav-item");
    const tabPanes = document.querySelectorAll(".tab-pane");
    const navFileCount = document.getElementById("nav-file-count");
    const navContribCount = document.getElementById("nav-contrib-count");
    const footerSessionName = document.getElementById("footer-session-name");
    const footerIndexedTime = document.getElementById("footer-indexed-time");

    // Mobile Navigation Elements
    const mobileNavToggle = document.getElementById("mobile-nav-toggle");
    const appSidebar = document.getElementById("app-sidebar");
    const sidebarBackdrop = document.getElementById("sidebar-backdrop");
    const sidebarCloseBtn = document.getElementById("sidebar-close-btn");

    // Modals
    const repoModal = document.getElementById("repo-modal");
    const closeRepoModalBtn = document.getElementById("close-repo-modal-btn");
    const cancelRepoModalBtn = document.getElementById("cancel-repo-modal-btn");
    const repoForm = document.getElementById("repo-form");
    const repoInput = document.getElementById("repo-input");
    const analyzeBtn = document.getElementById("analyze-btn");
    const repoAnalyzeStatus = document.getElementById("repo-analyze-status");

    const guideModal = document.getElementById("guide-modal");
    const openGuideModalBtn = document.getElementById("open-guide-modal-btn");
    const closeGuideModalBtn = document.getElementById("close-guide-modal-btn");
    const generateGuideBtn = document.getElementById("generate-guide-btn");
    const guideContent = document.getElementById("guide-content");
    const overviewGuideBtn = document.getElementById("overview-guide-btn");
    const overviewRescanBtn = document.getElementById("overview-rescan-btn");

    // Overview Elements
    const statFilesVal = document.getElementById("stat-files-val");
    const statLinesMeta = document.getElementById("stat-lines-meta");
    const statModulesVal = document.getElementById("stat-modules-val");
    const statModulesMeta = document.getElementById("stat-modules-meta");
    const statEntryVal = document.getElementById("stat-entry-val");
    const statEntryMeta = document.getElementById("stat-entry-meta");
    const statAuditVal = document.getElementById("stat-audit-val");
    const statAuditMeta = document.getElementById("stat-audit-meta");
    const overviewArchType = document.getElementById("overview-arch-type");
    const overviewArchNarrative = document.getElementById("overview-arch-narrative");
    const refreshNarrativeBtn = document.getElementById("refresh-narrative-btn");
    const viewGraphJumpBtn = document.getElementById("view-graph-jump-btn");
    const overviewCoreModulesTbody = document.getElementById("overview-core-modules-tbody");
    const overviewEntryPointsList = document.getElementById("overview-entry-points-list");
    const overviewActiveFilesTbody = document.getElementById("overview-active-files-tbody");
    const overviewLangBar = document.getElementById("overview-lang-bar");
    const overviewLangLegend = document.getElementById("overview-lang-legend");
    const overviewLangCount = document.getElementById("overview-lang-count");
    const overviewFindingsBadge = document.getElementById("overview-findings-badge");
    const overviewFindingsBody = document.getElementById("overview-findings-body");

    // Repository Elements
    const repoSearch = document.getElementById("repo-search");
    const treeContainer = document.getElementById("tree-container");
    const fileCount = document.getElementById("file-count");
    const currentFilename = document.getElementById("current-filename");
    const currentFileLines = document.getElementById("current-file-lines");
    const copyCodeBtn = document.getElementById("copy-code-btn");
    const codeContent = document.getElementById("code-content");
    const summarizeBtn = document.getElementById("summarize-btn");
    const summaryText = document.getElementById("summary-text");
    const fileSymbolsList = document.getElementById("file-symbols-list");
    const fileDepsList = document.getElementById("file-deps-list");

    // Architecture Elements
    const refreshGraphBtn = document.getElementById("refresh-graph-btn");
    const graphFilterSelect = document.getElementById("graph-filter-select");
    const graphLayoutSelect = document.getElementById("graph-layout-select");
    const graphExternalChk = document.getElementById("graph-external-chk");
    const nodeInspector = document.getElementById("node-inspector");
    const closeInspectorBtn = document.getElementById("close-inspector-btn");
    const inspectorNodeTitle = document.getElementById("inspector-node-title");
    const inspectorNodeType = document.getElementById("inspector-node-type");
    const inspectorInDegree = document.getElementById("inspector-in-degree");
    const inspectorOutDegree = document.getElementById("inspector-out-degree");
    const inspectorScore = document.getElementById("inspector-score");
    const inspectorDepsList = document.getElementById("inspector-deps-list");
    const inspectorSymbolsList = document.getElementById("inspector-symbols-list");
    const jumpCodeBtn = document.getElementById("jump-code-btn");
    const archModulesTbody = document.getElementById("arch-modules-tbody");
    const archCyclesList = document.getElementById("arch-cycles-list");
    const archCyclesCount = document.getElementById("arch-cycles-count");

    // AI Assistant Elements
    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("chat-input");
    const chatMessages = document.getElementById("chat-messages");
    const clearChatBtn = document.getElementById("clear-chat-btn");
    const chatModelTag = document.getElementById("chat-model-tag");

    // Contribution Elements
    const auditRepoBtn = document.getElementById("audit-repo-btn");
    const auditOpportunitiesContainer = document.getElementById("audit-opportunities-container");
    const contribForm = document.getElementById("contribution-form");
    const issueTitle = document.getElementById("issue-title");
    const issueDesc = document.getElementById("issue-desc");
    const analyzeContribBtn = document.getElementById("analyze-contrib-btn");
    const contributionContent = document.getElementById("contribution-content");

    // Agent Elements
    const agentForm = document.getElementById("agent-form");
    const agentInput = document.getElementById("agent-input");
    const agentExploreBtn = document.getElementById("agent-explore-btn");
    const agentTrace = document.getElementById("agent-trace");
    const agentAnswer = document.getElementById("agent-answer");
    const agentFiles = document.getElementById("agent-files");
    const agentSources = document.getElementById("agent-sources");
    const agentSummary = document.getElementById("agent-summary");
    const agentStepCount = document.getElementById("agent-step-count");

    // PR Review Elements
    const prForm = document.getElementById("pr-form");
    const prTitleInput = document.getElementById("pr-title-input");
    const prFileInput = document.getElementById("pr-file-input");
    const prDiffInput = document.getElementById("pr-diff-input");
    const prAnalyzeBtn = document.getElementById("pr-analyze-btn");
    const prReviewBtn = document.getElementById("pr-review-btn");
    const prResultsContainer = document.getElementById("pr-results-container");
    const prEmptyState = document.getElementById("pr-empty-state");
    const prMetricsBar = document.getElementById("pr-metrics-bar");
    const prSummaries = document.getElementById("pr-summaries");
    const loadFeatureBtn = document.getElementById("pr-load-feature-btn");
    const loadVulnBtn = document.getElementById("pr-load-vuln-btn");
    const loadArchBtn = document.getElementById("pr-load-arch-btn");

    // Helper: Escape HTML
    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Helper: Toast Notifications
    function showToast(message, type = "info", title = null, duration = 4000) {
        const container = document.getElementById("toast-container");
        if (!container) return;

        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;

        let icon = "fa-circle-info";
        if (type === "success") icon = "fa-circle-check";
        else if (type === "error") icon = "fa-circle-exclamation";
        else if (type === "warning") icon = "fa-triangle-exclamation";

        toast.innerHTML = `
            <i class="fa-solid ${icon} toast-icon"></i>
            <div class="toast-body">
                ${title ? `<div class="toast-title">${escapeHtml(title)}</div>` : ""}
                <div class="toast-message">${escapeHtml(message)}</div>
            </div>
            <button type="button" class="toast-close" aria-label="Dismiss">&times;</button>
        `;

        const closeBtn = toast.querySelector(".toast-close");
        const dismiss = () => {
            toast.classList.remove("show");
            setTimeout(() => { if (toast.parentNode) toast.remove(); }, 250);
        };
        if (closeBtn) closeBtn.addEventListener("click", dismiss);

        container.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add("show"));

        if (duration > 0) {
            setTimeout(dismiss, duration);
        }
    }

    // --- Tab Navigation Switcher ---
    function switchTab(tabId) {
        // Automatically close mobile sidebar drawer on navigation
        if (appSidebar) appSidebar.classList.remove("open");
        if (sidebarBackdrop) sidebarBackdrop.classList.remove("active");

        navItems.forEach(btn => {
            if (btn.dataset.tab === tabId) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
        });

        tabPanes.forEach(pane => {
            if (pane.id === tabId) {
                pane.classList.add("active");
            } else {
                pane.classList.remove("active");
            }
        });

        if (tabId === "architecture-tab") {
            setTimeout(() => {
                if (networkGraph) {
                    networkGraph.setSize("100%", "100%");
                    networkGraph.redraw();
                    networkGraph.fit();
                } else {
                    renderDependencyGraph();
                }
            }, 60);
        } else if (tabId === "overview-tab" && currentSession) {
            populateOverview(currentSession);
        }
    }

    navItems.forEach(btn => {
        btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    });

    // Mobile Sidebar Drawer Toggles
    if (mobileNavToggle) {
        mobileNavToggle.addEventListener("click", () => {
            if (appSidebar) appSidebar.classList.toggle("open");
            if (sidebarBackdrop) sidebarBackdrop.classList.toggle("active");
        });
    }
    if (sidebarBackdrop) {
        sidebarBackdrop.addEventListener("click", () => {
            if (appSidebar) appSidebar.classList.remove("open");
            sidebarBackdrop.classList.remove("active");
        });
    }
    if (sidebarCloseBtn) {
        sidebarCloseBtn.addEventListener("click", () => {
            if (appSidebar) appSidebar.classList.remove("open");
            if (sidebarBackdrop) sidebarBackdrop.classList.remove("active");
        });
    }

    if (viewGraphJumpBtn) {
        viewGraphJumpBtn.addEventListener("click", () => switchTab("architecture-tab"));
    }

    // --- Modal Handlers ---
    function openRepoModal() {
        if (repoModal) repoModal.classList.add("open");
    }
    function closeRepoModal() {
        if (repoModal) repoModal.classList.remove("open");
    }
    if (repoSwitcherBtn) repoSwitcherBtn.addEventListener("click", openRepoModal);
    if (quickRescanBtn) quickRescanBtn.addEventListener("click", openRepoModal);
    if (overviewRescanBtn) overviewRescanBtn.addEventListener("click", openRepoModal);
    if (closeRepoModalBtn) closeRepoModalBtn.addEventListener("click", closeRepoModal);
    if (cancelRepoModalBtn) cancelRepoModalBtn.addEventListener("click", closeRepoModal);

    function openGuideModal() {
        if (guideModal) guideModal.classList.add("open");
    }
    function closeGuideModal() {
        if (guideModal) guideModal.classList.remove("open");
    }
    if (openGuideModalBtn) openGuideModalBtn.addEventListener("click", openGuideModal);
    if (overviewGuideBtn) overviewGuideBtn.addEventListener("click", openGuideModal);
    if (closeGuideModalBtn) closeGuideModalBtn.addEventListener("click", closeGuideModal);

    // Close modals on clicking backdrop outside dialog
    [repoModal, guideModal].forEach(modal => {
        if (modal) {
            modal.addEventListener("click", (e) => {
                if (e.target === modal) modal.classList.remove("open");
            });
        }
    });

    // Sample Repo buttons in Switcher Modal
    document.querySelectorAll(".sample-repo-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            if (repoInput) repoInput.value = btn.dataset.url;
        });
    });

    // --- Backend Health Check ---
    async function checkHealth() {
        try {
            const res = await fetch("/api/health");
            const data = await res.json();
            if (data.groq_configured) {
                groqStatus.innerHTML = `<span class="status-dot green"></span> <span>${data.groq_model || 'Groq AI Ready'}</span>`;
                if (chatModelTag) chatModelTag.textContent = data.groq_model || "Groq LLaMA 3.3";
            } else {
                groqStatus.innerHTML = `<span class="status-dot amber"></span> <span>Groq Key Needed</span>`;
            }
        } catch (err) {
            groqStatus.innerHTML = `<span class="status-dot red"></span> <span>Backend Offline</span>`;
        }
    }
    checkHealth();

    // --- Auto-Load / Restore Session on Startup ---
    async function autoLoadSession() {
        try {
            const res = await fetch("/api/index?session_id=default");
            if (res.ok) {
                const repoIndex = await res.json();
                applyRepositorySession(repoIndex);
            } else {
                // Index default requests repository if nothing in cache
                const target = repoInput ? repoInput.value.trim() : "https://github.com/psf/requests";
                if (target) {
                    analyzeRepository(target);
                }
            }
        } catch (err) {
            console.warn("Auto-load session notice:", err.message);
        }
    }
    autoLoadSession();

    // --- Analyze / Clone Repository ---
    async function analyzeRepository(targetUrlOrPath) {
        if (!targetUrlOrPath) return;

        if (analyzeBtn) {
            analyzeBtn.disabled = true;
            analyzeBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Indexing AST...`;
        }
        if (repoAnalyzeStatus) {
            repoAnalyzeStatus.innerHTML = `<span style="color: var(--accent-primary);"><i class="fa-solid fa-spinner fa-spin"></i> Parsing AST, computing activity scores, and extracting graph...</span>`;
        }

        try {
            const res = await fetch("/api/clone", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url_or_path: targetUrlOrPath })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Failed to analyze repository.");
            }

            const repoIndex = await res.json();
            applyRepositorySession(repoIndex);
            closeRepoModal();

            if (repoAnalyzeStatus) repoAnalyzeStatus.innerHTML = "";
            showToast(`Repository "${repoIndex.repo_name}" successfully indexed.`, "success", "Repository Ready");
        } catch (err) {
            if (repoAnalyzeStatus) {
                repoAnalyzeStatus.innerHTML = `<span style="color: var(--color-danger);"><i class="fa-solid fa-triangle-exclamation"></i> ${escapeHtml(err.message)}</span>`;
            }
            showToast(err.message, "error", "Repository Analysis Failed");
        } finally {
            if (analyzeBtn) {
                analyzeBtn.disabled = false;
                analyzeBtn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Analyze Repository`;
            }
        }
    }

    if (repoForm) {
        repoForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const target = repoInput ? repoInput.value.trim() : "";
            analyzeRepository(target);
        });
    }

    // --- Apply Active Repository Session Across All Views ---
    function applyRepositorySession(repoIndex) {
        currentSession = repoIndex;

        // Shell Headers & Badges
        const repoName = repoIndex.repo_name || "repository";
        if (currentRepoLabel) currentRepoLabel.textContent = repoName;
        if (footerSessionName) footerSessionName.textContent = repoName;
        if (footerIndexedTime) {
            footerIndexedTime.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
        if (navFileCount) navFileCount.textContent = repoIndex.total_files || 0;
        if (fileCount) fileCount.textContent = `${repoIndex.total_files} files`;

        // 1. Populate Overview View
        populateOverview(repoIndex);

        // 2. Populate Repository View File Tree
        renderFilesIndex(repoIndex.files);
        if (repoIndex.files && repoIndex.files.length > 0) {
            const topFile = repoIndex.files.find(f => f.is_entry_point) || repoIndex.files[0];
            loadFileContent(topFile.full_path, topFile.relative_path);
        }

        // 3. Populate Architecture Modules Table & Cycles
        populateArchitectureTables(repoIndex);

        // 4. Trigger Background Audit for Badges & Findings
        fetchBackgroundAudit();
    }

    // =========================================================================
    // PAGE 1: OVERVIEW TAB LOGIC
    // =========================================================================
    function populateOverview(repoIndex) {
        if (!repoIndex) return;

        // Top 4 Stat Cards
        if (statFilesVal) statFilesVal.textContent = (repoIndex.total_files || 0).toLocaleString();
        if (statLinesMeta) statLinesMeta.textContent = `${(repoIndex.total_lines || 0).toLocaleString()} total source lines`;

        const moduleCounts = repoIndex.module_counts || {};
        const totalModules = Object.values(moduleCounts).reduce((a, b) => a + b, 0);
        if (statModulesVal) statModulesVal.textContent = totalModules.toLocaleString() || repoIndex.total_files;
        if (statModulesMeta) {
            const coreCount = moduleCounts.core || 0;
            const utilCount = moduleCounts.utility || 0;
            statModulesMeta.textContent = `${coreCount} core · ${utilCount} utilities`;
        }

        const entryCount = (repoIndex.entry_points || []).length;
        if (statEntryVal) statEntryVal.textContent = entryCount;
        if (statEntryMeta) statEntryMeta.textContent = entryCount > 0 ? "Application entry points detected" : "Standard library structure";

        // Architecture Narrative Card
        const arch = repoIndex.architecture_summary;
        if (overviewArchType) {
            overviewArchType.textContent = arch ? arch.architecture_type : "Modular API";
        }
        if (overviewArchNarrative) {
            if (arch && arch.overview_narrative) {
                overviewArchNarrative.innerHTML = marked.parse(arch.overview_narrative);
            } else {
                overviewArchNarrative.innerHTML = `
                    <p>The codebase is structured as a <strong>${arch ? arch.architecture_type : 'Modular API'}</strong> architecture comprising ${repoIndex.total_files} analyzed files across ${Object.keys(repoIndex.languages_breakdown || {}).length} language groups.</p>
                    <p>Central modules handle core orchestration with high in-degree connectivity, supported by shared utilities and isolated domain components.</p>
                `;
            }
        }

        // Core Architecture Modules Table
        if (overviewCoreModulesTbody) {
            const sortedByInDegree = [...(repoIndex.files || [])].sort((a, b) => b.in_degree - a.in_degree).slice(0, 6);
            if (sortedByInDegree.length === 0) {
                overviewCoreModulesTbody.innerHTML = `<tr><td colspan="5" class="empty-state">No core modules identified.</td></tr>`;
            } else {
                overviewCoreModulesTbody.innerHTML = sortedByInDegree.map(file => `
                    <tr>
                        <td>
                            <strong style="font-family: var(--font-mono); font-size: 11px;">${escapeHtml(file.relative_path)}</strong>
                            ${file.is_entry_point ? '<span class="badge badge-green" style="font-size: 9px; margin-left: 4px;">🚀 Entry</span>' : ''}
                        </td>
                        <td><span class="badge badge-blue">${file.in_degree || 0}</span></td>
                        <td><span class="badge">${file.out_degree || 0}</span></td>
                        <td><span class="badge" style="text-transform: capitalize;">${escapeHtml(file.module_category || 'standard')}</span></td>
                        <td>
                            <button type="button" class="btn btn-secondary btn-sm jump-file-btn" data-fullpath="${escapeHtml(file.full_path)}" data-relpath="${escapeHtml(file.relative_path)}">
                                <i class="fa-regular fa-file-code"></i> View
                            </button>
                        </td>
                    </tr>
                `).join("");

                overviewCoreModulesTbody.querySelectorAll(".jump-file-btn").forEach(btn => {
                    btn.addEventListener("click", () => {
                        switchTab("repository-tab");
                        loadFileContent(btn.dataset.fullpath, btn.dataset.relpath);
                    });
                });
            }
        }

        // Detected Entry Points List
        if (overviewEntryPointsList) {
            const entryPoints = repoIndex.entry_points || [];
            if (entryPoints.length === 0) {
                overviewEntryPointsList.innerHTML = `<span class="text-muted" style="font-size: 12px;">No standalone entry points detected.</span>`;
            } else {
                overviewEntryPointsList.innerHTML = entryPoints.map(ep => `
                    <button type="button" class="citation-chip jump-entry-btn" data-path="${escapeHtml(ep)}" style="font-size: 12px; padding: 4px 10px;">
                        <i class="fa-solid fa-rocket" style="color: var(--color-success);"></i> ${escapeHtml(ep)}
                    </button>
                `).join("");

                overviewEntryPointsList.querySelectorAll(".jump-entry-btn").forEach(btn => {
                    btn.addEventListener("click", () => {
                        const targetRel = btn.dataset.path;
                        const match = repoIndex.files.find(f => f.relative_path === targetRel);
                        if (match) {
                            switchTab("repository-tab");
                            loadFileContent(match.full_path, match.relative_path);
                        }
                    });
                });
            }
        }

        // Most Active Files Table
        if (overviewActiveFilesTbody) {
            const topActive = [...(repoIndex.files || [])].sort((a, b) => b.activity_score - a.activity_score).slice(0, 6);
            if (topActive.length === 0) {
                overviewActiveFilesTbody.innerHTML = `<tr><td colspan="4" class="empty-state">No file activity data.</td></tr>`;
            } else {
                overviewActiveFilesTbody.innerHTML = topActive.map(file => `
                    <tr>
                        <td>
                            <span style="font-family: var(--font-mono); font-size: 11px;">${escapeHtml(file.relative_path)}</span>
                        </td>
                        <td><strong style="color: var(--accent-primary); font-family: var(--font-mono);">${file.activity_score || 0}</strong></td>
                        <td>${(file.line_count || 0).toLocaleString()}</td>
                        <td>
                            <button type="button" class="btn btn-secondary btn-sm jump-file-btn" data-fullpath="${escapeHtml(file.full_path)}" data-relpath="${escapeHtml(file.relative_path)}">
                                Inspect
                            </button>
                        </td>
                    </tr>
                `).join("");

                overviewActiveFilesTbody.querySelectorAll(".jump-file-btn").forEach(btn => {
                    btn.addEventListener("click", () => {
                        switchTab("repository-tab");
                        loadFileContent(btn.dataset.fullpath, btn.dataset.relpath);
                    });
                });
            }
        }

        // Language Distribution Bar & Legend
        if (overviewLangBar && overviewLangLegend) {
            const langs = repoIndex.languages_breakdown || {};
            const totalLangFiles = Object.values(langs).reduce((a, b) => a + b, 0) || 1;
            const langColors = {
                python: "#3572A5",
                javascript: "#f1e05a",
                typescript: "#3178c6",
                html: "#e34c26",
                css: "#563d7c",
                markdown: "#083fa1",
                json: "#292929",
                shell: "#89e051"
            };

            const sortedLangs = Object.entries(langs).sort((a, b) => b[1] - a[1]);
            if (overviewLangCount) overviewLangCount.textContent = `${sortedLangs.length} languages`;

            overviewLangBar.innerHTML = sortedLangs.map(([lang, count]) => {
                const pct = ((count / totalLangFiles) * 100).toFixed(1);
                const color = langColors[lang.toLowerCase()] || "#64748b";
                return `<div class="lang-bar-segment" style="width: ${pct}%; background: ${color};" title="${lang}: ${pct}% (${count} files)"></div>`;
            }).join("");

            overviewLangLegend.innerHTML = sortedLangs.map(([lang, count]) => {
                const pct = ((count / totalLangFiles) * 100).toFixed(1);
                const color = langColors[lang.toLowerCase()] || "#64748b";
                return `
                    <div class="lang-legend-item">
                        <span class="lang-legend-dot" style="background: ${color};"></span>
                        <strong style="text-transform: capitalize;">${escapeHtml(lang)}</strong>
                        <span style="color: var(--text-muted);">${pct}%</span>
                    </div>
                `;
            }).join("");
        }
    }

    // Refresh Groq Deep Narrative
    if (refreshNarrativeBtn) {
        refreshNarrativeBtn.addEventListener("click", async () => {
            if (!currentSession) return;
            refreshNarrativeBtn.disabled = true;
            refreshNarrativeBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Generating Narrative...`;
            if (overviewArchNarrative) {
                overviewArchNarrative.innerHTML = `
                    <div class="skeleton-shimmer">
                        <div class="skeleton-line full"></div>
                        <div class="skeleton-line long"></div>
                        <div class="skeleton-line medium"></div>
                    </div>
                `;
            }

            try {
                const res = await fetch("/api/architecture?session_id=default&use_llm=true");
                if (!res.ok) throw new Error("Failed to generate narrative.");
                const data = await res.json();
                const narrative = data.architecture_summary?.overview_narrative;
                if (narrative && overviewArchNarrative) {
                    overviewArchNarrative.innerHTML = marked.parse(narrative);
                }
                showToast("Deep architecture narrative generated", "success");
            } catch (err) {
                if (overviewArchNarrative) {
                    overviewArchNarrative.innerHTML = `
                        <div class="alert-banner error">
                            <i class="fa-solid fa-triangle-exclamation"></i>
                            <div>${escapeHtml(err.message)}</div>
                        </div>
                    `;
                }
                showToast(err.message, "error", "Narrative Error");
            } finally {
                refreshNarrativeBtn.disabled = false;
                refreshNarrativeBtn.innerHTML = `<i class="fa-solid fa-bolt"></i> Generate Groq Deep Narrative`;
            }
        });
    }

    // Background Audit Fetch for Overview & Navigation Badges
    async function fetchBackgroundAudit() {
        try {
            const res = await fetch("/api/contribution/audit", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ session_id: "default" })
            });
            if (res.ok) {
                const audit = await res.json();
                auditReportCache = audit;
                const total = audit.total_opportunities || 0;
                if (statAuditVal) statAuditVal.textContent = total;
                if (statAuditMeta) {
                    statAuditMeta.textContent = `${audit.critical_count || 0} critical · ${audit.high_count || 0} high risks`;
                }
                if (navContribCount) navContribCount.textContent = total;
                if (overviewFindingsBadge) {
                    overviewFindingsBadge.textContent = `${total} Findings`;
                    overviewFindingsBadge.className = total > 0 ? "badge badge-amber" : "badge badge-green";
                }

                if (overviewFindingsBody) {
                    if (total === 0) {
                        overviewFindingsBody.innerHTML = `
                            <div style="display: flex; align-items: center; gap: 8px; color: var(--color-success);">
                                <i class="fa-solid fa-circle-check"></i>
                                <span>No critical vulnerabilities or test gaps detected. Excellent health!</span>
                            </div>
                        `;
                    } else {
                        const topOpps = (audit.opportunities || []).slice(0, 3);
                        overviewFindingsBody.innerHTML = `
                            <div style="display: flex; flex-direction: column; gap: 8px;">
                                ${topOpps.map(opp => `
                                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 8px; background: var(--bg-subtle); border-radius: var(--radius-sm);">
                                        <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-right: 8px;">
                                            <span class="badge ${opp.severity === 'Critical' ? 'badge-red' : opp.severity === 'High' ? 'badge-amber' : 'badge-blue'}" style="font-size: 10px;">${opp.severity}</span>
                                            <span style="font-size: 12px; margin-left: 4px;">${escapeHtml(opp.title)}</span>
                                        </div>
                                        <button type="button" class="btn btn-secondary btn-sm jump-contrib-btn" data-title="${encodeURIComponent(opp.suggested_issue_title)}" data-desc="${encodeURIComponent(opp.suggested_issue_desc)}">
                                            Fix Plan
                                        </button>
                                    </div>
                                `).join("")}
                                <button type="button" id="overview-view-all-findings" class="btn btn-secondary btn-sm" style="margin-top: 4px; width: 100%;">
                                    View All ${total} Contribution Opportunities in Contributions Tab →
                                </button>
                            </div>
                        `;

                        overviewFindingsBody.querySelectorAll(".jump-contrib-btn").forEach(btn => {
                            btn.addEventListener("click", () => {
                                switchTab("contributions-tab");
                                if (issueTitle) issueTitle.value = decodeURIComponent(btn.dataset.title || "");
                                if (issueDesc) issueDesc.value = decodeURIComponent(btn.dataset.desc || "");
                                runContributionAnalysis();
                            });
                        });

                        const viewAllBtn = document.getElementById("overview-view-all-findings");
                        if (viewAllBtn) {
                            viewAllBtn.addEventListener("click", () => {
                                switchTab("contributions-tab");
                                if (auditOpportunitiesContainer && auditReportCache) {
                                    renderAuditReport(auditReportCache);
                                }
                            });
                        }
                    }
                }
            }
        } catch (err) {
            console.warn("Background audit error:", err);
        }
    }

    // =========================================================================
    // PAGE 2: REPOSITORY TAB (IDE / CODE EXPLORER) LOGIC
    // =========================================================================
    function renderFilesIndex(files) {
        if (!treeContainer) return;
        if (!files || files.length === 0) {
            treeContainer.innerHTML = `<div class="empty-state"><p>No supported code files found.</p></div>`;
            return;
        }

        const sortedFiles = [...files].sort((a, b) => b.activity_score - a.activity_score);
        treeContainer.innerHTML = "";

        sortedFiles.forEach(file => {
            const node = document.createElement("div");
            node.className = "tree-node";
            node.dataset.filename = file.relative_path.toLowerCase();

            const entryBadge = file.is_entry_point
                ? `<span class="badge badge-green" style="font-size:9px; margin-left:4px;">🚀 Entry</span>`
                : "";

            node.innerHTML = `
                <div class="node-info">
                    <i class="fa-regular fa-file-code"></i>
                    <span>${escapeHtml(file.relative_path)}</span>
                    ${entryBadge}
                </div>
                <span class="node-meta">${file.activity_score || 0}</span>
            `;

            node.addEventListener("click", () => {
                document.querySelectorAll(".tree-node").forEach(n => n.classList.remove("active"));
                node.classList.add("active");
                loadFileContent(file.full_path, file.relative_path);
            });

            treeContainer.appendChild(node);
        });
    }

    // Filter File Tree via Search Input
    if (repoSearch) {
        repoSearch.addEventListener("input", (e) => {
            const query = e.target.value.toLowerCase().trim();
            const nodes = treeContainer.querySelectorAll(".tree-node");
            let visibleCount = 0;
            nodes.forEach(node => {
                const name = node.dataset.filename || "";
                const matches = name.includes(query);
                node.style.display = matches ? "flex" : "none";
                if (matches) visibleCount++;
            });

            let emptyMsg = treeContainer.querySelector(".tree-empty-search");
            if (visibleCount === 0 && query) {
                if (!emptyMsg) {
                    emptyMsg = document.createElement("div");
                    emptyMsg.className = "empty-state tree-empty-search";
                    emptyMsg.style.padding = "24px 12px";
                    emptyMsg.innerHTML = `
                        <i class="fa-solid fa-magnifying-glass" style="font-size: 20px;"></i>
                        <h3 style="font-size: 13px;">No matching files</h3>
                        <p style="font-size: 11px;">No files match "${escapeHtml(query)}"</p>
                        <button type="button" class="btn btn-secondary btn-sm" id="clear-search-btn" style="margin-top: 8px;">Clear search</button>
                    `;
                    treeContainer.appendChild(emptyMsg);
                    const clearBtn = emptyMsg.querySelector("#clear-search-btn");
                    if (clearBtn) {
                        clearBtn.addEventListener("click", () => {
                            repoSearch.value = "";
                            repoSearch.dispatchEvent(new Event("input"));
                        });
                    }
                }
            } else if (emptyMsg) {
                emptyMsg.remove();
            }
        });
    }

    // Load Source Code Content
    async function loadFileContent(fullPath, relPath) {
        selectedFilePath = fullPath;
        if (currentFilename) currentFilename.textContent = relPath;
        if (codeContent) codeContent.textContent = "// Loading source code...";
        if (summarizeBtn) summarizeBtn.disabled = true;
        if (summaryText) {
            summaryText.innerHTML = `<p class="placeholder-text" style="color: var(--text-muted);">Click <strong>"Summarize"</strong> to generate a developer architectural summary of <code>${escapeHtml(relPath)}</code>.</p>`;
        }

        // Highlight matching tree node
        document.querySelectorAll(".tree-node").forEach(n => {
            const text = n.querySelector(".node-info span")?.textContent;
            if (text === relPath) n.classList.add("active");
            else n.classList.remove("active");
        });

        // Populate Exported Symbols & Dependencies for this file
        if (currentSession) {
            const fileObj = currentSession.files.find(f => f.full_path === fullPath || f.relative_path === relPath);
            if (fileObj) {
                if (currentFileLines) currentFileLines.textContent = `${fileObj.line_count || 0} lines`;

                if (fileSymbolsList) {
                    if (fileObj.symbols && fileObj.symbols.length > 0) {
                        fileSymbolsList.innerHTML = fileObj.symbols.map(s => `
                            <span class="badge badge-purple" style="font-family: var(--font-mono); font-size: 11px;">
                                ${s.kind === 'class' ? '🏛️' : '⚙️'} ${escapeHtml(s.name)}()
                            </span>
                        `).join("");
                    } else {
                        fileSymbolsList.innerHTML = `<span class="text-muted" style="font-size: 11px;">No top-level functions or classes detected.</span>`;
                    }
                }

                if (fileDepsList) {
                    if (fileObj.dependencies && fileObj.dependencies.length > 0) {
                        fileDepsList.innerHTML = fileObj.dependencies.map(d => `
                            <span class="badge" style="font-family: var(--font-mono); font-size: 11px;">
                                ${escapeHtml(d.target_path)}
                            </span>
                        `).join("");
                    } else {
                        fileDepsList.innerHTML = `<span class="text-muted" style="font-size: 11px;">No imports declared.</span>`;
                    }
                }
            }
        }

        try {
            const res = await fetch(`/api/file-content?file_path=${encodeURIComponent(fullPath)}`);
            if (!res.ok) throw new Error("Failed to load file.");
            const data = await res.json();

            if (codeContent) {
                codeContent.textContent = data.content;
                if (window.Prism) Prism.highlightElement(codeContent);
            }
            if (currentFileLines) currentFileLines.textContent = `${data.lines || 0} lines`;
            if (summarizeBtn) summarizeBtn.disabled = false;
        } catch (err) {
            if (codeContent) codeContent.textContent = `// Error loading file: ${err.message}`;
        }
    }

    // Copy Code Button
    if (copyCodeBtn) {
        copyCodeBtn.addEventListener("click", () => {
            if (!codeContent) return;
            navigator.clipboard.writeText(codeContent.textContent).then(() => {
                copyCodeBtn.innerHTML = `<i class="fa-solid fa-check" style="color: var(--color-success);"></i>`;
                showToast("Code copied to clipboard", "success");
                setTimeout(() => {
                    copyCodeBtn.innerHTML = `<i class="fa-regular fa-copy"></i>`;
                }, 1500);
            });
        });
    }

    // Trigger Groq AI File Summarization
    if (summarizeBtn) {
        summarizeBtn.addEventListener("click", async () => {
            if (!selectedFilePath) return;
            summarizeBtn.disabled = true;
            summarizeBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Analyzing...`;
            if (summaryText) {
                summaryText.innerHTML = `
                    <div class="skeleton-shimmer">
                        <div class="skeleton-line full"></div>
                        <div class="skeleton-line long"></div>
                        <div class="skeleton-line medium"></div>
                        <div class="skeleton-line full"></div>
                    </div>
                `;
            }

            try {
                const res = await fetch("/api/summarize", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        file_path: selectedFilePath,
                        session_id: "default"
                    })
                });

                if (!res.ok) throw new Error("Summarization failed.");
                const data = await res.json();
                if (summaryText) summaryText.innerHTML = marked.parse(data.summary);
                showToast("File summary generated", "success");
            } catch (err) {
                if (summaryText) {
                    summaryText.innerHTML = `
                        <div class="alert-banner error">
                            <i class="fa-solid fa-triangle-exclamation"></i>
                            <div>
                                <strong>Summarization Failed</strong>
                                <div>${escapeHtml(err.message)}</div>
                            </div>
                        </div>
                    `;
                }
                showToast(err.message, "error", "Summarize Error");
            } finally {
                summarizeBtn.disabled = false;
                summarizeBtn.innerHTML = `<i class="fa-solid fa-bolt"></i> Summarize`;
            }
        });
    }

    // =========================================================================
    // PAGE 3: ARCHITECTURE (DEPENDENCY GRAPH) LOGIC
    // =========================================================================
    async function renderDependencyGraph() {
        const container = document.getElementById("network-graph");
        if (!container) return;

        if (typeof vis === 'undefined') {
            container.innerHTML = `<div class="empty-state"><p style="color: var(--color-danger);">Vis.js library could not be loaded.</p></div>`;
            return;
        }

        const filterType = graphFilterSelect ? graphFilterSelect.value : "all";
        const layoutType = graphLayoutSelect ? graphLayoutSelect.value : "force";
        const includeExt = graphExternalChk ? graphExternalChk.checked : true;

        try {
            if (!container.querySelector("canvas")) {
                container.innerHTML = `<div class="empty-state"><i class="fa-solid fa-spinner fa-spin"></i><p>Building 2D dependency graph (${filterType})...</p></div>`;
            }

            const res = await fetch(`/api/graph?session_id=default&filter_type=${filterType}&include_external=${includeExt}`);
            const data = await res.json();

            if (!data.nodes || data.nodes.length === 0) {
                if (networkGraph) {
                    networkGraph.destroy();
                    networkGraph = null;
                }
                container.innerHTML = `<div class="empty-state"><p>No dependency nodes found for filter: <strong>${escapeHtml(filterType)}</strong></p><p style="font-size:12px; color:var(--text-muted); margin-top:8px;">Switch filter to All Files or reset camera.</p></div>`;
                return;
            }

            container.innerHTML = "";

            // Modern Linear/GitHub light styling for Vis.js nodes
            const nodesDataSet = new vis.DataSet(data.nodes.map(n => {
                const baseSize = 14;
                const sizeBonus = Math.min(22, (n.in_degree || 0) * 3);
                const finalSize = baseSize + sizeBonus;

                let nodeBg = '#ffffff';
                let nodeBorder = '#2563eb';
                let shape = 'dot';

                if (n.node_type === 'external_package') {
                    nodeBorder = '#7c3aed';
                    nodeBg = '#f5f3ff';
                    shape = 'box';
                } else if (n.is_entry_point) {
                    nodeBorder = '#059669';
                    nodeBg = '#ecfdf5';
                    shape = 'diamond';
                } else if (n.is_circular) {
                    nodeBorder = '#dc2626';
                    nodeBg = '#fef2f2';
                } else {
                    nodeBorder = '#2563eb';
                    nodeBg = '#eff6ff';
                }

                return {
                    id: String(n.id),
                    label: n.label,
                    title: `${n.label}\nIn-Degree: ${n.in_degree || 0} | Out-Degree: ${n.out_degree || 0}\nCategory: ${n.module_category || 'standard'}`,
                    shape: shape,
                    size: finalSize,
                    color: {
                        background: nodeBg,
                        border: nodeBorder,
                        highlight: { background: '#dbeafe', border: '#1d4ed8' }
                    },
                    borderWidth: 2,
                    font: { color: '#0f172a', face: 'Inter', size: 11 },
                    rawData: n
                };
            }));

            const edgesDataSet = new vis.DataSet(data.edges.map(e => ({
                from: String(e.from),
                to: String(e.to),
                arrows: 'to',
                color: { color: e.edge_type === 'external_package' ? '#c4b5fd' : '#94a3b8', highlight: '#2563eb' },
                width: 1.2
            })));

            const isTree = layoutType === 'tree';
            const options = {
                autoResize: true,
                layout: isTree ? {
                    hierarchical: {
                        enabled: true,
                        direction: 'UD',
                        sortMethod: 'hubsize',
                        levelSeparation: 120,
                        nodeSpacing: 140
                    }
                } : {
                    hierarchical: { enabled: false }
                },
                physics: isTree ? {
                    enabled: true,
                    solver: 'hierarchicalRepulsion'
                } : {
                    enabled: true,
                    solver: 'forceAtlas2Based',
                    forceAtlas2Based: {
                        gravitationalConstant: -35,
                        centralGravity: 0.01,
                        springLength: 100,
                        springConstant: 0.08,
                        damping: 0.4
                    },
                    stabilization: { iterations: 120, updateInterval: 25 }
                },
                interaction: {
                    hover: true,
                    zoomView: true,
                    dragView: true
                }
            };

            if (networkGraph) {
                networkGraph.destroy();
                networkGraph = null;
            }
            networkGraph = new vis.Network(container, { nodes: nodesDataSet, edges: edgesDataSet }, options);

            networkGraph.once("stabilizationIterationsDone", () => {
                networkGraph.fit({ animation: { duration: 300, easingFunction: 'easeInOutQuad' } });
            });

            networkGraph.on("selectNode", (params) => {
                if (params.nodes.length > 0) {
                    const selectedId = params.nodes[0];
                    const nodeObj = nodesDataSet.get(selectedId);
                    if (nodeObj && nodeObj.rawData) {
                        openNodeInspector(nodeObj.rawData);
                    }
                }
            });

            networkGraph.on("deselectNode", closeNodeInspector);

        } catch (err) {
            container.innerHTML = `<div class="empty-state"><p style="color: var(--color-danger);">Graph error: ${escapeHtml(err.message)}</p></div>`;
        }
    }

    function openNodeInspector(nodeData) {
        currentInspectorNode = nodeData;
        if (!nodeInspector) return;

        if (inspectorNodeTitle) inspectorNodeTitle.textContent = nodeData.label;
        if (inspectorNodeType) {
            inspectorNodeType.textContent = nodeData.node_type === 'external_package' ? 'External Package' : (nodeData.is_entry_point ? '🚀 Entry Point' : 'Internal File');
        }
        if (inspectorInDegree) inspectorInDegree.textContent = nodeData.in_degree || 0;
        if (inspectorOutDegree) inspectorOutDegree.textContent = nodeData.out_degree || 0;
        if (inspectorScore) inspectorScore.textContent = nodeData.activity_score || 0.0;

        if (currentSession) {
            const fileObj = currentSession.files.find(f => f.relative_path === nodeData.path);
            if (fileObj) {
                if (inspectorDepsList) {
                    inspectorDepsList.innerHTML = (fileObj.dependencies && fileObj.dependencies.length > 0)
                        ? fileObj.dependencies.map(d => `<span class="badge">${escapeHtml(d.target_path)}</span>`).join("")
                        : `<span class="text-muted" style="font-size:11px;">No dependencies declared.</span>`;
                }
                if (inspectorSymbolsList) {
                    inspectorSymbolsList.innerHTML = (fileObj.symbols && fileObj.symbols.length > 0)
                        ? fileObj.symbols.map(s => `<span class="badge badge-purple">⚙️ ${escapeHtml(s.name)}()</span>`).join("")
                        : `<span class="text-muted" style="font-size:11px;">No exported functions.</span>`;
                }
            }
        }

        nodeInspector.classList.remove("hidden");
    }

    function closeNodeInspector() {
        if (nodeInspector) nodeInspector.classList.add("hidden");
        currentInspectorNode = null;
    }

    if (closeInspectorBtn) closeInspectorBtn.addEventListener("click", closeNodeInspector);

    if (jumpCodeBtn) {
        jumpCodeBtn.addEventListener("click", () => {
            if (!currentInspectorNode || currentInspectorNode.node_type === 'external_package') {
                showToast("Source code is not available locally for external packages.", "info");
                return;
            }
            const match = currentSession?.files.find(f => f.relative_path === currentInspectorNode.path);
            if (match) {
                switchTab("repository-tab");
                loadFileContent(match.full_path, match.relative_path);
            }
        });
    }

    if (refreshGraphBtn) {
        refreshGraphBtn.addEventListener("click", () => {
            if (graphFilterSelect) graphFilterSelect.value = "all";
            if (graphLayoutSelect) graphLayoutSelect.value = "force";
            if (graphExternalChk) graphExternalChk.checked = true;
            renderDependencyGraph();
        });
    }
    if (graphFilterSelect) graphFilterSelect.addEventListener("change", renderDependencyGraph);
    if (graphLayoutSelect) graphLayoutSelect.addEventListener("change", renderDependencyGraph);
    if (graphExternalChk) graphExternalChk.addEventListener("change", renderDependencyGraph);

    function populateArchitectureTables(repoIndex) {
        // Populate Modules Breakdown Table
        if (archModulesTbody) {
            const files = repoIndex.files || [];
            if (files.length === 0) {
                archModulesTbody.innerHTML = `<tr><td colspan="5" class="empty-state">No modules indexed.</td></tr>`;
            } else {
                archModulesTbody.innerHTML = files.map(f => `
                    <tr>
                        <td>
                            <strong style="font-family: var(--font-mono); font-size: 11px;">${escapeHtml(f.relative_path)}</strong>
                            ${f.is_entry_point ? '<span class="badge badge-green" style="font-size: 9px; margin-left: 4px;">Entry</span>' : ''}
                        </td>
                        <td><span class="badge" style="text-transform: capitalize;">${escapeHtml(f.module_category || 'standard')}</span></td>
                        <td><span class="badge badge-blue">${f.in_degree || 0}</span></td>
                        <td><span class="badge">${f.out_degree || 0}</span></td>
                        <td>${f.is_circular ? '<span class="badge badge-red">Circular</span>' : '<span class="text-muted" style="font-size:11px;">No</span>'}</td>
                    </tr>
                `).join("");
            }
        }

        // Populate Circular Cycles List
        if (archCyclesList) {
            const cycles = repoIndex.circular_cycles || [];
            if (archCyclesCount) archCyclesCount.textContent = `${cycles.length} Cycles`;

            if (cycles.length === 0) {
                archCyclesList.innerHTML = `
                    <div class="empty-state">
                        <i class="fa-solid fa-circle-check" style="color: var(--color-success);"></i>
                        <h3>No Circular Dependencies Detected</h3>
                        <p>The codebase exhibits clean acyclic module hierarchy.</p>
                    </div>
                `;
            } else {
                archCyclesList.innerHTML = cycles.map((c, i) => `
                    <div style="padding: 10px; background: var(--bg-subtle); border-radius: var(--radius-sm); margin-bottom: 8px; border-left: 3px solid var(--color-danger);">
                        <strong style="font-size: 12px; color: var(--color-danger);">Cycle #${i + 1} (${c.cycle_length} files)</strong>
                        <div style="font-family: var(--font-mono); font-size: 11px; margin-top: 4px; color: var(--text-primary);">
                            ${(c.cycle_path || []).map(p => escapeHtml(p)).join(' <i class="fa-solid fa-arrow-right" style="font-size: 9px; color: var(--text-muted);"></i> ')}
                        </div>
                    </div>
                `).join("");
            }
        }
    }

    // =========================================================================
    // PAGE 4: AI ASSISTANT LOGIC (WITH CITATIONS BESIDE / BELOW RESPONSES)
    // =========================================================================
    if (chatForm) {
        chatForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const question = chatInput ? chatInput.value.trim() : "";
            if (!question) return;

            appendChatMessage("user", question);
            if (chatInput) chatInput.value = "";

            const assistantMsgEl = appendChatMessage("assistant", `
                <div style="display: flex; align-items: center; gap: 6px;">
                    <div class="typing-indicator">
                        <span></span><span></span><span></span>
                    </div>
                    <span style="font-size: 11px; color: var(--text-muted);">Thinking & retrieving repository context...</span>
                </div>
            `);

            try {
                const res = await fetch("/api/chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ question: question, session_id: "default" })
                });

                if (!res.ok) throw new Error("Chat request failed.");
                const data = await res.json();

                const bubble = assistantMsgEl.querySelector(".message-bubble");
                bubble.innerHTML = marked.parse(data.answer);

                // Render Grounded Source Citations
                if (data.sources && data.sources.length > 0) {
                    const citationContainer = document.createElement("div");
                    citationContainer.className = "citation-container";
                    citationContainer.innerHTML = `<span style="font-size: 11px; color: var(--text-muted); font-weight: 500;">Grounded Sources:</span>`;

                    data.sources.forEach(src => {
                        const chip = document.createElement("button");
                        chip.type = "button";
                        chip.className = "citation-chip";
                        const sym = src.symbol_name ? `::${src.symbol_name}` : "";
                        const line = src.line_number ? `:${src.line_number}` : "";
                        chip.innerHTML = `<i class="fa-regular fa-file-code"></i> ${escapeHtml(src.file_path + sym + line)}`;
                        chip.title = src.relevance_reason || "Source citation";

                        chip.addEventListener("click", () => {
                            if (currentSession) {
                                const match = currentSession.files.find(f => f.relative_path === src.file_path);
                                if (match) {
                                    switchTab("repository-tab");
                                    loadFileContent(match.full_path, match.relative_path);
                                }
                            }
                        });

                        citationContainer.appendChild(chip);
                    });

                    bubble.appendChild(citationContainer);
                }

            } catch (err) {
                const bubble = assistantMsgEl.querySelector(".message-bubble");
                bubble.innerHTML = `
                    <div class="alert-banner error" style="margin: 0; padding: 8px 10px;">
                        <i class="fa-solid fa-triangle-exclamation"></i>
                        <div>
                            <strong>Assistant Error</strong>
                            <div style="font-size: 11px; margin-top: 2px;">${escapeHtml(err.message)}</div>
                        </div>
                    </div>
                `;
                showToast(err.message, "error", "Assistant Error");
            }
        });
    }

    function appendChatMessage(role, textHtml) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `chat-message ${role}`;

        const avatarIcon = role === "user" ? '<i class="fa-solid fa-user"></i>' : '<i class="fa-solid fa-robot"></i>';
        msgDiv.innerHTML = `
            <div class="message-avatar">${avatarIcon}</div>
            <div class="message-bubble">${textHtml}</div>
        `;

        if (chatMessages) {
            chatMessages.appendChild(msgDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
        return msgDiv;
    }

    // Prompt Chips Handler
    document.querySelectorAll(".prompt-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            if (chatInput) {
                chatInput.value = chip.dataset.prompt || "";
                chatForm.dispatchEvent(new Event("submit"));
            }
        });
    });

    // Clear History Button
    if (clearChatBtn) {
        clearChatBtn.addEventListener("click", async () => {
            try {
                await fetch("/api/chat/history?session_id=default", { method: "DELETE" });
                if (chatMessages) {
                    chatMessages.innerHTML = `
                        <div class="chat-message assistant">
                            <div class="message-avatar"><i class="fa-solid fa-robot"></i></div>
                            <div class="message-bubble">
                                Conversation history cleared. What would you like to explore next?
                            </div>
                        </div>
                    `;
                }
                showToast("Chat history cleared", "info");
            } catch (err) {
                console.warn("Clear chat error:", err);
            }
        });
    }

    // =========================================================================
    // PAGE 5: CONTRIBUTIONS TAB LOGIC
    // =========================================================================
    if (auditRepoBtn) {
        auditRepoBtn.addEventListener("click", async () => {
            auditRepoBtn.disabled = true;
            auditRepoBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Auditing AST & Security...`;
            if (auditOpportunitiesContainer) {
                auditOpportunitiesContainer.style.display = "block";
                auditOpportunitiesContainer.innerHTML = `<div class="empty-state"><i class="fa-solid fa-spinner fa-spin"></i><p>Scanning repository AST for security risks, test coverage gaps & refactoring opportunities...</p></div>`;
            }

            try {
                const res = await fetch("/api/contribution/audit", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ session_id: "default" })
                });

                if (!res.ok) throw new Error("Audit scanning failed.");
                const auditData = await res.json();
                auditReportCache = auditData;
                renderAuditReport(auditData);
            } catch (err) {
                if (auditOpportunitiesContainer) {
                    auditOpportunitiesContainer.innerHTML = `<div class="empty-state"><p style="color: var(--color-danger);">❌ ${err.message}</p></div>`;
                }
            } finally {
                auditRepoBtn.disabled = false;
                auditRepoBtn.innerHTML = `<i class="fa-solid fa-shield-halved"></i> Run Full Audit`;
            }
        });
    }

    function renderAuditReport(auditReport) {
        if (!auditOpportunitiesContainer) return;
        if (!auditReport.opportunities || auditReport.opportunities.length === 0) {
            auditOpportunitiesContainer.innerHTML = `
                <div class="dev-card">
                    <div class="empty-state">
                        <i class="fa-solid fa-circle-check" style="color: var(--color-success);"></i>
                        <h3>Excellent Repository Health!</h3>
                        <p>No critical security vulnerabilities, test gaps, or circular dependency risks detected.</p>
                    </div>
                </div>
            `;
            return;
        }

        let html = `<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px;">`;

        auditReport.opportunities.forEach(opp => {
            let severityClass = "badge-blue";
            if (opp.severity === "Critical") severityClass = "badge-red";
            else if (opp.severity === "High") severityClass = "badge-amber";
            else if (opp.severity === "Medium") severityClass = "badge-amber";

            const filesHtml = (opp.target_files || []).map(f => `<span class="badge" style="font-size: 10px; font-family: var(--font-mono);">${escapeHtml(f)}</span>`).join(" ");

            html += `
                <div class="opportunity-card" data-severity="${opp.severity.toLowerCase()}">
                    <div class="opportunity-card-top">
                        <span class="badge ${severityClass}">${escapeHtml(opp.severity)}</span>
                        <span style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">${escapeHtml(opp.category.replace('_', ' '))}</span>
                    </div>
                    <h4 style="font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 6px;">${escapeHtml(opp.title)}</h4>
                    <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; line-height: 1.4;">${escapeHtml(opp.description)}</p>
                    <div style="margin-bottom: 12px;">${filesHtml}</div>
                    <button type="button" class="btn btn-secondary btn-sm select-opp-btn" data-title="${encodeURIComponent(opp.suggested_issue_title)}" data-desc="${encodeURIComponent(opp.suggested_issue_desc)}" style="width: 100%;">
                        <i class="fa-solid fa-wand-magic-sparkles"></i> Analyze & Plan Issue
                    </button>
                </div>
            `;
        });

        html += `</div>`;
        auditOpportunitiesContainer.innerHTML = html;

        auditOpportunitiesContainer.querySelectorAll(".select-opp-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                const title = decodeURIComponent(btn.dataset.title || "");
                const desc = decodeURIComponent(btn.dataset.desc || "");
                if (issueTitle) issueTitle.value = title;
                if (issueDesc) issueDesc.value = desc;
                runContributionAnalysis();
            });
        });
    }

    // Filter Chips for Opportunities
    document.querySelectorAll(".filter-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            document.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            const filter = chip.dataset.filter;

            const cards = auditOpportunitiesContainer?.querySelectorAll(".opportunity-card");
            cards?.forEach(card => {
                if (filter === "all" || card.dataset.severity === filter) {
                    card.style.display = "block";
                } else {
                    card.style.display = "none";
                }
            });
        });
    });

    async function runContributionAnalysis() {
        const title = issueTitle ? issueTitle.value.trim() : "";
        const desc = issueDesc ? issueDesc.value.trim() : "";
        if (!title) return;

        if (analyzeContribBtn) {
            analyzeContribBtn.disabled = true;
            analyzeContribBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Calculating Blast Radius...`;
        }
        if (contributionContent) {
            contributionContent.innerHTML = `<div class="empty-state"><i class="fa-solid fa-spinner fa-spin"></i><p>Analyzing architectural blast radius and generating implementation plan...</p></div>`;
        }

        try {
            const res = await fetch("/api/contribution/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    title: title,
                    description: desc,
                    session_id: "default"
                })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Analysis failed.");
            }

            const data = await res.json();
            if (contributionContent) {
                contributionContent.innerHTML = `
                    <div class="dev-card-body markdown-body">
                        ${marked.parse(data.plan_narrative)}
                    </div>
                `;
            }
        } catch (err) {
            if (contributionContent) {
                contributionContent.innerHTML = `<div class="empty-state"><p style="color: var(--color-danger);">❌ ${escapeHtml(err.message)}</p></div>`;
            }
        } finally {
            if (analyzeContribBtn) {
                analyzeContribBtn.disabled = false;
                analyzeContribBtn.innerHTML = `<i class="fa-solid fa-bullseye"></i> Analyze Contribution & Blast Radius`;
            }
        }
    }

    // Preset Issue Buttons
    document.querySelectorAll(".preset-issue-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            if (issueTitle) issueTitle.value = btn.dataset.title || "";
            if (issueDesc) issueDesc.value = btn.dataset.desc || "";
            runContributionAnalysis();
        });
    });

    if (contribForm) {
        contribForm.addEventListener("submit", runContributionAnalysis);
    }

    // =========================================================================
    // PAGE 6: AGENT EXPLORER LOGIC
    // =========================================================================
    if (agentForm) {
        agentForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const query = agentInput ? agentInput.value.trim() : "";
            if (!query) return;

            if (agentExploreBtn) {
                agentExploreBtn.disabled = true;
                agentExploreBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Investigating...`;
            }
            if (agentTrace) {
                agentTrace.innerHTML = `<div class="trace-step-item"><i class="fa-solid fa-spinner fa-spin" style="color: var(--accent-primary);"></i><span>Starting autonomous investigation trace...</span></div>`;
            }
            if (agentAnswer) {
                agentAnswer.innerHTML = `<div class="empty-state"><i class="fa-solid fa-spinner fa-spin"></i><p>Collecting evidence across codebase AST...</p></div>`;
            }
            if (agentFiles) agentFiles.innerHTML = "";
            if (agentSources) agentSources.innerHTML = "";
            if (agentSummary) agentSummary.innerHTML = "";

            try {
                const res = await fetch("/api/agent/explore", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        query: query,
                        session_id: "default",
                        max_iterations: 8,
                        max_tool_calls: 15,
                        max_files: 20
                    })
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || "Agent exploration failed.");
                }

                const data = await res.json();
                renderAgentResult(data);
            } catch (err) {
                if (agentTrace) {
                    agentTrace.innerHTML = `<div class="trace-step-item" style="border-color: var(--color-danger);"><i class="fa-solid fa-triangle-exclamation" style="color: var(--color-danger);"></i><span>${escapeHtml(err.message)}</span></div>`;
                }
                if (agentAnswer) {
                    agentAnswer.innerHTML = `<div class="empty-state"><p style="color: var(--color-danger);">Error: ${escapeHtml(err.message)}</p></div>`;
                }
            } finally {
                if (agentExploreBtn) {
                    agentExploreBtn.disabled = false;
                    agentExploreBtn.innerHTML = `<i class="fa-solid fa-route"></i> Explore Codebase`;
                }
            }
        });
    }

    function renderAgentResult(data) {
        if (agentTrace) {
            const steps = data.trace || [];
            if (agentStepCount) agentStepCount.textContent = `${steps.length} Steps`;

            agentTrace.innerHTML = steps.map(event => {
                const icon = (event.status === "success" || event.status === "complete")
                    ? '<i class="fa-solid fa-check" style="color: var(--color-success);"></i>'
                    : event.status === "error"
                    ? '<i class="fa-solid fa-triangle-exclamation" style="color: var(--color-danger);"></i>'
                    : '<i class="fa-solid fa-circle-dot" style="color: var(--accent-primary);"></i>';

                return `
                    <div class="trace-step-item">
                        <span class="trace-step-num">${event.step || 1}</span>
                        <div style="flex: 1;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span>${icon} ${escapeHtml(event.description)}</span>
                                ${event.tool ? `<span class="badge" style="font-family:var(--font-mono); font-size:10px;">${escapeHtml(event.tool)}</span>` : ''}
                            </div>
                        </div>
                    </div>
                `;
            }).join("");
        }

        if (agentAnswer) {
            agentAnswer.innerHTML = `
                <h3 style="font-size: 14px; margin-bottom: 8px;">Final Grounded Answer</h3>
                ${marked.parse(data.answer || "No answer generated.")}
            `;
        }

        if (agentFiles) {
            const files = data.files_inspected || [];
            agentFiles.innerHTML = `
                <h4 style="font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px;">Files Inspected (${files.length})</h4>
                <div class="tag-cloud">
                    ${files.map(path => `<span class="badge" style="font-family: var(--font-mono);">${escapeHtml(path)}</span>`).join("") || '<span class="text-muted">None</span>'}
                </div>
            `;
        }

        if (agentSources) {
            const sources = data.sources || [];
            agentSources.innerHTML = `
                <h4 style="font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px;">Source Evidence</h4>
                <div style="display: flex; flex-direction: column; gap: 6px;">
                    ${sources.map(src => {
                        const sym = src.symbol_name ? `::${src.symbol_name}` : "";
                        const line = src.line_number ? `:${src.line_number}` : "";
                        return `
                            <div style="padding: 6px 10px; background: var(--bg-subtle); border-radius: var(--radius-sm); font-size: 11px;">
                                <strong style="font-family: var(--font-mono); color: var(--accent-primary);">${escapeHtml(src.file_path + sym + line)}</strong>
                                <div style="color: var(--text-secondary); margin-top: 2px;">${escapeHtml(src.relevance_reason || "")}</div>
                            </div>
                        `;
                    }).join("") || '<span class="text-muted">None</span>'}
                </div>
            `;
        }
    }

    // =========================================================================
    // PAGE 7: PR REVIEW TAB LOGIC
    // =========================================================================
    const SAMPLE_FEATURE_DIFF = `diff --git a/services/auth_service.py b/services/auth_service.py
new file mode 100644
--- /dev/null
+++ b/services/auth_service.py
@@ -0,0 +1,24 @@
+import jwt
+from datetime import datetime, timezone, timedelta
+
+class AuthService:
+    def __init__(self, secret: str = "configured_secret"):
+        self.secret = secret
+
+    def create_access_token(self, user_id: str) -> str:
+        payload = {
+            "sub": user_id,
+            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
+        }
+        return jwt.encode(payload, self.secret, algorithm="HS256")
+
+    def verify_token(self, token: str) -> dict:
+        try:
+            return jwt.decode(token, self.secret, algorithms=["HS256"])
+        except Exception as e:
+            return {"valid": False, "error": str(e)}
+`;

    const SAMPLE_VULN_DIFF = `diff --git a/services/report_service.py b/services/report_service.py
--- a/services/report_service.py
+++ b/services/report_service.py
@@ -10,6 +10,14 @@ def generate_report(query_param: str):
+    api_key = "AIzaSyD-TESTING-SECRET-KEY-12345678"
+    eval(query_param)
+    import subprocess
+    subprocess.Popen("cat /etc/passwd", shell=True)
+    import requests
+    requests.get(user_url, verify=False)
+    return {"status": "generated"}
+`;

    const SAMPLE_ARCH_DIFF = `diff --git a/models/user_model.py b/models/user_model.py
--- a/models/user_model.py
+++ b/models/user_model.py
@@ -3,6 +3,9 @@ from pydantic import BaseModel
+# Architectural layer violation: Model importing high-level API server
+from server import app, ACTIVE_SESSIONS
+
 class UserModel(BaseModel):
     user_id: str
     username: str
`;

    if (loadFeatureBtn) {
        loadFeatureBtn.addEventListener("click", () => {
            if (prTitleInput) prTitleInput.value = "feat(auth): implement AuthService token generation and validation";
            if (prDiffInput) prDiffInput.value = SAMPLE_FEATURE_DIFF;
        });
    }

    if (loadVulnBtn) {
        loadVulnBtn.addEventListener("click", () => {
            if (prTitleInput) prTitleInput.value = "fix(report): dynamic report query handling";
            if (prDiffInput) prDiffInput.value = SAMPLE_VULN_DIFF;
        });
    }

    if (loadArchBtn) {
        loadArchBtn.addEventListener("click", () => {
            if (prTitleInput) prTitleInput.value = "refactor(models): import server app inside user model";
            if (prDiffInput) prDiffInput.value = SAMPLE_ARCH_DIFF;
        });
    }

    if (prFileInput) {
        prFileInput.addEventListener("change", (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (event) => {
                if (prDiffInput) prDiffInput.value = event.target.result;
            };
            reader.readAsText(file);
        });
    }

    document.querySelectorAll(".pr-subtab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".pr-subtab-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const targetId = btn.dataset.subtab;
            document.querySelectorAll(".pr-subpanel").forEach(p => {
                p.style.display = p.id === targetId ? "block" : "none";
            });
        });
    });

    async function runPR(endpoint, btnEl, btnLabel) {
        const diffText = (prDiffInput ? prDiffInput.value : "").trim();
        if (!diffText) {
            showToast("Please paste a git diff patch or upload a .patch file first.", "warning");
            return;
        }

        const title = prTitleInput ? prTitleInput.value.trim() : "";
        if (btnEl) {
            btnEl.disabled = true;
            btnEl.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Analyzing Diff...`;
        }

        if (prEmptyState) prEmptyState.style.display = "none";
        if (prResultsContainer) {
            prResultsContainer.style.display = "block";
            if (prMetricsBar) {
                prMetricsBar.innerHTML = `
                    <div class="stat-card"><div class="skeleton-line short"></div><div class="skeleton-line medium" style="margin-top:8px;"></div></div>
                    <div class="stat-card"><div class="skeleton-line short"></div><div class="skeleton-line medium" style="margin-top:8px;"></div></div>
                    <div class="stat-card"><div class="skeleton-line short"></div><div class="skeleton-line medium" style="margin-top:8px;"></div></div>
                    <div class="stat-card"><div class="skeleton-line short"></div><div class="skeleton-line medium" style="margin-top:8px;"></div></div>
                `;
            }
            if (prSummaries) {
                prSummaries.innerHTML = `<div class="skeleton-shimmer"><div class="skeleton-line full"></div><div class="skeleton-line long"></div></div>`;
            }
        }

        try {
            const res = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    diff: diffText,
                    title: title,
                    session_id: "default"
                })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "PR analysis failed.");
            }

            const data = await res.json();
            renderPRResults(data);
            showToast("Pull request analysis complete", "success");
        } catch (err) {
            if (prResultsContainer) {
                prResultsContainer.innerHTML = `
                    <div class="alert-banner error" style="margin-top: 16px;">
                        <i class="fa-solid fa-triangle-exclamation"></i>
                        <div>
                            <strong>Pull Request Review Failed</strong>
                            <div style="font-size: 11px; margin-top: 2px;">${escapeHtml(err.message)}</div>
                        </div>
                    </div>
                `;
            }
            showToast(err.message, "error", "PR Review Error");
        } finally {
            if (btnEl) {
                btnEl.disabled = false;
                btnEl.innerHTML = btnLabel;
            }
        }
    }

    if (prForm) {
        prForm.addEventListener("submit", () => {
            runPR("/api/pr/analyze", prAnalyzeBtn, `<i class="fa-solid fa-magnifying-glass-chart"></i> Analyze Pull Request`);
        });
    }
    if (prReviewBtn) {
        prReviewBtn.addEventListener("click", () => {
            runPR("/api/pr/review", prReviewBtn, `<i class="fa-solid fa-robot"></i> Run PR Review Agent`);
        });
    }

    function renderPRResults(data) {
        if (prEmptyState) prEmptyState.style.display = "none";
        if (prResultsContainer) prResultsContainer.style.display = "block";

        const analysis = data.analysis || data;

        // Metric cards
        if (prMetricsBar) {
            const riskClass = analysis.risk_score > 60 ? "stat-card stat-card-danger" : "stat-card";
            prMetricsBar.innerHTML = `
                <div class="stat-card">
                    <span class="stat-card-label">Files Changed</span>
                    <span class="stat-card-value">${analysis.total_files_changed || 0}</span>
                </div>
                <div class="stat-card">
                    <span class="stat-card-label">Additions / Deletions</span>
                    <span class="stat-card-value" style="font-size: 20px;">
                        <span style="color: var(--color-success);">+${analysis.total_additions || 0}</span> /
                        <span style="color: var(--color-danger);">-${analysis.total_deletions || 0}</span>
                    </span>
                </div>
                <div class="stat-card">
                    <span class="stat-card-label">Blast Radius</span>
                    <span class="stat-card-value">${(analysis.blast_radius_score || 0).toFixed(1)}</span>
                </div>
                <div class="${riskClass}">
                    <span class="stat-card-label">Risk Score</span>
                    <span class="stat-card-value" style="color: ${analysis.risk_score > 60 ? 'var(--color-danger)' : 'var(--accent-primary)'};">
                        ${(analysis.risk_score || 0).toFixed(0)}/100
                    </span>
                </div>
            `;
        }

        // Summaries
        if (prSummaries) {
            const summary = data.summary || analysis.summary || {};
            prSummaries.innerHTML = `
                <div class="dev-card" style="margin-bottom: 12px;">
                    <div class="dev-card-header"><h3><i class="fa-solid fa-clipboard-check"></i> Executive Summary</h3></div>
                    <div class="dev-card-body"><p style="line-height: 1.5;">${escapeHtml(summary.executive_summary || "Diff analyzed.")}</p></div>
                </div>
            `;
        }

        // Subpanel 1: Files & Symbols
        const subFiles = document.getElementById("pr-sub-files");
        if (subFiles) {
            const files = analysis.changed_files || [];
            subFiles.innerHTML = `
                <div class="dev-card">
                    <div class="dev-card-header"><h3>Changed Files (${files.length})</h3></div>
                    <div class="dev-card-body" style="padding: 0;">
                        <table class="dev-table">
                            <thead><tr><th>File Path</th><th>Change Type</th><th>Additions</th><th>Deletions</th><th>Symbols</th></tr></thead>
                            <tbody>
                                ${files.map(f => `
                                    <tr>
                                        <td><code style="font-family: var(--font-mono); font-size: 11px;">${escapeHtml(f.file_path)}</code></td>
                                        <td><span class="badge">${escapeHtml(f.status)}</span></td>
                                        <td style="color: var(--color-success); font-family: var(--font-mono);">+${f.additions}</td>
                                        <td style="color: var(--color-danger); font-family: var(--font-mono);">-${f.deletions}</td>
                                        <td>${(f.symbols_modified || []).map(s => `<span class="badge badge-purple">${escapeHtml(s)}</span>`).join(" ") || '<span class="text-muted">None</span>'}</td>
                                    </tr>
                                `).join("")}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }

        // Subpanel 2: Architecture Impact
        const subArch = document.getElementById("pr-sub-arch");
        if (subArch) {
            const downstream = analysis.downstream_impacted_files || [];
            subArch.innerHTML = `
                <div class="dev-card">
                    <div class="dev-card-header"><h3>Downstream Impacted Files (${downstream.length})</h3></div>
                    <div class="dev-card-body">
                        <div class="tag-cloud">
                            ${downstream.map(d => `<span class="badge" style="font-family: var(--font-mono);">${escapeHtml(d)}</span>`).join("") || '<p class="placeholder-text">No downstream files affected.</p>'}
                        </div>
                    </div>
                </div>
            `;
        }

        // Subpanel 3: Test Impact
        const subTests = document.getElementById("pr-sub-tests");
        if (subTests) {
            const testImpact = analysis.test_impact || {};
            const existing = testImpact.existing_tests_to_run || [];
            const suggested = testImpact.suggested_new_tests || [];
            subTests.innerHTML = `
                <div class="overview-split">
                    <div class="dev-card">
                        <div class="dev-card-header"><h3>Existing Tests to Run (${existing.length})</h3></div>
                        <div class="dev-card-body">
                            <ul style="margin-left: 16px; font-size: 12px; line-height: 1.6;">
                                ${existing.map(t => `<li><code style="font-family: var(--font-mono);">${escapeHtml(t)}</code></li>`).join("") || '<span class="text-muted">No tests impacted.</span>'}
                            </ul>
                        </div>
                    </div>
                    <div class="dev-card">
                        <div class="dev-card-header"><h3>Suggested New Tests (${suggested.length})</h3></div>
                        <div class="dev-card-body">
                            <ul style="margin-left: 16px; font-size: 12px; line-height: 1.6;">
                                ${suggested.map(t => `<li>${escapeHtml(t)}</li>`).join("") || '<span class="text-muted">No test gaps detected.</span>'}
                            </ul>
                        </div>
                    </div>
                </div>
            `;
        }

        // Subpanel 4: Security Risks
        const subSec = document.getElementById("pr-sub-security");
        if (subSec) {
            const vulns = analysis.vulnerabilities || [];
            subSec.innerHTML = `
                <div class="dev-card">
                    <div class="dev-card-header"><h3>Diff Security Findings (${vulns.length})</h3></div>
                    <div class="dev-card-body">
                        ${vulns.length === 0 ? '<div class="empty-state"><i class="fa-solid fa-circle-check" style="color:var(--color-success);"></i><h3>Clean Patch</h3><p>No secrets, command injections, or unsafe eval calls detected.</p></div>' : ''}
                        ${vulns.map(v => `
                            <div class="review-comment-card" style="border-left-color: var(--color-danger); margin-bottom: 10px;">
                                <div style="display:flex; justify-content:space-between; margin-bottom: 4px;">
                                    <span class="badge badge-red">${escapeHtml(v.severity || 'HIGH')}</span>
                                    <span style="font-family: var(--font-mono); font-size: 11px;">${escapeHtml(v.file_path)}:${v.line_number || 1}</span>
                                </div>
                                <strong style="font-size: 13px;">${escapeHtml(v.rule_id)}</strong>
                                <p style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">${escapeHtml(v.description)}</p>
                            </div>
                        `).join("")}
                    </div>
                </div>
            `;
        }

        // Subpanel 5: Review Comments
        const subComments = document.getElementById("pr-sub-comments");
        if (subComments) {
            const review = data.review || {};
            const comments = review.comments || [];
            subComments.innerHTML = `
                <div class="dev-card">
                    <div class="dev-card-header"><h3>Automated Code Review Comments (${comments.length})</h3></div>
                    <div class="dev-card-body">
                        ${comments.length === 0 ? '<div class="empty-state"><i class="fa-solid fa-thumbs-up" style="color:var(--color-success);"></i><h3>Looks Good to Merge!</h3><p>No critical code style or architectural regressions noted.</p></div>' : ''}
                        ${comments.map(c => `
                            <div class="review-comment-card">
                                <div style="display:flex; justify-content:space-between; margin-bottom: 4px;">
                                    <span class="badge badge-purple">${escapeHtml(c.category || 'Quality')}</span>
                                    <span style="font-family: var(--font-mono); font-size: 11px;">${escapeHtml(c.file_path)}:${c.line_number || 1}</span>
                                </div>
                                <p style="font-size: 12px; color: var(--text-primary); line-height: 1.5;">${escapeHtml(c.comment)}</p>
                                ${c.suggested_code ? `<pre style="margin-top: 8px; background: var(--bg-subtle); padding: 8px; border-radius: var(--radius-sm); font-family: var(--font-mono); font-size: 11px;"><code>${escapeHtml(c.suggested_code)}</code></pre>` : ''}
                            </div>
                        `).join("")}
                    </div>
                </div>
            `;
        }
    }

    // =========================================================================
    // MODAL 2: ONBOARDING GUIDE GENERATOR
    // =========================================================================
    if (generateGuideBtn) {
        generateGuideBtn.addEventListener("click", async () => {
            if (!currentSession) {
                showToast("Please analyze a repository first.", "warning");
                return;
            }

            generateGuideBtn.disabled = true;
            generateGuideBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Generating Guide...`;
            if (guideContent) {
                guideContent.innerHTML = `
                    <div class="skeleton-shimmer" style="padding: 16px;">
                        <div class="skeleton-line full" style="height: 18px; margin-bottom: 8px;"></div>
                        <div class="skeleton-line long"></div>
                        <div class="skeleton-line medium"></div>
                        <div class="skeleton-line full" style="margin-top: 14px;"></div>
                        <div class="skeleton-line long"></div>
                        <div class="skeleton-line medium"></div>
                    </div>
                `;
            }

            try {
                const res = await fetch("/api/generate-guide", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ session_id: "default" })
                });

                if (!res.ok) throw new Error("Guide generation failed.");
                const data = await res.json();
                if (guideContent) guideContent.innerHTML = marked.parse(data.guide);
                showToast("Onboarding guide generated successfully", "success");
            } catch (err) {
                if (guideContent) {
                    guideContent.innerHTML = `
                        <div class="alert-banner error">
                            <i class="fa-solid fa-triangle-exclamation"></i>
                            <div>
                                <strong>Guide Generation Failed</strong>
                                <div>${escapeHtml(err.message)}</div>
                            </div>
                        </div>
                    `;
                }
                showToast(err.message, "error", "Guide Generation Failed");
            } finally {
                generateGuideBtn.disabled = false;
                generateGuideBtn.innerHTML = `<i class="fa-solid fa-sparkles"></i> Regenerate Guide`;
            }
        });
    }
});
