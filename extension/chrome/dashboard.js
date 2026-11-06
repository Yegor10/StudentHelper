const DAYS = [
  ["monday", "Понеділок"],
  ["tuesday", "Вівторок"],
  ["wednesday", "Середа"],
  ["thursday", "Четвер"],
  ["friday", "П’ятниця"]
];
let schedule;
let activeDay = DAYS[Math.min(Math.max(new Date().getDay() - 1, 0), 4)][0];
let assignments = [];
let selectedAssignment = null;
let latestAiAnswer = "";
let toastTimer;

function send(type, extra = {}) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type, ...extra }, (response) => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
      } else if (!response?.ok) {
        reject(new Error(response?.error || "StudentHelper request failed."));
      } else {
        resolve(response.data);
      }
    });
  });
}

function showToast(message, error = false) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.toggle("toast-error", error);
  toast.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.add("hidden"), 4500);
}

function setBusy(button, busy, busyText = "Зачекай…") {
  if (busy) {
    button.dataset.originalText = button.textContent;
    button.textContent = busyText;
    button.disabled = true;
  } else {
    button.textContent = button.dataset.originalText || button.textContent;
    button.disabled = false;
  }
}

function switchView(viewId) {
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("hidden", view.id !== viewId);
  });
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === viewId);
  });
}

document.querySelectorAll(".nav-button").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

function renderWeekdayTabs() {
  const tabs = document.getElementById("weekday-tabs");
  tabs.replaceChildren();
  for (const [day, title] of DAYS) {
    const button = document.createElement("button");
    button.className = `weekday-tab${day === activeDay ? " active" : ""}`;
    button.textContent = title;
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(day === activeDay));
    button.addEventListener("click", async () => {
      if (day === activeDay) return;
      try {
        schedule.weekdays[activeDay] = collectSchedule();
        await send("SAVE_SCHEDULE", { schedule });
      } catch (error) {
        showToast(error.message, true);
        return;
      }
      activeDay = day;
      renderWeekdayTabs();
      renderLessonRows();
    });
    tabs.append(button);
  }
}

function renderLessonRows() {
  const plan = schedule.weekdays[activeDay];
  document.getElementById("start-time").value = plan.start_time || "08:00";
  const body = document.getElementById("lesson-rows");
  body.replaceChildren();
  plan.lessons.forEach((lesson, index) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td class="row-index">${index + 1}</td>
      <td><input class="lesson-title" type="text" maxlength="120" placeholder="Назва предмета"></td>
      <td><input class="lesson-duration" type="number" min="1" max="600" value="80" aria-label="Тривалість у хвилинах"></td>
      <td><input class="lesson-break" type="number" min="0" max="180" value="5" aria-label="Перерва у хвилинах"></td>
      <td><input class="lesson-url" type="url" placeholder="https://meet.google.com/…" aria-label="Посилання на урок"></td>
      <td class="row-actions"><button class="icon-button open-meeting" type="button" title="Відкрити урок" aria-label="Відкрити урок">↗</button><button class="icon-button remove-lesson" type="button" title="Видалити пару" aria-label="Видалити пару">×</button></td>`;
    row.querySelector(".lesson-title").value = lesson.title || "";
    row.querySelector(".lesson-duration").value = lesson.duration_minutes || 80;
    row.querySelector(".lesson-break").value = lesson.break_minutes ?? 5;
    row.querySelector(".lesson-url").value = lesson.meeting_url || "";
    row.querySelector(".remove-lesson").addEventListener("click", () => {
      plan.lessons.splice(index, 1);
      renderLessonRows();
    });
    row.querySelector(".open-meeting").addEventListener("click", async () => {
      if (!lesson.meeting_url) {
        showToast("Для цієї пари не вказане посилання.", true);
        return;
      }
      try {
        await send("OPEN_URL", { url: lesson.meeting_url });
      } catch (error) {
        showToast(error.message, true);
      }
    });
    body.append(row);
  });
}

function collectSchedule() {
  const rows = [...document.querySelectorAll("#lesson-rows tr")];
  const lessons = rows.map((row) => {
    const title = row.querySelector(".lesson-title").value.trim();
    const duration = Number(row.querySelector(".lesson-duration").value);
    const breakMinutes = Number(row.querySelector(".lesson-break").value);
    const url = row.querySelector(".lesson-url").value.trim();
    if (!title || !Number.isInteger(duration) || duration < 1 ||
        !Number.isInteger(breakMinutes) || breakMinutes < 0) {
      throw new Error("Перевір назву пари, тривалість і перерву.");
    }
    if (url && !/^https?:\/\/\S+$/i.test(url)) {
      throw new Error("Посилання має починатися з http:// або https://.");
    }
    return {
      title,
      duration_minutes: duration,
      break_minutes: breakMinutes,
      meeting_url: url
    };
  });
  const startTime = document.getElementById("start-time").value;
  if (!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(startTime)) {
    throw new Error("Вкажи час початку у форматі ГГ:ХХ.");
  }
  return { start_time: startTime, lessons };
}

document.getElementById("add-lesson").addEventListener("click", () => {
  try {
    schedule.weekdays[activeDay] = collectSchedule();
  } catch (error) {
    showToast(error.message, true);
    return;
  }
  schedule.weekdays[activeDay].lessons.push({
    title: "",
    duration_minutes: 80,
    break_minutes: 5,
    meeting_url: ""
  });
  renderLessonRows();
  document.querySelector("#lesson-rows tr:last-child .lesson-title")?.focus();
});

document.getElementById("save-schedule").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  try {
    schedule.weekdays[activeDay] = collectSchedule();
    setBusy(button, true, "Зберігаю…");
    await send("SAVE_SCHEDULE", { schedule });
    document.getElementById("save-indicator").textContent = "Зміни збережені";
    showToast("Розклад збережено. Посилання відкриються за хвилину до пари.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
  }
});

function formatDueDate(dueDate, dueTime) {
  if (!dueDate) return "Дедлайн не вказано";
  const date = new Date(dueDate.year, dueDate.month - 1, dueDate.day);
  const formatted = new Intl.DateTimeFormat("uk-UA", {
    day: "numeric",
    month: "long",
    year: "numeric"
  }).format(date);
  if (!dueTime) return `Здати до ${formatted}`;
  const hours = String(dueTime.hours || 0).padStart(2, "0");
  const minutes = String(dueTime.minutes || 0).padStart(2, "0");
  return `Здати до ${formatted}, ${hours}:${minutes}`;
}

function renderAssignments() {
  const list = document.getElementById("assignment-list");
  list.replaceChildren();
  document.getElementById("assignment-count").textContent = String(assignments.length);
  if (!assignments.length) {
    list.textContent = "Активних завдань не знайдено.";
    list.className = "assignment-list empty-state";
    return;
  }
  list.className = "assignment-list";
  for (const assignment of assignments) {
    const button = document.createElement("button");
    button.className = `assignment-card${selectedAssignment?.courseWorkId === assignment.courseWorkId && selectedAssignment?.courseId === assignment.courseId ? " selected" : ""}`;
    const state = assignment.state === "TURNED_IN"
      ? "Здано"
      : assignment.state === "RETURNED"
        ? "Повернуто"
        : "Потрібно здати";
    button.innerHTML = `
      <span class="assignment-card-top"><span class="course-name"></span><span class="assignment-state"></span></span>
      <strong class="assignment-name"></strong>
      <span class="assignment-due"></span>`;
    button.querySelector(".course-name").textContent = assignment.courseName;
    button.querySelector(".assignment-name").textContent = assignment.title;
    button.querySelector(".assignment-state").textContent = state;
    button.querySelector(".assignment-due").textContent =
      formatDueDate(assignment.dueDate, assignment.dueTime);
    button.addEventListener("click", () => selectAssignment(assignment));
    list.append(button);
  }
}

function selectAssignment(assignment) {
  selectedAssignment = assignment;
  document.getElementById("assignment-placeholder").classList.add("hidden");
  document.getElementById("assignment-content").classList.remove("hidden");
  document.getElementById("assignment-course").textContent = assignment.courseName;
  document.getElementById("assignment-title").textContent = assignment.title;
  document.getElementById("assignment-due").textContent =
    formatDueDate(assignment.dueDate, assignment.dueTime);
  document.getElementById("assignment-description").textContent =
    assignment.description || "Для цього завдання викладач не додав опис.";
  const openLink = document.getElementById("open-assignment");
  if (assignment.alternateLink) {
    openLink.href = assignment.alternateLink;
    openLink.classList.remove("hidden");
  } else {
    openLink.classList.add("hidden");
  }
  document.getElementById("work-file").value = "";
  const attachments = assignment.attachments || [];
  document.getElementById("attachment-status").textContent = attachments.length
    ? `У Classroom уже є вкладення: ${attachments.map((item) => item.driveFile?.title || item.driveFile?.id || "файл").join(", ")}`
    : "Файл ще не прикріплений.";
  document.getElementById("attach-file").disabled =
    !assignment.submissionId || assignment.state === "TURNED_IN";
  document.getElementById("turn-in").disabled =
    !assignment.submissionId ||
    assignment.state === "TURNED_IN" ||
    attachments.length === 0;
  document.getElementById("ai-answer").classList.add("hidden");
  document.getElementById("download-answer").classList.add("hidden");
  renderAssignments();
}

function clearSelectedAssignment() {
  selectedAssignment = null;
  document.getElementById("assignment-content").classList.add("hidden");
  document.getElementById("assignment-placeholder").classList.remove("hidden");
}

document.getElementById("connect-classroom").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  setBusy(button, true, "Підключаю…");
  try {
    await send("AUTH_CONNECT");
    document.getElementById("classroom-status").textContent =
      "Google підключено. Тепер онови завдання.";
    showToast("Google Classroom успішно підключено.");
  } catch (error) {
    document.getElementById("classroom-status").textContent = error.message;
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
  }
});

document.getElementById("refresh-assignments").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  setBusy(button, true, "Завантажую…");
  document.getElementById("classroom-status").textContent =
    "Завантажую курси, завдання та статуси здачі…";
  try {
    const result = await send("GET_ASSIGNMENTS", { interactive: false });
    assignments = result.assignments;
    document.getElementById("classroom-status").textContent =
      `Завантажено завдань: ${assignments.length}.`;
    if (selectedAssignment) {
      const updated = assignments.find((item) =>
        item.courseId === selectedAssignment.courseId &&
        item.courseWorkId === selectedAssignment.courseWorkId
      );
      if (updated) {
        selectedAssignment = updated;
      } else {
        clearSelectedAssignment();
      }
    }
    renderAssignments();
    if (selectedAssignment) selectAssignment(selectedAssignment);
  } catch (error) {
    document.getElementById("classroom-status").textContent = error.message;
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
  }
});

document.getElementById("attach-file").addEventListener("click", async (event) => {
  if (!selectedAssignment) return;
  const file = document.getElementById("work-file").files[0];
  if (!file) {
    showToast("Спочатку вибери файл зі своєю роботою.", true);
    return;
  }
  if (file.size > 12 * 1024 * 1024) {
    showToast("Максимальний розмір файла — 12 МБ.", true);
    return;
  }
  const button = event.currentTarget;
  setBusy(button, true, "Завантажую…");
  try {
    const fileBase64 = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
      reader.onerror = () => reject(new Error("Не вдалося прочитати файл."));
      reader.readAsDataURL(file);
    });
    await send("UPLOAD_AND_ATTACH", {
      courseId: selectedAssignment.courseId,
      courseWorkId: selectedAssignment.courseWorkId,
      submissionId: selectedAssignment.submissionId,
      fileName: file.name,
      mimeType: file.type || "application/octet-stream",
      fileBase64
    });
    document.getElementById("attachment-status").textContent =
      `Прикріплено: ${file.name}. Перевір вкладення, а потім окремо натисни «Перевірити й здати».`;
    if (!selectedAssignment.attachments) selectedAssignment.attachments = [];
    selectedAssignment.attachments.push({ driveFile: { title: file.name } });
    document.getElementById("turn-in").disabled = false;
    showToast("Файл прикріплено до роботи.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
    button.disabled = selectedAssignment?.state === "TURNED_IN";
  }
});

document.getElementById("turn-in").addEventListener("click", async (event) => {
  if (!selectedAssignment) return;
  const confirmed = window.confirm(
    `Здати роботу «${selectedAssignment.title}» у курсі «${selectedAssignment.courseName}»? Після підтвердження Classroom позначить її як здану.`
  );
  if (!confirmed) return;
  const button = event.currentTarget;
  setBusy(button, true, "Здаю…");
  try {
    await send("TURN_IN", {
      courseId: selectedAssignment.courseId,
      courseWorkId: selectedAssignment.courseWorkId,
      submissionId: selectedAssignment.submissionId
    });
    showToast("Classroom підтвердив здавання роботи.");
    assignments = assignments.filter((assignment) =>
      assignment.courseId !== selectedAssignment.courseId ||
      assignment.courseWorkId !== selectedAssignment.courseWorkId
    );
    clearSelectedAssignment();
    renderAssignments();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
    button.disabled = !selectedAssignment || selectedAssignment.state === "TURNED_IN";
  }
});

document.getElementById("ask-gemini").addEventListener("click", async (event) => {
  if (!selectedAssignment) return;
  const button = event.currentTarget;
  setBusy(button, true, "Gemini готує пояснення…");
  try {
    const prompt = [
      `Курс: ${selectedAssignment.courseName}`,
      `Завдання: ${selectedAssignment.title}`,
      selectedAssignment.description
    ].filter(Boolean).join("\n\n");
    const result = await send("SOLVE_WITH_GEMINI", { prompt });
    latestAiAnswer = result.text;
    const answer = document.getElementById("ai-answer");
    answer.textContent = latestAiAnswer;
    answer.classList.remove("hidden");
    document.getElementById("download-answer").classList.remove("hidden");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
  }
});

document.getElementById("download-answer").addEventListener("click", () => {
  if (!latestAiAnswer) return;
  const blob = new Blob([latestAiAnswer], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "studenthelper-solution.txt";
  anchor.click();
  URL.revokeObjectURL(url);
});

async function initialize() {
  try {
    const result = await send("GET_SCHEDULE");
    schedule = result.schedule;
    renderWeekdayTabs();
    renderLessonRows();
    const auth = await send("AUTH_STATUS");
    document.getElementById("classroom-status").textContent = auth.connected
      ? "Google Classroom підключено. Онови завдання, щоб побачити актуальні дані."
      : "Щоб завантажити курси й роботи, підключи Google Classroom.";
  } catch (error) {
    showToast(error.message, true);
  }
}

initialize();
