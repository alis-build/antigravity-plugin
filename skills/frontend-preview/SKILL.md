---
name: frontend-preview
description: Show an Alis service's web frontend in a real browser and drive it with your own browser tools (Antigravity's browser in the IDE, agent-browser on a workstation, or a Playwright MCP) - open the page, click through it, read its console and errors, screenshot it, check a UI change. Use when the user asks to see, open, preview, check or test the app, a page, a form or a UI change of a service with a web frontend, or sends a note about a page element (a message starting with "> [preview]"). NOT for build or deploy logs, operation status, the Alis console, or anything the alis CLI answers directly.
---

# Frontend preview: see and drive a service's page

The `alis` CLI only says where the page is. You open it in the browser your
own tools drive, the user watches that browser, and you drive it. Nothing is
installed or launched for this; `curl` and fetching the HTML are not
substitutes for a rendered page.

## 1. Find the address

1. The dev server must answer. `alis run` stays in the foreground, so if it
   is not running, ask the user to start it in another terminal of the
   service folder and wait until it listens.
2. Run `alis preview --json` in the service folder, or
   `alis --cwd <service folder> preview --json` from elsewhere. It resolves
   the service's `.claude/launch.json` port, else the Makefile's `APP_URL`,
   else a Vite app's configured port, else `localhost:8080`. Pass `--port <n>`
   or `--url <address>` when you know better (a Vite server on 5173, a route
   such as `/checkout`).

Read the result:

- `url` with no workstation fields: a laptop. Go to step 2 with that address.
- `preview_pane: true`: this is a workstation whose shell has a Chrome pane
  showing the browser you drive. Run `agent-browser open <url>` and carry on
  with `agent-browser` (step 2); the person watches the same Chrome, and
  their tabs and logins are yours. If the person is not watching, pass on
  the `hint`: they click Chrome in the browser shell's top bar (`shell_url`).
  Leave the page open when you finish.
- `workstation_url` without `preview_pane`: an older workstation image. Give
  the user that address and the `hint`.
- `guessed: true`: no frontend or port was found, so the page may not answer.
  Tell the user which address you tried.
- `unknown command "preview"`: this CLI predates `alis preview`. Suggest
  `alis upgrade`, and meanwhile take the port from the service's
  `.claude/launch.json` or the dev server's output.

## 2. Drive it with your browser tools

Use whichever browser tools this session has; do not install any.

- **Antigravity's browser** (in the IDE): open the address, inspect and
  click through the page, read its console, and screenshot when layout
  matters. The user sees the page as you work.
- **agent-browser** (on a workstation, already attached to the shared
  Chrome): `agent-browser open <url>`, `agent-browser snapshot -i` for the
  interactive elements with refs like `@e5`, `agent-browser click @e5`,
  `agent-browser fill @e9 "text"`, `agent-browser press Enter`,
  `agent-browser console`, `agent-browser screenshot /tmp/page.png`. If a
  page needs the person (a sign-in, a 2FA prompt), say so in your reply and
  wait; they act in the same browser.
- **Playwright MCP** (`browser_*`), when its tools are declared to you:
  `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`,
  `browser_console_messages`, `browser_take_screenshot`.
- **No browser tools at all** (the `agy` CLI in a plain laptop terminal):
  give the user the address to open, and ask them what they see.

## 3. Close it only when asked

Leave the tab open when you finish; the user keeps looking at it. Close only
the tab you opened, never the user's other tabs or their browser.

## 4. The user points at something

A workstation shell's Chrome pane has an Annotate button that sends you one
line starting with `> [preview]`, describing the element, with its source
file for React dev builds and a screenshot path. Treat it as the thing to
change: find it in the code, change it, then reload the page and check the
result in the same browser.

## Not for

Build or deploy logs, operation status, the Alis console, or anything the
`alis` CLI answers (`alis logs`, `alis operations`, `alis context view`).
