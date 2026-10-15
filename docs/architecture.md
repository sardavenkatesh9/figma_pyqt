# Architecture

## Overview

The project has three major layers:

1. Input adapters and domain models
2. Headless conversion and validation services
3. Desktop GUI and CLI wrappers

The conversion engine is intentionally independent of PySide6 runtime types. The GUI simply invokes the same service layer.

## Threat model

- Imported JSON and remote configuration are untrusted.
- Output paths are validated before write operations.
- Generated code is treated as executable but not automatically imported into the main process.
- Unsupported Figma features are surfaced as warnings and diagnostics instead of hidden.

## Practical scopes

This repository provides a working local-json conversion workflow and desktop shell. Remote Figma API access and advanced preview tooling are intentionally scoped as future work, with the architecture ready for expansion.
