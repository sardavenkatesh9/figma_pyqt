# Security controls

- Input files are parsed from disk without dynamic imports.
- Generated output is written into a staged directory.
- Path traversal is blocked by using explicit project directories and file validation.
- Output generation is deterministic and does not execute user-provided Python code.
