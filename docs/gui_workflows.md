# GUI workflow

1. Paste a Figma design or file link and a personal access token, then choose **Verify link**.
   A link with `node-id` loads the frames directly inside that section; a plain file link loads
   every top-level frame of every page. Requests time out after 30 seconds.
2. Check the frames to include.
3. Choose a project name and output directory (empty fields fall back to `GeneratedApp` and
   `./generated_project`), then **Generate project**. Warnings (unsupported nodes, hand-edited files
   that were kept) are summarised in the result line.

The token is sent to Figma in the `X-Figma-Token` header and cleared from the input immediately. It is
not written to disk or logs. The window always opens maximized and uses one dark neon theme.
