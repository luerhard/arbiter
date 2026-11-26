# How Arbiter works

The [start page](../index.md) gives the short version: annotate, discuss, decide, revise the codebook, batch after batch. This page explains the parts in more detail: who does what, how a batch moves from one phase to the next, and what Arbiter keeps a record of.

## Roles

Everyone has an account on the Arbiter server. What they can do in a project depends on their role in it:

- **Annotators** label the texts, discuss the ones they disagree on, and read the codebook changes before each new batch.
- **Experts** lead the project. They upload the batches, write and revise the codebook, decide the texts the annotators could not agree on, and export the results.
- **Administrators** manage the user accounts of the server in its admin area. They take no part in projects through this role.

Roles belong to a project: the same person can annotate in one project and be the expert in another. Whoever creates a project chooses its annotators and experts, and when uploading a batch, which of them work on it.

## The phases of a batch

A project's texts are annotated in batches. Each batch goes through up to four phases, and moves on by itself once a phase is done:

| Phase               | Who        | What happens                                                                                                                                                | Moves on when                                           |
| ------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| **Annotation**      | annotators | Each annotator labels every text of the batch, without seeing the others' labels.                                                                           | every annotator has clicked **Finalize my annotations** |
| **Discussion**      | annotators | The texts the annotators labeled differently are discussed in a chat, one text at a time. After talking it through, each annotator saves their label again. | every text has been discussed                           |
| **Expert decision** | experts    | For the texts still labeled differently, an expert sets the final label, writes down the reason and, where needed, revises the codebook.                    | the expert has decided every text                       |
| **Finalized**       | –          | The batch is done and can be exported.                                                                                                                      | –                                                       |

A phase with nothing to do is skipped: if the annotators agree on every text, the batch goes from annotation straight to finalized; if the discussion settles every disagreement, there is no expert decision. Everyone in the batch gets a notification when it changes phase. Experts can also move a batch to another phase by hand, for example to give the annotators a second round.

The discussion starts once all annotators of the batch have the discussion page open, so they need to arrange a time for it.

### When annotators disagree

What counts as a disagreement depends on the kind of project:

- **Labels for the whole text:** the annotators did not choose the same labels.
- **Spans in the text:** the annotators did not mark exactly the same passages with the same labels.

A text that one of the annotators has not labeled yet also counts as a disagreement.

## The codebook

The codebook holds the annotation guidelines of a project, written in [Markdown](https://commonmark.org/help/). Annotators can open it next to every text they label or discuss.

Only experts change the codebook: freely in the codebook editor, or together with a decision, as the reason for it. Every change is saved as a new version with its reason. When a batch starts, Arbiter notes which version it starts with, so annotators can see what has changed since their previous batch, and everyone can compare any two versions.

## What Arbiter records

The labels of a later phase never replace those of an earlier one. For every text, Arbiter keeps each annotator's labels from the annotation phase, their labels after the discussion, the discussion chat and the expert's decision. For the project, it keeps every version of the codebook together with the reason for each change, including the reasons the experts gave for their decisions.

Experts can export both: the texts with all their labels and the chat as a data file, and the codebook with its complete history. A dataset can so be handed on together with the record of how its labels came about.
