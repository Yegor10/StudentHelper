const WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"];
const ALARM_PREFIX = "studenthelper-lesson:";
const MAX_UPLOAD_BYTES = 12 * 1024 * 1024;
const CLASSROOM_API = "https://classroom.googleapis.com/v1";
const DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files";

async function loadDefaultSchedule() {
  const response = await fetch(chrome.runtime.getURL("default-schedule.json"));
  if (!response.ok) {
    throw new Error("Could not load the bundled weekly schedule.");
  }
  return response.json();
}

function getAuthToken(interactive) {
  return new Promise((resolve, reject) => {
    chrome.identity.getAuthToken({ interactive }, (result) => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      const token = typeof result === "string" ? result : result?.token;
      if (!token) {
        reject(new Error("Google did not return an access token."));
        return;
      }
      resolve(token);
    });
  });
}

async function apiRequest(url, options = {}) {
  const token = await getAuthToken(Boolean(options.interactive));
  const method = (options.method || "GET").toUpperCase();
  const canRetry = method === "GET";
  let response;
  for (let attempt = 0; ; attempt += 1) {
    response = await fetch(url, {
      ...options,
      headers: {
        ...(options.headers || {}),
        Authorization: `Bearer ${token}`
      }
    });
    const retryableStatus = [408, 429, 500, 502, 503, 504].includes(response.status);
    if (!canRetry || !retryableStatus || attempt >= 2) break;

    const retryAfter = Number(response.headers.get("Retry-After"));
    const delay = Number.isFinite(retryAfter) && retryAfter >= 0
      ? Math.min(retryAfter * 1000, 5000)
      : 500 * (2 ** attempt);
    await new Promise((resolve) => setTimeout(resolve, delay));
  }

  const body = await response.text();
  let data = {};
  if (body) {
    try {
      data = JSON.parse(body);
    } catch {
      throw new Error(`Google API returned an unreadable response (${response.status}).`);
    }
  }
  if (!response.ok) {
    if (response.status === 503) {
      throw new Error(
        "Google Classroom тимчасово недоступний (503). Спробуй оновити завдання за хвилину."
      );
    }
    const message = data.error?.message || `Google API request failed (${response.status}).`;
    throw new Error(`${message} (${response.status})`);
  }
  return data;
}

async function listAll(url) {
  const items = [];
  let nextUrl = url;
  while (nextUrl) {
    const result = await apiRequest(nextUrl);
    items.push(...(result.courses || result.courseWork || result.studentSubmissions || []));
    nextUrl = result.nextPageToken
      ? `${url}${url.includes("?") ? "&" : "?"}pageToken=${encodeURIComponent(result.nextPageToken)}`
      : "";
  }
  return items;
}

async function fetchAssignments() {
  const courses = await listAll(
    `${CLASSROOM_API}/courses?courseStates=ACTIVE&pageSize=100`
  );
  const assignments = [];
  for (const course of courses) {
    const coursework = await listAll(
      `${CLASSROOM_API}/courses/${encodeURIComponent(course.id)}/courseWork?courseWorkStates=PUBLISHED&pageSize=100`
    );
    for (const item of coursework.filter((work) => work.workType === "ASSIGNMENT")) {
      if (isAssignmentOverdue(item)) continue;
      const submissions = await listAll(
        `${CLASSROOM_API}/courses/${encodeURIComponent(course.id)}/courseWork/${encodeURIComponent(item.id)}/studentSubmissions?userId=me&pageSize=100`
      );
      const submission = submissions[0] || null;
      const state = submission?.state || "UNKNOWN";
      if (state === "TURNED_IN" || state === "RETURNED") continue;
      assignments.push({
        courseId: course.id,
        courseName: course.name || "Classroom course",
        courseWorkId: item.id,
        title: item.title || "Untitled assignment",
        description: item.description || "",
        dueDate: item.dueDate || null,
        dueTime: item.dueTime || null,
        alternateLink: item.alternateLink || "",
        state,
        submissionId: submission?.id || null,
        attachments: submission?.assignmentSubmission?.attachments || []
      });
    }
  }
  return assignments.sort((left, right) => {
    const dueTimestamp = (assignment) => {
      if (!assignment.dueDate) return Number.POSITIVE_INFINITY;
      const date = assignment.dueDate;
      const time = assignment.dueTime || {};
      return Date.UTC(
        date.year,
        date.month - 1,
        date.day,
        time.hours || 0,
        time.minutes || 0,
        time.seconds || 0,
        Math.floor((time.nanos || 0) / 1_000_000)
      );
    };
    return dueTimestamp(left) - dueTimestamp(right);
  });
}

function isAssignmentOverdue(assignment, now = new Date()) {
  const dueDate = assignment.dueDate;
  if (!dueDate) return false;
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const dueDay = new Date(dueDate.year, dueDate.month - 1, dueDate.day);
  if (!assignment.dueTime) return dueDay < today;
  const dueTime = assignment.dueTime;
  const deadline = new Date(
    dueDate.year,
    dueDate.month - 1,
    dueDate.day,
    dueTime.hours || 0,
    dueTime.minutes || 0,
    dueTime.seconds || 0,
    Math.floor((dueTime.nanos || 0) / 1_000_000)
  );
  return deadline <= now;
}

function decodeBase64(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

async function uploadAndAttach(message) {
  if (!message.fileName || typeof message.fileBase64 !== "string") {
    throw new Error("Choose a file before attaching it.");
  }
  const bytes = decodeBase64(message.fileBase64);
  if (!bytes.length || bytes.length > MAX_UPLOAD_BYTES) {
    throw new Error("Choose a non-empty file smaller than 12 MB.");
  }
  if (!message.courseId || !message.courseWorkId || !message.submissionId) {
    throw new Error("The Classroom submission could not be identified.");
  }

  const mimeType = message.mimeType || "application/octet-stream";
  const boundary = `studenthelper-${crypto.randomUUID()}`;
  const metadata = JSON.stringify({ name: message.fileName });
  const multipartBody = new Blob([
    `--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n${metadata}\r\n`,
    `--${boundary}\r\nContent-Type: ${mimeType}\r\n\r\n`,
    bytes,
    `\r\n--${boundary}--`
  ]);
  const uploaded = await apiRequest(`${DRIVE_UPLOAD_API}?uploadType=multipart&fields=id,name,webViewLink`, {
    method: "POST",
    headers: { "Content-Type": `multipart/related; boundary=${boundary}` },
    body: multipartBody
  });
  if (!uploaded.id) {
    throw new Error("Drive did not return an uploaded file ID.");
  }

  try {
    const path = `${CLASSROOM_API}/courses/${encodeURIComponent(message.courseId)}/courseWork/${encodeURIComponent(message.courseWorkId)}/studentSubmissions/${encodeURIComponent(message.submissionId)}:modifyAttachments`;
    const result = await apiRequest(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        addAttachments: [{ driveFile: { id: uploaded.id, title: uploaded.name } }]
      })
    });
    return {
      file: uploaded,
      attachmentCount: result.assignmentSubmission?.attachments?.length || 0
    };
  } catch (error) {
    throw new Error(
      `The file was uploaded to Drive but Classroom could not attach it. ` +
      `Drive file: ${uploaded.webViewLink || uploaded.id}. ${error.message}`
    );
  }
}

async function turnInAssignment(message) {
  if (!message.courseId || !message.courseWorkId || !message.submissionId) {
    throw new Error("The Classroom submission could not be identified.");
  }
  const path = `${CLASSROOM_API}/courses/${encodeURIComponent(message.courseId)}/courseWork/${encodeURIComponent(message.courseWorkId)}/studentSubmissions/${encodeURIComponent(message.submissionId)}:turnIn`;
  await apiRequest(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}"
  });
  return { submitted: true };
}

async function solveWithGemini(message) {
  const { geminiApiKey, geminiModel = "gemini-2.5-flash" } =
    await chrome.storage.local.get(["geminiApiKey", "geminiModel"]);
  if (!geminiApiKey) {
    throw new Error("Add your Gemini API key in StudentHelper settings to use AI.");
  }
  if (!message.prompt?.trim()) {
    throw new Error("This assignment has no description to send to Gemini.");
  }
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(geminiModel)}:generateContent`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-goog-api-key": geminiApiKey
    },
    body: JSON.stringify({
      contents: [{
        parts: [{
          text: `Help me understand this homework. Give a clear, step-by-step explanation and state any assumptions. Do not claim to have submitted the work.\n\n${message.prompt}`
        }]
      }]
    })
  });
  const result = await response.json();
  if (!response.ok) {
    throw new Error(result.error?.message || `Gemini request failed (${response.status}).`);
  }
  const text = result.candidates?.[0]?.content?.parts
    ?.map((part) => part.text || "")
    .join("")
    .trim();
  if (!text) {
    throw new Error("Gemini returned no solution text.");
  }
  return { text };
}

function localDateKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function lessonTime(date, timeValue) {
  const [hours, minutes] = timeValue.split(":").map(Number);
  const result = new Date(date);
  result.setHours(hours, minutes, 0, 0);
  return result;
}

async function scheduleMeetingAlarms(schedule) {
  const alarms = await chrome.alarms.getAll();
  await Promise.all(
    alarms
      .filter((alarm) => alarm.name.startsWith(ALARM_PREFIX))
      .map((alarm) => chrome.alarms.clear(alarm.name))
  );
  if (!schedule?.weekdays) return;

  const now = new Date();
  for (let offset = 0; offset < 14; offset += 1) {
    const day = new Date(now);
    day.setDate(now.getDate() + offset);
    const weekday = WEEKDAYS[day.getDay() - 1];
    if (!weekday) continue;
    const dayPlan = schedule.weekdays[weekday];
    if (!dayPlan) continue;
    let startsAt = lessonTime(day, dayPlan.start_time);
    for (const [index, lesson] of dayPlan.lessons.entries()) {
      const joinTime = new Date(startsAt.getTime() - 60_000);
      if (lesson.meeting_url && joinTime.getTime() > now.getTime()) {
        const alarmName = `${ALARM_PREFIX}${localDateKey(day)}:${weekday}:${index}`;
        await chrome.alarms.create(alarmName, { when: joinTime.getTime() });
      }
      startsAt = new Date(
        startsAt.getTime() +
        (Number(lesson.duration_minutes) + Number(lesson.break_minutes)) * 60_000
      );
    }
  }
}

async function openScheduledMeeting(alarmName) {
  const parts = alarmName.slice(ALARM_PREFIX.length).split(":");
  const [, weekday, indexText] = parts;
  const { schedule } = await chrome.storage.local.get("schedule");
  const lesson = schedule?.weekdays?.[weekday]?.lessons?.[Number(indexText)];
  if (!lesson?.meeting_url || !/^https?:\/\//i.test(lesson.meeting_url)) return;
  await chrome.tabs.create({ url: lesson.meeting_url });
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icons/icon128.png",
    title: "StudentHelper",
    message: `Opened ${lesson.title}. Check the meeting window and join when ready.`
  });
}

async function handleMessage(message) {
  switch (message.type) {
    case "AUTH_CONNECT":
      await getAuthToken(true);
      return { connected: true };
    case "AUTH_STATUS":
      try {
        await getAuthToken(false);
        return { connected: true };
      } catch {
        return { connected: false };
      }
    case "GET_ASSIGNMENTS":
      await getAuthToken(Boolean(message.interactive));
      return { assignments: await fetchAssignments() };
    case "UPLOAD_AND_ATTACH":
      await getAuthToken(false);
      return uploadAndAttach(message);
    case "TURN_IN":
      await getAuthToken(false);
      return turnInAssignment(message);
    case "SAVE_SCHEDULE": {
      const { schedule } = message;
      if (!schedule?.weekdays) throw new Error("The weekly schedule is invalid.");
      await chrome.storage.local.set({ schedule });
      await scheduleMeetingAlarms(schedule);
      return { saved: true };
    }
    case "GET_SCHEDULE": {
      const { schedule } = await chrome.storage.local.get("schedule");
      return { schedule: schedule || await loadDefaultSchedule() };
    }
    case "OPEN_URL": {
      if (!/^https?:\/\//i.test(message.url || "")) {
        throw new Error("Only HTTP and HTTPS links can be opened.");
      }
      await chrome.tabs.create({ url: message.url });
      return { opened: true };
    }
    case "SOLVE_WITH_GEMINI":
      return solveWithGemini(message);
    default:
      throw new Error("Unknown StudentHelper request.");
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  handleMessage(message).then(
    (data) => sendResponse({ ok: true, data }),
    (error) => sendResponse({ ok: false, error: error.message || String(error) })
  );
  return true;
});

chrome.runtime.onInstalled.addListener(async () => {
  const { schedule } = await chrome.storage.local.get("schedule");
  const initialSchedule = schedule || await loadDefaultSchedule();
  await chrome.storage.local.set({ schedule: initialSchedule });
  await scheduleMeetingAlarms(initialSchedule);
});

chrome.runtime.onStartup.addListener(async () => {
  const { schedule } = await chrome.storage.local.get("schedule");
  if (schedule) await scheduleMeetingAlarms(schedule);
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (!alarm.name.startsWith(ALARM_PREFIX)) return;
  try {
    await openScheduledMeeting(alarm.name);
    const { schedule } = await chrome.storage.local.get("schedule");
    await scheduleMeetingAlarms(schedule);
  } catch (error) {
    chrome.notifications.create({
      type: "basic",
      iconUrl: "icons/icon128.png",
      title: "StudentHelper",
      message: `Could not open the scheduled meeting: ${error.message}`
    });
  }
});
