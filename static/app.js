// Global State
let isRunning = false;
let startTime = null;
let timerInterval = null;
let ws = null;
let selectedFilesCount = 0;
let defaultOutputDir = "";
let browserCurrentPath = "";
let presetsData = {};

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  initWebSocket();
  initDropzone();
  fetchStatus();
});

// WebSocket Connection
function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/progress`;

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log("WebSocket connected to PDF Auto Rename stream.");
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleProgressEvent(data);
    } catch (e) {
      console.error("Invalid WS message:", e);
    }
  };

  ws.onclose = () => {
    console.warn("WebSocket disconnected. Retrying in 2 seconds...");
    setTimeout(initWebSocket, 2000);
  };
}

// Fetch Initial Status
async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    if (data.master_records !== undefined) {
      const billingTag = data.master_billing ? ` • Billing #${data.master_billing}` : "";
      document.getElementById("masterStatus").textContent = `${data.active_master} (${data.master_records} records${billingTag})`;
    }
    if (data.active_periods) {
      const countTag = data.periods_count !== undefined ? ` (${data.periods_count} mappings)` : "";
      document.getElementById("periodsStatus").textContent = `${data.active_periods}${countTag}`;
    }
    if (data.output_dir) {
      defaultOutputDir = data.output_dir;
      const outputInput = document.getElementById("outputFolderInput");
      if (outputInput && !outputInput.value) {
        outputInput.value = data.output_dir;
      }
    }
    if (data.is_running) {
      setRunningState(true);
    }
    if (data.uploaded_files && Array.isArray(data.uploaded_files)) {
      currentUploadedFiles = data.uploaded_files;
      renderUploadedFileList();
    }
    // Load presets in background
    fetch("/api/browse-folders")
      .then(r => r.json())
      .then(bData => {
        if (bData.presets) {
          bData.presets.forEach(p => {
            presetsData[p.name] = p.path;
          });
        }
      })
      .catch(() => {});
  } catch (err) {
    console.error("Error fetching status:", err);
  }
}

// Dropzone & File Upload
function initDropzone() {
  const dropzone = document.getElementById("dropzone");

  ["dragenter", "dragover"].forEach(event => {
    dropzone.addEventListener(event, e => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(event => {
    dropzone.addEventListener(event, e => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", e => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      uploadFiles(files);
    }
  });
}

function handleFileSelect(event) {
  const files = event.target.files;
  if (files && files.length > 0) {
    uploadFiles(files);
  }
  event.target.value = "";
}

let currentUploadedFiles = [];

async function uploadFiles(fileList) {
  const formData = new FormData();
  for (let i = 0; i < fileList.length; i++) {
    if (fileList[i].name.toLowerCase().endsWith(".pdf")) {
      formData.append("files", fileList[i]);
    }
  }

  appendLog(`Uploading ${formData.getAll("files").length} PDF file(s)...`, "info");

  try {
    const res = await fetch("/api/upload-pdfs", {
      method: "POST",
      body: formData
    });
    const data = await res.json();

    // Merge uniquely into currentUploadedFiles
    data.files.forEach(f => {
      if (!currentUploadedFiles.includes(f)) {
        currentUploadedFiles.push(f);
      }
    });

    renderUploadedFileList();
    appendLog(`Uploaded ${data.files.length} PDF file(s). Total active in queue: ${currentUploadedFiles.length}.`, "ok");
    document.getElementById("btnStart").disabled = currentUploadedFiles.length === 0;
  } catch (err) {
    appendLog(`Upload failed: ${err.message}`, "err");
  }
}

function renderUploadedFileList() {
  const list = document.getElementById("uploadedFileList");
  if (!list) return;
  list.innerHTML = "";

  currentUploadedFiles.forEach((f, idx) => {
    const li = document.createElement("li");
    li.style.display = "flex";
    li.style.justifyContent = "space-between";
    li.style.alignItems = "center";
    
    const span = document.createElement("span");
    span.textContent = f;
    span.title = f;
    span.style.overflow = "hidden";
    span.style.textOverflow = "ellipsis";
    span.style.whiteSpace = "nowrap";

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.innerHTML = "&times;";
    removeBtn.title = "Remove file";
    removeBtn.style.background = "none";
    removeBtn.style.border = "none";
    removeBtn.style.color = "#e74c3c";
    removeBtn.style.cursor = "pointer";
    removeBtn.style.fontSize = "16px";
    removeBtn.style.fontWeight = "bold";
    removeBtn.style.padding = "0 6px";
    removeBtn.onclick = (e) => {
      e.stopPropagation();
      removeUploadedFile(f);
    };

    li.appendChild(span);
    li.appendChild(removeBtn);
    list.appendChild(li);
  });

  selectedFilesCount = currentUploadedFiles.length;
  const btnStart = document.getElementById("btnStart");
  if (btnStart) {
    btnStart.disabled = selectedFilesCount === 0;
  }
}

async function removeUploadedFile(filename) {
  try {
    await fetch("/api/remove-upload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename })
    });
  } catch (_) {}

  currentUploadedFiles = currentUploadedFiles.filter(f => f !== filename);
  renderUploadedFileList();
  appendLog(`Removed file: ${filename}`, "dim");
}

async function clearUploadedFiles() {
  try {
    await fetch("/api/clear-uploads", { method: "POST" });
  } catch (_) {}

  currentUploadedFiles = [];
  renderUploadedFileList();
  appendLog("Cleared uploaded files queue and purged upload cache.", "dim");
}

// Master / Periods Upload
async function uploadMaster(event) {
  const file = event.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  appendLog(`Uploading new master spreadsheet: ${file.name}...`, "info");
  try {
    const res = await fetch("/api/upload-master", { method: "POST", body: formData });
    const text = await res.text();
    let data = {};
    try {
      data = JSON.parse(text);
    } catch (_) {}

    if (!res.ok) {
      const errMsg = data.message || data.error || text || `Server error ${res.status}`;
      appendLog(`Failed to update master list: ${errMsg}`, "err");
      return;
    }

    const billingTag = data.billing ? ` • Billing #${data.billing}` : "";
    document.getElementById("masterStatus").textContent = `${file.name} (${data.records} records${billingTag})`;
    appendLog(`Master list updated: ${data.records} records loaded from ${file.name}${billingTag}.`, "ok");
  } catch (err) {
    appendLog(`Failed to update master list: ${err.message}`, "err");
  } finally {
    event.target.value = "";
  }
}

async function uploadPeriods(event) {
  const file = event.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  appendLog(`Uploading billing periods: ${file.name}...`, "info");
  try {
    const res = await fetch("/api/upload-periods", { method: "POST", body: formData });
    const text = await res.text();
    let data = {};
    try {
      data = JSON.parse(text);
    } catch (_) {}

    if (!res.ok) {
      const errMsg = data.message || data.error || text || `Server error ${res.status}`;
      appendLog(`Failed to update billing periods: ${errMsg}`, "err");
      return;
    }

    document.getElementById("periodsStatus").textContent = `${file.name} (${data.count} mappings)`;
    appendLog(`Billing periods updated (${data.count} mappings loaded from ${file.name}).`, "ok");
  } catch (err) {
    appendLog(`Failed to update billing periods: ${err.message}`, "err");
  } finally {
    event.target.value = "";
  }
}


// Reset Output Folder
function resetOutputDir() {
  const outputInput = document.getElementById("outputFolderInput");
  if (outputInput) {
    outputInput.value = defaultOutputDir;
    appendLog(`Output folder reset to default: ${defaultOutputDir}`, "dim");
  }
}

// Quick Preset Selection
function setQuickPath(type) {
  const outputInput = document.getElementById("outputFolderInput");
  if (!outputInput) return;

  if (presetsData[type]) {
    outputInput.value = presetsData[type];
    appendLog(`Output folder set to: ${presetsData[type]}`, "info");
  } else if (type === "network") {
    resetOutputDir();
  } else if (type === "local") {
    outputInput.value = "output";
    appendLog("Output folder set to project output/", "info");
  }
}

// Native Windows Folder Picker
async function openFolderBrowser() {
  const currentVal = (document.getElementById("outputFolderInput")?.value || "").trim();
  appendLog("Opening Windows Folder Explorer dialog...", "info");

  try {
    const res = await fetch("/api/browse-native", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_path: currentVal })
    });
    const data = await res.json();
    if (data.path) {
      document.getElementById("outputFolderInput").value = data.path;
      appendLog(`Output folder set to: ${data.path}`, "ok");
    } else {
      appendLog("Folder selection cancelled.", "dim");
    }
  } catch (err) {
    appendLog(`Failed to open folder picker: ${err.message}`, "err");
  }
}



// Start Processing
async function startProcessing() {
  if (isRunning) return;

  if (selectedFilesCount === 0) {
    appendLog("Please upload at least one PDF invoice before starting.", "warn");
    return;
  }

  const dryRun = document.getElementById("chkDryRun").checked;
  const outputFolderVal = (document.getElementById("outputFolderInput")?.value || "").trim();

  setRunningState(true);
  clearLog();
  appendLog(`Starting process (${selectedFilesCount} uploaded file(s), dry_run=${dryRun})...`, "info");
  if (outputFolderVal) {
    appendLog(`Target output folder: ${outputFolderVal}`, "info");
  }

  try {
    const res = await fetch("/api/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: "upload",
        dry_run: dryRun,
        output_dir: outputFolderVal || null,
        files: currentUploadedFiles
      })
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      const errMsg = data.error || data.message || `Server error ${res.status}`;
      appendLog(`Error: ${errMsg}`, "err");
      setRunningState(false);
    }
  } catch (err) {
    appendLog(`Failed to start job: ${err.message}`, "err");
    setRunningState(false);
  }
}

// Cancel Processing
async function cancelProcessing() {
  appendLog("Sending cancellation request...", "warn");
  try {
    await fetch("/api/cancel", { method: "POST" });
  } catch (err) {
    appendLog(`Cancellation error: ${err.message}`, "err");
  }
}

// Toggle Dry Run
function toggleDryRun(e) {
  const banner = document.getElementById("dryRunBanner");
  banner.style.display = e.target.checked ? "block" : "none";
}

// Handle WebSocket Progress Events
function handleProgressEvent(ev) {
  const phase = ev.phase;

  if (phase === "startup") {
    document.getElementById("serverStatusText").textContent = "Initializing...";
    appendLog(ev.message || "Loading OCR model and preparing pipeline...", "info");
    return;
  }

  if (phase === "ready") {
    document.getElementById("serverStatusText").textContent = "Processing";
    document.getElementById("statTotal").textContent = ev.total_pages;
    appendLog(`Ready: Found ${ev.total_pages} page(s) across ${ev.input_files} file(s). Loaded ${ev.excel_records} Excel records.`, "ok");
    return;
  }

  if (phase === "page") {
    const curr = ev.current;
    const total = ev.total;
    const pct = total > 0 ? Math.round((curr / total) * 100) : 0;

    // Progress bar & text
    document.getElementById("progressBarFill").style.width = `${pct}%`;
    document.getElementById("progressPercent").textContent = `${curr} / ${total} (${pct}%)`;

    // Item details
    document.getElementById("currFile").textContent = ev.filename || "—";
    document.getElementById("currCompany").textContent = ev.company || "—";
    document.getElementById("currBilling").textContent = ev.billing || "—";
    document.getElementById("currPeriod").textContent = ev.billing_period || "—";
    document.getElementById("currConfidence").textContent = ev.confidence || "—";
    document.getElementById("currSavedAs").textContent = ev.saved_as || "—";

    // Stat counters
    document.getElementById("statSuccess").textContent = ev.success;
    document.getElementById("statFailed").textContent = ev.failed;
    document.getElementById("statManual").textContent = ev.unknown;

    // Log line
    const logTag = ev.status.includes("✓") ? "ok" : ev.status.includes("UNKNOWN") ? "warn" : "err";
    appendLog(`[${curr}/${total}] ${ev.filename} ➔ ${ev.saved_as} (${ev.status})`, logTag);
    return;
  }

  if (phase === "complete" || phase === "cancelled") {
    setRunningState(false);
    const isCancelled = phase === "cancelled" || ev.cancelled;
    document.getElementById("serverStatusText").textContent = isCancelled ? "Cancelled" : "Completed";

    appendLog(
      isCancelled
        ? `PROCESS CANCELLED: Processed ${ev.success} success, ${ev.failed} failed.`
        : `PROCESS COMPLETED: ${ev.success} successful, ${ev.failed} failed, ${ev.unknown} manual review.`,
      isCancelled ? "warn" : "ok"
    );

    // If uploaded files were processed, show download ZIP button
    if (activeTab === "upload" && ev.success > 0 && !ev.dry_run) {
      document.getElementById("resultsActions").style.display = "block";
    }
  }
}

// UI State Management
function setRunningState(running) {
  isRunning = running;
  document.getElementById("btnStart").disabled = running;
  document.getElementById("btnCancel").disabled = !running;

  const dot = document.getElementById("statusDot");
  dot.className = "dot " + (running ? "running" : "idle");
  document.getElementById("serverStatusText").textContent = running ? "Processing..." : "Idle";

  if (running) {
    startTime = Date.now();
    timerInterval = setInterval(updateTimer, 1000);
    document.getElementById("resultsActions").style.display = "none";
  } else {
    clearInterval(timerInterval);
  }
}

function updateTimer() {
  if (!startTime) return;
  const elapsed = Math.floor((Date.now() - startTime) / 1000);
  const m = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const s = String(elapsed % 60).padStart(2, "0");
  document.getElementById("elapsedTimer").textContent = `${m}:${s}`;
}

// Activity Log Helper
function appendLog(msg, type = "info") {
  const stream = document.getElementById("logStream");
  if (!stream) return;
  const div = document.createElement("div");
  div.className = `log-entry ${type}`;
  const time = new Date().toLocaleTimeString();
  div.textContent = `[${time}] ${msg}`;
  stream.appendChild(div);

  // Keep DOM lean to avoid browser lag when processing 500+ pages
  while (stream.childElementCount > 250) {
    stream.removeChild(stream.firstElementChild);
  }

  stream.scrollTop = stream.scrollHeight;
}

function clearLog() {
  document.getElementById("logStream").innerHTML = "";
}
