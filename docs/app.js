const fileInput = document.querySelector("#fileInput");
const dropZone = document.querySelector("#dropZone");
const analyzeButton = document.querySelector("#analyzeButton");
const trailButton = document.querySelector("#trailButton");
const timelapseButton = document.querySelector("#timelapseButton");
const timeMetadataToggle = document.querySelector("#timeMetadata");
const timeWindowInput = document.querySelector("#timeWindowMinutes");
const logOutput = document.querySelector("#logOutput");
const groupsPanel = document.querySelector("#groupsPanel");
const groupTitle = document.querySelector("#groupTitle");
const statusChip = document.querySelector("#statusChip");
const previewCanvas = document.querySelector("#previewCanvas");
const downloadLink = document.querySelector("#downloadLink");
const starfield = document.querySelector("#starfield");
const editorTitle = document.querySelector("#editorTitle");
const photoCounter = document.querySelector("#photoCounter");
const photoPreview = document.querySelector("#photoPreview");
const photoName = document.querySelector("#photoName");
const previousPhotoButton = document.querySelector("#previousPhotoButton");
const nextPhotoButton = document.querySelector("#nextPhotoButton");
const targetGroup = document.querySelector("#targetGroup");
const movePhotoButton = document.querySelector("#movePhotoButton");
const removePhotoButton = document.querySelector("#removePhotoButton");
const undoButton = document.querySelector("#undoButton");
const groupNameInput = document.querySelector("#groupNameInput");
const renameGroupButton = document.querySelector("#renameGroupButton");
const addGroupButton = document.querySelector("#addGroupButton");
const filmstripCount = document.querySelector("#filmstripCount");
const photoStrip = document.querySelector("#photoStrip");

let files = [];
let groups = [];
let selectedGroup = 0;
let selectedPhotoIndex = 0;
let isBusy = false;
let photoPreviewUrl = "";
let photoPreviewFile = null;
let canvasPreviewToken = 0;
let photoStripKey = "";
let undoStack = [];

const SIGNATURE_CELLS = 12;
const MAX_UNDO_STATES = 50;

function log(lines) {
  logOutput.textContent = Array.isArray(lines) ? lines.join("\n") : String(lines);
  logOutput.scrollTop = logOutput.scrollHeight;
}

function settings() {
  const imageFormat = document.querySelector("#imageFormat").value;
  const imageQuality = clamp(Number(document.querySelector("#imageQuality").value), 1, 100);
  const videoFormat = document.querySelector("#videoFormat").value;
  const videoQualityMbps = clamp(Number(document.querySelector("#videoQuality").value), 0.5, 50);
  const timeWindowMinutes = clamp(Number(timeWindowInput.value), 1, 43200);
  return {
    threshold: Number(document.querySelector("#threshold").value),
    thumbSide: Number(document.querySelector("#thumbSide").value),
    maxSide: Number(document.querySelector("#maxSide").value),
    imageFormat,
    imageQuality,
    imageQualityRatio: imageQuality / 100,
    imageExtension: imageFormat === "image/jpeg" ? "jpg" : "png",
    fps: Number(document.querySelector("#fps").value),
    videoFormat,
    videoExtension: videoFormat === "video/mp4" ? "mp4" : "webm",
    videoLabel: videoFormat === "video/mp4" ? "MP4" : "WebM",
    videoQualityMbps,
    videoBitsPerSecond: Math.round(videoQualityMbps * 1000000),
    useTimeMetadata: timeMetadataToggle.checked,
    timeWindowMinutes,
    timeWindowMs: timeWindowMinutes * 60000
  };
}

function setBusy(busy) {
  isBusy = busy;
  [fileInput, analyzeButton, trailButton, timelapseButton].forEach((node) => {
    node.disabled = busy;
  });
  statusChip.textContent = busy ? "WORKING" : "BROWSER";
  renderEditor();
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
  const group = activeGroup();
  return group ? group.files : files;
}

function activeGroup() {
  if (!groups.length) return null;
  selectedGroup = Math.min(selectedGroup, groups.length - 1);
  return groups[selectedGroup];
}

function chooseFiles(nextFiles) {
  files = Array.from(nextFiles).filter((file) => file.type.startsWith("image/"));
  groups = [];
  selectedGroup = 0;
  selectedPhotoIndex = 0;
  undoStack = [];
  photoStripKey = "";
  clearDownload();
  groupsPanel.innerHTML = "";
  groupTitle.textContent = files.length ? `${files.length} photo(s)` : "No Photos";
  log(files.length ? `Loaded ${files.length} browser-readable photo(s).` : "Awaiting input.");
  renderEditor();
  void previewCurrentPhoto();
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
    selectedPhotoIndex = 0;
    undoStack = [];
    photoStripKey = "";
    renderGroups();
    renderEditor();
    await previewCurrentPhoto();
    log([`Groups: ${groups.length}`, ...groups.map((group, index) => `${groupLabel(index)}: ${group.files.length}`)]);
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
    const options = settings();
    const blob = await renderTrail(selected, options);
    setDownload(URL.createObjectURL(blob), `tihulu-star-trail.${options.imageExtension}`);
    log(`Trail ready from ${selected.length} frame(s) at ${options.imageFormat.split("/")[1].toUpperCase()} quality ${options.imageQuality}.`);
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
    const options = settings();
    const blob = await renderTimelapse(selected, options);
    setDownload(URL.createObjectURL(blob), `tihulu-timelapse.${options.videoExtension}`);
    log(`Timelapse ${options.videoLabel} ready from ${selected.length} frame(s) at ${options.videoQualityMbps} Mbps.`);
  } catch (error) {
    log(error.message || error);
  } finally {
    setBusy(false);
  }
});

previousPhotoButton.addEventListener("click", async () => {
  await selectPhoto(selectedPhotoIndex - 1);
});

nextPhotoButton.addEventListener("click", async () => {
  await selectPhoto(selectedPhotoIndex + 1);
});

movePhotoButton.addEventListener("click", async () => {
  await moveSelectedPhoto();
});

removePhotoButton.addEventListener("click", async () => {
  await removeSelectedPhoto();
});

undoButton.addEventListener("click", async () => {
  await undoLastEdit();
});

addGroupButton.addEventListener("click", async () => {
  await addManualGroup();
});

renameGroupButton.addEventListener("click", () => {
  renameSelectedGroup();
});

groupNameInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    renameSelectedGroup();
  }
});

document.addEventListener("keydown", (event) => {
  if (isBusy || isTypingTarget(event.target)) return;
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z" && !event.shiftKey) {
    event.preventDefault();
    void undoLastEdit();
    return;
  }
  if (event.key === "ArrowLeft" && activeFiles().length > 1) {
    event.preventDefault();
    void selectPhoto(selectedPhotoIndex - 1);
  }
  if (event.key === "ArrowRight" && activeFiles().length > 1) {
    event.preventDefault();
    void selectPhoto(selectedPhotoIndex + 1);
  }
});

async function groupPhotos(inputFiles, options) {
  const groupedFiles = options.useTimeMetadata
    ? Array.from(inputFiles).sort(compareFileTime)
    : inputFiles;
  const signatures = [];
  for (const [index, file] of groupedFiles.entries()) {
    log(`[${index + 1}/${groupedFiles.length}] analyzing ${file.name}`);
    signatures.push({file, signature: await imageSignature(file, options.thumbSide)});
  }

  const detected = [];
  for (const item of signatures) {
    let best = null;
    let bestScore = -1;
    for (const group of detected) {
      const representativeAllowed = timeCompatible(item.signature, group.representative, options);
      const latestAllowed = timeCompatible(item.signature, group.lastSignature, options);
      if (!representativeAllowed && !latestAllowed) continue;

      const representativeScore = representativeAllowed ? similarity(item.signature, group.representative) : 0;
      const latestScore = latestAllowed ? similarity(item.signature, group.lastSignature) : 0;
      const score = latestScore > representativeScore && (
        representativeScore >= options.threshold * 0.72 || !representativeAllowed
      )
        ? latestScore
        : representativeScore;
      if (score > bestScore) {
        best = group;
        bestScore = score;
      }
    }
    if (!best || bestScore < options.threshold) {
      detected.push({name: defaultGroupName(detected.length), representative: item.signature, lastSignature: item.signature, files: [item.file], scores: [1]});
    } else {
      best.files.push(item.file);
      best.scores.push(bestScore);
      best.lastSignature = item.signature;
    }
  }
  return detected;
}

async function imageSignature(file, side) {
  const bitmap = await decode(file);
  const aspect = bitmap.width / Math.max(bitmap.height, 1);
  const canvas = createWorkCanvas(side, side);
  const ctx = canvas.getContext("2d", {willReadFrequently: true});
  ctx.fillStyle = "black";
  ctx.fillRect(0, 0, side, side);
  const target = contain(bitmap.width, bitmap.height, side);
  ctx.drawImage(bitmap, target.x, target.y, target.width, target.height);
  const pixels = ctx.getImageData(0, 0, side, side).data;
  const pixelCount = side * side;
  const lumaGrid = new Float32Array(pixelCount);
  let lumaTotal = 0;
  let lumaSquares = 0;
  let redTotal = 0;
  let greenTotal = 0;
  let blueTotal = 0;

  for (let index = 0; index < pixelCount; index += 1) {
    const offset = index * 4;
    const red = pixels[offset];
    const green = pixels[offset + 1];
    const blue = pixels[offset + 2];
    const luma = 0.2126 * red + 0.7152 * green + 0.0722 * blue;
    lumaGrid[index] = luma;
    lumaTotal += luma;
    lumaSquares += luma * luma;
    redTotal += red;
    greenTotal += green;
    blueTotal += blue;
  }

  const meanLuma = lumaTotal / Math.max(pixelCount, 1);
  const contrast = Math.sqrt(Math.max(lumaSquares / Math.max(pixelCount, 1) - meanLuma * meanLuma, 0));
  const luma = [];
  const edges = [];
  const colors = [];
  const cells = Math.min(SIGNATURE_CELLS, Math.max(4, Math.floor(side / 4)));

  for (let cellY = 0; cellY < cells; cellY += 1) {
    for (let cellX = 0; cellX < cells; cellX += 1) {
      const sx = Math.floor(cellX * side / cells);
      const sy = Math.floor(cellY * side / cells);
      const ex = Math.floor((cellX + 1) * side / cells);
      const ey = Math.floor((cellY + 1) * side / cells);
      let totalLuma = 0;
      let totalEdge = 0;
      let totalRed = 0;
      let totalGreen = 0;
      let totalBlue = 0;
      let count = 0;
      for (let py = sy; py < ey; py += 1) {
        for (let px = sx; px < ex; px += 1) {
          const index = py * side + px;
          const offset = index * 4;
          const current = lumaGrid[index];
          const right = px + 1 < side ? lumaGrid[index + 1] : current;
          const down = py + 1 < side ? lumaGrid[index + side] : current;
          totalLuma += current;
          totalEdge += Math.min(Math.hypot(right - current, down - current) / 255, 1);
          totalRed += pixels[offset];
          totalGreen += pixels[offset + 1];
          totalBlue += pixels[offset + 2];
          count += 1;
        }
      }
      const safeCount = Math.max(count, 1);
      const colorTotal = totalRed + totalGreen + totalBlue;
      luma.push((totalLuma / safeCount - meanLuma) / Math.max(contrast, 1));
      edges.push(totalEdge / safeCount);
      if (colorTotal > safeCount * 8) {
        colors.push(totalRed / colorTotal, totalGreen / colorTotal, totalBlue / colorTotal);
      } else {
        colors.push(0, 0, 0);
      }
    }
  }

  bitmap.close?.();
  return {
    luma: centeredUnitVector(luma),
    edges: centeredUnitVector(edges),
    colors,
    meanColor: [
      redTotal / Math.max(pixelCount * 255, 1),
      greenTotal / Math.max(pixelCount * 255, 1),
      blueTotal / Math.max(pixelCount * 255, 1)
    ],
    meanLuma: meanLuma / 255,
    contrast: contrast / 255,
    aspect,
    capturedAt: fileTime(file)
  };
}

function compareFileTime(first, second) {
  const firstTime = fileTime(first) ?? 0;
  const secondTime = fileTime(second) ?? 0;
  return firstTime - secondTime || first.name.localeCompare(second.name);
}

function fileTime(file) {
  return Number.isFinite(file.lastModified) && file.lastModified > 0
    ? file.lastModified
    : null;
}

function timeCompatible(first, second, options) {
  if (!options.useTimeMetadata) return true;
  const firstTime = first?.capturedAt;
  const secondTime = second?.capturedAt;
  if (!Number.isFinite(firstTime) || !Number.isFinite(secondTime)) return true;
  return Math.abs(firstTime - secondTime) <= options.timeWindowMs;
}

function similarity(first, second) {
  const structureScore = vectorSimilarity(first.luma, second.luma);
  const edgeScore = vectorSimilarity(first.edges, second.edges);
  const colorScore = distanceSimilarity(first.colors, second.colors, 0.28);
  const meanColorScore = distanceSimilarity(first.meanColor, second.meanColor, 0.35);
  const brightnessScore = scalarSimilarity(first.meanLuma, second.meanLuma, 0.30);
  const contrastScore = scalarSimilarity(first.contrast, second.contrast, 0.22);
  const aspectScore = scalarSimilarity(Math.log(first.aspect), Math.log(second.aspect), Math.log(1.5));
  let score = (
    (0.40 * structureScore)
    + (0.22 * edgeScore)
    + (0.17 * colorScore)
    + (0.08 * meanColorScore)
    + (0.05 * brightnessScore)
    + (0.05 * contrastScore)
    + (0.03 * aspectScore)
  );
  score = softGate(score, structureScore, 0.52);
  score = softGate(score, edgeScore, 0.42);
  score = softGate(score, colorScore, 0.35);
  score = softGate(score, meanColorScore, 0.35);
  return clamp(score, 0, 1);
}

function centeredUnitVector(values) {
  if (!values.length) return [];
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  const centered = values.map((value) => value - mean);
  const norm = Math.sqrt(centered.reduce((sum, value) => sum + value * value, 0));
  if (norm < 0.000001) return centered.map(() => 0);
  return centered.map((value) => value / norm);
}

function vectorSimilarity(first, second) {
  if (!first.length || first.length !== second.length) return 0;
  let dot = 0;
  let firstNorm = 0;
  let secondNorm = 0;
  for (let index = 0; index < first.length; index += 1) {
    dot += first[index] * second[index];
    firstNorm += first[index] * first[index];
    secondNorm += second[index] * second[index];
  }
  if (firstNorm < 0.000001 || secondNorm < 0.000001) return 0;
  return clamp((dot / Math.sqrt(firstNorm * secondNorm) + 1) / 2, 0, 1);
}

function distanceSimilarity(first, second, scale) {
  if (!first.length || first.length !== second.length) return 0;
  let total = 0;
  for (let index = 0; index < first.length; index += 1) {
    const delta = first[index] - second[index];
    total += delta * delta;
  }
  const rms = Math.sqrt(total / first.length);
  return clamp(1 - rms / Math.max(scale, 0.000001), 0, 1);
}

function scalarSimilarity(first, second, tolerance) {
  return clamp(1 - Math.abs(first - second) / Math.max(tolerance, 0.000001), 0, 1);
}

function softGate(score, value, minimum) {
  if (value >= minimum) return score;
  return score * Math.max(value, 0) / Math.max(minimum, 0.000001);
}

async function renderGroups() {
  groupsPanel.innerHTML = "";
  for (const [index, group] of groups.entries()) {
    const card = document.createElement("button");
    card.type = "button";
    card.disabled = isBusy;
    card.className = `group-card${index === selectedGroup ? " active" : ""}`;

    const title = document.createElement("strong");
    title.textContent = groupLabel(index);
    const meta = document.createElement("span");
    meta.textContent = groupSummary(group);
    const strip = document.createElement("div");
    strip.className = "thumb-strip";

    for (const file of group.files.slice(0, 4)) {
      const image = document.createElement("img");
      image.alt = "";
      image.src = URL.createObjectURL(file);
      image.addEventListener("load", () => URL.revokeObjectURL(image.src), {once: true});
      image.addEventListener("error", () => URL.revokeObjectURL(image.src), {once: true});
      strip.appendChild(image);
    }

    card.append(title, meta, strip);
    card.addEventListener("click", async () => {
      selectedGroup = index;
      selectedPhotoIndex = 0;
      renderGroups();
      renderEditor();
      await previewCurrentPhoto();
    });
    groupsPanel.appendChild(card);
  }
}

function renderEditor() {
  const selected = activeFiles();
  const group = activeGroup();
  const hasGroup = Boolean(group);
  const hasPhoto = selected.length > 0;
  if (selectedPhotoIndex >= selected.length) selectedPhotoIndex = Math.max(0, selected.length - 1);

  editorTitle.textContent = group ? groupLabel(selectedGroup) : files.length ? "All Photos" : "Photo Editor";
  photoCounter.textContent = hasPhoto ? `${selectedPhotoIndex + 1} / ${selected.length}` : "0 / 0";
  photoName.textContent = hasPhoto ? selected[selectedPhotoIndex].name : "Select photos.";
  groupNameInput.value = hasGroup ? groupLabel(selectedGroup) : "";
  setPhotoPreview(hasPhoto ? selected[selectedPhotoIndex] : null);
  renderPhotoStrip();

  previousPhotoButton.disabled = isBusy || selected.length < 2;
  nextPhotoButton.disabled = isBusy || selected.length < 2;
  removePhotoButton.disabled = isBusy || !hasPhoto;
  undoButton.disabled = isBusy || !undoStack.length;
  addGroupButton.disabled = isBusy || !files.length;
  renameGroupButton.disabled = isBusy || !hasGroup;
  groupNameInput.disabled = isBusy || !hasGroup;

  targetGroup.innerHTML = "";
  if (groups.length) {
    for (const [index] of groups.entries()) {
      if (index === selectedGroup) continue;
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = groupLabel(index);
      targetGroup.appendChild(option);
    }
    const option = document.createElement("option");
    option.value = "new";
    option.textContent = "New Group";
    targetGroup.appendChild(option);
  } else {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = files.length ? "Create Group First" : "Analyze First";
    targetGroup.appendChild(option);
  }
  movePhotoButton.disabled = isBusy || !hasPhoto || !groups.length || !targetGroup.value;
  targetGroup.disabled = isBusy || !hasPhoto || !groups.length;
}

function setPhotoPreview(file) {
  if (file === photoPreviewFile) return;
  if (photoPreviewUrl) URL.revokeObjectURL(photoPreviewUrl);
  photoPreviewUrl = "";
  photoPreviewFile = file;
  if (!file) {
    photoPreview.removeAttribute("src");
    photoPreview.alt = "";
    return;
  }
  photoPreviewUrl = URL.createObjectURL(file);
  photoPreview.src = photoPreviewUrl;
  photoPreview.alt = file.name;
}

async function selectPhoto(nextIndex) {
  const selected = activeFiles();
  if (!selected.length) {
    renderEditor();
    return;
  }
  selectedPhotoIndex = (nextIndex + selected.length) % selected.length;
  renderEditor();
  await previewCurrentPhoto();
}

async function moveSelectedPhoto() {
  const sourceGroup = activeGroup();
  const selected = activeFiles();
  const file = selected[selectedPhotoIndex];
  if (!sourceGroup || !file || !targetGroup.value) return;

  const targetValue = targetGroup.value;
  const targetIndexBeforeMove = targetValue === "new" ? groups.length : Number(targetValue);
  if (targetValue !== "new" && (!groups[targetIndexBeforeMove] || targetIndexBeforeMove === selectedGroup)) return;

  pushUndo(`move ${file.name}`);
  const sourceIndex = selectedPhotoIndex;
  const [movedFile] = sourceGroup.files.splice(sourceIndex, 1);
  const [movedScore] = sourceGroup.scores.splice(sourceIndex, 1);

  let targetIndex = targetIndexBeforeMove;
  if (targetValue === "new") {
    groups.push(createManualGroup({files: [movedFile], scores: [movedScore ?? 1]}));
  } else {
    groups[targetIndex].files.push(movedFile);
    groups[targetIndex].scores.push(movedScore ?? 1);
  }

  if (!sourceGroup.files.length) {
    const removedIndex = selectedGroup;
    groups.splice(removedIndex, 1);
    if (targetIndex > removedIndex) targetIndex -= 1;
  }

  selectedGroup = Math.min(Math.max(targetIndex, 0), Math.max(groups.length - 1, 0));
  selectedPhotoIndex = Math.max(activeFiles().length - 1, 0);
  refreshGroupsAfterEdit(`Moved ${movedFile.name} to ${groups.length ? groupLabel(selectedGroup) : "a group"}.`);
  await previewCurrentPhoto();
}

async function removeSelectedPhoto() {
  const selected = activeFiles();
  const file = selected[selectedPhotoIndex];
  if (!file) return;

  pushUndo(`remove ${file.name}`);
  files = files.filter((item) => item !== file);
  if (groups.length) {
    const group = activeGroup();
    group.files.splice(selectedPhotoIndex, 1);
    group.scores.splice(selectedPhotoIndex, 1);
    groups = groups.filter((item) => item.files.length);
  }

  selectedGroup = Math.min(selectedGroup, Math.max(groups.length - 1, 0));
  selectedPhotoIndex = Math.min(selectedPhotoIndex, Math.max(activeFiles().length - 1, 0));
  refreshGroupsAfterEdit(`Removed ${file.name} from the working set.`);
  await previewCurrentPhoto();
}

async function addManualGroup() {
  if (!files.length) return log("Select photos first.");
  pushUndo("add group");
  if (!groups.length) {
    groups.push(createManualGroup({files: files.slice(), scores: files.map(() => 1)}));
  }
  groups.push(createManualGroup());
  selectedGroup = groups.length - 1;
  selectedPhotoIndex = 0;
  refreshGroupsAfterEdit(`Added ${groupLabel(selectedGroup)}.`);
  await previewCurrentPhoto();
}

function renameSelectedGroup() {
  const group = activeGroup();
  if (!group) return;
  const nextName = groupNameInput.value.trim();
  if (!nextName) return log("Group name cannot be empty.");
  const duplicate = groups.some((item, index) => index !== selectedGroup && groupName(item, index).toLowerCase() === nextName.toLowerCase());
  if (duplicate) return log(`Group name already exists: ${nextName}`);
  if (nextName === groupLabel(selectedGroup)) return;
  pushUndo(`rename ${groupLabel(selectedGroup)}`);
  group.name = nextName;
  refreshGroupsAfterEdit(`Renamed group to ${nextName}.`);
}

async function undoLastEdit() {
  const snapshot = undoStack.pop();
  if (!snapshot) return;
  files = snapshot.files;
  groups = snapshot.groups;
  selectedGroup = snapshot.selectedGroup;
  selectedPhotoIndex = snapshot.selectedPhotoIndex;
  photoStripKey = "";
  renderGroups();
  renderEditor();
  log(`Undid ${snapshot.label}.`);
  await previewCurrentPhoto();
}

function pushUndo(label) {
  undoStack.push({
    label,
    files: files.slice(),
    groups: groups.map(cloneGroup),
    selectedGroup,
    selectedPhotoIndex
  });
  if (undoStack.length > MAX_UNDO_STATES) undoStack.shift();
}

function cloneGroup(group) {
  return {
    name: group.name,
    representative: group.representative,
    lastSignature: group.lastSignature,
    files: group.files.slice(),
    scores: group.scores.slice(),
    manual: group.manual
  };
}

function createManualGroup({files: groupFiles = [], scores = []} = {}) {
  return {
    name: nextGroupName(),
    representative: null,
    lastSignature: null,
    files: groupFiles,
    scores: scores.length ? scores : groupFiles.map(() => 1),
    manual: true
  };
}

function refreshGroupsAfterEdit(message) {
  photoStripKey = "";
  renderGroups();
  renderEditor();
  log(message);
}

async function previewCurrentPhoto() {
  const selected = activeFiles();
  const current = selected[selectedPhotoIndex];
  groupTitle.textContent = groups.length ? `${groupLabel(selectedGroup)} (${selected.length} frame(s))` : `${selected.length} photo(s)`;
  if (!current) {
    canvasPreviewToken += 1;
    const ctx = previewCanvas.getContext("2d");
    ctx?.clearRect(0, 0, previewCanvas.width, previewCanvas.height);
    return;
  }
  const token = (canvasPreviewToken += 1);
  const bitmap = await decode(current);
  if (token !== canvasPreviewToken) {
    bitmap.close?.();
    return;
  }
  fitCanvas(previewCanvas, bitmap.width, bitmap.height, 900);
  const ctx = previewCanvas.getContext("2d");
  ctx.drawImage(bitmap, 0, 0, previewCanvas.width, previewCanvas.height);
  bitmap.close?.();
}

function groupLabel(index) {
  return groupName(groups[index], index);
}

function groupName(group, index) {
  return group?.name || defaultGroupName(index);
}

function defaultGroupName(index) {
  return `group_${String(index + 1).padStart(3, "0")}`;
}

function nextGroupName() {
  const usedNames = new Set(groups.map((group, index) => groupName(group, index).toLowerCase()));
  let index = 0;
  while (usedNames.has(defaultGroupName(index).toLowerCase())) index += 1;
  return defaultGroupName(index);
}

function groupScore(group) {
  return group.scores.length ? group.scores.reduce((sum, value) => sum + value, 0) / group.scores.length : null;
}

function groupSummary(group) {
  const score = groupScore(group);
  return `${group.files.length} frame(s) / ${score === null ? "manual" : score.toFixed(2)}`;
}

function renderPhotoStrip() {
  const selected = activeFiles();
  filmstripCount.textContent = `${selected.length} photo(s)`;
  const key = `${selectedGroup}:${groupLabel(selectedGroup)}:${selected.map(fileKey).join("|")}`;
  if (key === photoStripKey) {
    syncPhotoStripSelection();
    return;
  }

  photoStripKey = key;
  photoStrip.innerHTML = "";
  if (!selected.length) {
    const empty = document.createElement("p");
    empty.className = "empty-strip";
    empty.textContent = files.length ? "This group is empty." : "Select photos.";
    photoStrip.appendChild(empty);
    return;
  }

  for (const [index, file] of selected.entries()) {
    const button = document.createElement("button");
    button.type = "button";
    button.disabled = isBusy;
    button.className = "photo-thumb";
    button.dataset.index = String(index);

    const image = document.createElement("img");
    image.alt = "";
    image.src = URL.createObjectURL(file);
    image.addEventListener("load", () => URL.revokeObjectURL(image.src), {once: true});
    image.addEventListener("error", () => URL.revokeObjectURL(image.src), {once: true});

    const label = document.createElement("span");
    label.textContent = file.name;
    button.append(image, label);
    button.addEventListener("click", async () => {
      await selectPhoto(index);
    });
    photoStrip.appendChild(button);
  }
  syncPhotoStripSelection();
}

function syncPhotoStripSelection() {
  const buttons = photoStrip.querySelectorAll(".photo-thumb");
  for (const button of buttons) {
    button.classList.toggle("active", Number(button.dataset.index) === selectedPhotoIndex);
  }
  const activeButton = photoStrip.querySelector(".photo-thumb.active");
  activeButton?.scrollIntoView({block: "nearest", inline: "nearest"});
}

function fileKey(file) {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

function isTypingTarget(target) {
  return target instanceof HTMLElement && (
    target.isContentEditable
    || target.tagName === "INPUT"
    || target.tagName === "SELECT"
    || target.tagName === "TEXTAREA"
  );
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
    else reject(new Error("Could not create image output."));
  }, options.imageFormat, options.imageQualityRatio));
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
  const mimeType = supportedVideoMimeType(options.videoFormat);
  if (!mimeType) {
    stream.getTracks().forEach((track) => track.stop());
    throw new Error(`${options.videoLabel} recording is not supported by this browser. Choose WebM or use the Linux desktop app for MP4 output.`);
  }
  const recorder = new MediaRecorder(stream, {
    mimeType,
    videoBitsPerSecond: options.videoBitsPerSecond
  });
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

function supportedVideoMimeType(format) {
  const candidates = format === "video/mp4"
    ? [
        "video/mp4;codecs=avc1.42E01E",
        "video/mp4;codecs=h264",
        "video/mp4"
      ]
    : [
        "video/webm;codecs=vp9",
        "video/webm;codecs=vp8",
        "video/webm"
      ];
  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) || "";
}

function clamp(value, min, max) {
  if (Number.isNaN(value)) return min;
  return Math.min(Math.max(value, min), max);
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
renderEditor();
