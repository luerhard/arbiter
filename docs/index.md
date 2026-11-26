# Arbiter

**Arbiter** is an open-source web application for annotating text in a team. It treats disagreement between annotators as information to act on while the annotation is running, not as noise to clean up afterwards.

Annotators label the data in batches. Where their labels differ, they discuss the sample in a real-time chat. What they cannot settle goes to an expert, who decides the final label and revises the annotation guidelines, the _codebook_. Every label, discussion, decision and codebook change is recorded, so the dataset comes with a record of how the team's understanding of the task developed.

## Why Arbiter?

Low agreement between annotators in subjective or complex tasks usually has one of two causes:

1. **The task is underspecified:** the codebook leaves room for interpretation, especially in edge cases.
2. **The codebook is misapplied:** annotators misunderstand a rule or apply it wrongly.

Statistical methods deal with disagreement after the data has been collected. Arbiter deals with it **during** annotation: misapplication is cleared up in the discussion between annotators, underspecification by the expert's decision and a revised codebook.

## How it works

:::{figure} screenshots/workflow_diagram.png
:width: 420px
:align: center
:alt: The Arbiter workflow: annotation, discussion, expert decision and codebook revision, batch after batch
:::

1. **Set up:** an expert creates a project with its labels and team, writes the first codebook and uploads the first batch of texts.
2. **Annotate:** the annotators label the batch, each on their own.
3. **Discuss:** texts with diverging labels go to a real-time chat between the annotators. If they agree, their labels are updated; if not, the text goes to the expert.
4. **Decide:** the expert sets the final label for these texts, gives a reason and, where needed, revises the codebook.
5. **Catch up:** before the next batch, the annotators read the codebook with the changes highlighted. Then the cycle starts again.
6. **Export:** labels, discussions, decisions and the codebook history can be exported per batch or for the whole project.

Batch after batch, there is less to discuss and the codebook changes less: the team has arrived at a shared understanding of the task.

## What you can annotate

Arbiter works with texts, uploaded as a CSV or Excel file with one text per row. A project is one of two kinds:

- **Labels for the whole text:** annotators choose the labels that apply to each text.
- **Spans in the text:** annotators mark passages in each text and label them.

## Where to start

- **You annotate or lead a project** on a running Arbiter: start with [how Arbiter works](get-started/how-it-works.md), then read the guide [for annotators](annotators/annotate.md) or [for project leads](project-leads/create-project.md).
- **You want to run Arbiter yourself or work on its code:** the [guide for developers](dev/index.md) covers installation, tests and the structure of the code; the [API documentation](api/index.md) describes the modules.

The source code is on [GitHub](https://github.com/luerhard/arbiter). Bugs and feature requests go to the [issue tracker](https://github.com/luerhard/arbiter/issues).

## License and funding

Arbiter is released under the [MIT License](https://github.com/luerhard/arbiter/blob/main/LICENSE). Its development was funded by the State Ministry of Science, Research and the Arts Baden-Württemberg (grant number Az.MWK11-0430.0-1/7/5).

```{toctree}
:hidden:
:caption: Get started

get-started/how-it-works.md
get-started/sign-in.md
```

```{toctree}
:hidden:
:caption: For annotators

annotators/annotate.md
annotators/discuss.md
annotators/codebook-changes.md
```

```{toctree}
:hidden:
:caption: For project leads

project-leads/create-project.md
project-leads/upload-data.md
project-leads/codebook.md
project-leads/decide.md
project-leads/export.md
```

```{toctree}
:hidden:
:caption: Administration

admin/users.md
```

```{toctree}
:hidden:
:caption: Developers

dev/index.md
api/index.md
```
