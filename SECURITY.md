# Security

This project treats all imported Figma data and generated output as untrusted.

## Controls

- JSON parsing is restricted to local file input and explicit validation.
- Generated project output is written into a staged directory before publication.
- Arbitrary dynamic code execution is not performed during conversion.
- Generated code is previewed only via a separate process boundary when launched from the GUI.

## Reporting

Report vulnerabilities privately to the project maintainer.
