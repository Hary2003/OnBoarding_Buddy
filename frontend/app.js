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

    const agentForm = document.getElementById("agent-form");
    const agentInput = document.getElementById("agent-input");
    const agentExploreBtn = document.getElementById("agent-explore-btn");
    const agentTrace = document.getElementById("agent-trace");
    const agentAnswer = document.getElementById("agent-answer");
    const agentFiles = document.getElementById("agent-files");
    const agentSources = document.getElementById("agent-sources");
    const agentSummary = document.getElementById("agent-summary");

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

            if (btn.dataset.tab === "graph-tab") {
                if (!currentSession) {
                    fetch("/api/index?session_id=default")
                        .then(r => r.ok ? r.json() : null)
                        .then(data => { if (data) currentSession = data; })
                        .catch(() => {});
                }
                setTimeout(() => {
                    renderDependencyGraph();
                }, 60);
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

        if (typeof vis === 'undefined') {
            container.innerHTML = `<div class="empty-state"><p style="color: var(--accent-rose);"><i class="fa-solid fa-triangle-exclamation"></i> Vis.js library could not be loaded. Please check network connection.</p></div>`;
            return;
        }

        const filterType = graphFilterSelect ? graphFilterSelect.value : "all";
        const layoutType = graphLayoutSelect ? graphLayoutSelect.value : "force";
        const includeExt = graphExternalChk ? graphExternalChk.checked : true;

        try {
            // Show loading placeholder if canvas is not yet initialized
            if (!container.querySelector("canvas")) {
                container.innerHTML = `<div class="empty-state"><i class="fa-solid fa-spinner fa-spin"></i><p>Loading dependency network (${filterType})...</p></div>`;
            }

            const res = await fetch(`/api/graph?session_id=default&filter_type=${filterType}&include_external=${includeExt}`);
            const data = await res.json();

            if (!data.nodes || data.nodes.length === 0) {
                if (networkGraph) {
                    networkGraph.destroy();
                    networkGraph = null;
                }
                container.innerHTML = `<div class="empty-state"><p>No dependency nodes found for filter: <strong>${filterType}</strong></p><p style="font-size:12px; color:var(--text-muted); margin-top:8px;">Try switching to <em>All Files & Modules</em> or click Reset View.</p></div>`;
                return;
            }

            // Clear container
            container.innerHTML = "";

            const nodesDataSet = new vis.DataSet(data.nodes.map(n => {
                const baseSize = 15;
                const sizeBonus = Math.min(26, (n.in_degree || 0) * 4);
                const finalSize = baseSize + sizeBonus;

                let nodeColor = '#06b6d4'; // default cyan
                if (n.language === 'python') nodeColor = '#6366f1';
                else if (n.language === 'javascript' || n.language === 'typescript') nodeColor = '#f59e0b';
                else if (n.node_type === 'external_package') nodeColor = '#8b5cf6';
                if (n.is_entry_point) nodeColor = '#10b981';
                if (n.is_circular) nodeColor = '#f43f5e';

                return {
                    id: String(n.id),
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
                from: String(e.from),
                to: String(e.to),
                arrows: 'to',
                color: { color: e.edge_type === 'external_package' ? 'rgba(139,92,246,0.35)' : 'rgba(99,102,241,0.45)' },
                width: 1.2
            })));

            const graphData = { nodes: nodesDataSet, edges: edgesDataSet };
            const isTree = layoutType === 'tree';

            const options = {
                autoResize: true,
                layout: isTree ? {
                    hierarchical: {
                        enabled: true,
                        direction: 'UD',
                        sortMethod: 'hubsize',
                        levelSeparation: 130,
                        nodeSpacing: 160,
                        treeSpacing: 220,
                        blockShifting: true,
                        edgeMinimization: true,
                        parentCentralization: true
                    }
                } : {
                    hierarchical: { enabled: false }
                },
                physics: isTree ? {
                    enabled: true,
                    solver: 'hierarchicalRepulsion',
                    hierarchicalRepulsion: {
                        nodeDistance: 150,
                        centralGravity: 0.0,
                        springLength: 110,
                        springConstant: 0.01,
                        damping: 0.09
                    },
                    stabilization: { iterations: 120, updateInterval: 25 }
                } : {
                    enabled: true,
                    solver: 'forceAtlas2Based',
                    forceAtlas2Based: {
                        gravitationalConstant: -35,
                        centralGravity: 0.01,
                        springLength: 110,
                        springConstant: 0.08,
                        damping: 0.4,
                        avoidOverlap: 0.6
                    },
                    stabilization: { iterations: 140, updateInterval: 25 }
                },
                interaction: {
                    hover: true,
                    tooltipDelay: 100,
                    zoomView: true,
                    dragView: true,
                    navigationButtons: true
                }
            };

            if (networkGraph) {
                networkGraph.destroy();
                networkGraph = null;
            }
            networkGraph = new vis.Network(container, graphData, options);

            // Fit graph view once stabilized
            networkGraph.once("stabilizationIterationsDone", () => {
                networkGraph.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });
            });

            // Fallback fit in case stabilization finishes instantly
            setTimeout(() => {
                if (networkGraph) {
                    networkGraph.setSize('100%', '100%');
                    networkGraph.redraw();
                    networkGraph.fit();
                }
            }, 300);

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
            container.innerHTML = `<div class="empty-state"><p style="color: var(--accent-rose);"><i class="fa-solid fa-triangle-exclamation"></i> Graph error: ${err.message}</p></div>`;
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

    // Agentic Repository Explorer
    if (agentForm) {
        agentForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const query = agentInput ? agentInput.value.trim() : "";
            if (!query) return;

            if (agentExploreBtn) {
                agentExploreBtn.disabled = true;
                agentExploreBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Exploring...`;
            }
            if (agentTrace) {
                agentTrace.innerHTML = `<div class="trace-item running"><i class="fa-solid fa-spinner fa-spin"></i><span>Starting read-only repository investigation...</span></div>`;
            }
            if (agentAnswer) {
                agentAnswer.innerHTML = `<div class="empty-state large"><i class="fa-solid fa-spinner fa-spin"></i><h3>Collecting repository evidence...</h3></div>`;
            }
            if (agentFiles) agentFiles.innerHTML = "";
            if (agentSources) agentSources.innerHTML = "";
            if (agentSummary) agentSummary.innerHTML = "";

            try {
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
                    renderFilesIndex(currentSession.files);
                }

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
                    agentTrace.innerHTML = `<div class="trace-item error"><i class="fa-solid fa-triangle-exclamation"></i><span>${escapeHtml(err.message)}</span></div>`;
                }
                if (agentAnswer) {
                    agentAnswer.innerHTML = `<div class="empty-state"><p style="color: var(--accent-rose);">Error: ${escapeHtml(err.message)}</p></div>`;
                }
            } finally {
                if (agentExploreBtn) {
                    agentExploreBtn.disabled = false;
                    agentExploreBtn.innerHTML = `<i class="fa-solid fa-magnifying-glass-location"></i> Explore Repository`;
                }
            }
        });
    }

    function renderAgentResult(data) {
        if (agentTrace) {
            agentTrace.innerHTML = (data.trace || []).map(event => {
                const icon = event.status === "success" || event.status === "complete" ? "fa-check" :
                    event.status === "error" ? "fa-triangle-exclamation" :
                    event.status === "running" ? "fa-spinner fa-spin" : "fa-circle";
                return `
                    <div class="trace-item ${event.status}">
                        <i class="fa-solid ${icon}"></i>
                        <span>${escapeHtml(event.description)}</span>
                        ${event.tool ? `<code>${escapeHtml(event.tool)}</code>` : ""}
                    </div>
                `;
            }).join("");
        }

        if (agentAnswer) {
            agentAnswer.innerHTML = `<h3>Answer</h3>${marked.parse(data.answer || "No answer generated.")}`;
        }

        if (agentFiles) {
            agentFiles.innerHTML = `
                <h3>Relevant Files</h3>
                <div class="agent-chip-list">${(data.files_inspected || []).map(path => `<span class="badge">${escapeHtml(path)}</span>`).join("") || `<span class="text-muted">No files inspected.</span>`}</div>
            `;
        }

        if (agentSources) {
            agentSources.innerHTML = `
                <h3>Sources</h3>
                <div class="agent-source-list">
                    ${(data.sources || []).map(src => {
                        const symbol = src.symbol_name ? `::${src.symbol_name}` : "";
                        const line = src.line_number ? `:${src.line_number}` : "";
                        return `<div class="agent-source"><code>${escapeHtml(src.file_path + symbol + line)}</code><span>${escapeHtml(src.relevance_reason || "")}</span></div>`;
                    }).join("") || `<span class="text-muted">No source attributions collected.</span>`}
                </div>
            `;
        }

        if (agentSummary) {
            const meta = data.metadata || {};
            agentSummary.innerHTML = `
                <h3>Investigation Summary</h3>
                <p class="text-muted">Iterations: ${data.iterations || 0} | Tool calls: ${meta.tool_calls || 0} | Tools: ${(data.tools_used || []).join(", ") || "none"}</p>
            `;
        }
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
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

    // --- M7 Pull Request Intelligence Logic ---
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

    const SAMPLE_FEATURE_DIFF = `diff --git a/services/auth_service.py b/services/auth_service.py
new file mode 100644
index 0000000..e69de29
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
     # Added dangerous dynamic evaluation and shell execution
+    api_key = "AIzaSyD-TESTING-SECRET-KEY-12345678"
+    eval(query_param)
+    import subprocess
+    subprocess.Popen("cat /etc/passwd", shell=True)
+    import requests
+    requests.get(user_url, verify=False)
+    return {"status": "generated"}
`;

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

    const loadFeatureBtn = document.getElementById("pr-load-feature-btn");
    const loadVulnBtn = document.getElementById("pr-load-vuln-btn");
    const loadArchBtn = document.getElementById("pr-load-arch-btn");

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
                if (p.id === targetId) {
                    p.style.display = "block";
                    p.classList.add("active");
                } else {
                    p.style.display = "none";
                    p.classList.remove("active");
                }
            });
        });
    });

    async function runPRAnalysis(runReview = false) {
        const diffText = (prDiffInput ? prDiffInput.value : "").trim();
        if (!diffText) {
            alert("Please paste a git diff patch or upload a .diff file first.");
            return;
        }

        const endpoint = runReview ? "/api/pr/review" : "/api/pr/analyze";
        const title = prTitleInput ? prTitleInput.value.trim() : "";
        const originalText = runReview ? (prReviewBtn ? prReviewBtn.innerHTML : "") : (prAnalyzeBtn ? prAnalyzeBtn.innerHTML : "");

        if (runReview && prReviewBtn) {
            prReviewBtn.disabled = true;
            prReviewBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Reviewing...';
        } else if (prAnalyzeBtn) {
            prAnalyzeBtn.disabled = true;
            prAnalyzeBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analyzing...';
        }

        try {
            const res = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ diff: diffText, title: title, session_id: "default" })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Failed to analyze PR diff.");
            }

            const data = await res.json();
            renderPRResults(data, runReview);
        } catch (err) {
            alert(`PR Analysis Error: ${err.message}`);
        } finally {
            if (runReview && prReviewBtn) {
                prReviewBtn.disabled = false;
                prReviewBtn.innerHTML = originalText;
            } else if (prAnalyzeBtn) {
                prAnalyzeBtn.disabled = false;
                prAnalyzeBtn.innerHTML = originalText;
            }
        }
    }

    if (prForm) {
        prForm.addEventListener("submit", (e) => {
            e.preventDefault();
            runPRAnalysis(false);
        });
    }

    if (prReviewBtn) {
        prReviewBtn.addEventListener("click", (e) => {
            e.preventDefault();
            runPRAnalysis(true);
        });
    }

    function renderPRResults(data, isReview = false) {
        if (prEmptyState) prEmptyState.style.display = "none";
        if (prResultsContainer) prResultsContainer.style.display = "block";

        const summary = data.summary || {};
        const verdict = isReview ? data.verdict : (summary.risk_level === "Critical" || summary.risk_level === "High" ? "REQUEST_CHANGES" : (summary.risk_level === "Medium" ? "COMMENT" : "APPROVE"));
        const risks = data.risks || [];
        const fileChanges = data.file_changes || [];
        const archImpact = data.architecture_impact || {};
        const testRec = data.test_recommendations || {};
        const comments = data.review_comments || [];

        let verdictColor = verdict === "APPROVE" ? "#10b981" : (verdict === "REQUEST_CHANGES" ? "#ef4444" : "#f59e0b");
        let riskColor = summary.risk_level === "Critical" ? "#ef4444" : (summary.risk_level === "High" ? "#f97316" : (summary.risk_level === "Medium" ? "#f59e0b" : "#10b981"));

        if (prMetricsBar) {
            prMetricsBar.innerHTML = `
                <div class="pr-metric-card">
                    <span class="label">Verdict</span>
                    <span class="value" style="color: ${verdictColor}; font-size: 15px;"><i class="fa-solid fa-stamp"></i> ${verdict}</span>
                </div>
                <div class="pr-metric-card">
                    <span class="label">Change Type</span>
                    <span class="value" style="text-transform: capitalize; font-size: 15px; color: var(--accent-cyan);">${(summary.change_type || "feature").replace('_', ' ')}</span>
                </div>
                <div class="pr-metric-card">
                    <span class="label">Risk Level</span>
                    <span class="value" style="color: ${riskColor}; font-size: 15px;">${summary.risk_level || "Low"}</span>
                </div>
                <div class="pr-metric-card">
                    <span class="label">Files Changed</span>
                    <span class="value">${summary.files_changed || fileChanges.length || 0}</span>
                </div>
                <div class="pr-metric-card">
                    <span class="label">Additions</span>
                    <span class="value" style="color: #10b981;">+${summary.lines_added || 0}</span>
                </div>
                <div class="pr-metric-card">
                    <span class="label">Deletions</span>
                    <span class="value" style="color: #ef4444;">-${summary.lines_removed || 0}</span>
                </div>
            `;
        }

        if (prSummaries) {
            prSummaries.innerHTML = `
                <div class="pr-summary-card">
                    <h4><i class="fa-solid fa-briefcase"></i> Executive Summary</h4>
                    <p>${summary.executive_summary || "No executive summary generated."}</p>
                </div>
                <div class="pr-summary-card">
                    <h4><i class="fa-solid fa-code"></i> Developer Summary</h4>
                    <div style="font-size: 12px; line-height: 1.5; color: var(--text-secondary); white-space: pre-line;">${summary.developer_summary || "No technical summary generated."}</div>
                </div>
            `;
        }

        const subFiles = document.getElementById("pr-sub-files");
        if (subFiles) {
            if (!fileChanges.length) {
                subFiles.innerHTML = `<p class="text-muted" style="padding: 10px;">No parsed file changes available.</p>`;
            } else {
                subFiles.innerHTML = fileChanges.map(fc => `
                    <div class="pr-file-card">
                        <div class="pr-file-header">
                            <div>
                                <span class="badge" style="margin-right: 6px; font-size: 10px; text-transform: uppercase;">${fc.status}</span>
                                <span class="pr-file-path">${fc.file_path}</span>
                            </div>
                            <div class="pr-diff-stat">
                                <span class="add">+${fc.additions}</span> / <span class="del">-${fc.deletions}</span>
                            </div>
                        </div>
                        ${fc.modified_symbols && fc.modified_symbols.length ? `
                            <div style="margin-top: 8px; font-size: 12px; color: var(--text-muted);">
                                <strong>Symbols:</strong> ${fc.modified_symbols.map(s => `<code style="background: rgba(255,255,255,0.08); padding: 2px 6px; border-radius: 3px; color: #a5b4fc;">${s}</code>`).join(' ')}
                            </div>
                        ` : ''}
                    </div>
                `).join('');
            }
        }

        const subArch = document.getElementById("pr-sub-arch");
        if (subArch) {
            subArch.innerHTML = `
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px;">
                    <div class="glass-panel" style="padding: 14px;">
                        <h4 style="margin-top:0; font-size: 13px; color: var(--accent-cyan);"><i class="fa-solid fa-layer-group"></i> Layers Touched</h4>
                        <p style="font-size: 12px; color: var(--text-secondary);">${archImpact.architectural_layers && archImpact.architectural_layers.length ? archImpact.architectural_layers.join(', ') : 'Standard'}</p>
                        <h4 style="margin-top: 10px; font-size: 13px; color: var(--accent-cyan);"><i class="fa-solid fa-door-open"></i> Impacted Entry Points</h4>
                        <p style="font-size: 12px; color: var(--text-secondary);">${archImpact.affected_entry_points && archImpact.affected_entry_points.length ? archImpact.affected_entry_points.map(e => `<code>${e}</code>`).join(', ') : 'None'}</p>
                    </div>
                    <div class="glass-panel" style="padding: 14px;">
                        <h4 style="margin-top:0; font-size: 13px; color: var(--accent-cyan);"><i class="fa-solid fa-arrow-up-right-dots"></i> Coupling Impact Score</h4>
                        <p style="font-size: 18px; font-weight: 700; color: #a5b4fc; margin: 4px 0;">${archImpact.coupling_increase_score || 0} / 10.0</p>
                        <h4 style="margin-top: 10px; font-size: 13px; color: var(--accent-cyan);"><i class="fa-solid fa-arrows-split-up-and-left"></i> Upstream Blast Radius</h4>
                        <p style="font-size: 12px; color: var(--text-secondary);">${archImpact.upstream_impact && archImpact.upstream_impact.length ? `${archImpact.upstream_impact.length} dependent file(s)` : 'Isolated component'}</p>
                    </div>
                </div>
                ${archImpact.layer_violations && archImpact.layer_violations.length ? `
                    <div class="pr-risk-item" style="border-left: 4px solid #ef4444;">
                        <h4 style="margin:0 0 6px 0; color: #ef4444; font-size: 13px;"><i class="fa-solid fa-triangle-exclamation"></i> Architectural Layer Violations Detected</h4>
                        ${archImpact.layer_violations.map(v => `<p style="font-size: 12px; margin: 4px 0; color: #fca5a5;">${v}</p>`).join('')}
                    </div>
                ` : '<div class="glass-panel" style="padding: 12px; color: #10b981; font-size: 12.5px;"><i class="fa-solid fa-circle-check"></i> No architectural layer violations detected.</div>'}
            `;
        }

        const subTests = document.getElementById("pr-sub-tests");
        if (subTests) {
            subTests.innerHTML = `
                ${testRec.missing_tests && testRec.missing_tests.length ? `
                    <div class="pr-risk-item Medium" style="margin-bottom: 14px;">
                        <h4 style="margin:0 0 6px 0; color: #f59e0b; font-size: 13px;"><i class="fa-solid fa-circle-exclamation"></i> Missing Test Warnings</h4>
                        ${testRec.missing_tests.map(m => `<p style="font-size: 12px; margin: 4px 0; color: #fde68a;">${m}</p>`).join('')}
                    </div>
                ` : ''}
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
                    <div class="glass-panel" style="padding: 14px;">
                        <h4 style="margin-top:0; font-size: 13px; color: var(--accent-cyan);"><i class="fa-solid fa-vial-circle-check"></i> Recommended Tests to Run</h4>
                        ${testRec.recommended_test_files && testRec.recommended_test_files.length ? `
                            <ul style="padding-left: 18px; margin: 4px 0; font-size: 12px; color: var(--text-secondary);">
                                ${testRec.recommended_test_files.map(t => `<li><code>${t}</code></li>`).join('')}
                            </ul>
                        ` : '<p style="font-size: 12px; color: var(--text-muted);">No specific test files identified.</p>'}
                    </div>
                    <div class="glass-panel" style="padding: 14px;">
                        <h4 style="margin-top:0; font-size: 13px; color: var(--accent-cyan);"><i class="fa-solid fa-list-check"></i> Recommended Scenarios & Edge Cases</h4>
                        ${testRec.recommended_scenarios && testRec.recommended_scenarios.length ? `
                            <ul style="padding-left: 18px; margin: 4px 0; font-size: 12px; color: var(--text-secondary);">
                                ${testRec.recommended_scenarios.slice(0, 4).map(s => `<li>${s}</li>`).join('')}
                                ${testRec.recommended_edge_cases ? testRec.recommended_edge_cases.slice(0, 3).map(e => `<li style="color: #cbd5e1;"><em>Edge case:</em> ${e}</li>`).join('') : ''}
                            </ul>
                        ` : '<p style="font-size: 12px; color: var(--text-muted);">No custom test scenarios needed.</p>'}
                    </div>
                </div>
            `;
        }

        const subSecurity = document.getElementById("pr-sub-security");
        if (subSecurity) {
            if (!risks.length) {
                subSecurity.innerHTML = `<div class="glass-panel" style="padding: 14px; color: #10b981; font-size: 13px;"><i class="fa-solid fa-shield-check"></i> Static security review passed: 0 vulnerabilities found in PR diff.</div>`;
            } else {
                subSecurity.innerHTML = risks.map(r => `
                    <div class="pr-risk-item ${r.severity}">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <strong style="color: ${r.severity === 'Critical' ? '#ef4444' : (r.severity === 'High' ? '#f97316' : '#f59e0b')}; font-size: 13.5px;"><i class="fa-solid fa-bug"></i> ${r.title}</strong>
                            <span class="badge" style="background: ${r.severity === 'Critical' ? '#ef4444' : '#f59e0b'}; color: white; font-size: 10px;">${r.severity.toUpperCase()}</span>
                        </div>
                        <p style="font-size: 12px; margin: 2px 0 6px 0; color: var(--text-secondary);">File: <code>${r.file_path}${r.line_number ? `:${r.line_number}` : ''}</code></p>
                        ${r.evidence ? `<pre style="background: rgba(0,0,0,0.4); padding: 8px; border-radius: 4px; font-size: 11.5px; color: #fca5a5; overflow-x: auto;">${r.evidence}</pre>` : ''}
                        <p style="font-size: 12px; margin-top: 6px; color: #6ee7b7;"><strong>Remediation:</strong> ${r.remediation}</p>
                    </div>
                `).join('');
            }
        }

        const subComments = document.getElementById("pr-sub-comments");
        if (subComments) {
            if (!comments.length) {
                subComments.innerHTML = `<div class="glass-panel" style="padding: 14px; color: #10b981; font-size: 13px;"><i class="fa-solid fa-thumbs-up"></i> No actionable review comments generated. Code looks ready to merge.</div>`;
            } else {
                subComments.innerHTML = comments.map(c => `
                    <div class="pr-comment-card ${c.severity || 'warning'}">
                        <div class="pr-comment-header">
                            <span class="pr-comment-title"><i class="fa-solid fa-comment-dots"></i> ${c.title}</span>
                            <div>
                                <span class="badge" style="font-size: 10px; margin-right: 6px; text-transform: uppercase;">${c.severity}</span>
                                <code>${c.file_path}${c.line_number ? `:${c.line_number}` : ''}</code>
                            </div>
                        </div>
                        <p style="font-size: 12.5px; line-height: 1.5; color: var(--text-secondary); margin: 6px 0;">${c.body}</p>
                        ${c.evidence ? `<div class="pr-comment-evidence">${c.evidence}</div>` : ''}
                        ${c.recommendation ? `<div class="pr-comment-recommendation"><strong>Recommendation:</strong> ${c.recommendation}</div>` : ''}
                    </div>
                `).join('');
            }
        }
    }
});
