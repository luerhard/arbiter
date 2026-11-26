# Annotate

The Annotator role focuses on independent labeling, peer discussion of conflicting samples, and staying synchronized with evolving Codebook guidelines.

## Project Dashboard View

When logging in, Annotators see a summary of all assigned projects, active batches, and current phase statuses. Batches in _Discussion_ phase are highlited and displayed first.

:::{figure} ../screenshots/annotator_start.png
:width: 650px
:align: center
:alt: Annotator Home Dashboard

**Figure 11: Annotator Home Dashboard**. Overview of assigned projects, active batches, and current phase indicator.
:::

## 1. First Batch Overview & Codebook View

Clicking on a project opens the project view:

- **Start Annotating** (Batch section): Opens the labeling interface for the assigned batch.
- **Open** (Codebook section): Opens the current annotation guidelines.
- **Codebook Changes** (Batch section): Displays the codebook view showing newly added rules since the previous batch.

:::{figure} ../screenshots/annotator_first_batch_overview.png
:width: 650px
:align: center
:alt: Annotator Batch Overview

**Figure 12: Annotator Batch Overview Card**. Displaying assigned samples for the current project, codebook and action buttons.
:::

## 2. Annotation Phase

In the Annotation phase, annotators label each sample independently:

1. Read the presented text sample.
2. Click the appropriate candidate label button and save to move to the next sample (or use custom keyboard shortcuts).
3. Navigate through samples using arrow buttons or keyboard shortcuts.
4. When all samples for the current batch are annotated, you can either check and change your labels by clicking on **Review my labels** or lock in your annotations for the current batch by clicking on **Finalize annotation**. When all annotators have finalized, the batch moves to the _Discussion_ phase in case of disagreements.

You can click on the **Codebook** button anytime to display the annotation guidelines next to the sample you're annotating.

:::{figure} ../screenshots/annotator_annotation_interface.png
:width: 550px
:align: center
:alt: Independent Annotation Screen

**Figure 14: Annotation Interface**. Single-sample labeling screen with progress bar, label selection buttons, and navigation controls.
:::

:::{figure} ../screenshots/annotator_finalize_annotation.png
:width: 550px
:align: center
:alt: Finalize Batch Screen

**Figure 15: Finalize Batch**. Completion prompt displayed when all samples in a batch have been labeled.
:::

### Keyboard Shortcuts

The annotation interface supports hotkeys for rapid labeling and navigation:

- **Left Arrow Key (←)**: Move to the previous sample.
- **Right Arrow Key (→)**: Move to the next sample.
- **Enter Key (↵)**: Save annotation.
- **Custom Hotkeys**: Custom key bindings defined during project setup.
