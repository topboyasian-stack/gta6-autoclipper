(() => {
  const qs = new URLSearchParams(window.location.search);
  const incomingToken = qs.get("access_token");
  if (incomingToken) {
    sessionStorage.setItem("creatorStudioToken", incomingToken);
    qs.delete("access_token");
    const cleanUrl = window.location.pathname + (qs.toString() ? "?" + qs.toString() : "") + window.location.hash;
    window.history.replaceState({}, "", cleanUrl);
  }
  const token = sessionStorage.getItem("creatorStudioToken") || "";
  const $ = (selector) => document.querySelector(selector);
  const notebookUrl = "https://colab.research.google.com/github/topboyasian-stack/gta6-autoclipper/blob/main/notebooks/GTA6_AutoClipper_Browser_Only.ipynb";
  let refreshTimer = null;

  function toast(message) {
    const el = $("#toast");
    el.textContent = message;
    el.classList.add("visible");
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => el.classList.remove("visible"), 3400);
  }

  async function api(url, options = {}) {
    const headers = new Headers(options.headers || {});
    if (token) headers.set("X-Studio-Token", token);
    const response = await fetch(url, {...options, headers});
    if (response.status === 401) {
      sessionStorage.removeItem("creatorStudioToken");
      throw new Error("Your private Studio link has expired. Reopen it from the Colab setup cell.");
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Could not connect to the production workspace.");
    return data;
  }

  function mediaUrl(projectId, kind) {
    const url = new URL("/api/studio/projects/" + encodeURIComponent(projectId) + "/media", window.location.origin);
    url.searchParams.set("kind", kind);
    return url.toString();
  }

  function dateLabel(value) {
    if (!value) return "Saved project";
    const parsed = new Date(value.replace(" ", "T"));
    return Number.isNaN(parsed.getTime())
      ? value
      : parsed.toLocaleString(undefined, {month:"short", day:"numeric", year:"numeric"});
  }

  function shortBytes(bytes) {
    const amount = Number(bytes || 0);
    if (amount < 1024 * 1024) return Math.max(1, Math.round(amount / 1024)) + " KB";
    return (amount / (1024 * 1024)).toFixed(1) + " MB";
  }

  function modeLabel(mode) {
    const map = {
      "Kids story production": "Puffy Kids Story",
      "Animated engineering explainer": "Engineering Explainer",
      "Gaming highlights": "Gaming Highlights",
      "AI scene assembly": "AI Scene Assembly",
      "Long-form video": "Long-form Video",
      "Multi-clip compilation": "Multi-clip Compilation"
    };
    return map[mode] || mode || "Production project";
  }

  function statusLabel(value) {
    const map = {
      running: "In production",
      ready: "Ready",
      sources_ready: "Sources ready",
      preview_ready: "Preview ready",
      exported: "Exported",
      complete: "Complete",
      stalled: "Needs attention",
      created: "New project",
      error: "Needs attention"
    };
    return map[value] || value.replaceAll("_", " ");
  }

  function makeButton(label, className, action) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.addEventListener("click", action);
    return button;
  }

  function openPreview(project, kind) {
    const media = $("#previewVideo");
    $("#previewTitle").textContent = (project.story?.title || project.name) + " · " + (kind === "final_video" ? "Final video" : "Draft preview");
    media.pause();
    media.src = mediaUrl(project.id, kind);
    media.load();
    $("#previewDialog").showModal();
  }

  async function downloadScript(project) {
    try {
      const response = await fetch("/api/studio/projects/" + encodeURIComponent(project.id) + "/script", {
        headers: token ? {"X-Studio-Token": token} : {}
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "The script is not available yet.");
      }
      const blob = await response.blob();
      const href = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = href;
      link.download = (project.story?.title || project.name || "story").replace(/[^A-Za-z0-9_-]+/g, "_") + "_script.md";
      document.body.append(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(href);
    } catch (error) {
      toast(error.message);
    }
  }

  function projectCard(project) {
    const card = document.createElement("article");
    card.className = "project-card";
    const cover = document.createElement("div");
    cover.className = "project-cover " + (project.mode === "Kids story production" ? "cover-puffy" : project.mode === "Animated engineering explainer" ? "cover-engineering" : "cover-general");
    const mark = document.createElement("span");
    mark.className = "cover-mark";
    mark.textContent = project.mode === "Kids story production" ? "✿" : project.mode === "Animated engineering explainer" ? "⌬" : "▣";
    const coverMode = document.createElement("span");
    coverMode.textContent = modeLabel(project.mode);
    cover.append(mark, coverMode);

    const body = document.createElement("div");
    body.className = "project-card-body";
    const status = document.createElement("span");
    status.className = "status-pill status-" + (project.status?.status || "created").replace(/[^a-z_]/g, "");
    status.textContent = statusLabel(project.status?.status || "created");
    const title = document.createElement("h3");
    title.textContent = project.story?.title || project.name;
    const sub = document.createElement("p");
    sub.className = "project-sub";
    sub.textContent = project.source_count + " source clips · " + dateLabel(project.updated_at || project.created_at);
    const message = document.createElement("p");
    message.className = "project-message";
    message.textContent = project.status?.message || "Saved to your Drive workspace.";
    body.append(status, title, sub, message);

    if (project.narration?.available) {
      const voice = document.createElement("div");
      voice.className = "voice-note";
      voice.textContent = (project.narration.profile || "Narration ready") + (project.narration.duration_seconds ? " · " + project.narration.duration_seconds.toFixed(1) + "s" : "");
      body.append(voice);
    }

    const actions = document.createElement("div");
    actions.className = "project-actions";
    const previewKind = project.media?.draft ? "draft" : project.media?.final_video ? "final_video" : null;
    if (previewKind) actions.append(makeButton("Preview", "small-button primary-small", () => openPreview(project, previewKind)));
    if (project.story?.script_available) actions.append(makeButton("Story script", "small-button", () => downloadScript(project)));
    if (project.media?.export_zip) {
      const exportLink = document.createElement("a");
      exportLink.className = "small-button download-small";
      exportLink.href = mediaUrl(project.id, "export_zip");
      exportLink.textContent = "Download ZIP ↓";
      actions.append(exportLink);
    }
    if (!actions.children.length) {
      const continueLink = document.createElement("a");
      continueLink.className = "small-button";
      continueLink.href = notebookUrl;
      continueLink.target = "_blank";
      continueLink.rel = "noopener";
      continueLink.textContent = "Continue in Colab ↗";
      actions.append(continueLink);
    }
    body.append(actions);
    card.append(cover, body);
    return card;
  }

  function renderProjects(projects) {
    const grid = $("#projectGrid");
    grid.replaceChildren();
    $("#projectPill").textContent = projects.length + (projects.length === 1 ? " PROJECT" : " PROJECTS");
    if (!projects.length) {
      $("#emptyState").hidden = false;
      grid.hidden = true;
      return;
    }
    $("#emptyState").hidden = true;
    grid.hidden = false;
    projects.slice(0, 12).forEach(project => grid.append(projectCard(project)));
  }

  function renderAssets(summary) {
    const assets = summary.shared_assets || {};
    const profiles = assets.voice_profiles || [];
    $("#voiceAssets").textContent = profiles.length ? profiles.join(" · ") : "No shared voice models detected yet.";
    $("#voiceStatus").textContent = assets.puffy_voice_ready ? "READY" : profiles.length ? "AVAILABLE" : "NOT FOUND";
    $("#voiceStatus").className = "asset-status " + (assets.puffy_voice_ready ? "asset-ok" : "");
    $("#musicAssets").textContent = assets.music_library_ready ? "Shared library is present in Drive." : "No shared music library detected.";
    $("#musicStatus").textContent = assets.music_library_ready ? "READY" : "NOT FOUND";
    $("#musicStatus").className = "asset-status " + (assets.music_library_ready ? "asset-ok" : "");
    $("#storageAssets").textContent = summary.workspace_ready ? "Connected to your production workspace." : "Drive production folder is not available.";
    $("#storageStatus").textContent = summary.workspace_ready ? "CONNECTED" : "OFFLINE";
    $("#storageStatus").className = "asset-status " + (summary.workspace_ready ? "asset-ok" : "asset-warn");
  }

  async function loadDashboard() {
    $("#connectionLabel").textContent = "Syncing";
    $("#connectionLabel").classList.remove("offline");
    try {
      const [summary, projects] = await Promise.all([
        api("/api/studio/summary"),
        api("/api/studio/projects")
      ]);
      $("#projectCount").textContent = summary.project_count ?? 0;
      $("#activeCount").textContent = summary.active_count ?? 0;
      $("#sourceCount").textContent = summary.source_count ?? 0;
      $("#exportCount").textContent = summary.export_count ?? 0;
      renderProjects(projects);
      renderAssets(summary);
      $("#connectionLabel").textContent = summary.workspace_ready ? "Drive connected" : "Workspace unavailable";
      if (!summary.workspace_ready) $("#connectionLabel").classList.add("offline");
    } catch (error) {
      $("#connectionLabel").textContent = "Connection issue";
      $("#connectionLabel").classList.add("offline");
      $("#projectGrid").replaceChildren();
      const problem = document.createElement("div");
      problem.className = "error-card";
      problem.textContent = error.message + " Check that the Colab runtime is still connected, then reopen the dashboard link from the setup cell.";
      $("#projectGrid").append(problem);
      toast(error.message);
    }
  }

  $("#refreshButton").addEventListener("click", loadDashboard);
  $("#closePreview").addEventListener("click", () => {
    $("#previewVideo").pause();
    $("#previewVideo").removeAttribute("src");
    $("#previewDialog").close();
  });
  $("#previewDialog").addEventListener("click", event => {
    if (event.target === $("#previewDialog")) $("#previewDialog").close();
  });
  $("#previewDialog").addEventListener("close", () => {
    $("#previewVideo").pause();
    $("#previewVideo").removeAttribute("src");
  });

  loadDashboard();
  window.setInterval(loadDashboard, 15000);
})();