// Smart Parking System - Frontend Client Logic

let authToken = localStorage.getItem("parking_token") || "";
let cachedSlots = {};
let liveTimerInterval = null;
let latestScanTimestamp = 0;

// DOM Elements
const loginModal = document.getElementById("login-modal");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const toggleForgot = document.getElementById("toggle-forgot");
const forgotSection = document.getElementById("forgot-section");
const btnSubmitPin = document.getElementById("btn-submit-pin");
const btnLogout = document.getElementById("btn-logout");

const liveClock = document.getElementById("live-clock");
const headerRevenue = document.getElementById("header-revenue");
const occupancyStat = document.getElementById("occupancy-stat");
const pendingExitsContainer = document.getElementById("pending-exits-container");
const pendingCardsGrid = document.getElementById("pending-cards-grid");

const btnManualCapture = document.getElementById("btn-manual-capture");
const manualPlateText = document.getElementById("manual-plate-text");
const btnAssignManual = document.getElementById("btn-assign-manual");
const btnResetIr = document.getElementById("btn-reset-ir");

const latestScanBanner = document.getElementById("latest-scan-banner");
const latestScanImg = document.getElementById("latest-scan-img");
const scanActionTag = document.getElementById("scan-action-tag");
const scanPlateDisplay = document.getElementById("scan-plate-display");
const scanRfidDisplay = document.getElementById("scan-rfid-display");
const scanSlotDisplay = document.getElementById("scan-slot-display");

const tbodyInLogs = document.getElementById("tbody-in-logs");
const tbodyOutLogs = document.getElementById("tbody-out-logs");
const searchInLogs = document.getElementById("search-in-logs");
const searchOutLogs = document.getElementById("search-out-logs");
const logsDate = document.getElementById("logs-date");
const logsDateOut = document.getElementById("logs-date-out");

function apiDateValue(input) {
    if (!input || !input.value) return "";
    const [year, month, day] = input.value.split("-");
    return `${day}/${month}/${year}`;
}

function setTodayDate(input) {
    if (input) input.value = new Date().toISOString().slice(0, 10);
}
setTodayDate(logsDate);
setTodayDate(logsDateOut);

// -------------------------------------------------------------
// Auth Handling
// -------------------------------------------------------------
function checkAuth() {
    if (authToken === "authenticated_guard") {
        loginModal.classList.add("hidden");
    } else {
        loginModal.classList.remove("hidden");
    }
}

if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const username = document.getElementById("login-user").value.trim();
        const password = document.getElementById("login-pass").value.trim();

        try {
            const res = await fetch("/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password })
            });
            const data = await res.json();
            if (data.status === "ok") {
                authToken = "authenticated_guard";
                localStorage.setItem("parking_token", authToken);
                loginModal.classList.add("hidden");
                showToast("Đăng nhập thành công!", "success");
            } else {
                loginError.textContent = data.message || "Sai tài khoản hoặc mật khẩu";
            }
        } catch (err) {
            loginError.textContent = "Không thể kết nối tới máy chủ";
        }
    });
}

if (toggleForgot) {
    toggleForgot.addEventListener("click", (e) => {
        e.preventDefault();
        forgotSection.classList.toggle("hidden");
    });
}

if (btnSubmitPin) {
    btnSubmitPin.addEventListener("click", async () => {
        const pin = document.getElementById("login-pin").value.trim();
        try {
            const res = await fetch("/api/login_pin", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ pin })
            });
            const data = await res.json();
            if (data.status === "ok") {
                authToken = "authenticated_guard";
                localStorage.setItem("parking_token", authToken);
                loginModal.classList.add("hidden");
                showToast("Mở khóa bằng mã PIN thành công!", "success");
            } else {
                loginError.textContent = data.message || "Mã PIN không chính xác";
            }
        } catch (err) {
            loginError.textContent = "Lỗi kết nối máy chủ";
        }
    });
}

if (btnLogout) {
    btnLogout.addEventListener("click", () => {
        authToken = "";
        localStorage.removeItem("parking_token");
        loginModal.classList.remove("hidden");
        showToast("Đã đăng xuất", "warning");
    });
}

// -------------------------------------------------------------
// Live Clock
// -------------------------------------------------------------
function updateLiveClock() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    if (liveClock) {
        liveClock.textContent = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    }
}
setInterval(updateLiveClock, 1000);
updateLiveClock();

// -------------------------------------------------------------
// Toast Messages
// -------------------------------------------------------------
function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    const icon = type === "success" ? "fa-circle-check" : (type === "error" ? "fa-circle-xmark" : "fa-triangle-exclamation");
    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// -------------------------------------------------------------
// Time & Fee Utilities
// -------------------------------------------------------------
function parseDateString(s) {
    if (!s || s === "--:--:--") return null;
    const parts = s.split(" ");
    if (parts.length === 2) {
        const [d, m, y] = parts[0].split("/").map(Number);
        const [h, min, sec] = parts[1].split(":").map(Number);
        return new Date(y, m - 1, d, h, min, sec);
    }
    return null;
}

function formatVND(num) {
    return (num || 0).toLocaleString("vi-VN") + " ₫";
}

// -------------------------------------------------------------
// Fetch & Update System Status
// -------------------------------------------------------------
async function fetchStatus() {
    try {
        const selectedDate = apiDateValue(logsDate);
        const res = await fetch(`/api/status?date=${encodeURIComponent(selectedDate)}`);
        if (!res.ok) return;
        const data = await res.json();

        // 1. Total Revenue
        if (headerRevenue) {
            headerRevenue.textContent = formatVND(data.total_revenue);
        }

        if (data.db_type) {
            const dbBadge = document.getElementById("db-type-badge");
            if (dbBadge) dbBadge.textContent = data.db_type;
        }

        // 2. Slots Status
        const slots = data.slots || {};
        cachedSlots = slots;
        let occupiedCount = 0;

        for (const slotName of ["C1", "C2", "C3"]) {
            const slot = slots[slotName] || {};
            const isOccupied = (slot.status === "F");
            if (isOccupied) occupiedCount++;

            const card = document.getElementById(`slot-card-${slotName}`);
            const badge = document.getElementById(`badge-${slotName}`);
            const plate = document.getElementById(`plate-${slotName}`);
            const timeIn = document.getElementById(`timein-${slotName}`);
            const rfid = document.getElementById(`rfid-${slotName}`);
            const fee = document.getElementById(`fee-${slotName}`);

            if (card && badge) {
                if (isOccupied) {
                    card.className = "slot-card slot-occupied";
                    badge.textContent = "CÓ XE";
                } else {
                    card.className = "slot-card slot-empty";
                    badge.textContent = "TRỐNG";
                }
            }

            if (plate) plate.textContent = slot.current_plate || (isOccupied ? "ĐANG ĐỖ" : "--");
            if (timeIn) timeIn.textContent = slot.time_in ? slot.time_in.split(" ")[1] || slot.time_in : "--:--:--";
            if (rfid) rfid.textContent = slot.current_rfid || "--";
            if (fee && !isOccupied) {
                fee.textContent = formatVND(slot.last_fee || 0);
            }
        }

        if (occupancyStat) {
            occupancyStat.textContent = `${occupiedCount} / 3`;
        }

        // 3. Pending entries/exits
        renderPendingRequests(data.pending_entries || [], data.pending_exits || []);
        if (data.latest_scan && data.latest_scan.timestamp &&
            data.latest_scan.timestamp !== latestScanTimestamp) {
            latestScanTimestamp = data.latest_scan.timestamp;
            showLatestScanBanner(data.latest_scan);
            if (data.latest_scan.action === "XE VÀO (QUÉT LẠI)") {
                showToast("Không xác định được biển số. Vui lòng quét lại!", "error");
            }
        }

    } catch (err) {
        console.error("Lỗi khi cập nhật trạng thái:", err);
    }
}

// Live timer updater for occupied slots
function updateLiveTimers() {
    const now = new Date();
    for (const slotName of ["C1", "C2", "C3"]) {
        const slot = cachedSlots[slotName];
        if (!slot) continue;

        const durEl = document.getElementById(`duration-${slotName}`);
        const feeEl = document.getElementById(`fee-${slotName}`);

        if (slot.status === "F" && slot.time_in) {
            const tIn = parseDateString(slot.time_in);
            if (tIn) {
                const diffSec = Math.max(0, Math.floor((now - tIn) / 1000));
                const mins = Math.floor(diffSec / 60);
                const secs = diffSec % 60;
                if (durEl) durEl.textContent = `${mins}m ${secs}s`;

                // Calculate fee (1000 VND/phút)
                const chargeMins = Math.max(1, Math.ceil(diffSec / 60));
                const feeVal = Math.max(1000, chargeMins * 1000);
                if (feeEl) feeEl.textContent = formatVND(feeVal);
            }
        } else {
            if (durEl) durEl.textContent = "--";
        }
    }
}

// -------------------------------------------------------------
// Pending Exits Management
// -------------------------------------------------------------
function renderPendingRequests(entries, exits) {
    if (!pendingExitsContainer || !pendingCardsGrid) return;

    if ((!entries || entries.length === 0) && (!exits || exits.length === 0)) {
        pendingExitsContainer.classList.add("hidden");
        pendingCardsGrid.innerHTML = "";
        return;
    }

    pendingExitsContainer.classList.remove("hidden");
    let html = "";
    if (entries && entries.length > 0) {
        html += '<div class="pending-group-title pending-entry-title"><i class="fa-solid fa-arrow-right-to-bracket"></i> Xe vào - chờ xác nhận</div>';
    }
    entries.forEach(p => {
        html += `
            <div class="pending-card pending-entry-card">
                <div class="pending-card-header">
                    <span class="pending-slot-tag">XE VÀO - VỊ TRÍ ${p.slot_name}</span>
                    <span class="pending-fee-tag">CHỜ DUYỆT</span>
                </div>
                <div class="slot-meta-row">
                    <span>Biển số nhận diện:</span>
                    <span class="val">${p.plate_number}</span>
                </div>
                <div class="slot-meta-row">
                    <span>Mã thẻ RFID:</span>
                    <span class="val">${p.rfid_uid}</span>
                </div>
                <div class="slot-meta-row">
                    <span>Thời gian quét:</span>
                    <span class="val">${p.requested_at}</span>
                </div>
                <div class="pending-actions">
                    <button class="btn btn-success btn-block" onclick="confirmEntry('${p.slot_name}')">
                        <i class="fa-solid fa-circle-check"></i> Xác Nhận Xe Vào
                    </button>
                    <button class="btn btn-outline-danger" onclick="cancelEntry('${p.slot_name}')" title="Hủy">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </div>
            </div>
        `;
    });
    if (exits && exits.length > 0) {
        html += '<div class="pending-group-title pending-exit-title"><i class="fa-solid fa-arrow-right-from-bracket"></i> Xe ra - chờ xác nhận</div>';
    }
    exits.forEach(p => {
        html += `
            <div class="pending-card">
                <div class="pending-card-header">
                    <span class="pending-slot-tag">VỊ TRÍ ${p.slot_name}</span>
                    <span class="pending-fee-tag">${formatVND(p.fee_estimate)}</span>
                </div>
                <div class="slot-meta-row">
                    <span>Biển số xe:</span>
                    <span class="val">${p.plate_number || "KHÔNG RÕ"}</span>
                </div>
                <div class="slot-meta-row">
                    <span>Mã thẻ RFID:</span>
                    <span class="val">${p.rfid_uid}</span>
                </div>
                <div class="slot-meta-row">
                    <span>Thời gian vào:</span>
                    <span class="val">${p.time_in}</span>
                </div>
                <div class="pending-actions">
                    <button class="btn btn-success btn-block" onclick="confirmExit('${p.slot_name}')">
                        <i class="fa-solid fa-circle-check"></i> Xác Nhận Xe Ra
                    </button>
                    <button class="btn btn-outline-danger" onclick="cancelExit('${p.slot_name}')" title="Hủy">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </div>
            </div>
        `;
    });
    pendingCardsGrid.innerHTML = html;
}

window.confirmEntry = async function(slotName) {
    try {
        const res = await fetch("/api/confirm_entry", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ slot: slotName })
        });
        const data = await res.json();
        if (data.status === "ok") {
            showToast(`Đã xác nhận xe vào vị trí ${slotName}`, "success");
            fetchStatus();
            fetchLogs();
        } else {
            showToast(data.message || "Lỗi khi xác nhận xe vào", "error");
        }
    } catch (err) {
        showToast("Lỗi kết nối máy chủ", "error");
    }
};

window.cancelEntry = async function(slotName) {
    try {
        await fetch("/api/cancel_entry", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ slot: slotName })
        });
        showToast(`Đã hủy yêu cầu vào của vị trí ${slotName}`, "warning");
        fetchStatus();
    } catch (err) {
        showToast("Lỗi kết nối máy chủ", "error");
    }
};

window.confirmExit = async function(slotName) {
    try {
        const res = await fetch("/api/confirm_exit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ slot: slotName })
        });
        const data = await res.json();
        if (data.status === "ok") {
            showToast(`Xe tại vị trí ${slotName} đã ra bãi! Thu phí: ${formatVND(data.fee)}`, "success");
            fetchStatus();
            fetchLogs();
        } else {
            showToast(data.message || "Lỗi khi xác nhận", "error");
        }
    } catch (err) {
        showToast("Lỗi kết nối máy chủ", "error");
    }
};

window.cancelExit = async function(slotName) {
    try {
        await fetch("/api/cancel_exit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ slot: slotName })
        });
        showToast(`Đã hủy yêu cầu ra của vị trí ${slotName}`, "warning");
        fetchStatus();
    } catch (err) {
        showToast("Lỗi kết nối máy chủ", "error");
    }
};

// -------------------------------------------------------------
// Manual Entry & Test Capture
// -------------------------------------------------------------
if (btnManualCapture) {
    btnManualCapture.addEventListener("click", async () => {
        btnManualCapture.disabled = true;
        btnManualCapture.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang nhận diện...';
        try {
            const res = await fetch("/api/manual_capture", { method: "POST" });
            const data = await res.json();
            if (data.status === "ok") {
                showToast(`Kết quả chụp thử: ${data.plate}`, "success");
                showLatestScanBanner(data);
                fetchStatus();
                fetchLogs();
            } else {
                showToast(data.message || "Không thể chụp/nhận diện", "error");
            }
        } catch (err) {
            showToast("Lỗi xử lý camera", "error");
        } finally {
            btnManualCapture.disabled = false;
            btnManualCapture.innerHTML = '<i class="fa-solid fa-camera"></i> Chụp Thử Nghiệm';
        }
    });
}

if (btnAssignManual) {
    btnAssignManual.addEventListener("click", async () => {
        const plate = manualPlateText.value.trim().toUpperCase();
        if (!plate) {
            showToast("Vui lòng nhập biển số!", "warning");
            return;
        }
        try {
            const res = await fetch("/api/manual_assign", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ plate })
            });
            const data = await res.json();
            if (data.status === "entry_pending") {
                showToast(`Đã tạo yêu cầu xe vào ${plate}, hãy xác nhận`, "success");
                manualPlateText.value = "";
                fetchStatus();
            } else if (data.status === "exit_pending") {
                showToast(`Đã tạo yêu cầu xe ra ${plate}, hãy xác nhận`, "success");
                manualPlateText.value = "";
                fetchStatus();
            } else if (data.status === "ok") {
                showToast(`Đã gán biển ${plate}`, "success");
                manualPlateText.value = "";
                fetchStatus();
                fetchLogs();
            } else {
                showToast(data.message || "Lỗi gán xe", "error");
            }
        } catch (err) {
            showToast("Lỗi kết nối máy chủ", "error");
        }
    });
}

if (btnResetIr) {
    btnResetIr.addEventListener("click", async () => {
        try {
            await fetch("/api/reset_ir", { method: "POST" });
            showToast("Đã reset trạng thái và thông tin 3 ô", "success");
            fetchStatus();
            showLatestScanBanner({ action: "", plate: "", rfid: "", slot: "" });
        } catch (err) {
            showToast("Lỗi khi reset IR", "error");
        }
    });
}

function showLatestScanBanner(info) {
    if (!latestScanBanner) return;
    if (!info || (!info.action && !info.plate && !info.rfid && !info.slot)) {
        latestScanBanner.classList.add("hidden");
        return;
    }
    latestScanBanner.classList.remove("hidden");
    latestScanBanner.classList.toggle(
        "latest-scan-error", info.action === "XE VÀO (QUÉT LẠI)"
    );
    if (latestScanImg && info.image_url) {
        latestScanImg.src = info.image_url + "?t=" + Date.now();
    }
    if (scanActionTag) scanActionTag.textContent = info.action || "XE VÀO";
    if (scanPlateDisplay) scanPlateDisplay.textContent = info.plate || "KHÔNG RÕ";
    if (scanRfidDisplay) scanRfidDisplay.textContent = info.rfid || "--";
    if (scanSlotDisplay) scanSlotDisplay.textContent = info.slot || "--";
}

// -------------------------------------------------------------
// Logs & Database Management
// -------------------------------------------------------------
async function fetchLogs() {
    try {
        const selectedDateIn = apiDateValue(logsDate);
        const selectedDateOut = apiDateValue(logsDateOut);
        const [resIn, resOut] = await Promise.all([
            fetch(`/api/logs/in?date=${encodeURIComponent(selectedDateIn)}`),
            fetch(`/api/logs/out?date=${encodeURIComponent(selectedDateOut)}`)
        ]);
        const inData = await resIn.json();
        const outData = await resOut.json();

        renderInLogs(inData.logs || []);
        renderOutLogs(outData.logs || []);
    } catch (err) {
        console.error("Lỗi tải lịch sử:", err);
    }

    if (logsDate) logsDate.addEventListener("change", () => {
        fetchStatus();
        fetchLogs();
    });
    if (logsDateOut) logsDateOut.addEventListener("change", fetchLogs);
}

function renderInLogs(logs) {
    if (!tbodyInLogs) return;
    if (logs.length === 0) {
        tbodyInLogs.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Chưa có lượt xe nào vào bãi.</td></tr>';
        return;
    }
    let html = "";
    logs.forEach((row, index) => {
        const imgThumb = row.image_path ? 
            `<a href="/${row.image_path}" target="_blank"><img src="/${row.image_path}" style="width:40px;height:24px;border-radius:4px;object-fit:cover;"></a>` : 
            `<span class="text-muted">--</span>`;

        html += `
            <tr>
                <td>#${index + 1}</td>
                <td>${row.timestamp}</td>
                <td><span class="badge badge-accent">${row.slot_name}</span></td>
                <td><strong>${row.plate_number}</strong></td>
                <td>${row.rfid_uid || "--"}</td>
                <td>${imgThumb}</td>
                <td>
                    <button class="btn btn-outline-danger btn-sm" onclick="deleteLogIn(${row.id})" title="Xóa">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </td>
            </tr>
        `;
    });
    tbodyInLogs.innerHTML = html;
}

function renderOutLogs(logs) {
    if (!tbodyOutLogs) return;
    if (logs.length === 0) {
        tbodyOutLogs.innerHTML = '<tr><td colspan="8" class="text-center text-muted">Chưa có lượt xe nào ra khỏi bãi.</td></tr>';
        return;
    }
    let html = "";
    logs.forEach((row, index) => {
        html += `
            <tr>
                <td>#${index + 1}</td>
                <td><span class="badge badge-accent">${row.slot_name}</span></td>
                <td><strong>${row.plate_number}</strong></td>
                <td>${row.rfid_uid || "--"}</td>
                <td>${row.time_in}</td>
                <td>${row.time_out}</td>
                <td class="highlight-green">${formatVND(row.fee)}</td>
                <td>
                    <button class="btn btn-outline-danger btn-sm" onclick="deleteLogOut(${row.id})" title="Xóa">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </td>
            </tr>
        `;
    });
    tbodyOutLogs.innerHTML = html;
}

window.deleteLogIn = async function(id) {
    if (!confirm("Bạn có chắc chắn muốn xóa bản ghi xe vào này?")) return;
    try {
        await fetch(`/api/logs/in/${id}`, { method: "DELETE" });
        showToast("Đã xóa bản ghi xe vào", "success");
        fetchLogs();
    } catch (err) {
        showToast("Lỗi xóa bản ghi", "error");
    }
};

window.deleteLogOut = async function(id) {
    if (!confirm("Bạn có chắc chắn muốn xóa bản ghi xe ra này?")) return;
    try {
        await fetch(`/api/logs/out/${id}`, { method: "DELETE" });
        showToast("Đã xóa bản ghi xe ra", "success");
        fetchLogs();
    } catch (err) {
        showToast("Lỗi xóa bản ghi", "error");
    }
};

window.clearEntireDatabase = async function() {
    if (!confirm("CẢNH BÁO: Thao tác này sẽ XÓA TOÀN BỘ lịch sử xe vào, xe ra và doanh thu về 0 để test lại từ đầu. Bạn có chắc chắn?")) return;
    try {
        await fetch("/api/database/clear", { method: "POST" });
        showToast("Đã xóa trắng toàn bộ dữ liệu CSDL!", "success");
        fetchStatus();
        fetchLogs();
    } catch (err) {
        showToast("Lỗi khi xóa CSDL", "error");
    }
};

// -------------------------------------------------------------
// Tabs Navigation
// -------------------------------------------------------------
document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

        btn.classList.add("active");
        const targetId = btn.getAttribute("data-tab");
        const targetContent = document.getElementById(targetId);
        if (targetContent) targetContent.classList.add("active");
    });
});

// -------------------------------------------------------------
// Search Filters
// -------------------------------------------------------------
if (searchInLogs) {
    searchInLogs.addEventListener("input", (e) => {
        const filter = e.target.value.toLowerCase();
        document.querySelectorAll("#tbody-in-logs tr").forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(filter) ? "" : "none";
        });
    });
}

if (searchOutLogs) {
    searchOutLogs.addEventListener("input", (e) => {
        const filter = e.target.value.toLowerCase();
        document.querySelectorAll("#tbody-out-logs tr").forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(filter) ? "" : "none";
        });
    });
}

// -------------------------------------------------------------
// Initialization & Loops
// -------------------------------------------------------------
checkAuth();
fetchStatus();
fetchLogs();

// Real-time loops
setInterval(fetchStatus, 1500);      // Poll status & pending exits every 1.5s
setInterval(updateLiveTimers, 1000); // Live duration count every second
setInterval(fetchLogs, 5000);        // Refresh logs every 5s
