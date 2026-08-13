const fileInput = document.querySelector("#fileInput");
const dropZone = document.querySelector("#dropZone");
const analyzeButton = document.querySelector("#analyzeButton");
const trailButton = document.querySelector("#trailButton");
const timelapseButton = document.querySelector("#timelapseButton");
const logOutput = document.querySelector("#logOutput");
const groupsPanel = document.querySelector("#groupsPanel");
const groupTitle = document.querySelector("#groupTitle");
const statusChip = document.querySelector("#statusChip");
const previewCanvas = document.querySelector("#previewCanvas");
const downloadLink = document.querySelector("#downloadLink");
const starfield = document.querySelector("#starfield");

let files = [];
let groups = [];
let selectedGroup = 0;

function log(lines) {
  logOutput.textContent = Array.isArray(lines) ? lines.join("\n") : String(lines);
  logOutput.scrollTop = logOutput.scrollHeight;
}

function settings() {
  return {
    threshold: Number(document.querySelector("#threshold").value),
    thumbSide: Number(document.querySelector("#thumbSide").value),
    maxSide: Number(document.querySelector("#maxSide").value),
    fps: Number(document.querySelector("#fps").value)
  };
}

function setBusy(busy) {
  [fileInput, analyzeButton, trailButton, timelapseButton].forEach((node) => {
    node.disabled = busy;
  });
  statusChip.textContent = busy ? "WORKING" : "BROWSER";
}

function setDownload(url, filename) {
  downloadLink.href = url;
  downloadLink.download = filename;
  downloadLink.hidden = false;
}

function clearDownload() {
  if (downloadLink.href) URL.revokeObjectURL(downloadLink.href);
  downloadLink.removeAttribute("href");
  downloadLink.removeAttribute("download");
  downloadLink.hidden = true;
}

function activeFiles() {
  if (!groups.length) return files;
  return groups[Math.min(selectedGroup, groups.length - 1)].files;
}

function chooseFiles(nextFiles) {
  files = Array.from(nextFiles).filter((file) => file.type.startsWith("image/"));
  groups = [];
  selectedGroup = 0;
  clearDownload();
  groupsPanel.innerHTML = "";
  groupTitle.textContent = files.length ? `${files.length} photo(s)` : "No Photos";
  log(files.length ? `Loaded ${files.length} browser-readable photo(s).` : "Awaiting input.");
}

fileInput.addEventListener("change", () => chooseFiles(fileInput.files));

for (const eventName of ["dragenter", "dragover"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragging");
  });
}

for (const eventName of ["dragleave", "drop"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
  });
}

dropZone.addEventListener("drop", (event) => {
  chooseFiles(event.dataTransfer.files);
});

analyzeButton.addEventListener("click", async () => {
  if (!files.length) return log("Select photos first.");
  setBusy(true);
  clearDownload();
  try {
    groups = await groupPhotos(files, settings());
    selectedGroup = 0;
    renderGroups();
    await previewGroup();
    log([`Groups: ${groups.length}`, ...groups.map((group, index) => `group_${String(index + 1).padStart(3, "0")}: ${group.files.length}`)]);
  } catch (error) {
    log(error.message || error);
  } finally {
    setBusy(false);
  }
});

trailButton.addEventListener("click", async () => {
  const selected = activeFiles();
  if (!selected.length) return log("Select photos first.");
  setBusy(true);
  clearDownload();
  try {
    const blob = await renderTrail(selected, settings());
    setDownload(URL.createObjectURL(blob), "tihulu-star-trail.png");
    log(`Trail ready from ${selected.length} frame(s).`);
  } catch (error) {
    log(error.message || error);
  } finally {
    setBusy(false);
  }
});

timelapseButton.addEventListener("click", async () => {
  const selected = activeFiles();
  if (!selected.length) return log("Select photos first.");
  setBusy(true);
  clearDownload();
  try {
    const blob = await renderTimelapse(selected, settings());
    setDownload(URL.createObjectURL(blob), "tihulu-timelapse.webm");
    log(`Timelapse ready from ${selected.length} frame(s).`);
  } catch (error) {
    log(error.message || error);
  } finally {
    setBusy(false);
  }
});

async function groupPhotos(inputFiles, options) {
  const signatures = [];
  for (const [index, file] of inputFiles.entries()) {
    log(`[${index + 1}/${inputFiles.length}] analyzing ${file.name}`);
    signatures.push({file, signature: await imageSignature(file, options.thumbSide)});
  }

  const detected = [];
  for (const item of signatures) {
    let best = null;
    let bestScore = -1;
    for (const group of detected) {
      const score = similarity(item.signature.hash, group.representative.hash);
      if (score > bestScore) {
        best = group;
        bestScore = score;
      }
    }
    if (!best || bestScore < options.threshold) {
      detected.push({representative: item.signature, files: [item.file], scores: [1]});
    } else {
      best.files.push(item.file);
      best.scores.push(bestScore);
    }
  }
  return detected;
}

async function imageSignature(file, side) {
  const bitmap = await decode(file);
  const canvas = createWorkCanvas(side, side);
  const ctx = canvas.getContext("2d", {willReadFrequently: true});
  ctx.fillStyle = "black";
  ctx.fillRect(0, 0, side, side);
  const target = contain(bitmap.width, bitmap.height, side);
  ctx.drawImage(bitmap, target.x, target.y, target.width, target.height);
  const pixels = ctx.getImageData(0, 0, side, side).data;
  const cells = 8;
  const cellSide = side / cells;
  const values = [];
  for (let y = 0; y < cells; y += 1) {
    for (let x = 0; x < cells; x += 1) {
      let total = 0;
      let count = 0;
      const sx = Math.floor(x * cellSide);
      const sy = Math.floor(y * cellSide);
      const ex = Math.floor((x + 1) * cellSide);
      const ey = Math.floor((y + 1) * cellSide);
      for (let py = sy; py < ey; py += 1) {
        for (let px = sx; px < ex; px += 1) {
          const offset = (py * side + px) * 4;
          total += 0.2126 * pixels[offset] + 0.7152 * pixels[offset + 1] + 0.0722 * pixels[offset + 2];
          count += 1;
        }
      }
      values.push(total / Math.max(count, 1));
    }
  }
  const average = values.reduce((sum, value) => sum + value, 0) / values.length;
  bitmap.close?.();
  return {hash: values.map((value) => value >= average ? 1 : 0)};
}

function similarity(first, second) {
  let same = 0;
  for (let index = 0; index < first.length; index += 1) {
    if (first[index] === second[index]) same += 1;
  }
  return same / first.length;
}

async function renderGroups() {
  groupsPanel.innerHTML = "";
  for (const [index, group] of groups.entries()) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `group-card${index === selectedGroup ? " active" : ""}`;
    const score = group.scores.length ? group.scores.reduce((sum, value) => sum + value, 0) / group.scores.length : 1;
    card.innerHTML = `<strong>group_${String(index + 1).padStart(3, "0")}</strong><span>${group.files.length} frame(s) / ${score.toFixed(2)}</span><div class="thumb-strip"></div>`;
    const strip = card.querySelector(".thumb-strip");
    for (const file of group.files.slice(0, 4)) {
      const image = document.createElement("img");
      image.alt = "";
      image.src = URL.createObjectURL(file);
      image.addEventListener("load", () => URL.revokeObjectURL(image.src), {once: true});
      strip.appendChild(image);
    }
    card.addEventListener("click", async () => {
      selectedGroup = index;
      renderGroups();
      await previewGroup();
    });
    groupsPanel.appendChild(card);
  }
}

async function previewGroup() {
  const selected = activeFiles();
  groupTitle.textContent = groups.length ? `group_${String(selectedGroup + 1).padStart(3, "0")}` : `${selected.length} photo(s)`;
  if (!selected.length) return;
  const bitmap = await decode(selected[0]);
  fitCanvas(previewCanvas, bitmap.width, bitmap.height, 900);
  const ctx = previewCanvas.getContext("2d");
  ctx.drawImage(bitmap, 0, 0, previewCanvas.width, previewCanvas.height);
  bitmap.close?.();
}

async function renderTrail(selected, options) {
  const first = await decode(selected[0]);
  fitCanvas(previewCanvas, first.width, first.height, options.maxSide);
  const width = previewCanvas.width;
  const height = previewCanvas.height;
  const ctx = previewCanvas.getContext("2d", {willReadFrequently: true});
  ctx.drawImage(first, 0, 0, width, height);
  first.close?.();
  let stack = ctx.getImageData(0, 0, width, height);
  const temp = createWorkCanvas(width, height);
  const tempCtx = temp.getContext("2d", {willReadFrequently: true});

  for (let index = 1; index < selected.length; index += 1) {
    log(`[${index + 1}/${selected.length}] stacking ${selected[index].name}`);
    const bitmap = await decode(selected[index]);
    tempCtx.clearRect(0, 0, width, height);
    tempCtx.drawImage(bitmap, 0, 0, width, height);
    bitmap.close?.();
    const frame = tempCtx.getImageData(0, 0, width, height);
    for (let offset = 0; offset < stack.data.length; offset += 4) {
      stack.data[offset] = Math.max(stack.data[offset], frame.data[offset]);
      stack.data[offset + 1] = Math.max(stack.data[offset + 1], frame.data[offset + 1]);
      stack.data[offset + 2] = Math.max(stack.data[offset + 2], frame.data[offset + 2]);
      stack.data[offset + 3] = 255;
    }
    ctx.putImageData(stack, 0, 0);
    await frameTick();
  }

  return new Promise((resolve, reject) => previewCanvas.toBlob((blob) => {
    if (blob) resolve(blob);
    else reject(new Error("Could not create PNG output."));
  }, "image/png"));
}

async function renderTimelapse(selected, options) {
  if (!previewCanvas.captureStream || !window.MediaRecorder) {
    throw new Error("This browser cannot record canvas video.");
  }
  const first = await decode(selected[0]);
  fitCanvas(previewCanvas, first.width, first.height, options.maxSide);
  first.close?.();
  const ctx = previewCanvas.getContext("2d");
  const stream = previewCanvas.captureStream(options.fps);
  const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp9") ? "video/webm;codecs=vp9" : "video/webm";
  const recorder = new MediaRecorder(stream, {mimeType});
  const chunks = [];
  recorder.addEventListener("dataavailable", (event) => {
    if (event.data.size) chunks.push(event.data);
  });
  const done = new Promise((resolve) => recorder.addEventListener("stop", resolve, {once: true}));
  recorder.start();
  for (let index = 0; index < selected.length; index += 1) {
    log(`[${index + 1}/${selected.length}] recording ${selected[index].name}`);
    const bitmap = await decode(selected[index]);
    ctx.clearRect(0, 0, previewCanvas.width, previewCanvas.height);
    ctx.drawImage(bitmap, 0, 0, previewCanvas.width, previewCanvas.height);
    bitmap.close?.();
    await delay(1000 / options.fps);
  }
  recorder.stop();
  await done;
  stream.getTracks().forEach((track) => track.stop());
  return new Blob(chunks, {type: mimeType});
}

async function decode(file) {
  if (window.createImageBitmap) {
    return createImageBitmap(file, {imageOrientation: "from-image"});
  }
  const url = URL.createObjectURL(file);
  try {
    const image = await new Promise((resolve, reject) => {
      const element = new Image();
      element.onload = () => resolve(element);
      element.onerror = reject;
      element.src = url;
    });
    return image;
  } finally {
    URL.revokeObjectURL(url);
  }
}

function fitCanvas(canvas, width, height, maxSide) {
  const scale = Math.min(maxSide / Math.max(width, height), 1);
  canvas.width = Math.max(1, Math.round(width * scale));
  canvas.height = Math.max(1, Math.round(height * scale));
}

function contain(width, height, side) {
  const scale = Math.min(side / width, side / height);
  const targetWidth = Math.round(width * scale);
  const targetHeight = Math.round(height * scale);
  return {
    x: Math.floor((side - targetWidth) / 2),
    y: Math.floor((side - targetHeight) / 2),
    width: targetWidth,
    height: targetHeight
  };
}

function createWorkCanvas(width, height) {
  if (window.OffscreenCanvas) return new OffscreenCanvas(width, height);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  return canvas;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function frameTick() {
  return new Promise((resolve) => requestAnimationFrame(resolve));
}

function startStarfield() {
  const ctx = starfield.getContext("2d");
  const stars = Array.from({length: 140}, () => ({
    x: Math.random(),
    y: Math.random(),
    r: 0.5 + Math.random() * 1.6,
    s: 0.25 + Math.random() * 0.65,
    hue: Math.random() > 0.72 ? PINK : CYAN
  }));

  function resize() {
    starfield.width = window.innerWidth * window.devicePixelRatio;
    starfield.height = window.innerHeight * window.devicePixelRatio;
  }

  function draw(time) {
    const width = starfield.width;
    const height = starfield.height;
    ctx.clearRect(0, 0, width, height);
    const gradient = ctx.createLinearGradient(0, 0, width, height);
    gradient.addColorStop(0, "#05070d");
    gradient.addColorStop(0.52, "#08111d");
    gradient.addColorStop(1, "#120617");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (const star of stars) {
      const drift = (time * 0.000018 * star.s) % 1;
      const x = ((star.x + drift) % 1) * width;
      const y = star.y * height;
      ctx.beginPath();
      ctx.fillStyle = star.hue;
      ctx.globalAlpha = 0.35 + Math.sin(time * 0.002 * star.s + star.x * 20) * 0.25;
      ctx.arc(x, y, star.r * window.devicePixelRatio, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
    requestAnimationFrame(draw);
  }

  window.addEventListener("resize", resize);
  resize();
  requestAnimationFrame(draw);
}

const CYAN = "#43f7ff";
const PINK = "#ff2bd6";
startStarfield();
