# Arbiter

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
<!-- PLACEHOLDER: Docker badge, couldn't find the link -->
<!-- PLACEHOLDER: JOSS / DOI badge in the future -->


**Arbiter** is an open-source, collaborative web application for data annotation that treats
disagreement as useful information to use during the annotation process rather than noise to resolve post-hoc. Annotators label data in batches, discuss conflicting labels in a real-time chat, and pass unresolved cases to an expert who decides the
final label and revises the annotation guidelines (the _codebook_). Every label, discussion, and codebook revision is logged, so the evolution of the team's shared understanding of the task is documented alongside the dataset.


<!-- PLACEHOLDER: GIF of the workflow using screenshots from user doc?-->

## Why Arbiter?

Low inter-annotator agreement in subjective or complex tasks usually has one of two causes:

1. **Task underspecification:** the annotation guidelines are too generic, leaving the space for personal interpretation, especially for edge cases.
2. **Misapplication:** annotators misunderstand or wrongly apply the guidelines.

Post-hoc statistical methods model disagreement after the data has been collected. 
Arbiter addresses it **during** annotation: misapplication is resolved by synchronous discussion between
annotators, underspecification by expert adjudication and in-tool codebook revisions.

## Workflow

![Arbiter workflow](docs/usage/screenshots/workflow_diagram.png)

1. **Setup:** an expert creates a project (labels, annotators, experts), writes the first
   codebook and uploads the first batch of data.
2. **Annotation:** annotators label the batch independently.
3. **Discussion:** samples with diverging labels enter a real-time chat between annotators. If
   they agree, the labels are updated; otherwise the sample is escalated to the expert.
4. **Expert decision:** the expert chooses the final label for escalated samples and, where
   needed, updates the codebook.
5. **Codebook synchronisation:** before the next batch, annotators read the codebook with all
   changes highlighted. The cycle repeats until the team has converged to a shared understanding of the guidelines.
6. **Export:** the annotated data, discussions, and codebook history are exported.

## Key features

**Experts**

- Create projects with custom labels and assign annotators and experts
- Upload data in batches as CSV or XLSX (a `text` column is required; all other columns are kept as sample metadata)
- Review annotator labels and chat transcripts, set the final label and record a rationale
- Edit the codebook
- Export a single batch or the whole project as JSON files, including discussions and revision history

**Annotators**

- Label samples independently
- Discuss disagreements with peers in a real-time chat
- See what changed in the codebook since the previous batch

**Administrators**

- Manage user accounts, groups and permissions through the Django admin interface

## Installation and quick start

Arbiter runs as a set of Docker containers (web app, Vite, PostgreSQL, Redis). 

[Get Docker](https://docs.docker.com/get-docker/).

To get the code run:
```bash
git clone https://github.com/luerhard/arbiter.git
cd arbiter
```
More information in the [guide for devs](docs/dev/index.md).

## Documentation

Documentation is built with Sphinx and published at **<https://luerhard.github.io/arbiter>**:

- **User guide** (experts, annotators, administrators): [`docs/usage`](docs/usage/index.md)
- **Developer guide** (setup, tests, debugging, architecture): [`docs/dev`](docs/dev/index.md)
<!-- - **API reference** (generated from the docstrings with Sphinx autodoc): [`docs/api`](docs/api/index.md) -->

## Tests

Tests are run automatically with GitHub Actions on every push and pull request to `main`.
To run them yourself, see the [developer guide](docs/dev/index.md#run-tests).

## Contributing

Contributions are welcome! 
Complete guide for contributions: [Contributing Guidelines](CONTRIBUTING.md)

## Citation

If you use Arbiter in your research, please cite:

```bibtex
@article{PLACEHOLDER_arbiter,
  title   = {PLACEHOLDER},
  author  = {PLACEHOLDER},
  journal = {PLACEHOLDER},
  year    = {PLACEHOLDER},
  doi     = {PLACEHOLDER}
}
```


## License

Arbiter is released under the [MIT License](LICENSE).

## Acknowledgements



## Contact

Bugs and feature requests: [GitHub Issues](https://github.com/luerhard/arbiter/issues).
