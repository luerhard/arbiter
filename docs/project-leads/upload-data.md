# Upload data

Once a project is created, data samples must be grouped and uploaded in batches:

1. Navigate to the project dashboard and click **New Batch** at the top of the page.
2. In the batch upload page, select a dataset file (`CSV` or `XLSX` containing a `text` column) and select the designated annotators and experts for that batch.
   Every other column (for example an `id`, the source or a date) is kept as metadata of the sample and included in the exports, so you can join the labels back to your data.
   Every row needs a text; the upload is rejected and names the rows that are empty.
   Put each piece of metadata in its own column, and save files from pandas with `df.to_csv(..., index=False)`; otherwise the row index is stored as an extra column called `Unnamed: 0`.
3. Upon upload, the new batch appears in the project's **Batches** list in **Annotation** mode.

:::{figure} ../screenshots/expert_upload_first_batch.png
:width: 550px
:align: center
:alt: Empty Project Dashboard

**Figure 4: Initial Project Dashboard**. Dashboard view before uploading dataset batches.
:::

:::{figure} ../screenshots/expert_create_first_batch.png
:width: 550px
:align: center
:alt: Create Batch Page

**Figure 5: Batch Creation Page**. Uploading a dataset file and assigning specific annotators and experts to the batch.
:::

:::{figure} ../screenshots/expert_batch_uploaded.png
:width: 650px
:align: center
:alt: Active Batch Overview

**Figure 6: Active Batch Dashboard**. Overview card displaying Batch 1 in the _Annotation_ phase, showing real-time annotation progress per user.
:::

## 2.1 Reorder samples within a batch

Once a batch is uploaded, it's possible to reorder the samples within that batch by clicking on "Batch #" (e.g., **Batch 1**) in the batch overview card. Once the samples view is open, click on the button at the left side of each sample row and drag it to change order.

:::{figure} ../screenshots/expert_reorder_samples.png
:width: 650px
:align: center
:alt: Reorder batch samples

**Figure 5: Reorder batch samples**. Click and drag on the samples to change order.
:::
