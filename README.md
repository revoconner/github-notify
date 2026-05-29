# GitHub Tray Notifier

A small Windows tray app that keeps an eye on your own GitHub repositories and lets you know when something happens on your issues and pull requests, without keeping a browser tab open.

## What it does

- Watches the issues and pull requests across the repositories you own.
- Groups them by repository in a simple tabbed window (Issues and PRs) that you can collapse and expand.
- Flags items with new activity (new comments, updates, and so on) with a count, and shows a small dot on a collapsed repository that has unread items.
- Switches its tray icon when you have unread activity, and pops a Windows notification when something new arrives while the app isn't in focus.
- Lives quietly in the system tray and stays out of your way.
  
<img width="auto" height="600" alt="image" src="https://github.com/user-attachments/assets/0d91d7cd-a75d-44f6-95b8-e54742df9813" />
<img width="auto" height="600" alt="image" src="https://github.com/user-attachments/assets/f82f7ffe-80b7-47e4-821c-100c565cd842" />

## What you need

- Windows 10 or 11.
- A GitHub Personal Access Token so the app can read your repositories. Either a classic token (with the notifications and repo permissions) or a fine-grained token (with read access to metadata, issues, and pull requests) will work.
- Python
- These packages

```
PySide6
httpx
keyring
win11toast
```

## Getting started

1. Start the app using run.bat. On the very first run it opens its window so you can set things up; after that it starts quietly in the tray.
2. Open the Settings tab, paste your GitHub token into the Token field, and click Save.
3. That's it. The app checks GitHub every few minutes (you can change how often in Settings) and fills the Issues and PRs tabs.

## Everyday use

- Click the tray icon to open the window. Closing the window hides it back to the tray; quit from the tray's right-click menu.
- Click an item to open it in your browser. This also marks it as read.
- Use the poll button at the top right of the tabs to refresh right away.
- Right-click an item or a repository to mark things read or unread.
- Hold Ctrl and click to select several items, or a whole repository, then right-click to act on all of them at once.
- Use the Settings tab to choose which issues and pull requests you see, hide bot activity, and set how often the app checks.

---

Credit: SVG from  [svgrepo.com](svgrepo.com)
