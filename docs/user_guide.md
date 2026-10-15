# User guide

## Start the workbench

```bash
figma-to-pyside6          # or: figma-to-pyside6 gui, or the packaged FigmaToPySide6 binary
```

## Verify, select, generate

Paste a Figma design or file link, enter a personal access token and choose **Verify link**. Select the
frames to include, set a project name and output directory and choose **Generate project**. Each selected
frame becomes its own page in the generated app, reachable from a sidebar.

## Run the generated app

```bash
cd generated_project
python main.py
```

The app opens maximized and uses the same dark neon theme.

## Command line

```bash
figma-to-pyside6 inspect  file.json                      # list frames as JSON
figma-to-pyside6 convert  file.json --project-name Demo --output-dir out
figma-to-pyside6 validate out                            # or: validate file.json
figma-to-pyside6 report   out                            # print the generation manifest
```
