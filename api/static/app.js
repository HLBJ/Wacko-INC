const state = {
  projects: [],
  tasks: [],
  agents: {},
  templates: {},
  approvals: [],
  runs: [],
  buildRuns: [],
  gitStatus: null,
  jobs: [],
  jobEvents: [],
  settings: {},
  supportTickets: [],
  fileBrowser: {
    projectId: null,
    projectPath: "",
    files: [],
    selectedPath: "",
    selectedContent: ""
  },
  qualityReview: null,
  securityReview: null,
  approvalReview: null,
  commandProjectId: null,
  commandOverview: null,
  commandMessage: "",
  ceoReport: ""
};

const api = async (path, options = {}) => {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });

  if (!response.ok) {
    const text = await response.text();
    try {
      const payload = JSON.parse(text);
      const detail = payload.detail || payload;
      if (detail.code || detail.message) {
        const missing = detail.missing_models?.length ? ` Missing models: ${detail.missing_models.join(", ")}.` : "";
        throw new Error(`${detail.code || response.statusText}: ${detail.message || ""}${missing}`);
      }
      throw new Error(JSON.stringify(detail));
    } catch (error) {
      if (error instanceof SyntaxError) {
        throw new Error(text || response.statusText);
      }
      throw error;
    }
  }

  return response.json();
};

const formData = (form) => Object.fromEntries(new FormData(form).entries());

const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  "\"": "&quot;",
  "'": "&#039;"
}[char]));

const jsArg = (value) => escapeHtml(JSON.stringify(String(value ?? "")));

const parseOutputFiles = (run) => {
  if (Array.isArray(run.output_files)) {
    return run.output_files;
  }

  if (typeof run.output_files === "string" && run.output_files.trim()) {
    try {
      const parsed = JSON.parse(run.output_files);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [run.output_files];
    }
  }

  return run.output_file ? [run.output_file] : [];
};

const basename = (path) => String(path || "").replace(/\\/g, "/").split("/").filter(Boolean).pop() || "";

const badgeTone = (status) => ["FAILED", "FAIL", "ERROR", "CRITICAL", "HIGH", "WARN"].includes(String(status || "").toUpperCase())
  ? "warn"
  : "";

const prettyText = (value) => {
  const text = String(value || "");
  if (!text.trim()) {
    return "";
  }
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
};

const relativeOutputPath = (absolutePath) => {
  const filePath = String(absolutePath || "").replace(/\\/g, "/");
  const projectPath = String(state.fileBrowser.projectPath || "").replace(/\\/g, "/");
  if (projectPath && filePath.toLowerCase().startsWith(projectPath.toLowerCase() + "/")) {
    return filePath.slice(projectPath.length + 1);
  }
  return filePath;
};

const statusCounts = () => state.tasks.reduce((counts, task) => {
  counts[task.status] = (counts[task.status] || 0) + 1;
  return counts;
}, {});

const renderProgress = () => {
  const tracker = document.querySelector("#progressTracker");
  const counts = statusCounts();
  const total = state.tasks.length;
  const done = (counts.DONE || 0) + (counts.AWAITING_APPROVAL || 0);
  const percent = total ? Math.round((done / total) * 100) : 0;
  const pendingApprovals = state.approvals.filter(approval => approval.status === "PENDING").length;

  tracker.innerHTML = `
    <div class="progress-head">
      <div>
        <h3>Live Task Progress</h3>
        <p class="meta">${done} of ${total} tasks completed or awaiting approval. ${pendingApprovals} pending approvals.</p>
      </div>
      <span class="badge">${percent}%</span>
    </div>
    <div class="progress-bar" aria-label="Task progress">
      <span style="width:${percent}%"></span>
    </div>
    <div class="progress-grid">
      ${["BACKLOG", "IN_PROGRESS", "AWAITING_APPROVAL", "NEEDS_CHANGES", "DONE", "FAILED"].map(status => `
        <div class="progress-cell">
          <strong>${counts[status] || 0}</strong>
          <span>${status}</span>
        </div>
      `).join("")}
    </div>
  `;
};

const renderProjects = () => {
  const list = document.querySelector("#projectsList");
  const projectSelect = document.querySelector("[name='project_id']");
  const fileProjectSelect = document.querySelector("#fileProjectSelect");
  const qualityProjectSelect = document.querySelector("#qualityProjectSelect");
  const securityProjectSelect = document.querySelector("#securityProjectSelect");
  const commandProjectSelect = document.querySelector("#commandProjectSelect");
  const supportProjectSelect = document.querySelector("#supportTicketForm [name='project_id']");

  list.innerHTML = state.projects.length
    ? state.projects.map(project => `
      <article class="item">
        <h4>${escapeHtml(project.name)}</h4>
        <p class="meta">${escapeHtml(project.status)} - ${new Date(project.created_at).toLocaleString()}</p>
        ${project.project_path ? `<p class="meta" style="word-break:break-all">${escapeHtml(project.project_path)}</p>` : ""}
        <p>${escapeHtml(project.description || "No description yet.")}</p>
        <div class="actions">
          <button type="button" class="secondary" onclick="runProject(${project.id})">Run Project Agents</button>
          <button type="button" class="secondary" onclick="browseProjectFiles(${project.id})">Browse Files</button>
          <button type="button" class="secondary" onclick="generateArchitecture(${project.id})">Architecture</button>
          <button type="button" class="secondary" onclick="runQualityReview(${project.id})">Quality Review</button>
          <button type="button" class="secondary" onclick="runSecurityReview(${project.id})">Security Review</button>
          <button type="button" onclick="runBuild(${project.id})">Run Build/Test</button>
          <button type="button" class="secondary" onclick="initGit(${project.id})">Init Git</button>
          <button type="button" class="secondary" onclick="showGitStatus(${project.id})">Git Status</button>
          <button type="button" onclick="commitGit(${project.id})">Commit</button>
          <button type="button" onclick="approveGit(${project.id})">Approve & Commit</button>
          <button type="button" class="danger" onclick="revertGit(${project.id})">Reject & Revert</button>
        </div>
      </article>
    `).join("")
    : "<p class='meta'>No projects yet.</p>";

  projectSelect.innerHTML = state.projects.map(project => `
    <option value="${project.id}">${escapeHtml(project.name)}</option>
  `).join("");

  fileProjectSelect.innerHTML = state.projects.map(project => `
    <option value="${project.id}">${escapeHtml(project.name)}</option>
  `).join("");
  if (state.fileBrowser.projectId) {
    fileProjectSelect.value = String(state.fileBrowser.projectId);
  }

  qualityProjectSelect.innerHTML = state.projects.map(project => `
    <option value="${project.id}">${escapeHtml(project.name)}</option>
  `).join("");
  if (state.qualityReview?.project_id) {
    qualityProjectSelect.value = String(state.qualityReview.project_id);
  }

  securityProjectSelect.innerHTML = state.projects.map(project => `
    <option value="${project.id}">${escapeHtml(project.name)}</option>
  `).join("");
  if (state.securityReview?.project_id) {
    securityProjectSelect.value = String(state.securityReview.project_id);
  }

  commandProjectSelect.innerHTML = state.projects.map(project => `
    <option value="${project.id}">${escapeHtml(project.name)}</option>
  `).join("");
  if (state.commandProjectId) {
    commandProjectSelect.value = String(state.commandProjectId);
  }

  supportProjectSelect.innerHTML = `<option value="">No project</option>` + state.projects.map(project => `
    <option value="${project.id}">${escapeHtml(project.name)}</option>
  `).join("");
};

const renderOllamaStatus = async () => {
  const status = document.querySelector("#ollamaStatus");
  try {
    const result = await api("/api/ollama/health");
    if (result.ok) {
      status.innerHTML = `Connected to ${escapeHtml(result.base_url)}. Models: ${escapeHtml(result.models.join(", ") || "none installed")}`;
    } else {
      status.innerHTML = `Not connected to ${escapeHtml(result.base_url)}. ${escapeHtml(result.error || "")}`;
    }
  } catch (error) {
    status.textContent = error.message;
  }
};

const renderGatewayStatus = async () => {
  const status = document.querySelector("#gatewayStatus");
  try {
    const [result, preflight] = await Promise.all([
      api("/api/ai-gateway/health"),
      api("/api/ollama/preflight")
    ]);
    const models = result.models || {};
    const modelText = Object.entries(models)
      .map(([role, model]) => `${role}: ${model}`)
      .join(", ");
    const preflightText = preflight.ok
      ? "Ready"
      : `${preflight.code}: ${preflight.missing_models?.join(", ") || preflight.message}`;
    status.innerHTML = `AI gateway: ${escapeHtml(result.provider)} (${result.local_only ? "local only" : "remote allowed"}). ${escapeHtml(modelText)}. Preflight: ${escapeHtml(preflightText)}`;
  } catch (error) {
    status.textContent = error.message;
  }
};

const renderAgents = () => {
  const list = document.querySelector("#agentsList");
  const agentSelect = document.querySelector("[name='assigned_agent']");
  const entries = Object.entries(state.agents);

  list.innerHTML = entries.map(([key, agent]) => `
    <article class="item">
      <h4>${escapeHtml(agent.name)}</h4>
      <p class="meta">${escapeHtml(key)}</p>
      <p>${escapeHtml(agent.description)}</p>
      <p>${agent.capabilities.map(capability => `<span class="badge">${escapeHtml(capability)}</span>`).join(" ")}</p>
    </article>
  `).join("");

  agentSelect.innerHTML = entries.map(([key, agent]) => `
    <option value="${key}">${escapeHtml(agent.name)}</option>
  `).join("");
};

const renderTemplates = () => {
  const select = document.querySelector("#stackSelect");
  const current = select.value || "auto";
  select.innerHTML = Object.entries(state.templates).map(([key, template]) => `
    <option value="${escapeHtml(key)}">${escapeHtml(template.name)} - ${escapeHtml(template.description)}</option>
  `).join("");
  select.value = state.templates[current] ? current : "auto";
};

const renderSettings = () => {
  const form = document.querySelector("#settingsForm");
  if (!form || !state.settings) {
    return;
  }
  form.output_base_dir.value = state.settings.output_base_dir || "C:/Project";
  form.max_fix_attempts.value = state.settings.max_fix_attempts ?? 3;
  form.max_autopilot_cycles.value = state.settings.max_autopilot_cycles ?? 8;
  form.local_only.checked = Boolean(state.settings.local_only);
  form.auto_save_ceo_reports.checked = Boolean(state.settings.auto_save_ceo_reports);

  const maxFixInput = document.querySelector("#maxFixAttempts");
  const maxCycleInput = document.querySelector("#maxAutopilotCycles");
  if (maxFixInput && !maxFixInput.dataset.userChanged) {
    maxFixInput.value = state.settings.max_fix_attempts ?? 3;
  }
  if (maxCycleInput && !maxCycleInput.dataset.userChanged) {
    maxCycleInput.value = state.settings.max_autopilot_cycles ?? 8;
  }
};

const renderTasks = () => {
  const list = document.querySelector("#tasksList");

  list.innerHTML = state.tasks.length
    ? state.tasks.map(task => `
      <article class="item">
        <h4>${escapeHtml(task.title)}</h4>
        <p class="meta">
          <span class="badge ${task.status === "AWAITING_APPROVAL" ? "warn" : ""}">${escapeHtml(task.status)}</span>
          <span class="badge">${escapeHtml(task.priority)}</span>
          <span class="badge">${escapeHtml(task.assigned_agent)}</span>
          ${task.branch_name ? `<span class="badge">${escapeHtml(task.branch_name)}</span>` : ""}
        </p>
        <p>${escapeHtml(task.description || "No details provided.")}</p>
        <div class="actions">
          <button type="button" onclick="runTask(${task.id})">Run Agent</button>
          ${task.branch_name ? `
            <button type="button" onclick="mergeBranch(${task.project_id}, '${escapeHtml(task.branch_name)}')">Merge Branch</button>
            <button type="button" class="danger" onclick="deleteBranch(${task.project_id}, '${escapeHtml(task.branch_name)}')">Delete Branch</button>
          ` : ""}
        </div>
      </article>
    `).join("")
    : "<p class='meta'>No tasks yet.</p>";
};

const renderApprovals = () => {
  const list = document.querySelector("#approvalsList");

  list.innerHTML = state.approvals.length
    ? state.approvals.map(approval => `
      <article class="item">
        <h4>${escapeHtml(approval.title)}</h4>
        <p class="meta">
          <span class="badge ${approval.status === "PENDING" ? "warn" : ""}">${escapeHtml(approval.status)}</span>
          Task #${approval.task_id}
        </p>
        <p>${escapeHtml(approval.reason)}</p>
        ${approval.status === "PENDING" ? `
          <div class="actions">
            <button type="button" class="secondary" onclick="reviewApproval(${approval.id})">Review</button>
            <button type="button" onclick="decideApproval(${approval.id}, 'APPROVED')">Approve</button>
            <button type="button" class="danger" onclick="decideApproval(${approval.id}, 'REJECTED')">Reject</button>
          </div>
        ` : `<p class="meta">${escapeHtml(approval.decision_notes || "No notes.")}</p>`}
      </article>
    `).join("")
    : "<p class='meta'>No approvals yet.</p>";
};

const renderApprovalReview = () => {
  const panel = document.querySelector("#approvalReviewPanel");
  const review = state.approvalReview;
  if (!review) {
    panel.innerHTML = "<p class='meta'>Open an approval review to inspect changes before deciding.</p>";
    return;
  }

  const qualityFindings = review.quality?.findings || [];
  const securityFindings = review.security?.findings || [];
  const outputFiles = review.output_files || [];
  panel.innerHTML = `
    <article class="item">
      <h4>${escapeHtml(review.approval.title)} - ${escapeHtml(review.approval.status)}</h4>
      <p class="meta">
        Project #${escapeHtml(review.project_id || "")}
        Task #${escapeHtml(review.task?.id || "")}
        ${review.branch_name ? `<span class="badge">${escapeHtml(review.branch_name)}</span>` : ""}
      </p>
      <p>${escapeHtml(review.task?.title || "")}</p>
      <div class="actions">
        ${review.approval.status === "PENDING" ? `
          <button type="button" onclick="decideApproval(${review.approval.id}, 'APPROVED')">Approve</button>
          <button type="button" class="danger" onclick="decideApproval(${review.approval.id}, 'REJECTED')">Reject</button>
        ` : ""}
        ${review.project_id ? `<button type="button" class="secondary" onclick="browseProjectFiles(${review.project_id})">Browse Files</button>` : ""}
      </div>
    </article>
    <article class="item">
      <h4>Build and Quality</h4>
      <p class="meta">
        Build: ${escapeHtml(review.latest_build?.status || "No build run")}
        ${review.latest_build?.exit_code !== undefined ? `Exit ${escapeHtml(review.latest_build.exit_code)}` : ""}
        Quality: ${escapeHtml(review.quality?.status || "Not run")}
        Security: ${escapeHtml(review.security?.status || "Not run")}
      </p>
      ${qualityFindings.length ? qualityFindings.map(finding => `
        <div class="quality-finding">
          <span class="badge ${finding.severity === "CRITICAL" || finding.severity === "HIGH" ? "warn" : ""}">${escapeHtml(finding.severity)}</span>
          <strong>${escapeHtml(finding.file)}</strong>
          <p>${escapeHtml(finding.message)}</p>
        </div>
      `).join("") : "<p class='meta'>No deterministic quality issues found.</p>"}
      ${securityFindings.length ? `
        <h4>Security Findings</h4>
        ${securityFindings.map(finding => `
          <div class="quality-finding">
            <span class="badge ${finding.severity === "CRITICAL" || finding.severity === "HIGH" ? "warn" : ""}">${escapeHtml(finding.severity)}</span>
            <strong>${escapeHtml(finding.file)}</strong>
            <p>${escapeHtml(finding.message)}</p>
          </div>
        `).join("")}
      ` : "<p class='meta'>No deterministic security issues found.</p>"}
    </article>
    <article class="item">
      <h4>Output Files</h4>
      ${outputFiles.length ? `
        <div class="file-list">
          ${outputFiles.map(file => `<button type="button" class="file-link" onclick="openApprovalOutputFile(${jsArg(file)})">${escapeHtml(file)}</button>`).join("")}
        </div>
      ` : "<p class='meta'>No output files recorded.</p>"}
    </article>
    <article class="item">
      <h4>Git Diff</h4>
      <p class="meta">${escapeHtml(review.git?.branch || "")} ${escapeHtml(review.git?.project_path || "")}</p>
      <pre>${escapeHtml(review.git?.diff || review.git?.staged_diff || "No diff available.")}</pre>
    </article>
  `;
};

const renderRuns = () => {
  const list = document.querySelector("#runsList");

  list.innerHTML = state.runs.length
    ? state.runs.map(run => {
      const files = parseOutputFiles(run);
      return `
        <article class="item">
          <h4>${escapeHtml(run.agent_name)} - Task #${run.task_id}</h4>
          <p class="meta">
          <span class="badge">${escapeHtml(run.status)}</span>
          ${run.branch_name ? `<span class="badge">${escapeHtml(run.branch_name)}</span>` : ""}
          ${new Date(run.created_at).toLocaleString()}
          </p>
          ${files.length ? `
            <div class="file-list">
              <strong>Output files</strong>
              ${files.map(file => `<button type="button" class="file-link" onclick="openOutputFile(${run.task_id}, ${jsArg(file)})">${escapeHtml(file)}</button>`).join("")}
            </div>
          ` : ""}
          <pre>${escapeHtml(run.output_text || "Still running or no output yet.")}</pre>
        </article>
      `;
    }).join("")
    : "<p class='meta'>No agent runs yet.</p>";
};

const renderFileBrowser = () => {
  const tree = document.querySelector("#fileTree");
  const title = document.querySelector("#filePreviewTitle");
  const meta = document.querySelector("#filePreviewMeta");
  const content = document.querySelector("#filePreviewContent");
  const files = state.fileBrowser.files;

  if (!state.fileBrowser.projectId) {
    tree.innerHTML = "<p class='meta'>Choose a project and browse files.</p>";
    title.textContent = "No file selected";
    meta.textContent = "";
    content.textContent = "Select a readable text file to preview it.";
    return;
  }

  tree.innerHTML = files.length
    ? files.map(file => `
      <button type="button" class="file-row ${file.readable ? "" : "disabled"} ${file.note ? "note" : ""}" ${file.readable ? `onclick="openProjectFile(${state.fileBrowser.projectId}, ${jsArg(file.path)})"` : "disabled"}>
        <span>${escapeHtml(file.path)}</span>
        <small>${file.note ? "note" : ""} ${Math.ceil((file.size || 0) / 1024)} KB</small>
      </button>
    `).join("")
    : "<p class='meta'>No files found in this project path.</p>";

  title.textContent = state.fileBrowser.selectedPath || "No file selected";
  meta.textContent = state.fileBrowser.selectedPath
    ? `${state.fileBrowser.selectedContent.length.toLocaleString()} characters`
    : "";
  content.textContent = state.fileBrowser.selectedPath
    ? state.fileBrowser.selectedContent
    : "Select a readable text file to preview it.";
};

const renderBuildRuns = () => {
  const list = document.querySelector("#buildRunsList");

  list.innerHTML = state.buildRuns.length
    ? state.buildRuns.map(run => `
      <article class="item">
        <h4>Project #${run.project_id} - ${escapeHtml(run.stack || "unknown")}</h4>
        <p class="meta">
          <span class="badge ${run.status === "FAILED" ? "warn" : ""}">${escapeHtml(run.status)}</span>
          ${run.branch_name ? `<span class="badge">${escapeHtml(run.branch_name)}</span>` : ""}
          Exit ${escapeHtml(run.exit_code ?? "")}
          ${new Date(run.created_at).toLocaleString()}
        </p>
        <p class="meta" style="word-break:break-all">${escapeHtml(run.project_path || "")}</p>
        <p class="meta">${escapeHtml(run.command || "")}</p>
        <pre>${escapeHtml(run.output_text || "Build/test still running or no output yet.")}</pre>
      </article>
    `).join("")
    : "<p class='meta'>No build/test runs yet.</p>";
};

const renderQualityReview = () => {
  const panel = document.querySelector("#qualityReviewPanel");
  const review = state.qualityReview;
  if (!review) {
    panel.innerHTML = "<p class='meta'>Choose a project and run a quality review.</p>";
    return;
  }

  panel.innerHTML = `
    <article class="item">
      <h4>Project #${review.project_id} - ${escapeHtml(review.status)}</h4>
      <p class="meta" style="word-break:break-all">${escapeHtml(review.project_path || "")}</p>
      ${review.findings.length ? review.findings.map(finding => `
        <div class="quality-finding">
          <span class="badge ${finding.severity === "CRITICAL" || finding.severity === "HIGH" ? "warn" : ""}">${escapeHtml(finding.severity)}</span>
          <strong>${escapeHtml(finding.file)}</strong>
          <p>${escapeHtml(finding.message)}</p>
        </div>
      `).join("") : "<p class='meta'>No deterministic quality issues found.</p>"}
    </article>
  `;
};

const renderSecurityReview = () => {
  const panel = document.querySelector("#securityReviewPanel");
  const review = state.securityReview;
  if (!review) {
    panel.innerHTML = "<p class='meta'>Choose a project and run a security review.</p>";
    return;
  }

  panel.innerHTML = `
    <article class="item">
      <h4>Project #${review.project_id} - ${escapeHtml(review.status)}</h4>
      <p class="meta" style="word-break:break-all">${escapeHtml(review.project_path || "")}</p>
      ${review.findings.length ? review.findings.map(finding => `
        <div class="quality-finding">
          <span class="badge ${finding.severity === "CRITICAL" || finding.severity === "HIGH" ? "warn" : ""}">${escapeHtml(finding.severity)}</span>
          <strong>${escapeHtml(finding.file)}</strong>
          <p>${escapeHtml(finding.message)}</p>
        </div>
      `).join("") : "<p class='meta'>No deterministic security issues found.</p>"}
    </article>
  `;
};

const renderCommandCenter = () => {
  const panel = document.querySelector("#commandOverview");
  const status = document.querySelector("#commandStatus");
  const report = document.querySelector("#ceoReportPanel");
  const select = document.querySelector("#commandProjectSelect");

  select.innerHTML = state.projects.map(project => `
    <option value="${project.id}">${escapeHtml(project.name)}</option>
  `).join("");

  if (!state.projects.length) {
    panel.innerHTML = "<p class='meta'>Create a project first. The command center will become the main control point for it.</p>";
    status.textContent = "";
    report.textContent = "";
    return;
  }

  if (state.commandProjectId) {
    select.value = String(state.commandProjectId);
  }

  const overview = state.commandOverview;
  status.textContent = state.commandMessage || "";
  report.textContent = state.ceoReport || "";
  report.style.display = state.ceoReport ? "block" : "none";
  if (!overview) {
    panel.innerHTML = "<p class='meta'>Choose a project and load its overview.</p>";
    return;
  }

  const counts = overview.task_counts || {};
  const qualityStatus = overview.quality?.status || "UNKNOWN";
  const securityStatus = overview.security?.status || "UNKNOWN";
  const buildStatus = overview.latest_build?.status || "NONE";
  const jobStatus = overview.latest_job?.status || "NONE";
  const qualityFindings = overview.quality?.findings?.length || 0;
  const securityFindings = overview.security?.findings?.length || 0;
  const nextAction = overview.recommended_next_action || {};
  const agentWorkload = overview.agent_workload || [];
  const supportCounts = overview.support_counts || {};
  const openSupport = Object.entries(supportCounts)
    .filter(([status]) => status !== "CLOSED")
    .reduce((total, [, count]) => total + Number(count || 0), 0);

  panel.innerHTML = `
    <article class="item command-summary">
      <div>
        <h4>${escapeHtml(overview.project.name)}</h4>
        <p class="meta" style="word-break:break-all">${escapeHtml(overview.project.project_path || "")}</p>
        <p>${escapeHtml(overview.project.description || "No description yet.")}</p>
        <p class="next-action">
          <span class="badge ${nextAction.can_run === false ? "warn" : ""}">${escapeHtml(nextAction.label || "No recommendation")}</span>
          ${escapeHtml(nextAction.reason || "")}
        </p>
      </div>
      <div class="command-grid">
        <div class="status-tile">
          <span>Stack</span>
          <strong>${escapeHtml(overview.stack || "unknown")}</strong>
        </div>
        <div class="status-tile">
          <span>Architecture</span>
          <strong>${overview.architecture_ready ? "Ready" : "Missing"}</strong>
        </div>
        <div class="status-tile">
          <span>Build</span>
          <strong><span class="badge ${badgeTone(buildStatus)}">${escapeHtml(buildStatus)}</span></strong>
        </div>
        <div class="status-tile">
          <span>Quality</span>
          <strong><span class="badge ${badgeTone(qualityStatus)}">${escapeHtml(qualityStatus)}</span></strong>
          <small>${qualityFindings} findings</small>
        </div>
        <div class="status-tile">
          <span>Security</span>
          <strong><span class="badge ${badgeTone(securityStatus)}">${escapeHtml(securityStatus)}</span></strong>
          <small>${securityFindings} findings</small>
        </div>
        <div class="status-tile">
          <span>Open Approvals</span>
          <strong>${escapeHtml(overview.pending_approvals || 0)}</strong>
        </div>
        <div class="status-tile">
          <span>Latest Job</span>
          <strong><span class="badge ${badgeTone(jobStatus)}">${escapeHtml(jobStatus)}</span></strong>
        </div>
        <div class="status-tile">
          <span>Tasks</span>
          <strong>${escapeHtml(overview.task_total || 0)}</strong>
          <small>${Object.entries(counts).map(([key, value]) => `${key}: ${value}`).join(" | ") || "No tasks"}</small>
        </div>
        <div class="status-tile">
          <span>Support</span>
          <strong>${escapeHtml(openSupport)}</strong>
          <small>${Object.entries(supportCounts).map(([key, value]) => `${key}: ${value}`).join(" | ") || "No tickets"}</small>
        </div>
      </div>
      <div class="agent-workload">
        ${agentWorkload.map(agent => `
          <div class="agent-tile">
            <strong>${escapeHtml(agent.name)}</strong>
            <span>${escapeHtml(agent.task_total || 0)} task(s)</span>
            <small>${agent.latest_task ? `${escapeHtml(agent.latest_task.status)}: ${escapeHtml(agent.latest_task.title)}` : "No assigned tasks"}</small>
            ${agent.latest_run ? `<small>Latest run: ${escapeHtml(agent.latest_run.status)}</small>` : ""}
          </div>
        `).join("")}
      </div>
    </article>
  `;
};

const renderJobs = () => {
  const list = document.querySelector("#jobsList");
  const eventsByJob = state.jobEvents.reduce((groups, event) => {
    groups[event.job_id] = groups[event.job_id] || [];
    groups[event.job_id].push(event);
    return groups;
  }, {});

  list.innerHTML = state.jobs.length
    ? state.jobs.map(job => `
      <article class="item">
        <h4>${escapeHtml(job.title || job.job_type)}</h4>
        <p class="meta">
          <span class="badge ${job.status === "FAILED" ? "warn" : ""}">${escapeHtml(job.status)}</span>
          ${escapeHtml(job.job_type)}
          ${job.project_id ? `Project #${job.project_id}` : ""}
          ${job.task_id ? `Task #${job.task_id}` : ""}
          ${job.retry_of_job_id ? `Retry of #${job.retry_of_job_id}` : ""}
          ${job.process_id ? `PID ${job.process_id}` : ""}
        </p>
        <div class="actions">
          ${["PENDING", "RUNNING"].includes(job.status)
            ? `<button type="button" class="danger" onclick="cancelJob(${job.id})">Cancel</button>`
            : `<button type="button" onclick="retryJob(${job.id})">Retry</button>`}
        </div>
        ${(eventsByJob[job.id] || []).length ? `
          <div class="job-events">
            ${(eventsByJob[job.id] || []).slice(0, 6).map(event => `
              <div class="job-event">
                <span class="badge ${event.level === "ERROR" || event.level === "WARN" ? "warn" : ""}">${escapeHtml(event.level)}</span>
                <span>${escapeHtml(event.message)}</span>
                <small>${new Date(event.created_at).toLocaleTimeString()}</small>
              </div>
            `).join("")}
          </div>
        ` : ""}
        ${job.output_text ? `<pre>${escapeHtml(prettyText(job.output_text))}</pre>` : ""}
        ${job.error_text ? `<pre>${escapeHtml(job.error_text)}</pre>` : ""}
      </article>
    `).join("")
    : "<p class='meta'>No jobs yet.</p>";
};

const renderSupportTickets = () => {
  const list = document.querySelector("#supportTicketsList");
  list.innerHTML = state.supportTickets.length
    ? state.supportTickets.map(ticket => `
      <article class="item">
        <h4>${escapeHtml(ticket.subject)}</h4>
        <p class="meta">
          <span class="badge ${badgeTone(ticket.priority)}">${escapeHtml(ticket.priority)}</span>
          <span class="badge">${escapeHtml(ticket.status)}</span>
          ${escapeHtml(ticket.category)}
          ${ticket.project_id ? `Project #${ticket.project_id}` : "No project"}
          ${ticket.created_task_id ? `Task #${ticket.created_task_id}` : ""}
        </p>
        <p class="meta">${escapeHtml(ticket.sender_email || "Unknown sender")}</p>
        <p>${escapeHtml(ticket.body)}</p>
        <div class="actions">
          <button type="button" class="secondary" onclick="triageSupportTicket(${ticket.id})">Triage</button>
          <button type="button" onclick="escalateSupportTicket(${ticket.id})">Escalate</button>
          <button type="button" class="secondary" onclick="closeSupportTicket(${ticket.id})">Close</button>
        </div>
        ${ticket.suggested_reply ? `<pre>${escapeHtml(ticket.suggested_reply)}</pre>` : ""}
      </article>
    `).join("")
    : "<p class='meta'>No support tickets yet.</p>";
};

const renderGitStatus = () => {
  const panel = document.querySelector("#gitStatusPanel");
  const git = state.gitStatus;
  if (!git) {
    panel.innerHTML = "<p class='meta'>Run Git Status on a project to inspect changes.</p>";
    return;
  }

  panel.innerHTML = `
    <article class="item">
      <h4>Project #${git.project_id}</h4>
      <p class="meta">${git.is_repo ? "Git repository" : "Not initialized"} - ${escapeHtml(git.project_path || "")}</p>
      <h4>Status</h4>
      <pre>${escapeHtml(git.status || "No changed files.")}</pre>
      <h4>Unstaged Diff</h4>
      <pre>${escapeHtml(git.diff || "No unstaged tracked file diff.")}</pre>
      <h4>Staged Diff</h4>
      <pre>${escapeHtml(git.staged_diff || "No staged file diff.")}</pre>
    </article>
  `;
};

const refresh = async () => {
  [state.projects, state.tasks, state.agents, state.templates, state.approvals, state.runs, state.buildRuns, state.jobs, state.jobEvents, state.settings, state.supportTickets] = await Promise.all([
    api("/api/projects"),
    api("/api/tasks"),
    api("/api/agents"),
    api("/api/templates"),
    api("/api/approvals"),
    api("/api/runs"),
    api("/api/build-runs"),
    api("/api/jobs"),
    api("/api/job-events"),
    api("/api/settings"),
    api("/api/support-tickets")
  ]);

  if (!state.projects.some(project => project.id === state.commandProjectId)) {
    state.commandProjectId = state.projects[0]?.id || null;
    state.commandOverview = null;
    state.ceoReport = "";
  }
  if (state.commandProjectId) {
    try {
      state.commandOverview = await api(`/api/projects/${state.commandProjectId}/overview`);
    } catch (error) {
      state.commandOverview = null;
      state.commandMessage = error.message;
    }
  }

  renderProgress();
  renderProjects();
  renderCommandCenter();
  renderAgents();
  renderTemplates();
  renderSettings();
  renderTasks();
  renderApprovals();
  renderApprovalReview();
  renderRuns();
  renderBuildRuns();
  renderQualityReview();
  renderSecurityReview();
  renderGitStatus();
  renderJobs();
  renderSupportTickets();
  renderFileBrowser();
  await renderOllamaStatus();
  await renderGatewayStatus();
};

window.runTask = async (taskId) => {
  await api(`/api/tasks/${taskId}/run`, { method: "POST" });
  await refresh();
};

window.reviewApproval = async (approvalId) => {
  state.approvalReview = await api(`/api/approvals/${approvalId}/review`);
  renderApprovalReview();
  document.querySelector("#approvalReview").scrollIntoView({ behavior: "smooth", block: "start" });
};

window.openApprovalOutputFile = async (outputFile) => {
  const review = state.approvalReview;
  if (!review?.project_id) {
    return;
  }
  if (state.fileBrowser.projectId !== review.project_id) {
    await window.browseProjectFiles(review.project_id);
  }
  const path = relativeOutputPath(outputFile);
  await window.openProjectFile(review.project_id, path);
};

window.mergeBranch = async (projectId, branchName) => {
  const confirmed = window.confirm(`Merge branch ${branchName} into main?`);
  if (!confirmed) {
    return;
  }
  await api(`/api/projects/${projectId}/git/merge-branch`, {
    method: "POST",
    body: JSON.stringify({ branch_name: branchName })
  });
  await refresh();
};

window.deleteBranch = async (projectId, branchName) => {
  const confirmed = window.confirm(`Delete branch ${branchName}?`);
  if (!confirmed) {
    return;
  }
  await api(`/api/projects/${projectId}/git/delete-branch`, {
    method: "POST",
    body: JSON.stringify({ branch_name: branchName })
  });
  await refresh();
};

window.runProject = async (projectId) => {
  await api(`/api/projects/${projectId}/run`, { method: "POST" });
  state.commandProjectId = projectId;
  await refresh();
};

window.loadProjectOverview = async (projectId) => {
  if (!projectId) {
    return;
  }
  state.commandProjectId = Number(projectId);
  state.commandOverview = await api(`/api/projects/${state.commandProjectId}/overview`);
  state.commandMessage = "";
  state.ceoReport = "";
  renderCommandCenter();
};

window.runCommandWorkflow = async (workflow) => {
  const projectId = Number(document.querySelector("#commandProjectSelect").value || state.commandProjectId);
  if (!projectId) {
    return;
  }

  const maxFixAttempts = Number(document.querySelector("#maxFixAttempts")?.value || 3);
  const maxCycles = Number(document.querySelector("#maxAutopilotCycles")?.value || 8);
  state.commandProjectId = projectId;
  state.commandMessage = "Starting workflow...";
  state.ceoReport = "";
  renderCommandCenter();

  try {
    const result = await api(`/api/projects/${projectId}/workflow`, {
      method: "POST",
      body: JSON.stringify({
        workflow,
        max_fix_attempts: maxFixAttempts,
        max_cycles: maxCycles,
        overwrite_architecture: workflow === "refresh_architecture"
      })
    });

    if (workflow === "health_check") {
      state.qualityReview = result.quality;
      state.securityReview = result.security;
    }

    if (result.status === "waiting") {
      state.commandMessage = result.recommended?.reason || "A workflow is already running.";
    } else if (workflow === "release_check" || result.workflow === "release_check") {
      state.commandMessage = result.ready
        ? "Release check passed. This project is ready for CEO approval."
        : `Release check blocked: ${(result.blockers || []).join(" | ")}`;
    } else {
      const chosen = workflow === "auto_next" ? `Auto Next chose ${String(result.workflow || "").replaceAll("_", " ")}. ` : "";
      state.commandMessage = result.job_id
        ? `${chosen}Started ${String(result.workflow || workflow).replaceAll("_", " ")} as job #${result.job_id}.`
        : `${chosen}Completed ${String(result.workflow || workflow).replaceAll("_", " ")}.`;
    }
    await refresh();
  } catch (error) {
    state.commandMessage = error.message;
    renderCommandCenter();
  }
};

window.loadCeoReport = async () => {
  const projectId = Number(document.querySelector("#commandProjectSelect").value || state.commandProjectId);
  if (!projectId) {
    return;
  }
  state.commandProjectId = projectId;
  const result = await api(`/api/projects/${projectId}/ceo-report`);
  state.ceoReport = result.report || "";
  state.commandMessage = result.ready
    ? "CEO report generated. No release blockers found."
    : `CEO report generated with ${result.blockers?.length || 0} blocker(s).`;
  renderCommandCenter();
};

window.saveCeoReport = async () => {
  const projectId = Number(document.querySelector("#commandProjectSelect").value || state.commandProjectId);
  if (!projectId) {
    return;
  }
  state.commandProjectId = projectId;
  const result = await api(`/api/projects/${projectId}/ceo-report/save`, { method: "POST" });
  state.ceoReport = result.report || "";
  state.commandMessage = `CEO report saved: ${result.latest_path || result.saved_path}`;
  renderCommandCenter();
  if (state.fileBrowser.projectId === projectId) {
    await window.browseProjectFiles(projectId);
  }
};

window.triageSupportTicket = async (ticketId) => {
  await api(`/api/support-tickets/${ticketId}/triage`, { method: "POST" });
  await refresh();
};

window.escalateSupportTicket = async (ticketId) => {
  try {
    await api(`/api/support-tickets/${ticketId}/escalate`, { method: "POST" });
    await refresh();
  } catch (error) {
    window.alert(error.message);
  }
};

window.closeSupportTicket = async (ticketId) => {
  await api(`/api/support-tickets/${ticketId}`, {
    method: "PATCH",
    body: JSON.stringify({ status: "CLOSED" })
  });
  await refresh();
};

window.browseProjectFiles = async (projectId) => {
  const result = await api(`/api/projects/${projectId}/files`);
  state.fileBrowser = {
    projectId,
    projectPath: result.project_path || "",
    files: result.files || [],
    selectedPath: "",
    selectedContent: ""
  };
  const selector = document.querySelector("#fileProjectSelect");
  selector.value = String(projectId);
  renderFileBrowser();
  document.querySelector("#files").scrollIntoView({ behavior: "smooth", block: "start" });
};

window.generateArchitecture = async (projectId) => {
  await api(`/api/projects/${projectId}/architecture`, {
    method: "POST"
  });
  await window.browseProjectFiles(projectId);
  await window.openProjectFile(projectId, "ARCHITECTURE.md");
};

window.runQualityReview = async (projectId) => {
  state.qualityReview = await api(`/api/projects/${projectId}/quality`);
  const selector = document.querySelector("#qualityProjectSelect");
  selector.value = String(projectId);
  renderQualityReview();
  document.querySelector("#quality").scrollIntoView({ behavior: "smooth", block: "start" });
};

window.runSecurityReview = async (projectId) => {
  state.securityReview = await api(`/api/projects/${projectId}/security`);
  const selector = document.querySelector("#securityProjectSelect");
  selector.value = String(projectId);
  renderSecurityReview();
  document.querySelector("#security").scrollIntoView({ behavior: "smooth", block: "start" });
};

window.openProjectFile = async (projectId, path) => {
  const result = await api(`/api/projects/${projectId}/files/content?path=${encodeURIComponent(path)}`);
  state.fileBrowser.selectedPath = result.path;
  state.fileBrowser.selectedContent = result.content || "";
  renderFileBrowser();
};

window.openOutputFile = async (taskId, outputFile) => {
  const task = state.tasks.find(item => item.id === taskId);
  if (!task) {
    return;
  }
  if (state.fileBrowser.projectId !== task.project_id) {
    await window.browseProjectFiles(task.project_id);
  }
  const path = relativeOutputPath(outputFile);
  await window.openProjectFile(task.project_id, path);
};

window.runBuild = async (projectId) => {
  const maxFixAttempts = Number(document.querySelector("#maxFixAttempts")?.value || 3);
  await api(`/api/projects/${projectId}/build`, {
    method: "POST",
    body: JSON.stringify({ max_fix_attempts: maxFixAttempts })
  });
  state.commandProjectId = projectId;
  await refresh();
};

window.cancelJob = async (jobId) => {
  const confirmed = window.confirm(`Cancel job #${jobId}?`);
  if (!confirmed) {
    return;
  }
  await api(`/api/jobs/${jobId}/cancel`, { method: "POST" });
  await refresh();
};

window.retryJob = async (jobId) => {
  await api(`/api/jobs/${jobId}/retry`, { method: "POST" });
  await refresh();
};

window.initGit = async (projectId) => {
  state.gitStatus = await api(`/api/projects/${projectId}/git/init`, {
    method: "POST",
    body: JSON.stringify({})
  });
  await showGitStatus(projectId);
};

window.showGitStatus = async (projectId) => {
  state.gitStatus = await api(`/api/projects/${projectId}/git/status`, {
    method: "POST",
    body: JSON.stringify({})
  });
  renderGitStatus();
};

window.commitGit = async (projectId) => {
  const message = window.prompt("Commit message", "Wacko Inc agent changes");
  if (message === null) {
    return;
  }
  await api(`/api/projects/${projectId}/git/commit`, {
    method: "POST",
    body: JSON.stringify({ message })
  });
  await showGitStatus(projectId);
};

window.approveGit = async (projectId) => {
  const message = window.prompt("Approval commit message", "Approve Wacko Inc changes");
  if (message === null) {
    return;
  }
  await api(`/api/projects/${projectId}/git/approve`, {
    method: "POST",
    body: JSON.stringify({ message })
  });
  await showGitStatus(projectId);
};

window.revertGit = async (projectId) => {
  const confirmed = window.confirm(
    "Reject and revert all uncommitted changes in this project? This deletes untracked files and restores tracked files."
  );
  if (!confirmed) {
    return;
  }
  await api(`/api/projects/${projectId}/git/revert`, {
    method: "POST",
    body: JSON.stringify({})
  });
  await showGitStatus(projectId);
};

window.decideApproval = async (approvalId, status) => {
  const promptText = status === "APPROVED"
    ? "Approval notes. If build or quality is failing, include override to approve anyway."
    : "Rejection notes for the agents";
  const notes = window.prompt(promptText, "") || "";
  try {
    await api(`/api/approvals/${approvalId}/decision`, {
      method: "POST",
      body: JSON.stringify({ status, notes })
    });
    state.approvalReview = null;
    await refresh();
  } catch (error) {
    window.alert(error.message);
  }
};

document.querySelector("#refreshButton").addEventListener("click", refresh);

document.querySelector("#maxFixAttempts")?.addEventListener("input", (event) => {
  event.currentTarget.dataset.userChanged = "true";
});

document.querySelector("#maxAutopilotCycles")?.addEventListener("input", (event) => {
  event.currentTarget.dataset.userChanged = "true";
});

document.querySelector("#loadCommandProjectButton").addEventListener("click", async () => {
  const projectId = Number(document.querySelector("#commandProjectSelect").value);
  await window.loadProjectOverview(projectId);
});

document.querySelector("#commandProjectSelect").addEventListener("change", async (event) => {
  await window.loadProjectOverview(Number(event.currentTarget.value));
});

document.querySelector("#loadFilesButton").addEventListener("click", async () => {
  const projectId = Number(document.querySelector("#fileProjectSelect").value);
  if (projectId) {
    await window.browseProjectFiles(projectId);
  }
});

document.querySelector("#runQualityButton").addEventListener("click", async () => {
  const projectId = Number(document.querySelector("#qualityProjectSelect").value);
  if (projectId) {
    await window.runQualityReview(projectId);
  }
});

document.querySelector("#runSecurityButton").addEventListener("click", async () => {
  const projectId = Number(document.querySelector("#securityProjectSelect").value);
  if (projectId) {
    await window.runSecurityReview(projectId);
  }
});

document.querySelector("#clearDatabaseButton").addEventListener("click", async () => {
  const confirmed = window.confirm(
    "Clear all projects, tasks, agent runs, approvals, and execution logs? This cannot be undone."
  );
  if (!confirmed) {
    return;
  }

  await api("/api/admin/clear-database", { method: "POST" });
  state.commandProjectId = null;
  state.commandOverview = null;
  state.commandMessage = "";
  state.ceoReport = "";
  await refresh();
});

document.querySelector("#settingsForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const status = document.querySelector("#settingsStatus");
  const data = formData(form);
  const payload = {
    output_base_dir: data.output_base_dir || "C:/Project",
    max_fix_attempts: Number(data.max_fix_attempts || 3),
    max_autopilot_cycles: Number(data.max_autopilot_cycles || 8),
    local_only: form.local_only.checked,
    auto_save_ceo_reports: form.auto_save_ceo_reports.checked
  };

  try {
    state.settings = await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify(payload)
    });
    status.textContent = "Settings saved.";
    document.querySelector("#maxFixAttempts").dataset.userChanged = "";
    document.querySelector("#maxAutopilotCycles").dataset.userChanged = "";
    renderSettings();
  } catch (error) {
    status.textContent = error.message;
  }
});

document.querySelector("#supportTicketForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  const payload = {
    project_id: data.project_id ? Number(data.project_id) : null,
    sender_email: data.sender_email || "",
    subject: data.subject,
    body: data.body
  };
  await api("/api/support-tickets", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  form.reset();
  await refresh();
});

document.querySelector("#goalForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const status = document.querySelector("#goalStatus");
  const data = formData(form);
  const output_dir = data.output_dir && data.output_dir.trim() ? data.output_dir.trim() : null;

  const payload = {
    goal: data.goal,
    auto_start: form.auto_start.checked,
    output_dir,
    stack: data.stack || "auto"
  };

  status.textContent = "Manager is planning the company workflow...";

  try {
    const result = await api("/api/goals", { method: "POST", body: JSON.stringify(payload) });
    form.reset();
    form.auto_start.checked = true;

    const dir = output_dir || result.template?.project_dir || `C:/Project/${result.project?.name ?? ""}`;
    const template = result.template?.template_name || "selected template";
    status.textContent = `Created project #${result.project.id} with ${result.tasks.length} tasks using ${template}. Files: ${dir}`;
    await refresh();
  } catch (error) {
    status.textContent = error.message;
  }
});

document.querySelector("#updateProjectForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const status = document.querySelector("#updateStatus");
  const data = formData(form);

  const payload = {
    project_path: data.project_path.trim(),
    instructions: data.instructions,
    auto_start: form.auto_start.checked
  };

  status.textContent = "Manager is studying the project and planning updates...";

  try {
    const result = await api("/api/project-updates", { method: "POST", body: JSON.stringify(payload) });
    form.reset();
    form.auto_start.checked = true;
    status.textContent = `Created update project #${result.project.id} with ${result.tasks.length} tasks. Updating: ${result.project_path}`;
    await refresh();
  } catch (error) {
    status.textContent = error.message;
  }
});

document.querySelector("#projectForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  if (!data.project_path || !data.project_path.trim()) {
    delete data.project_path;
  }
  await api("/api/projects", { method: "POST", body: JSON.stringify(data) });
  form.reset();
  await refresh();
});

document.querySelector("#taskForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = formData(form);
  data.project_id = Number(data.project_id);
  data.requires_approval = form.requires_approval.checked;
  await api("/api/tasks", { method: "POST", body: JSON.stringify(data) });
  form.reset();
  form.requires_approval.checked = true;
  await refresh();
});

refresh().catch(error => {
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="panel" style="position:fixed;right:16px;bottom:16px;max-width:420px;color:#b91c1c;">${escapeHtml(error.message)}</div>`
  );
});

window.setInterval(() => {
  refresh().catch(() => {});
}, 5000);
