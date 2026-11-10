(() => {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const imageInput = byId("cropImage");
  const preview = byId("cropImagePreview");
  const previewWrap = byId("imagePreviewWrap");
  if (!imageInput || !preview || !previewWrap) return;

  const dialog = byId("cameraDialog");
  const video = byId("cameraVideo");
  const snapshot = byId("cameraSnapshot");
  const capture = byId("capturePhoto");
  const retake = byId("retakePhoto");
  const usePhoto = byId("usePhoto");
  const photoError = byId("photoError");
  const photoStatus = byId("photoStatus");
  const cameraError = byId("cameraError");
  const cameraStatus = byId("cameraStatus");
  let previewUrl = null;
  let snapshotUrl = null;
  let stream = null;
  let pendingPhoto = null;
  let requestVersion = 0;
  let capturing = false;

  const message = (element, text) => {
    if (!element) return;
    element.textContent = text;
    element.hidden = !text;
  };

  const revoke = (url) => {
    if (url) URL.revokeObjectURL(url);
  };

  const stopStream = () => {
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    if (video) video.srcObject = null;
  };

  const resetCamera = () => {
    requestVersion += 1;
    stopStream();
    capturing = false;
    pendingPhoto = null;
    revoke(snapshotUrl);
    snapshotUrl = null;
    snapshot.removeAttribute("src");
    snapshot.hidden = true;
    video.hidden = false;
    capture.hidden = false;
    capture.disabled = true;
    retake.hidden = true;
    usePhoto.hidden = true;
  };

  const closeCamera = () => {
    if (dialog.open) dialog.close();
    resetCamera();
  };

  const updatePreview = () => {
    revoke(previewUrl);
    previewUrl = null;
    const [file] = imageInput.files;
    message(photoError, "");
    if (!file) {
      preview.removeAttribute("src");
      previewWrap.hidden = true;
      if (photoStatus) photoStatus.textContent = "No photo selected.";
      return;
    }
    previewUrl = URL.createObjectURL(file);
    preview.src = previewUrl;
    previewWrap.hidden = false;
    if (photoStatus) {
      photoStatus.textContent = `Selected: ${file.name}. Uploaded with your assessment.`;
    }
  };

  imageInput.addEventListener("change", updatePreview);
  preview.addEventListener("error", () => {
    previewWrap.hidden = true;
    message(photoError, "This image cannot be previewed. Choose a readable JPG, PNG, or WEBP photo.");
  });

  byId("removePhoto")?.addEventListener("click", () => {
    imageInput.value = "";
    updatePreview();
    if (byId("photoActions") && !byId("photoActions").hidden) {
      byId("choosePhoto").focus();
    } else {
      imageInput.focus();
    }
  });

  // The ordinary file input stays usable if enhancement is unavailable.
  if (!dialog || typeof dialog.showModal !== "function") return;
  byId("photoActions").hidden = false;
  imageInput.hidden = true;

  byId("choosePhoto").addEventListener("click", () => imageInput.click());

  const cameraFailure = (error) => {
    const explanations = {
      NotAllowedError: "Camera permission was not granted. Allow camera access in your browser or choose a photo instead.",
      NotFoundError: "No camera was found on this device. You can choose an existing photo instead.",
      NotReadableError: "The camera could not be opened. It may be in use by another application.",
      OverconstrainedError: "This camera could not use the requested settings. You can choose a photo instead.",
    };
    return explanations[error.name] || "The camera could not start. Try again or choose an existing photo.";
  };

  const startCamera = async () => {
    message(photoError, "");
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      message(photoError, "Live camera access needs a supported browser on HTTPS or localhost. You can still choose a photo.");
      return;
    }
    resetCamera();
    message(cameraError, "");
    cameraStatus.textContent = "Allow camera access, then position the plant clearly in the frame.";
    if (!dialog.open) dialog.showModal();
    const version = requestVersion;
    try {
      const openedStream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
      });
      // Permission may finish after the user has cancelled or left the tab.
      if (version !== requestVersion || !dialog.open) {
        openedStream.getTracks().forEach((track) => track.stop());
        return;
      }
      stream = openedStream;
      video.srcObject = stream;
      await video.play();
      if (version !== requestVersion || !dialog.open) return;
      capture.disabled = !(video.videoWidth && video.videoHeight);
      cameraStatus.textContent = capture.disabled
        ? "Waiting for the camera image. Try reopening the camera if it stays blank."
        : "Position the plant clearly, then select Capture.";
    } catch (error) {
      if (version !== requestVersion) return;
      stopStream();
      capture.disabled = true;
      message(cameraError, cameraFailure(error));
      cameraStatus.textContent = "Close this window to choose an existing photo.";
    }
  };

  byId("takePicture").addEventListener("click", startCamera);
  retake.addEventListener("click", startCamera);
  video.addEventListener("loadeddata", () => {
    if (dialog.open && stream && !pendingPhoto && !capturing) {
      capture.disabled = !(video.videoWidth && video.videoHeight);
    }
  });

  capture.addEventListener("click", () => {
    if (!stream || !video.videoWidth || !video.videoHeight || capturing) return;
    const version = requestVersion;
    const canvas = document.createElement("canvas");
    const scale = Math.min(1, 2048 / Math.max(video.videoWidth, video.videoHeight));
    canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
    canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
    const context = canvas.getContext("2d");
    if (!context) {
      message(cameraError, "A picture could not be created. Try again or choose a photo.");
      return;
    }
    capturing = true;
    capture.disabled = true;
    message(cameraError, "");
    try {
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob((blob) => {
        if (version !== requestVersion || !dialog.open) return;
        capturing = false;
        if (!blob || blob.size > 5 * 1024 * 1024) {
          capture.disabled = false;
          message(cameraError, "The picture could not be saved within the 5 MB limit. Try again or choose a smaller photo.");
          return;
        }
        const format = blob.type === "image/png" ? "png" : "jpg";
        pendingPhoto = new File([blob], `crop-camera-${Date.now()}.${format}`, {
          type: blob.type,
          lastModified: Date.now(),
        });
        snapshotUrl = URL.createObjectURL(pendingPhoto);
        snapshot.src = snapshotUrl;
        snapshot.hidden = false;
        video.hidden = true;
        capture.hidden = true;
        retake.hidden = false;
        usePhoto.hidden = false;
        stopStream();
        cameraStatus.textContent = "Review your picture. Use photo to attach it, or Retake to try again.";
        usePhoto.focus();
      }, "image/jpeg", 0.9);
    } catch {
      capturing = false;
      capture.disabled = false;
      message(cameraError, "A picture could not be created. Try again or choose a photo.");
    }
  });

  usePhoto.addEventListener("click", () => {
    if (!pendingPhoto) return;
    try {
      const transfer = new DataTransfer();
      transfer.items.add(pendingPhoto);
      imageInput.files = transfer.files;
      imageInput.dispatchEvent(new Event("change", { bubbles: true }));
      closeCamera();
      byId("removePhoto").focus();
    } catch {
      message(cameraError, "This browser could not attach the picture. Close the camera and choose a photo instead.");
    }
  });

  byId("closeCamera").addEventListener("click", closeCamera);
  byId("cancelCamera").addEventListener("click", closeCamera);
  dialog.addEventListener("cancel", closeCamera);
  dialog.addEventListener("close", () => {
    if (!dialog.open) resetCamera();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && dialog.open) closeCamera();
  });
  window.addEventListener("pagehide", () => {
    closeCamera();
    revoke(previewUrl);
    previewUrl = null;
  });
})();
