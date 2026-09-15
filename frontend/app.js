document.addEventListener("DOMContentLoaded", () => {
    // State Variables
    let currentSession = null;
    let selectedFilePath = null;
    let networkGraph = null;
    let currentInspectorNode = null;

    // DOM Elements
    const repoForm = document.getElementById("repo-form");
    const repoInput = document.getElementById("repo-input");
    const analyzeBtn = document.getElementById("analyze-btn");
    const groqStatus = document.getElementById("groq-status");
    
    const treeContainer = document.getElementById("tree-container");
    const fileCount = document.getElementById("file-count");
    const currentFilename = document.getElementById("current-filename");
    const codeContent = document.getElementById("code-content");
    const summarizeBtn = document.getElementById("summarize-btn");
    const summaryText = document.getElementById("summary-text");
    
    const generateGuideBtn = document.getElementById("generate-guide-btn");
    const guideContent = document.getElementById("guide-content");
    
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
    
    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("chat-input");
    const chatMessages = document.getElementById("chat-messages");

    const contribForm = document.getElementById("contribution-form");
    const issueTitle = document.getElementById("issue-title");
    const issueDesc = document.getElementById("issue-desc");
    const analyzeContribBtn = document.getElementById("analyze-contrib-btn");
    const contributionContent = document.getElementById("contribution-content");
    const auditRepoBtn = document.getElementById("audit-repo-btn");
    const auditOpportunitiesContainer = document.getElementById("audit-opportunities-container");

    // Check Backend Health & Groq Status on Startup
    async function checkHealth() {
        try {
            const res = await fetch("/api/health");
            const data = await res.json();
            if (data.groq_configured) {
                groqStatus.innerHTML = `<span class="pulse-dot green"></span> Groq AI Connected (${data.groq_model})`;
            } else {
                groqStatus.innerHTML = `<span class="pulse-dot red"></span> Groq API Key Missing (.env)`;
            }
        } catch (err) {
            groqStatus.innerHTML = `<span class="pulse-dot red"></span> Backend Offline`;
        }
    }
    checkHealth();

    // Auto-restore active session from server or auto-index default repository
    async function autoLoadSession() {
        try {
            const res = await fetch("/api/index?session_id=default");
            if (res.ok) {
                const repoIndex = await res.json();
                currentSession = repoIndex;
                fileCount.textContent = `${repoIndex.total_files} files (${repoIndex.total_lines} lines)`;
                renderFilesIndex(repoIndex.files);
                if (repoIndex.files.length > 0) {
                    const topFile = repoIndex.files.find(f => f.is_entry_point) || repoIndex.files[0];
                    loadFileContent(topFile.full_path, topFile.relative_path);
                }
            } else {
                const target = repoInput.value.trim();
                if (target) {
                    const cloneRes = await fetch("/api/clone", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ url_or_path: target })
                    });
                    if (cloneRes.ok) {
                        const repoIndex = await cloneRes.json();
                        currentSession = repoIndex;
                        fileCount.textContent = `${repoIndex.total_files} files (${repoIndex.total_lines} lines)`;
                        renderFilesIndex(repoIndex.files);
                        if (repoIndex.files.length > 0) {
                            const topFile = repoIndex.files.find(f => f.is_entry_point) || repoIndex.files[0];
                            loadFileContent(topFile.full_path, topFile.relative_path);
                        }
                    }
                }
            }
        } catch (err) {
            console.warn("Auto-load session notice:", err.message);
        }
    }
    autoLoadSession();

    // Tab Switching Logic
    const tabBtns = document.querySelectorAll(".tab-btn");
    const tabPanes = document.querySelectorAll(".tab-pane");

    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            tabBtns.forEach(b => b.classList.remove("active"));
            tabPanes.forEach(p => p.classList.remove("active"));

            btn.classList.add("active");
            const targetPane = document.getElementById(btn.dataset.tab);
            if (targetPane) targetPane.classList.add("active");

            if (btn.dataset.tab === "graph-tab" && currentSession) {
                renderDependencyGraph();
            }
        });
    });

    // Handle Repo Analysis
    repoForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const target = repoInput.value.trim();
        if (!target) return;

        analyzeBtn.disabled = true;
        analyzeBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Indexing...`;
        treeContainer.innerHTML = `<div class="empty-state"><i class="fa-solid fa-spinner fa-spin"></i><p>Parsing AST, computing activity scores, and detecting entry points...</p></div>`;

        try {
            const res = await fetch("/api/clone", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url_or_path: target })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Failed to analyze repository.");
            }

            const repoIndex = await res.json();
            currentSession = repoIndex;
            fileCount.textContent = `${repoIndex.total_files} files (${repoIndex.total_lines} lines)`;
            
            renderFilesIndex(repoIndex.files);
            analyzeBtn.disabled = false;
            analyzeBtn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Analyze Repo`;

            if (repoIndex.files.length > 0) {
                const topFile = repoIndex.files.find(f => f.is_entry_point) || repoIndex.files[0];
                loadFileContent(topFile.full_path, topFile.relative_path);
            }

        } catch (err) {
            analyzeBtn.disabled = false;
            analyzeBtn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Analyze Repo`;
            treeContainer.innerHTML = `<div class="empty-state"><i class="fa-solid fa-triangle-exclamation" style="color: var(--accent-rose);"></i><p>${err.message}</p></div>`;
        }
    });

    // Render Files List from RepositoryIndex
    function renderFilesIndex(files) {
        if (!files || files.length === 0) {
            treeContainer.innerHTML = `<div class="empty-state"><p>No supported code files found.</p></div>`;
            return;
        }

        const sortedFiles = [...files].sort((a, b) => b.activity_score - a.activity_score);

        treeContainer.innerHTML = "";
        sortedFiles.forEach(file => {
            const node = document.createElement("div");
            node.className = "tree-node";
            
            const entryBadge = file.is_entry_point 
                ? `<span class="badge badge-purple" style="font-size:10px; margin-left:4px;">🚀 Entry</span>` 
                : "";

            node.innerHTML = `
                <div class="node-info">
                    <i class="fa-regular fa-file-code"></i>
                    <span>${file.relative_path}</span>
                    ${entryBadge}
                </div>
                <span class="node-meta">Score: ${file.activity_score}</span>
            `;

            node.addEventListener("click", () => {
                document.querySelectorAll(".tree-node").forEach(n => n.classList.remove("active"));
                node.classList.add("active");
                loadFileContent(file.full_path, file.relative_path);
            });

            treeContainer.appendChild(node);
        });
    }

    // Load File Content into Code Viewer
    async function loadFileContent(fullPath, relPath) {
        selectedFilePath = fullPath;
        currentFilename.textContent = relPath;
        codeContent.textContent = "Loading file content...";
        summarizeBtn.disabled = true;
        summaryText.innerHTML = `<p class="placeholder-text">Click <strong>"Summarize with Groq AI"</strong> to generate a summary for <code>${relPath}</code>.</p>`;

        try {
            const res = await fetch(`/api/file-content?file_path=${encodeURIComponent(fullPath)}`);
            if (!res.ok) throw new Error("Failed to load file.");
            const data = await res.json();

            codeContent.textContent = data.content;
            Prism.highlightElement(codeContent);
            summarizeBtn.disabled = false;
        } catch (err) {
            codeContent.textContent = `// Error loading file: ${err.message}`;
        }
    }

    // Trigger Groq AI Summarization
    summarizeBtn.addEventListener("click", async () => {
        if (!selectedFilePath) return;

        summarizeBtn.disabled = true;
        summarizeBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Summarizing...`;
        summaryText.innerHTML = `<p class="placeholder-text"><i class="fa-solid fa-spinner fa-spin"></i> Asking Groq AI to analyze file architecture...</p>`;

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

            summaryText.innerHTML = marked.parse(data.summary);
            summarizeBtn.disabled = false;
            summarizeBtn.innerHTML = `<i class="fa-solid fa-bolt"></i> Summarize with Groq AI`;

        } catch (err) {
            summaryText.innerHTML = `<p style="color: var(--accent-rose);">❌ ${err.message}</p>`;
            summarizeBtn.disabled = false;
            summarizeBtn.innerHTML = `<i class="fa-solid fa-bolt"></i> Summarize with Groq AI`;
        }
    });

    // Generate Onboarding Guide
    generateGuideBtn.addEventListener("click", async () => {
        if (!currentSession) {
            alert("Please analyze a repository first.");
            return;
        }

        generateGuideBtn.disabled = true;
        generateGuideBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Generating Onboarding Guide...`;
        guideContent.innerHTML = `<div class="empty-state large"><i class="fa-solid fa-spinner fa-spin"></i><h3>Groq AI is building your Onboarding Guide...</h3></div>`;

        try {
            const res = await fetch("/api/generate-guide", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ session_id: "default" })
            });

            if (!res.ok) throw new Error("Guide generation failed.");
            const data = await res.json();

            guideContent.innerHTML = marked.parse(data.guide);
            generateGuideBtn.disabled = false;
            generateGuideBtn.innerHTML = `<i class="fa-solid fa-sparkles"></i> Regenerate Guide`;

        } catch (err) {
            guideContent.innerHTML = `<div class="empty-state"><p style="color: var(--accent-rose);">❌ ${err.message}</p></div>`;
            generateGuideBtn.disabled = false;
            generateGuideBtn.innerHTML = `<i class="fa-solid fa-sparkles"></i> Generate Guide with Groq`;
        }
    });

    // Render Dependency Graph (Vis Network)
    async function renderDependencyGraph() {
        const container = document.getElementById("network-graph");
        if (!container) return;

        const filterType = graphFilterSelect ? graphFilterSelect.value : "all";
        const layoutType = graphLayoutSelect ? graphLayoutSelect.value : "force";
        const includeExt = graphExternalChk ? graphExternalChk.checked : true;

        try {
            const res = await fetch(`/api/graph?session_id=default&filter_type=${filterType}&include_external=${includeExt}`);
            const data = await res.json();

            if (!data.nodes || data.nodes.length === 0) {
                container.innerHTML = `<div class="empty-state"><p>No dependency graph nodes found for filter mode: <strong>${filterType}</strong></p></div>`;
                return;
            }

            const nodesDataSet = new vis.DataSet(data.nodes.map(n => {
                // Compute size based on in_degree centrality
                const baseSize = 14;
                const sizeBonus = Math.min(24, (n.in_degree || 0) * 4);
                const finalSize = baseSize + sizeBonus;

                let nodeColor = '#06b6d4'; // default cyan
                if (n.language === 'python') nodeColor = '#6366f1';
                else if (n.language === 'javascript' || n.language === 'typescript') nodeColor = '#f59e0b';
                else if (n.node_type === 'external_package') nodeColor = '#8b5cf6';
                if (n.is_entry_point) nodeColor = '#10b981';
                if (n.is_circular) nodeColor = '#f43f5e';

                return {
                    id: n.id,
                    label: n.label,
                    title: n.title,
                    shape: n.node_type === 'external_package' ? 'box' : (n.is_entry_point ? 'diamond' : 'dot'),
                    size: finalSize,
                    color: {
                        background: nodeColor,
                        border: n.is_circular ? '#f43f5e' : '#ffffff',
                        highlight: { background: '#8b5cf6', border: '#ffffff' }
                    },
                    font: { color: '#f8fafc', face: 'Inter', size: 12 },
                    rawData: n
                };
            }));

            const edgesDataSet = new vis.DataSet(data.edges.map(e => ({
                from: e.from,
                to: e.to,
                arrows: 'to',
                color: { color: e.edge_type === 'external_package' ? 'rgba(139,92,246,0.3)' : 'rgba(99,102,241,0.3)' },
                width: 1
            })));

            const graphData = { nodes: nodesDataSet, edges: edgesDataSet };
            const options = {
                physics: layoutType === 'force' ? {
                    solver: 'forceAtlas2Based',
                    forceAtlas2Based: { gravitationalConstant: -35, centralGravity: 0.01, springLength: 100 }
                } : false,
                layout: layoutType === 'tree' ? {
                    hierarchical: { direction: 'UD', sortMethod: 'directed', levelSeparation: 120 }
                } : {},
                interaction: { hover: true, tooltipDelay: 100 }
            };

            if (networkGraph) networkGraph.destroy();
            networkGraph = new vis.Network(container, graphData, options);

            // Handle Node Select / Click
            networkGraph.on("selectNode", (params) => {
                if (params.nodes.length > 0) {
                    const selectedId = params.nodes[0];
                    const nodeObj = nodesDataSet.get(selectedId);
                    if (nodeObj && nodeObj.rawData) {
                        openNodeInspector(nodeObj.rawData);
                    }
                }
            });

            networkGraph.on("deselectNode", () => {
                closeNodeInspector();
            });

        } catch (err) {
            container.innerHTML = `<div class="empty-state"><p style="color: var(--accent-rose);">Graph error: ${err.message}</p></div>`;
        }
    }

    // Open Node Inspector Side Drawer
    function openNodeInspector(nodeData) {
        currentInspectorNode = nodeData;
        inspectorNodeTitle.textContent = nodeData.label;
        inspectorNodeType.textContent = nodeData.node_type === 'external_package' ? 'External Package' : (nodeData.is_entry_point ? '🚀 Entry Point' : 'Source File');
        
        inspectorInDegree.textContent = nodeData.in_degree || 0;
        inspectorOutDegree.textContent = nodeData.out_degree || 0;
        inspectorScore.textContent = nodeData.activity_score || 0.0;

        // Populate connected deps if session is active
        if (currentSession) {
            const fileObj = currentSession.files.find(f => f.relative_path === nodeData.path);
            if (fileObj) {
                // Dependencies list
                if (fileObj.dependencies && fileObj.dependencies.length > 0) {
                    inspectorDepsList.innerHTML = fileObj.dependencies.map(d => `<span class="badge">${d.target_path}</span>`).join("");
                } else {
                    inspectorDepsList.innerHTML = `<span class="text-muted" style="font-size:12px;">No dependencies declared.</span>`;
                }

                // Symbols list
                if (fileObj.symbols && fileObj.symbols.length > 0) {
                    inspectorSymbolsList.innerHTML = fileObj.symbols.map(s => `<span class="badge badge-purple">⚙️ ${s.name}()</span>`).join("");
                } else {
                    inspectorSymbolsList.innerHTML = `<span class="text-muted" style="font-size:12px;">No exported functions found.</span>`;
                }
            } else {
                inspectorDepsList.innerHTML = `<span class="text-muted" style="font-size:12px;">External third-party module.</span>`;
                inspectorSymbolsList.innerHTML = `<span class="text-muted" style="font-size:12px;">External package.</span>`;
            }
        }

        nodeInspector.classList.remove("hidden");
    }

    function closeNodeInspector() {
        nodeInspector.classList.add("hidden");
        currentInspectorNode = null;
    }

    if (closeInspectorBtn) {
        closeInspectorBtn.addEventListener("click", closeNodeInspector);
    }

    // Jump to Code button handler
    if (jumpCodeBtn) {
        jumpCodeBtn.addEventListener("click", () => {
            if (!currentInspectorNode || currentInspectorNode.node_type === 'external_package') {
                alert("Cannot view source code for external packages.");
                return;
            }

            // Find matching file in tree
            const targetRelPath = currentInspectorNode.path;
            const fileObj = currentSession ? currentSession.files.find(f => f.relative_path === targetRelPath) : null;
            
            if (fileObj) {
                // Switch to Code Explorer tab
                document.querySelector('.tab-btn[data-tab="explorer-tab"]').click();
                loadFileContent(fileObj.full_path, fileObj.relative_path);
            }
        });
    }

    // Toolbar Event Listeners
    if (refreshGraphBtn) refreshGraphBtn.addEventListener("click", renderDependencyGraph);
    if (graphFilterSelect) graphFilterSelect.addEventListener("change", renderDependencyGraph);
    if (graphLayoutSelect) graphLayoutSelect.addEventListener("change", renderDependencyGraph);
    if (graphExternalChk) graphExternalChk.addEventListener("change", renderDependencyGraph);

    // AI Chat Assistant
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const question = chatInput.value.trim();
        if (!question) return;

        appendMessage("user", question);
        chatInput.value = "";

        const assistantMsgEl = appendMessage("assistant", `<i class="fa-solid fa-spinner fa-spin"></i> Thinking...`);

        try {
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question: question, session_id: "default" })
            });

            if (!res.ok) throw new Error("Chat request failed.");
            const data = await res.json();

            assistantMsgEl.querySelector(".msg-bubble").innerHTML = marked.parse(data.answer);

        } catch (err) {
            assistantMsgEl.querySelector(".msg-bubble").innerHTML = `<span style="color: var(--accent-rose);">❌ ${err.message}</span>`;
        }
    });

    function appendMessage(role, text) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${role}`;
        msgDiv.innerHTML = `<div class="msg-bubble">${text}</div>`;
        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return msgDiv;
    }

    // Contribution Intelligence Runner & Preset Handlers
    async function runContributionAnalysis(e) {
        if (e && e.preventDefault) e.preventDefault();
        const title = issueTitle ? issueTitle.value.trim() : "";
        const desc = issueDesc ? issueDesc.value.trim() : "";
        if (!title) return false;

        if (analyzeContribBtn) {
            analyzeContribBtn.disabled = true;
            analyzeContribBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Analyzing Issue & Impact...`;
        }
        if (contributionContent) {
            contributionContent.innerHTML = `<div class="empty-state large"><i class="fa-solid fa-spinner fa-spin"></i><h3>Mapping issue requirements to repository files and graph impact...</h3></div>`;
        }

        try {
            async function callAnalyzeApi() {
                return await fetch("/api/contribution/analyze", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        title: title,
                        description: desc,
                        session_id: "default"
                    })
                });
            }

            if (!currentSession) {
                const target = repoInput ? repoInput.value.trim() : "d:\\onboarding";
                const cloneRes = await fetch("/api/clone", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ url_or_path: target || "d:\\onboarding" })
                });
                if (!cloneRes.ok) {
                    const err = await cloneRes.json();
                    throw new Error(err.detail || "Repository indexing failed.");
                }
                currentSession = await cloneRes.json();
                if (fileCount) fileCount.textContent = `${currentSession.total_files} files (${currentSession.total_lines} lines)`;
                if (typeof renderFilesIndex === "function") renderFilesIndex(currentSession.files);
            }

            let res = await callAnalyzeApi();

            if (res.status === 404) {
                const target = repoInput ? repoInput.value.trim() : "d:\\onboarding";
                const cloneRes = await fetch("/api/clone", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ url_or_path: target || "d:\\onboarding" })
                });
                if (cloneRes.ok) {
                    currentSession = await cloneRes.json();
                    if (fileCount) fileCount.textContent = `${currentSession.total_files} files (${currentSession.total_lines} lines)`;
                    if (typeof renderFilesIndex === "function") renderFilesIndex(currentSession.files);
                    res = await callAnalyzeApi();
                }
            }

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Contribution analysis failed.");
            }

            const data = await res.json();

            if (contributionContent) {
                const formattedHtml = typeof marked !== "undefined" && marked.parse ? marked.parse(data.plan_narrative) : data.plan_narrative;
                contributionContent.innerHTML = formattedHtml;
            }
        } catch (err) {
            if (contributionContent) {
                contributionContent.innerHTML = `<div class="empty-state"><p style="color: var(--accent-rose);">❌ ${err.message}</p></div>`;
            }
        } finally {
            if (analyzeContribBtn) {
                analyzeContribBtn.disabled = false;
                analyzeContribBtn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Analyze Contribution`;
            }
        }
        return false;
    }

    // Preset Issue Buttons Handler
    document.querySelectorAll(".preset-issue-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            if (issueTitle) issueTitle.value = btn.dataset.title || "";
            if (issueDesc) issueDesc.value = btn.dataset.desc || "";
            runContributionAnalysis(e);
        });
    });

    if (contribForm) {
        contribForm.addEventListener("submit", runContributionAnalysis);
    }

    // Open-Source Audit & Opportunity Scanner Handler
    if (auditRepoBtn) {
        auditRepoBtn.addEventListener("click", async () => {
            auditRepoBtn.disabled = true;
            auditRepoBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Auditing AST & Security...`;
            if (auditOpportunitiesContainer) {
                auditOpportunitiesContainer.style.display = "block";
                auditOpportunitiesContainer.innerHTML = `<div class="empty-state large"><i class="fa-solid fa-spinner fa-spin"></i><h3>Scanning repository AST for security risks, refactoring debt & test coverage gaps...</h3></div>`;
            }

            try {
                if (!currentSession) {
                    const target = repoInput ? repoInput.value.trim() : "d:\\onboarding";
                    const cloneRes = await fetch("/api/clone", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ url_or_path: target || "d:\\onboarding" })
                    });
                    if (cloneRes.ok) {
                        currentSession = await cloneRes.json();
                    }
                }

                const res = await fetch("/api/contribution/audit", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ session_id: "default" })
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || "Audit scanning failed.");
                }

                const auditData = await res.json();
                renderAuditReport(auditData);

            } catch (err) {
                if (auditOpportunitiesContainer) {
                    auditOpportunitiesContainer.innerHTML = `<div class="empty-state"><p style="color: var(--accent-rose);">❌ ${err.message}</p></div>`;
                }
            } finally {
                auditRepoBtn.disabled = false;
                auditRepoBtn.innerHTML = `<i class="fa-solid fa-shield-halved"></i> 🔍 Audit Repo & Find Opportunities`;
            }
        });
    }

    function renderAuditReport(auditReport) {
        if (!auditOpportunitiesContainer) return;
        if (!auditReport.opportunities || auditReport.opportunities.length === 0) {
            auditOpportunitiesContainer.innerHTML = `<div class="empty-state"><h3>✅ Excellent Repository Health!</h3><p>No critical security vulnerabilities, test gaps, or circular dependency risks detected.</p></div>`;
            return;
        }

        let html = `<div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 12px; padding: 16px; margin-bottom: 16px;">`;
        html += `<h3 style="margin-top:0; font-size: 16px; display: flex; align-items: center; gap: 8px;">🔍 Open Source Contribution Opportunities Audit Report for <code>${auditReport.repo_name}</code></h3>`;
        html += `<p style="font-size: 13px; color: #94a3b8; margin-bottom: 12px;">Identified <strong>${auditReport.total_opportunities} actionable contribution opportunities</strong> across 🔴 Critical (${auditReport.critical_count}), 🟠 High (${auditReport.high_count}), 🟡 Medium (${auditReport.medium_count}), 🔵 Low (${auditReport.low_count}). Click any opportunity card to auto-generate a full PR implementation plan.</p>`;
        html += `<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px;">`;

        auditReport.opportunities.forEach((opp) => {
            let badgeColor = "#64748b";
            if (opp.severity === "Critical") badgeColor = "#f43f5e";
            else if (opp.severity === "High") badgeColor = "#f97316";
            else if (opp.severity === "Medium") badgeColor = "#eab308";
            else if (opp.severity === "Low") badgeColor = "#3b82f6";

            const fileBadges = opp.target_files.map(f => `<span class="badge" style="font-size:10px;">${f}</span>`).join(" ");

            html += `
                <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 12px; display: flex; flex-direction: column; justify-content: space-between;">
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <span class="badge" style="background: ${badgeColor}; color: white; font-weight: 600; font-size: 11px;">${opp.severity.toUpperCase()}</span>
                            <span style="font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px;">${opp.category.replace('_', ' ')}</span>
                        </div>
                        <h4 style="margin: 4px 0 6px 0; font-size: 14px; line-height: 1.3;">${opp.title}</h4>
                        <p style="font-size: 12px; color: #cbd5e1; margin-bottom: 8px; line-height: 1.4;">${opp.description}</p>
                        <div style="margin-bottom: 10px;">${fileBadges}</div>
                    </div>
                    <button type="button" class="btn btn-secondary btn-sm select-opp-btn" data-title="${encodeURIComponent(opp.suggested_issue_title)}" data-desc="${encodeURIComponent(opp.suggested_issue_desc)}" style="width: 100%; justify-content: center; font-size: 12px;">
                        ⚡ Analyze & Generate PR Plan
                    </button>
                </div>
            `;
        });

        html += `</div></div>`;
        auditOpportunitiesContainer.innerHTML = html;

        auditOpportunitiesContainer.querySelectorAll(".select-opp-btn").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                const title = decodeURIComponent(btn.dataset.title || "");
                const desc = decodeURIComponent(btn.dataset.desc || "");
                if (issueTitle) issueTitle.value = title;
                if (issueDesc) issueDesc.value = desc;
                runContributionAnalysis(e);
            });
        });
    }
});
