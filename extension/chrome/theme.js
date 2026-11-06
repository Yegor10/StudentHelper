function applyStudentHelperTheme(settings = {}) {
  const appearance = settings.appearance || "Dark";
  const resolvedAppearance = appearance === "System"
    ? (window.matchMedia("(prefers-color-scheme: light)").matches ? "Light" : "Dark")
    : appearance;
  document.documentElement.dataset.appearance = resolvedAppearance;
  document.documentElement.dataset.colorTheme = settings.colorTheme || "blue";
}

chrome.storage.local.get(["appearance", "colorTheme"], applyStudentHelperTheme);
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local" || (!changes.appearance && !changes.colorTheme)) return;
  chrome.storage.local.get(["appearance", "colorTheme"], applyStudentHelperTheme);
});
