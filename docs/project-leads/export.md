# Export

When all annotations, discussions, and expert adjudications for a batch are complete:

- Click **...** and **Export batch** on an individual batch card to download its final labels, discussion transcripts, and revision history.
- Click **Export Project** at the top right of the project page to download the complete dataset and full Git-backed audit trail for the entire project.
- Both exports are JSON Lines files with one sample per line. The extra columns of the uploaded file appear under `metadata`, e.g. `"metadata": {"id": 4711, "source": "twitter"}`.

:::{figure} ../screenshots/expert_export_project.png
:width: 650px
:align: center
:alt: Export Project Dashboard

**Figure 10: Data Export**. Project dashboard view offering individual batch or full project data export options.
:::
