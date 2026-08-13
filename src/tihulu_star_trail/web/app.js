const form = document.querySelector("#jobForm");
const scanButton = document.querySelector("#scanButton");
const logOutput = document.querySelector("#logOutput");
const jobTitle = document.querySelector("#jobTitle");
const jobState = document.querySelector("#jobState");
const resultGrid = document.querySelector("#resultGrid");
let pollTimer = null;

function payload() {
  const timeMetadata = document.querySelector("#timeMetadata");
  const timeWindowInput = document.querySelector("#timeWindowHours") || document.querySelector("#timeWindowMinutes");
  return {
    action: document.querySelector("input[name='action']:checked").value,
    input: document.querySelector("#inputPath").value,
    output: document.querySelector("#outputPath").value,
    recursive: document.querySelector("#recursive").checked,
    timelapse: document.querySelector("#includeTimelapse").checked,
    time_metadata: Boolean(timeMetadata?.checked),
    threshold: Number(document.querySelector("#threshold").value),
    min_matches: Number(document.querySelector("#minMatches").value),
    min_frames: Number(document.querySelector("#minFrames").value),
    jpeg_quality: Number(document.querySelector("#jpegQuality").value),
    fps: Number(document.querySelector("#fps").value),
    video_max_side: Number(document.querySelector("#videoMaxSide").value),
    max_side: Number(document.querySelector("#maxSide").value),
    time_window_hours: Number(timeWindowInput?.value ?? 6),
    link_mode: document.querySelector("#linkMode").value,
    codec: "mp4v"
  };
}

function setBusy(isBusy) {
  form.querySelectorAll("button, input, select").forEach((node) => {
    node.disabled = isBusy;
  });
}

function writeLog(lines) {
  logOutput.textContent = lines.length ? lines.join("\n") : "Awaiting input.";
  logOutput.scrollTop = logOutput.scrollHeight;
}

function renderResult(result) {
  resultGrid.innerHTML = "";
  if (!result) return;
  const entries = [];
  if (result.groups !== undefined) entries.push(["Groups", String(result.groups)]);
  if (result.trails) entries.push(["Trails", String(result.trails.length)]);
  if (result.timelapses) entries.push(["Timelapses", String(result.timelapses.length)]);
  if (result.manifest) entries.push(["Manifest", result.manifest]);
  for (const [label, value] of entries) {
    const pill = document.createElement("div");
    pill.className = "result-pill";
    pill.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    resultGrid.appendChild(pill);
  }
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

async function poll(jobId) {
  const response = await fetch(`/api/jobs/${jobId}`);
  const job = await response.json();
  if (!response.ok) throw new Error(job.error || response.statusText);
  jobTitle.textContent = `${job.action} / ${job.id}`;
  jobState.textContent = job.status;
  writeLog(job.logs || []);
  renderResult(job.result);
  if (job.status === "completed" || job.status === "failed") {
    clearInterval(pollTimer);
    pollTimer = null;
    setBusy(false);
    if (job.status === "failed") {
      writeLog([...(job.logs || []), job.error || "Unknown failure"]);
    }
  }
}

scanButton.addEventListener("click", async () => {
  try {
    setBusy(true);
    const data = await postJson("/api/scan", payload());
    jobTitle.textContent = "Scan";
    jobState.textContent = "DONE";
    const extLines = Object.entries(data.extensions)
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([ext, count]) => `${ext}: ${count}`);
    writeLog([`Images: ${data.count}`, ...extLines]);
  } catch (error) {
    jobState.textContent = "ERROR";
    writeLog([String(error.message || error)]);
  } finally {
    setBusy(false);
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    setBusy(true);
    resultGrid.innerHTML = "";
    jobState.textContent = "QUEUED";
    writeLog(["Submitting job..."]);
    const data = await postJson("/api/run", payload());
    await poll(data.job_id);
    pollTimer = setInterval(() => poll(data.job_id).catch((error) => {
      clearInterval(pollTimer);
      pollTimer = null;
      setBusy(false);
      jobState.textContent = "ERROR";
      writeLog([String(error.message || error)]);
    }), 1200);
  } catch (error) {
    setBusy(false);
    jobState.textContent = "ERROR";
    writeLog([String(error.message || error)]);
  }
});
