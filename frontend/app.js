document.addEventListener("DOMContentLoaded", () => {
    // State Variables
    let currentSession = null;
    let selectedFilePath = null;
    let networkGraph = null;

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
    
    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("chat-input");
    const chatMessages = document.getElementById("chat-messages");

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
        analyzeBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Analyzing...`;
        treeContainer.innerHTML = `<div class="empty-state"><i class="fa-solid fa-spinner fa-spin"></i><p>Cloning & analyzing repository structure...</p></div>`;

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

            const data = await res.json();
            currentSession = data;
            fileCount.textContent = `${data.total_files} files`;
            
            renderRankedFiles(data.ranked_files);
            analyzeBtn.disabled = false;
            analyzeBtn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Analyze Repo`;

            // Auto-select first file if available
            if (data.ranked_files.length > 0) {
                loadFileContent(data.ranked_files[0].full_path, data.ranked_files[0].rel_path);
            }

        } catch (err) {
            analyzeBtn.disabled = false;
            analyzeBtn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Analyze Repo`;
            treeContainer.innerHTML = `<div class="empty-state"><i class="fa-solid fa-triangle-exclamation" style="color: var(--accent-rose);"></i><p>${err.message}</p></div>`;
        }
    });

    // Render File List Ranked by Git Activity
    function renderRankedFiles(rankedFiles) {
        if (!rankedFiles || rankedFiles.length === 0) {
            treeContainer.innerHTML = `<div class="empty-state"><p>No supported code files found.</p></div>`;
            return;
        }

        treeContainer.innerHTML = "";
        rankedFiles.forEach(file => {
            const node = document.createElement("div");
            node.className = "tree-node";
            node.innerHTML = `
                <div class="node-info">
                    <i class="fa-regular fa-file-code"></i>
                    <span>${file.rel_path}</span>
                </div>
                <span class="node-meta">${file.last_modified}</span>
            `;

            node.addEventListener("click", () => {
                document.querySelectorAll(".tree-node").forEach(n => n.classList.remove("active"));
                node.classList.add("active");
                loadFileContent(file.full_path, file.rel_path);
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

        try {
            const res = await fetch("/api/graph?session_id=default");
            const data = await res.json();

            if (!data.nodes || data.nodes.length === 0) {
                container.innerHTML = `<div class="empty-state"><p>No dependency graph data available.</p></div>`;
                return;
            }

            const nodes = new vis.DataSet(data.nodes.map(n => ({
                id: n.id,
                label: n.label,
                title: n.title,
                shape: 'dot',
                size: 16,
                color: n.group === 'python' ? '#6366f1' : (n.group === 'javascript' ? '#f59e0b' : '#06b6d4')
            })));

            const edges = new vis.DataSet(data.edges.map(e => ({
                from: e.from,
                to: e.to,
                arrows: 'to',
                color: { color: 'rgba(255,255,255,0.2)' }
            })));

            const graphData = { nodes, edges };
            const options = {
                physics: {
                    solver: 'forceAtlas2Based',
                    forceAtlas2Based: { gravitationalConstant: -30 }
                },
                interaction: { hover: true }
            };

            if (networkGraph) networkGraph.destroy();
            networkGraph = new vis.Network(container, graphData, options);

        } catch (err) {
            container.innerHTML = `<div class="empty-state"><p style="color: var(--accent-rose);">Graph error: ${err.message}</p></div>`;
        }
    }

    if (refreshGraphBtn) {
        refreshGraphBtn.addEventListener("click", renderDependencyGraph);
    }

    // AI Chat Assistant
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const question = chatInput.value.trim();
        if (!question) return;

        // Append user msg
        appendMessage("user", question);
        chatInput.value = "";

        // Placeholder assistant msg
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
});
