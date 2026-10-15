# Security controls

What the code does today:

- Figma links must be `https://figma.com` or `https://www.figma.com` design/file links; the file key
  and node id are validated against strict patterns before a request is built.
- The access token is only placed in the request header, cleared from the input right after, and
  never stored.
- JSON is parsed with the standard library only; there are no dynamic imports, `eval` or `exec`.
- Strings from Figma (names, text) are embedded into generated code with `json.dumps`, and module names
  are reduced to `[a-z0-9_]`, so a hostile frame name cannot inject code or escape the pages directory.
- The converter writes files but never executes generated code.
- Regeneration only deletes pages that carry the generator marker.

What it does not do:

- The output directory is whatever the user chooses; it is not sandboxed or staged. Pick an empty or
  dedicated folder.
- Generated apps are ordinary Python; review them before running, as with any generated code.
- Released binaries are not code-signed or notarized.
