"""Demo data for the screenshots in the documentation: three people and two projects. The
texts are made up; no real party, politician or commenter.

Each project has one batch in progress, as in real work. In "Populist Communication" a first
batch is finished, and --stage sets how far the second has got (annotation, discussion,
expert, final), so every page of the documentation can be shown with a state that occurs.

Run it again to start over: it replaces the demo projects and resets the demo accounts.
It leaves everything else in the database alone. Labels, finalizing and the expert's
decisions go through the real views, so the result is what the app itself would store; only
the discussion, which runs over a websocket, is written directly.
"""

from datetime import timedelta
import json

from codebook.models import Codebook
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from notifications.models import Notification

from data.models import Example
from data.models import ExampleAssignment
from data.models import Label
from data.models import label_color
from discuss.models import Message
from discuss.models import Room
from projects.models import Batch
from projects.models import BatchPhase
from projects.models import Project
from projects.models import ProjectRole

PASSWORD = "demo"  # noqa: S105
PEOPLE = {
    # username: (first name, last name, email)
    "anna.berger": ("Anna", "Berger", "anna.berger@example.org"),
    "tom.keller": ("Tom", "Keller", "tom.keller@example.org"),
    "lena.hoffmann": ("Lena", "Hoffmann", "lena.hoffmann@example.org"),
}
ANNOTATORS = ["anna.berger", "tom.keller"]
EXPERTS = ["lena.hoffmann"]

CLASSIFICATION = "Populist Communication"
SPANS = "Offensive Language"
STAGES = ["annotation", "discussion", "expert", "final"]

# --- the classification project ---------------------------------------------------------
# Labels by letter: A Anti-elitism, P People-centrism, S Popular sovereignty
LABELS = {"A": "Anti-elitism", "P": "People-centrism", "S": "Popular sovereignty"}

CODEBOOK_V1 = """\
# Populist communication

We code short statements of parties and politicians: social media posts, press releases and
excerpts from speeches. A statement can express none, one or several of the three core ideas
of populism. Code what the statement says, not what you know about the party behind it.

## Anti-elitism

The statement presents an elite as a group that is out of touch with ordinary people, works
against them or has betrayed them. Elites can be politicians as a class, "the establishment",
the media, banks and corporations, or institutions such as the EU.

- Code: "The political class has betrayed the nation for decades."
- Do not code: criticism of a single decision or person, without an elite as a group behind it.
  "The minister's plan is far too expensive."

## People-centrism

The statement speaks of "the people" as one group with shared, legitimate interests that
deserve to be put first: hard-working families, ordinary citizens, the silent majority.

- Code: "Hard-working families keep this country running."
- Do not code: citizens mentioned as the addressees of a service. "Citizens can renew their
  passports online."

## Popular sovereignty

The statement demands that the people themselves decide, instead of parliaments, courts or
other institutions: referendums, "taking back control", the will of the people as the final word.

- Code: "Let the people vote on the energy transition!"

## No label

Factual announcements and policy proposals without any of the three ideas get no label.
"""

CODEBOOK_V2 = CODEBOOK_V1.replace(
    """\
- Do not code: criticism of a single decision or person, without an elite as a group behind it.
  "The minister's plan is far too expensive."
""",
    """\
- Do not code: criticism of a single decision or person, without an elite as a group behind it.
  "The minister's plan is far too expensive."
- Experts and scientists count as an elite when the statement sets them as a group against
  ordinary people: "The so-called experts got it wrong again, ordinary citizens knew better."
  Disagreeing with a single study or expert does not count.
""",
)

CODEBOOK_V2_RATIONALE = (
    "Anna and Tom disagreed whether attacking 'the so-called experts' is anti-elitism. It is: "
    "the statement sets the experts as a group against ordinary citizens. Added this to the "
    "rule, together with where it ends."
)

# One entry per text: (text, metadata, Anna's labels, Tom's labels).
# Batch 1 is finalized: discussed, and decided by the expert where still needed.
BATCH_1 = [
    (
        "The political class in the capital has betrayed this nation for decades. Enough is "
        "enough.",
        {"doc_id": "PC-001", "party": "Party A", "medium": "social media", "date": "2024-03-04"},
        "A",
        "A",
    ),
    (
        "Hard-working families keep this country running, and it is time they were heard.",
        {"doc_id": "PC-002", "party": "Party C", "medium": "social media", "date": "2024-03-04"},
        "P",
        "P",
    ),
    (
        "From Monday, citizens can renew their passports online.",
        {"doc_id": "PC-003", "party": "Party B", "medium": "press release", "date": "2024-03-05"},
        "",
        "",
    ),
    (
        "The so-called experts got it wrong again – ordinary citizens knew better all along.",
        {"doc_id": "PC-004", "party": "Party A", "medium": "social media", "date": "2024-03-06"},
        "AP",
        "P",
    ),
    (
        "The people should decide on this treaty in a referendum, not a handful of MPs behind "
        "closed doors.",
        {"doc_id": "PC-005", "party": "Party C", "medium": "speech", "date": "2024-03-07"},
        "AS",
        "S",
    ),
    (
        "Our new childcare plan will create 20,000 places by next year.",
        {"doc_id": "PC-006", "party": "Party B", "medium": "press release", "date": "2024-03-08"},
        "",
        "",
    ),
    (
        "The big banks write the rules and the politicians sign them. We will end this.",
        {"doc_id": "PC-007", "party": "Party A", "medium": "speech", "date": "2024-03-08"},
        "A",
        "A",
    ),
    (
        "This government listens to lobbyists, not to you.",
        {"doc_id": "PC-008", "party": "Party C", "medium": "social media", "date": "2024-03-09"},
        "AP",
        "A",
    ),
    (
        "We thank all volunteers who helped after the floods last week.",
        {"doc_id": "PC-009", "party": "Party B", "medium": "social media", "date": "2024-03-11"},
        "",
        "",
    ),
    (
        "Only the people can give this government its mandate – and only the people can take "
        "it away.",
        {"doc_id": "PC-010", "party": "Party A", "medium": "speech", "date": "2024-03-12"},
        "S",
        "PS",
    ),
]

# Batch 2 is the one in progress; --stage says how far it has got. In the annotation stage
# Tom is through and Anna has labeled the first ANNA_DONE texts.
ANNA_DONE = 3
BATCH_2 = [
    (
        "Unelected judges in Strasbourg must not overrule the will of our voters.",
        {"doc_id": "PC-011", "party": "Party A", "medium": "social media", "date": "2024-04-02"},
        "AS",
        "S",
    ),
    (
        "The minister's plan for the new motorway is far too expensive.",
        {"doc_id": "PC-012", "party": "Party B", "medium": "press release", "date": "2024-04-02"},
        "A",
        "",
    ),
    (
        "Ordinary people have had enough of being told what to think.",
        {"doc_id": "PC-013", "party": "Party C", "medium": "social media", "date": "2024-04-03"},
        "P",
        "AP",
    ),
    (
        "Party B presents its programme for the regional election on Saturday.",
        {"doc_id": "PC-014", "party": "Party B", "medium": "press release", "date": "2024-04-04"},
        "",
        "",
    ),
    (
        "Let the people vote on the energy transition!",
        {"doc_id": "PC-015", "party": "Party C", "medium": "social media", "date": "2024-04-05"},
        "S",
        "S",
    ),
    (
        "The media establishment despises everyone who lives outside the big cities.",
        {"doc_id": "PC-016", "party": "Party A", "medium": "speech", "date": "2024-04-05"},
        "AP",
        "AP",
    ),
    (
        "We will defend the will of the people against a parliament that no longer represents it.",
        {"doc_id": "PC-017", "party": "Party A", "medium": "speech", "date": "2024-04-08"},
        "PS",
        "APS",
    ),
    (
        "Unemployment fell by 0.3 percent in the last quarter.",
        {"doc_id": "PC-018", "party": "Party B", "medium": "social media", "date": "2024-04-09"},
        "",
        "",
    ),
    (
        "They call us extremists because we say what everyone thinks.",
        {"doc_id": "PC-019", "party": "Party C", "medium": "social media", "date": "2024-04-10"},
        "AP",
        "P",
    ),
    (
        "Real democracy means the people decide, not bureaucrats in Brussels.",
        {"doc_id": "PC-020", "party": "Party A", "medium": "social media", "date": "2024-04-11"},
        "APS",
        "AS",
    ),
]

# The discussions: doc_id -> (chat, labels both save afterwards; None: they still disagree)
DISCUSSIONS = {
    "PC-004": (
        [
            ("tom.keller", "I only saw people-centrism here: 'ordinary citizens knew better'."),
            (
                "anna.berger",
                "But 'the so-called experts' is an attack on a group, not on one study.",
            ),
            ("tom.keller", "Experts aren't in the list of elites in the codebook though."),
            ("anna.berger", "True. Let's leave it to Lena, the codebook should say it."),
        ],
        None,
    ),
    "PC-005": (
        [
            (
                "anna.berger",
                "'a handful of MPs behind closed doors' – I read that as anti-elitism.",
            ),
            ("tom.keller", "Fair, it is more than criticising one decision. I'll add it."),
        ],
        "AS",
    ),
    "PC-008": (
        [
            ("tom.keller", "Where is the people-centrism? 'you' is just the reader."),
            ("anna.berger", "Hm, there's no 'the people' as a group. You're right, only A."),
        ],
        "A",
    ),
    "PC-010": (
        [
            ("anna.berger", "This is about who decides, so sovereignty. Why P as well?"),
            ("tom.keller", "'only the people' – the people as the one legitimate group."),
            ("anna.berger", "I still think that is part of the sovereignty claim."),
        ],
        None,
    ),
    "PC-011": (
        [
            ("anna.berger", "'Unelected judges' sounds like an elite to me."),
            ("tom.keller", "It's a court, an institution. The point is who decides."),
            ("anna.berger", "We won't agree on this one, let's pass it on."),
        ],
        None,
    ),
    "PC-012": (
        [
            ("tom.keller", "This is one plan of one minister, the codebook says not to code that."),
            ("anna.berger", "You're right, I'll remove it."),
        ],
        "",
    ),
    "PC-013": (
        [
            ("tom.keller", "Who tells them what to think? Sounds like the media or politicians."),
            ("anna.berger", "But they are not named. I wouldn't code A without a group."),
        ],
        None,
    ),
    "PC-017": (
        [
            (
                "tom.keller",
                "'a parliament that no longer represents it' – that's anti-elitism too.",
            ),
            ("anna.berger", "Or is it only about who decides? Not sure."),
        ],
        None,
    ),
    "PC-019": (
        [
            ("anna.berger", "'They' call us extremists – they are the elite here, I'd say."),
            ("tom.keller", "Ok, makes sense, I'll add A."),
        ],
        "AP",
    ),
    "PC-020": (
        [
            ("tom.keller", "I don't see people-centrism, 'the people' is the one who decides."),
            ("anna.berger", "Agreed, that's sovereignty. Taking P out."),
        ],
        "AS",
    ),
}

# The expert's decisions (doc_id -> labels, codebook change or None); batch 2's are only
# made in the final stage
DECISIONS = {
    "PC-004": ("AP", (CODEBOOK_V2, CODEBOOK_V2_RATIONALE)),
    "PC-010": ("PS", None),
    "PC-011": ("S", None),
    "PC-013": ("P", None),
    "PC-017": ("APS", None),
}

# --- the span project: offensive language ---------------------------------------------------
SPAN_LABELS = ["Insult", "Threat", "Profanity"]
SPAN_CODEBOOK = """\
# Offensive language in reader comments

We annotate the comments under local news articles. Mark every passage that is offensive and
give it one of the labels below. A passage covers the words that carry the offence, usually a
word or a short phrase, not the whole sentence. Harsh criticism of a decision is not offensive
in itself.

## Insult

Words that degrade a person or a group: name-calling, mockery of their intelligence or worth.

- Mark: "Only a complete **idiot** would build this."

## Threat

An announcement, open or veiled, that someone will come to harm.

- Mark: "**Someone will pay you a visit.**"

## Profanity

Vulgar or obscene words that are not aimed at anyone.

- Mark: "Another **damn** construction site."
"""
COMMENTS = [
    (
        "Only a complete idiot would put a bike lane on Main Street. What a damn mess. Whoever "
        "planned this had better watch out on their way home.",
        {"comment_id": "C-101", "article": "Bike lanes on Main Street", "date": "2024-09-02"},
    ),
    (
        "Great, another damn construction site right in front of my house. Thanks for nothing.",
        {"comment_id": "C-102", "article": "Bike lanes on Main Street", "date": "2024-09-02"},
    ),
    (
        "I disagree with the council's decision, but I can see why they made it.",
        {"comment_id": "C-103", "article": "Bike lanes on Main Street", "date": "2024-09-03"},
    ),
    (
        "Keep talking like that and someone will pay you a visit. You have been warned.",
        {"comment_id": "C-104", "article": "Council vote on parking fees", "date": "2024-09-05"},
    ),
    (
        "People like you are the reason this town is going down the drain, you clown.",
        {"comment_id": "C-105", "article": "Council vote on parking fees", "date": "2024-09-05"},
    ),
    (
        "This is a load of crap and you know it. Show your face at the next meeting and we will "
        "see how brave you are.",
        {"comment_id": "C-106", "article": "Council vote on parking fees", "date": "2024-09-06"},
    ),
]

# What Anna and Tom marked in each comment, (label, passage) by comment_id; from the
# discussion stage on, the comments are annotated and the batch is in its discussion.
# They disagree on where an insult or a threat starts and ends, and whether C-106 threatens.
COMMENT_SPANS = {
    "C-101": (
        [
            ("Insult", "complete idiot"),
            ("Profanity", "damn"),
            ("Threat", "had better watch out on their way home."),
        ],
        [
            ("Insult", "idiot"),
            ("Profanity", "damn"),
            ("Threat", "had better watch out on their way home."),
        ],
    ),
    "C-102": ([("Profanity", "damn")], [("Profanity", "damn")]),
    "C-103": ([], []),
    "C-104": (
        [("Threat", "someone will pay you a visit.")],
        [
            (
                "Threat",
                "Keep talking like that and someone will pay you a visit. You have been warned.",
            )
        ],
    ),
    "C-105": (
        [("Insult", "People like you are the reason"), ("Insult", "you clown.")],
        [("Insult", "you clown.")],
    ),
    "C-106": (
        [
            ("Profanity", "crap"),
            ("Threat", "Show your face at the next meeting and we will see how brave you are."),
        ],
        [("Profanity", "crap")],
    ),
}


class Command(BaseCommand):
    help = "Create the demo accounts and projects for the documentation's screenshots"

    def add_arguments(self, parser):
        parser.add_argument(
            "--stage",
            choices=STAGES,
            default="annotation",
            help="how far the second batch of the populism project has got; from "
            "discussion on, the offensive language batch is in its discussion too",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        self.users = self._people()
        Project.objects.filter(name__in=[CLASSIFICATION, SPANS]).delete()

        self._classification_project(options["stage"])
        self._span_project(options["stage"])
        # the phase changes above notified everyone; start without unread toasts
        Notification.objects.filter(user__in=self.users.values(), read_at__isnull=True).update(
            read_at=timezone.now(),
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data created. Sign in as {', '.join(PEOPLE)} with the password "
                f"'{PASSWORD}'.",
            ),
        )

    # --- helpers --------------------------------------------------------------------------

    def _people(self):
        User = get_user_model()  # noqa: N806
        users = {}
        for username, (first, last, email) in PEOPLE.items():
            user, _ = User.objects.get_or_create(username=username)
            user.first_name, user.last_name, user.email = first, last, email
            user.set_password(PASSWORD)
            user.save()
            users[username] = user
        return users

    def _client(self, username):
        client = Client(HTTP_HOST="localhost")
        client.force_login(self.users[username])
        return client

    def _project(self, name, description, labels, project_type):
        project = Project.objects.create(
            name=name,
            description=description,
            owner=self.users[EXPERTS[0]],
            project_type=project_type,
            show_metadata_in_annotation=True,
        )
        for username in ANNOTATORS:
            project.users.add(
                self.users[username],
                through_defaults={"default_role": ProjectRole.ANNOTATOR},
            )
        for username in EXPERTS:
            project.users.add(
                self.users[username],
                through_defaults={"default_role": ProjectRole.EXPERT},
            )
        for i, label in enumerate(labels):
            Label.objects.create(
                project=project,
                name=label,
                color=label_color(i),
                hotkey=str(i + 1),
            )
        return project

    def _batch(self, project, rows):
        """A new batch as an upload creates it: examples, team, annotation phase."""
        batch = Batch.objects.create(project=project)
        Example.objects.bulk_create(
            Example(batch=batch, content=text, metadata=metadata, position=position)
            for position, (text, metadata, *_) in enumerate(rows, start=1)
        )
        batch.users.add(
            *(self.users[u] for u in ANNOTATORS),
            through_defaults={"role": ProjectRole.ANNOTATOR},
        )
        batch.users.add(
            *(self.users[u] for u in EXPERTS),
            through_defaults={"role": ProjectRole.EXPERT},
        )
        batch.set_phase(BatchPhase.ANNOTATION)
        return batch

    def _label_ids(self, project, letters):
        names = [LABELS[letter] for letter in letters]
        return list(project.labels.filter(name__in=names).values_list("id", flat=True))

    def _assignments(self, batch, username, phase):
        return ExampleAssignment.objects.filter(
            batch=batch,
            user=self.users[username],
            phase=phase,
        ).select_related("example")

    def _annotate(self, batch, rows, finalize, first_annotator_done=None):
        """Each annotator saves their labels on the annotation page and, if asked, finalizes.
        first_annotator_done: the first annotator only labels that many texts."""
        by_doc = {metadata["doc_id"]: (anna, tom) for _, metadata, anna, tom in rows}
        for index, username in enumerate(ANNOTATORS):
            client = self._client(username)
            for assignment in self._assignments(batch, username, BatchPhase.ANNOTATION):
                if index == 0 and first_annotator_done and assignment.order > first_annotator_done:
                    continue
                letters = by_doc[assignment.example.metadata["doc_id"]][index]
                url = reverse("annotate-assignment", args=(batch.id, assignment.id))
                client.post(url, {"labels": self._label_ids(batch.project, letters)})
            if finalize:
                client.post(reverse("annotate-done", args=(batch.id,)))
        batch.refresh_from_db()

    def _write_codebook(self, project, content, rationale):
        """The expert writes the codebook in the codebook editor."""
        codebook = Codebook.objects.get(project=project)
        self._client(EXPERTS[0]).post(
            reverse("codebook-edit", args=(codebook.pk,)),
            {"content": content, "rationale": rationale, "modified": "on"},
        )

    def _annotate_spans(self, batch):
        """Both annotators mark their passages (COMMENT_SPANS) and finalize."""
        labels = dict(batch.project.labels.values_list("name", "id"))
        for index, username in enumerate(ANNOTATORS):
            client = self._client(username)
            for assignment in self._assignments(batch, username, BatchPhase.ANNOTATION):
                text = assignment.example.content
                spans = [
                    [labels[label], text.index(passage), text.index(passage) + len(passage)]
                    for label, passage in COMMENT_SPANS[assignment.example.metadata["comment_id"]][
                        index
                    ]
                ]
                url = reverse("annotate-assignment", args=(batch.id, assignment.id))
                client.post(url, {"value": json.dumps(spans)})
            client.post(reverse("annotate-done", args=(batch.id,)))

    def _discuss(self, batch):
        """The chat and the labels saved after it, then the batch moves on as it would when
        the last text has been discussed."""
        room, _ = Room.objects.get_or_create(pk=batch.id)
        start = timezone.now() - timedelta(days=1)
        for username in ANNOTATORS:
            for assignment in self._assignments(batch, username, BatchPhase.DISCUSSION):
                doc_id = assignment.example.metadata["doc_id"]
                chat, agreed = DISCUSSIONS[doc_id]
                if agreed is None:
                    # both keep their labels from the annotation
                    before = ExampleAssignment.objects.get(
                        batch=batch,
                        user=assignment.user,
                        example=assignment.example,
                        phase=BatchPhase.ANNOTATION,
                    )
                    value = sorted(a.label_id for a in before.annotations.all())
                else:
                    value = self._label_ids(batch.project, agreed)
                assignment.set_user_annotations(value)

                if username == ANNOTATORS[0]:
                    for n, (author, text) in enumerate(chat):
                        message = Message.objects.create(
                            room=room,
                            user=author,
                            message=text,
                            example=assignment.example,
                        )
                        start += timedelta(seconds=40)
                        Message.objects.filter(pk=message.pk).update(
                            created_at=start + timedelta(seconds=n),
                        )
        batch.advance_from_discussion()
        batch.refresh_from_db()

    def _decide(self, batch):
        """The expert decides on the decision page, with a codebook change where given."""
        client = self._client(EXPERTS[0])
        for assignment in self._assignments(batch, EXPERTS[0], BatchPhase.EXPERT):
            letters, change = DECISIONS[assignment.example.metadata["doc_id"]]
            args = (batch.id, assignment.id)
            if change:
                content, rationale = change
                client.post(
                    reverse("expert-draft-save", args=args),
                    {"content": content, "rationale": rationale},
                )
            client.post(
                reverse("expert-assignment", args=args),
                {"labels": self._label_ids(batch.project, letters)},
            )
        batch.refresh_from_db()

    # --- the projects -----------------------------------------------------------------------

    def _classification_project(self, stage):
        project = self._project(
            CLASSIFICATION,
            "Which ideas of populism do party statements express? Posts, press releases and "
            "speech excerpts of three parties.",
            list(LABELS.values()),
            "classification",
        )
        self._write_codebook(
            project,
            CODEBOOK_V1,
            "First version: the three ideas of populism, each with an example to code and one "
            "not to code.",
        )

        batch = self._batch(project, BATCH_1)
        self._annotate(batch, BATCH_1, finalize=True)
        self._discuss(batch)
        self._decide(batch)

        batch = self._batch(project, BATCH_2)
        if stage == "annotation":
            self._annotate(batch, BATCH_2, finalize=False, first_annotator_done=ANNA_DONE)
        else:
            self._annotate(batch, BATCH_2, finalize=True)
        if stage in ("expert", "final"):
            self._discuss(batch)
        if stage == "final":
            self._decide(batch)

        phases = ", ".join(
            f"batch {b.batch_number}: {b.get_current_phase_display()}"
            for b in project.batches.order_by("batch_number")
        )
        self.stdout.write(f"{CLASSIFICATION}: {phases}")

    def _span_project(self, stage):
        project = self._project(
            SPANS,
            "Mark the offensive passages in reader comments under local news articles.",
            SPAN_LABELS,
            "span",
        )
        self._write_codebook(
            project,
            SPAN_CODEBOOK,
            "First version: three kinds of offensive language, and how much of a comment to mark.",
        )
        batch = self._batch(project, COMMENTS)
        if stage != "annotation":
            self._annotate_spans(batch)
        batch.refresh_from_db()
        self.stdout.write(f"{SPANS}: batch 1: {batch.get_current_phase_display()}")
