const state = {
  projects: [],
  tasks: [],
  agents: {},
  approvals: [],
  runs: []
};

const api = async (path, options = {}) => {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || response.statusText);
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

const renderProjects = () => {
  const list = document.querySelector("#projectsList");
  const projectSelect = document.querySelector("[name='project_id']");

  list.innerHTML = state.projects.length
    ? state.projects.map(project => `
      <article class="item">
        <h4>${escapeHtml(project.name)}</h4>
        <p class="meta">${escapeHtml(project.status)} - ${new Date(project.created_at).toLocaleString()}</p>
        <p>${escapeHtml(project.description || "No description yet.")}</p>
        <div class="actions">
          <button type="button" class="secondary" onclick="runProject(${project.id})">Run Project Agents</button>
        </div>
      </article>
    `).join("")
    : "<p class='meta'>No projects yet.</p>";

  projectSelect.innerHTML = state.projects.map(project => `
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
        </p>
        <p>${escapeHtml(task.description || "No details provided.")}</p>
        <div class="actions">
          <button type="button" onclick="runTask(${task.id})">Run Agent</button>
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
            <button type="button" onclick="decideApproval(${approval.id}, 'APPROVED')">Approve</button>
            <button type="button" class="danger" onclick="decideApproval(${approval.id}, 'REJECTED')">Reject</button>
          </div>
        ` : `<p class="meta">${escapeHtml(approval.decision_notes || "No notes.")}</p>`}
      </article>
    `).join("")
    : "<p class='meta'>No approvals yet.</p>";
};

const renderRuns = () => {
  const list = document.querySelector("#runsList");

  list.innerHTML = state.runs.length
    ? state.runs.map(run => `
      <article class="item">
        <h4>${escapeHtml(run.agent_name)} - Task #${run.task_id}</h4>
        <p class="meta">
          <span class="badge">${escapeHtml(run.status)}</span>
          ${new Date(run.created_at).toLocaleString()}
        </p>
        <pre>${escapeHtml(run.output_text || "Still running or no output yet.")}</pre>
      </article>
    `).join("")
    : "<p class='meta'>No agent runs yet.</p>";
};

const refresh = async () => {
  [state.projects, state.tasks, state.agents, state.approvals, state.runs] = await Promise.all([
    api("/api/projects"),
    api("/api/tasks"),
    api("/api/agents"),
    api("/api/approvals"),
    api("/api/runs")
  ]);

  renderProjects();
  renderAgents();
  renderTasks();
  renderApprovals();
  renderRuns();
  await renderOllamaStatus();
};

window.runTask = async (taskId) => {
  await api(`/api/tasks/${taskId}/run`, { method: "POST" });
  await refresh();
};

window.runProject = async (projectId) => {
  await api(`/api/projects/${projectId}/run`, { method: "POST" });
  await refresh();
};

window.decideApproval = async (approvalId, status) => {
  const notes = window.prompt(`Notes for ${status.toLowerCase()} decision`, "") || "";
  await api(`/api/approvals/${approvalId}/decision`, {
    method: "POST",
    body: JSON.stringify({ status, notes })
  });
  await refresh();
};

document.querySelector("#refreshButton").addEventListener("click", refresh);

document.querySelector("#goalForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const status = document.querySelector("#goalStatus");
  const data = formData(event.currentTarget);
  data.auto_start = event.currentTarget.auto_start.checked;
  status.textContent = "Manager is planning the company workflow...";

  try {
    const result = await api("/api/goals", { method: "POST", body: JSON.stringify(data) });
    event.currentTarget.reset();
    event.currentTarget.auto_start.checked = true;
    status.textContent = `Created project #${result.project.id} and ${result.tasks.length} specialist tasks.`;
    await refresh();
  } catch (error) {
    status.textContent = error.message;
  }
});

document.querySelector("#projectForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = formData(event.currentTarget);
  await api("/api/projects", { method: "POST", body: JSON.stringify(data) });
  event.currentTarget.reset();
  await refresh();
});

document.querySelector("#taskForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = formData(event.currentTarget);
  data.project_id = Number(data.project_id);
  data.requires_approval = event.currentTarget.requires_approval.checked;
  await api("/api/tasks", { method: "POST", body: JSON.stringify(data) });
  event.currentTarget.reset();
  event.currentTarget.requires_approval.checked = true;
  await refresh();
});

refresh().catch(error => {
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="panel" style="position:fixed;right:16px;bottom:16px;max-width:420px;color:#b91c1c;">${escapeHtml(error.message)}</div>`
  );
});
