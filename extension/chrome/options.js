const keyInput = document.getElementById("gemini-key");
const modelInput = document.getElementById("gemini-model");
const appearanceInput = document.getElementById("appearance");
const colorThemeInput = document.getElementById("color-theme");
const status = document.getElementById("settings-status");

chrome.storage.local.get(["geminiModel", "appearance", "colorTheme"], (values) => {
  modelInput.value = values.geminiModel || "gemini-2.5-flash";
  appearanceInput.value = values.appearance || "Dark";
  colorThemeInput.value = values.colorTheme || "blue";
});

document.getElementById("save-settings").addEventListener("click", () => {
  const model = modelInput.value.trim();
  if (!model) {
    status.textContent = "Вкажи назву моделі Gemini.";
    return;
  }
  const changes = {
    geminiModel: model,
    appearance: appearanceInput.value,
    colorTheme: colorThemeInput.value
  };
  if (keyInput.value.trim()) changes.geminiApiKey = keyInput.value.trim();
  chrome.storage.local.set(changes, () => {
    if (chrome.runtime.lastError) {
      status.textContent = chrome.runtime.lastError.message;
      return;
    }
    keyInput.value = "";
    status.textContent = "Налаштування збережено.";
    document.documentElement.dataset.appearance = appearanceInput.value;
    document.documentElement.dataset.colorTheme = colorThemeInput.value;
  });
});

document.getElementById("clear-key").addEventListener("click", () => {
  chrome.storage.local.remove("geminiApiKey", () => {
    if (chrome.runtime.lastError) {
      status.textContent = chrome.runtime.lastError.message;
      return;
    }
    keyInput.value = "";
    status.textContent = "Ключ видалено зі сховища розширення.";
  });
});
