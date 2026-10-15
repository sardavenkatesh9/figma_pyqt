# GUI workflow

1. Paste a Figma design or file link and a personal access token, then choose **Verify link**.
   A link with `node-id` loads the frames directly inside that section; a plain file link loads
   every top-level frame of every page. Requests time out after 30 seconds.
2. Check the frames to include. Each row shows the frame name (numbered when several share a name),
   page or section, size, layer count and Figma node id; **Select all** and **Clear** help with long lists.
3. Choose a project name and output directory (empty fields fall back to `GeneratedApp` and
   `./generated_project`), then **Generate project**. Warnings (unsupported nodes, hand-edited files
   that were kept) are summarised in the result line.

**Generate project** then loads the full detail of the selected frames from Figma, exports vector and
image layers, and writes the project, in a background thread. A progress bar in the footer shows the current stage and the overall percentage
(loading frames, rendering and downloading images, writing files); it disappears when the job ends Closing the window (or Ctrl+C in the terminal) cancels a running generation at its next step and writes
nothing half-finished. (typically
10-60 seconds per frame). The token is sent only to Figma (`X-Figma-Token` header), cleared from the input
immediately, kept in memory only for the Generate step, and never written to disk or logs. The window always opens maximized and uses one dark neon theme.
