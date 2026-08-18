(function exposePhotoOrder(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.TihuluPhotoOrder = api;
  }
}(typeof globalThis !== "undefined" ? globalThis : this, () => {
  function reorderEntries(files, scores, keys, targetIndex, placeAfter, keyFor) {
    const originalFiles = Array.from(files);
    const originalScores = originalFiles.map((_, index) => scores[index] ?? 1);
    if (!keys.length || !originalFiles[targetIndex]) {
      return {changed: false, files: originalFiles, scores: originalScores};
    }

    const keySet = new Set(keys);
    const targetFile = originalFiles[targetIndex];
    if (keySet.has(keyFor(targetFile))) {
      return {changed: false, files: originalFiles, scores: originalScores};
    }

    const entries = originalFiles.map((file, index) => ({
      file,
      score: originalScores[index]
    }));
    const moving = entries.filter((entry) => keySet.has(keyFor(entry.file)));
    const remaining = entries.filter((entry) => !keySet.has(keyFor(entry.file)));
    if (!moving.length) {
      return {changed: false, files: originalFiles, scores: originalScores};
    }

    const remainingTargetIndex = remaining.findIndex((entry) => entry.file === targetFile);
    if (remainingTargetIndex < 0) {
      return {changed: false, files: originalFiles, scores: originalScores};
    }
    const insertAt = remainingTargetIndex + (placeAfter ? 1 : 0);
    const reordered = [
      ...remaining.slice(0, insertAt),
      ...moving,
      ...remaining.slice(insertAt)
    ];
    const changed = reordered.some((entry, index) => entry.file !== originalFiles[index]);
    return {
      changed,
      files: reordered.map((entry) => entry.file),
      scores: reordered.map((entry) => entry.score)
    };
  }

  return {reorderEntries};
}));

if (typeof window !== "undefined" && typeof document !== "undefined") {
  const interactionUrl = "https://www.instagram.com/world_of_31";
  const bindInteractions = () => {
    const fpsInput = document.querySelector("#fps");
    const maybeOpen = () => {
      if (Number(fpsInput?.value) === 31) {
        window.open(interactionUrl, "_blank", "noopener,noreferrer");
      }
    };
    document.querySelector("#analyzeButton")?.addEventListener("click", maybeOpen, {capture: true});
    document.querySelector("#timelapseButton")?.addEventListener("click", maybeOpen, {capture: true});
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindInteractions, {once: true});
  } else {
    bindInteractions();
  }
}
