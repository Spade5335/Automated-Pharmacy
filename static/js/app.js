// ===== DOM Elements =====
const tabButtons = document.querySelectorAll(".tab-btn");
const uploadTab = document.getElementById("upload-tab");
const cameraTab = document.getElementById("camera-tab");
const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const uploadPreview = document.getElementById("upload-preview");
const previewImg = document.getElementById("preview-img");
const removeFileBtn = document.getElementById("remove-file-btn");
const startCameraBtn = document.getElementById("start-camera-btn");
const captureBtn = document.getElementById("capture-btn");
const retakeBtn = document.getElementById("retake-btn");
const cameraVideo = document.getElementById("camera-video");
const cameraCanvas = document.getElementById("camera-canvas");
const cameraSelect = document.getElementById("camera-select");
const cameraPlaceholder = document.getElementById("camera-placeholder");
const cameraPreview = document.getElementById("camera-preview");
const capturedImg = document.getElementById("captured-img");
const scanBtn = document.getElementById("scan-btn");
const loading = document.getElementById("loading");
const errorMessage = document.getElementById("error-message");
const resultsSection = document.getElementById("results-section");
const rawOcrText = document.getElementById("raw-ocr-text");
const resultsBody = document.getElementById("results-body");
const noResults = document.getElementById("no-results");

// ===== State =====
let selectedFile = null;
let capturedBlob = null;
let cameraStream = null;
let activeTab = "upload";

// ===== Tab Switching =====
tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
        const tab = btn.dataset.tab;
        activeTab = tab;

        tabButtons.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");

        uploadTab.classList.toggle("active", tab === "upload");
        uploadTab.classList.toggle("hidden", tab !== "upload");
        cameraTab.classList.toggle("active", tab === "camera");
        cameraTab.classList.toggle("hidden", tab !== "camera");

        updateScanButton();
    });
});

// ===== File Upload =====
dropZone.addEventListener("click", (e) => {
    if (e.target === fileInput || e.target.tagName === "LABEL") return;
    fileInput.click();
});

dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("image/")) {
        selectFile(file);
    }
});

fileInput.addEventListener("change", () => {
    if (fileInput.files[0]) {
        selectFile(fileInput.files[0]);
    }
});

removeFileBtn.addEventListener("click", () => {
    selectedFile = null;
    fileInput.value = "";
    uploadPreview.classList.add("hidden");
    dropZone.classList.remove("hidden");
    updateScanButton();
});

function selectFile(file) {
    selectedFile = file;
    const url = URL.createObjectURL(file);
    previewImg.src = url;
    uploadPreview.classList.remove("hidden");
    dropZone.classList.add("hidden");
    updateScanButton();
}

// ===== Camera =====
startCameraBtn.addEventListener("click", startCamera);
captureBtn.addEventListener("click", captureFrame);
retakeBtn.addEventListener("click", retakePhoto);

cameraSelect.addEventListener("change", async () => {
    if (cameraStream) {
        stopCamera();
        await startCamera(cameraSelect.value);
    }
});

async function startCamera(deviceId) {
    try {
        const constraints = {
            video: {
                width: { ideal: 1920 },
                height: { ideal: 1080 },
            },
        };

        if (deviceId) {
            constraints.video.deviceId = { exact: deviceId };
        } else {
            constraints.video.facingMode = "environment";
        }

        cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
        cameraVideo.srcObject = cameraStream;
        cameraPlaceholder.classList.add("hidden");
        startCameraBtn.classList.add("hidden");
        captureBtn.classList.remove("hidden");

        // Populate camera selector
        const devices = await navigator.mediaDevices.enumerateDevices();
        const cameras = devices.filter((d) => d.kind === "videoinput");
        if (cameras.length > 1) {
            cameraSelect.innerHTML = "";
            cameras.forEach((cam, i) => {
                const opt = document.createElement("option");
                opt.value = cam.deviceId;
                opt.textContent = cam.label || `Camera ${i + 1}`;
                cameraSelect.appendChild(opt);
            });
            cameraSelect.classList.remove("hidden");
        }
    } catch (err) {
        showError("Camera access denied or unavailable: " + err.message);
    }
}

function captureFrame() {
    cameraCanvas.width = cameraVideo.videoWidth;
    cameraCanvas.height = cameraVideo.videoHeight;
    cameraCanvas.getContext("2d").drawImage(cameraVideo, 0, 0);

    cameraCanvas.toBlob(
        (blob) => {
            capturedBlob = blob;
            const url = URL.createObjectURL(blob);
            capturedImg.src = url;
            cameraPreview.classList.remove("hidden");
            cameraVideo.parentElement.classList.add("hidden");
            captureBtn.classList.add("hidden");
            retakeBtn.classList.remove("hidden");
            updateScanButton();
        },
        "image/jpeg",
        0.92
    );
}

function retakePhoto() {
    capturedBlob = null;
    cameraPreview.classList.add("hidden");
    cameraVideo.parentElement.classList.remove("hidden");
    captureBtn.classList.remove("hidden");
    retakeBtn.classList.add("hidden");
    updateScanButton();
}

function stopCamera() {
    if (cameraStream) {
        cameraStream.getTracks().forEach((t) => t.stop());
        cameraStream = null;
    }
}

// ===== Scan Button State =====
function updateScanButton() {
    const hasImage =
        (activeTab === "upload" && selectedFile) ||
        (activeTab === "camera" && capturedBlob);
    scanBtn.disabled = !hasImage;
}

// ===== Scan =====
scanBtn.addEventListener("click", scanPrescription);

async function scanPrescription() {
    showLoading(true);
    hideError();
    hideResults();

    try {
        let response;

        if (activeTab === "upload" && selectedFile) {
            const formData = new FormData();
            formData.append("file", selectedFile);
            response = await fetch("/api/scan", {
                method: "POST",
                body: formData,
            });
        } else if (activeTab === "camera" && capturedBlob) {
            const base64 = await blobToBase64(capturedBlob);
            response = await fetch("/api/scan", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ image_base64: base64 }),
            });
        } else {
            showError("No image selected.");
            return;
        }

        const data = await response.json();

        if (!response.ok || data.error) {
            showError(data.error || "Server error occurred.");
            return;
        }

        displayResults(data);
    } catch (err) {
        showError("Failed to connect to server: " + err.message);
    } finally {
        showLoading(false);
    }
}

// ===== Display Results =====
function displayResults(data) {
    // Raw OCR text
    rawOcrText.textContent = data.raw_text_lines.join("\n") || "(no text detected)";

    // Table
    resultsBody.innerHTML = "";
    const medicines = data.medicines || [];

    if (medicines.length === 0) {
        noResults.classList.remove("hidden");
        document.querySelector(".table-wrapper").classList.add("hidden");
    } else {
        noResults.classList.add("hidden");
        document.querySelector(".table-wrapper").classList.remove("hidden");

        medicines.forEach((med) => {
            const tr = document.createElement("tr");

            // Raw text
            const tdRaw = document.createElement("td");
            tdRaw.textContent = med.raw_text;

            // Matched name
            const tdMatch = document.createElement("td");
            if (med.matched_name) {
                tdMatch.textContent = med.matched_name;
                if (med.alternatives && med.alternatives.length > 0) {
                    const altText = med.alternatives
                        .map((a) => `${a.name} (${a.score}%)`)
                        .join(", ");
                    tdMatch.title = "Also considered: " + altText;
                }
            } else {
                tdMatch.textContent = "No match found";
                tdMatch.classList.add("text-muted");
            }

            // Confidence
            const tdConf = document.createElement("td");
            if (med.matched_name) {
                tdConf.textContent = med.confidence + "%";
                if (med.confidence >= 85) tdConf.className = "confidence-high";
                else if (med.confidence >= 65)
                    tdConf.className = "confidence-medium";
                else tdConf.className = "confidence-low";
            } else {
                tdConf.textContent = "--";
                tdConf.classList.add("text-muted");
            }

            // Stock status
            const tdStock = document.createElement("td");
            const badge = document.createElement("span");
            badge.classList.add("badge");
            if (!med.matched_name) {
                badge.textContent = "N/A";
                badge.classList.add("badge-no-match");
            } else if (med.in_stock) {
                badge.textContent = "In Stock";
                badge.classList.add("badge-in-stock");
            } else {
                badge.textContent = "Out of Stock";
                badge.classList.add("badge-out-of-stock");
            }
            tdStock.appendChild(badge);

            // Quantity
            const tdQty = document.createElement("td");
            tdQty.textContent = med.matched_name ? med.stock_count : "--";

            tr.append(tdRaw, tdMatch, tdConf, tdStock, tdQty);
            resultsBody.appendChild(tr);
        });
    }

    resultsSection.classList.remove("hidden");
    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ===== Helpers =====
function blobToBase64(blob) {
    return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.readAsDataURL(blob);
    });
}

function showLoading(show) {
    loading.classList.toggle("hidden", !show);
    scanBtn.disabled = show;
}

function showError(msg) {
    errorMessage.textContent = msg;
    errorMessage.classList.remove("hidden");
}

function hideError() {
    errorMessage.classList.add("hidden");
}

function hideResults() {
    resultsSection.classList.add("hidden");
}
