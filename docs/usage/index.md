# Usage

## General Info & Overview

You can access Arbiter at this link: [http://193.196.55.39/](http://193.196.55.39/)

You must be connected to University of Stuttgart's network (either by being on site or via VPN).

### What is Arbiter?

**Arbiter** is an open-source collaborative software tool and web application designed to build and document a shared understanding during data annotation tasks.

In subjective or complex data annotation tasks, low inter-annotator agreement often derives from two primary sources:

1. **Task Underspecification**: Ambiguity or gaps in the annotation guidelines where existing rules are vague, making it difficult to determine the label, especially for edge/difficult cases.
2. **Misapplication**: Annotators misunderstanding or incorrectly applying guidelines.

Unlike traditional post-hoc statistical methods that attempt to model disagreement after data collection is complete, Arbiter addresses disagreement **during** the active annotation process.

### Key Features

- **Project Creation and Data Batches Upload**: create your annotation project describing its purpose, choose the user accounts that will participate, define the labels, write initial annotation guidelines (i.e., **codebook**) and upload your dataset batch by batch.
- **Batch-Based Annotation and Real-Time Chat**: data is annotated in batches. When label disagreements occur, annotators discuss them synchronously in an integrated real-time chat interface.
- **Expert Adjudication and Guideline Revision**: disagreements that cannot be resolved between annotators are passed to an expert, who adjudicates the final label and updates the annotation guidelines.
- **Traceable Dataset Documentation**: every label assignment, discussion, expert decision rationale, and guideline revision is logged. This creates a complete audit trail that documents how the team's interpretation evolved over time, serving as a reproducibility artifact for downstream dataset users.

## User Login

To log into Arbiter, enter the credentials provided by your system administrator. The login interface is identical for annotators and experts.

:::{figure} screenshots/login.png
:width: 500px
:align: center
:alt: Arbiter Login Interface

**Figure 1: Arbiter Login**. Authentication page for Annotators and Experts.
:::

## User Roles and Workflow Description

Arbiter structures data labeling around three distinct user roles and a multi-stage collaborative loop.

### Users

- **Annotator**: Independently label data batches, deliberate with peers in real-time chat regarding disagreed samples to resolve misapplications, and review codebook updates before starting subsequent batches annotation.
- **Expert**: Create projects, upload data batches, review annotators' unresolved disagreements, assign final adjudicated labels, provide explanatory rationales, edit the codebook and export projects.
- **Administrator**: Manage user accounts and groups.

### Workflow

1. **First batch and codebook upload**: Expert user uploads batches and writes the first version of the annotation guidelines.
2. **Annotation**: Annotators independently assign labels according to current codebook guidelines.
3. **Discussion (Resolving Misapplication)**: Once independent labeling for a batch is complete, samples with divergent labels automatically enter the discussion stage. Annotators use the real-time chat interface to discuss their reasoning. If they reach consensus, updated labels are saved. If they don't, the sample is passed to the Expert.
4. **Expert adjudication and codebook update (Resolving Underspecification)**: The expert selects the final decision for the samples with divergent label and, where needed, updates the codebook to clarify the rule or edge case, writing the rationale on which is based the final decision.
5. **Codebook synchronization and maturation**: Before beginning the next batch, annotators read the updated codebook with changes highlighted. Over time, as guidelines mature, discussion counts and annotation guidelines edits decrease, signaling that the team has converged on a relatively stable, shared understanding.

:::{figure} screenshots/workflow_diagram.png
:width: 500px
:align: center
:alt: Arbiter Workflow Diagram

**Figure 2: Arbiter Workflow**
:::

---

## Expert User Guide

### 1. Create a Project

To set up a new annotation project:

1. Log in with an Expert account and click **+** in the navigation menu or **New Project** on the right side of the page, at the top of **Your Projects** section.
2. Fill out the project configuration form:
   - **Project title**: A name for your project.
   - **Description**: A summary defining the project scope and goals.
   - **Annotators & Experts**: Assign user profiles to their respective roles for this project.
   - **Labels**: Define labels along with custom display colors and hotkeys.

3. Click **Create Project** at the bottom of the page to save and create the project.

:::{figure} screenshots/expert_create_project_filled.png
:width: 650px
:align: center
:alt: Create Project Form

**Figure 3: Project Creation Form**. Fill in project info and save.
:::

---

### 2. Upload Batches

Once a project is created, data samples must be grouped and uploaded in batches:

1. Navigate to the project dashboard and click **New Batch** at the top of the page.
2. In the batch upload page, select a dataset file (`CSV` or `XLSX` containing a `text` column) and select the designated annotators and experts for that batch.
   Every other column (for example an `id`, the source or a date) is kept as metadata of the sample and included in the exports, so you can join the labels back to your data.
   Every row needs a text; the upload is rejected and names the rows that are empty.
   Put each piece of metadata in its own column, and save files from pandas with `df.to_csv(..., index=False)`; otherwise the row index is stored as an extra column called `Unnamed: 0`.
3. Upon upload, the new batch appears in the project's **Batches** list in **Annotation** mode.

:::{figure} screenshots/expert_upload_first_batch.png
:width: 550px
:align: center
:alt: Empty Project Dashboard

**Figure 4: Initial Project Dashboard**. Dashboard view before uploading dataset batches.
:::

:::{figure} screenshots/expert_create_first_batch.png
:width: 550px
:align: center
:alt: Create Batch Page

**Figure 5: Batch Creation Page**. Uploading a dataset file and assigning specific annotators and experts to the batch.
:::

:::{figure} screenshots/expert_batch_uploaded.png
:width: 650px
:align: center
:alt: Active Batch Overview

**Figure 6: Active Batch Dashboard**. Overview card displaying Batch 1 in the _Annotation_ phase, showing real-time annotation progress per user.
:::

### 2.1 Reorder samples within a batch

Once a batch is uploaded, it's possible to reorder the samples within that batch by clicking on "Batch #" (e.g., **Batch 1**) in the batch overview card. Once the samples view is open, click on the button at the left side of each sample row and drag it to change order.

:::{figure} screenshots/expert_reorder_samples.png
:width: 650px
:align: center
:alt: Reorder batch samples

**Figure 5: Reorder batch samples**. Click and drag on the samples to change order.
:::

---

### 3. First Codebook

After creating a batch, the Expert writes the initial annotation guidelines (Codebook):

1. Click **Open** in the Codebook card on the project dashboard, or on **Codebook** on the menu on the left side of the page.
2. Click **Edit**, enter the initial guideline instructions, write an explanatory rationale, and click on **Save changes**.

:::{figure} screenshots/expert_first_codebook.png
:width: 650px
:align: center
:alt: Initial Codebook Editor

**Figure 7: Initial Codebook Setup**. Editor interface where Experts input first instructions and save the first version of the Codebook.
:::

---

### 4. Resolve Disagreements and Edit the Codebook

When annotators complete peer discussion without reaching consensus on a sample, the batch moves to the _Expert decision_ phase.

1. Click **Resolve disagreements** on the batch card to open the adjudication panel.
2. Review the sample text, individual annotator labels, and the Annotators chat transcript.
3. Select the final adjudicated label for the sample and click on **Save and next case**.
4. Edit the Codebook instructions in the right-hand panel to address the underlying underspecification (e.g., adding an edge case rule).
5. Enter a detailed rationale explaining your decision and click **Save draft**.

:::{figure} screenshots/expert_resolve.png
:width: 650px
:align: center
:alt: Unresolved Disagreements Alert

**Figure 8: Unresolved Disagreement Alert**. Batch dashboard card indicating cases needing expert adjudication via the "Resolve disagreements" button.
:::

:::{figure} screenshots/expert_codebook_editing.png
:width: 650px
:align: center
:alt: Expert Adjudication Interface

**Figure 9: Expert Adjudication & Codebook Revision Interface**. Comprehensive panel displaying sample text, annotator labels, chat history, final label selection, Codebook editing, and rationale logging.
:::

---

### 5. Export Batch Data After Annotation and Discussion

When all annotations, discussions, and expert adjudications for a batch are complete:

- Click **...** and **Export batch** on an individual batch card to download its final labels, discussion transcripts, and revision history.
- Click **Export Project** at the top right of the project page to download the complete dataset and full Git-backed audit trail for the entire project.
- Both exports are JSON Lines files with one sample per line. The extra columns of the uploaded file appear under `metadata`, e.g. `"metadata": {"id": 4711, "source": "twitter"}`.

:::{figure} screenshots/expert_export_project.png
:width: 650px
:align: center
:alt: Export Project Dashboard

**Figure 10: Data Export**. Project dashboard view offering individual batch or full project data export options.
:::

---

## Annotator User Guide

The Annotator role focuses on independent labeling, peer discussion of conflicting samples, and staying synchronized with evolving Codebook guidelines.

### Project Dashboard View

When logging in, Annotators see a summary of all assigned projects, active batches, and current phase statuses. Batches in _Discussion_ phase are highlited and displayed first.

:::{figure} screenshots/annotator_start.png
:width: 650px
:align: center
:alt: Annotator Home Dashboard

**Figure 11: Annotator Home Dashboard**. Overview of assigned projects, active batches, and current phase indicator.
:::

---

### 1. First Batch Overview & Codebook View

Clicking on a project opens the project view:

- **Start Annotating** (Batch section): Opens the labeling interface for the assigned batch.
- **Open** (Codebook section): Opens the current annotation guidelines.
- **Codebook Changes** (Batch section): Displays the codebook view showing newly added rules since the previous batch.

:::{figure} screenshots/annotator_first_batch_overview.png
:width: 650px
:align: center
:alt: Annotator Batch Overview

**Figure 12: Annotator Batch Overview Card**. Displaying assigned samples for the current project, codebook and action buttons.
:::

---

### 2. Annotation Phase

In the Annotation phase, annotators label each sample independently:

1. Read the presented text sample.
2. Click the appropriate candidate label button and save to move to the next sample (or use custom keyboard shortcuts).
3. Navigate through samples using arrow buttons or keyboard shortcuts.
4. When all samples for the current batch are annotated, you can either check and change your labels by clicking on **Review my labels** or lock in your annotations for the current batch by clicking on **Finalize annotation**. When all annotators have finalized, the batch moves to the _Discussion_ phase in case of disagreements.

You can click on the **Codebook** button anytime to display the annotation guidelines next to the sample you're annotating.

:::{figure} screenshots/annotator_annotation_interface.png
:width: 550px
:align: center
:alt: Independent Annotation Screen

**Figure 14: Annotation Interface**. Single-sample labeling screen with progress bar, label selection buttons, and navigation controls.
:::

:::{figure} screenshots/annotator_finalize_annotation.png
:width: 550px
:align: center
:alt: Finalize Batch Screen

**Figure 15: Finalize Batch**. Completion prompt displayed when all samples in a batch have been labeled.
:::

#### Keyboard Shortcuts

The annotation interface supports hotkeys for rapid labeling and navigation:

- **Left Arrow Key (←)**: Move to the previous sample.
- **Right Arrow Key (→)**: Move to the next sample.
- **Enter Key (↵)**: Save annotation.
- **Custom Hotkeys**: Custom key bindings defined during project setup.

---

### 3. Peer Discussion Phase

When independent annotation is complete and label mismatches exist between annotators, the batch moves to the _Discussion_ phase.

1. Click **Join Discussion** on the batch card.
2. The split-screen discussion interface displays:
   - Left Panel: The sample text, labels before discussion, label choice after discussion.
   - Right Panel: A real-time chat window.
3. Discuss the sample with your peer, writing messages in the designated box at the bottom-right corner of the page.
4. If you reach consensus, update your label selections. If you remain in disagreement, leave the conflicting labels as-is to escalate the sample to the Expert. Click **Save my label**.

:::{figure} screenshots/annotator_start_discussion.png
:width: 550px
:align: center
:alt: Start Discussion Alert

**Figure 16: Peer Discussion Open**. Batch card notifying annotators that independent labeling is complete and peer discussion is open.
:::

:::{figure} screenshots/annotator_discussion_interface.png
:width: 650px
:align: center
:alt: Real-Time Chat Discussion Interface

**Figure 17: Real-Time Peer Discussion Interface**. Split-screen workspace showing conflicting label choices, connection status, and live chat messaging.
:::

---

### 4. View Codebook After Update

When the Expert adjudicates an escalated sample and updates the guidelines:

1. In the project page, click **Codebook changes** in the new batch section.
2. The Codebook view highlights all newly added or modified rules in highlighted format.

:::{figure} screenshots/annotator_open_codebook_changes.png
:width: 550px
:align: center
:alt: Codebook Update

**Figure 18: Codebook Update**. Click on codebook changes button on new batch card to see updates in the codebook.
:::

:::{figure} screenshots/annotator_codebook_view_edited.png
:width: 650px
:align: center
:alt: Diff-Highlighted Codebook View

**Figure 19: Highlighted Codebook Edits View**. Updated guideline screen with edits highlighted.
:::

---

## Admin User Guide

Administrators manage system deployment, user account creation, user group assignments, and Django permissions. Access the admin interface at `/admin` using administrator credentials.

### 1. Admin Homepage

Log in at `http://<your-server-ip>/admin`. The dashboard provides quick access to User and Group management, along with a log of recent administrative actions.

:::{figure} screenshots/admin.png
:width: 650px
:align: center
:alt: Django Admin Homepage

**Figure 20: Django Administration Homepage**. Central management portal for site administration, user accounts, and system logs.
:::

---

### 2. Add Users

To register new Annotators or Experts:

1. Under **Users**, click **+ Add**.
2. Enter a unique username and password.
3. Click **Save** to create the user account.

:::{figure} screenshots/admin_add_user.png
:width: 650px
:align: center
:alt: Add User Form

**Figure 21: User Registration Form**. Admin form for creating new user credentials.
:::

---

### 3. Manage User Groups

Organize users into functional groups to streamline role assignments:

1. Navigate to **Groups** under Authentication and Authorization.
2. Use the dual-list selector to assign users to specific system groups (e.g., Annotators, Experts).

:::{figure} screenshots/admin_user_groups.png
:width: 650px
:align: center
:alt: User Group Assignment

**Figure 22: User Group Management**. Interface for assigning users to designated functional groups.
:::

---

### 4. Manage User Permissions

Fine-tune model-level access rights for specific accounts or groups:

1. Open a user account profile in the admin portal.
2. In the **User permissions** section, select specific Django model permissions (e.g., `Expert | codebook draft | Can add codebook draft`, `Projects | batch | Can add batch`).
3. Click **Save** to enforce permission settings.

:::{figure} screenshots/admin_user_permissions.png
:width: 650px
:align: center
:alt: User Permissions Selector

**Figure 23: Fine-Grained User Permissions**. Selector panel for assigning specific system and model permissions to user profiles.
:::
