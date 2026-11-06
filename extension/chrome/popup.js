const statusElement = document.getElementById("popup-status");
const connectButton = document.getElementById("connect-button");

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

async function updateStatus() {
  try {
    const result = await send("AUTH_STATUS");
    statusElement.textContent = result.connected
      ? "Google Classroom підключено."
      : "Google Classroom ще не підключено.";
    connectButton.textContent = result.connected
      ? "Оновити доступ Google"
      : "Підключити Google Classroom";
  } catch (error) {
    statusElement.textContent = error.message;
  }
}

connectButton.addEventListener("click", async () => {
  connectButton.disabled = true;
  statusElement.textContent = "Очікую на вхід Google…";
  try {
    await send("AUTH_CONNECT");
    statusElement.textContent = "Google Classroom підключено.";
  } catch (error) {
    statusElement.textContent = error.message;
  } finally {
    connectButton.disabled = false;
    await updateStatus();
  }
});

document.getElementById("open-dashboard").addEventListener("click", () => {
  chrome.tabs.create({ url: chrome.runtime.getURL("dashboard.html") });
  window.close();
});

updateStatus();
