from django.urls import reverse
import pytest
import json

from data.models import ExampleAssignment, Label

# Update the tuples to have just the assignment id (not a tuple)
URLS_WITH_URL_PARAMS = [
    ("annotate-batch", 1),
]

URLS_WITH_GET_PARAMS = [
    ("annotate-next", 1),
    ("annotate-prev", 11),
]


class TestViews:
    pytestmark = pytest.mark.django_db

    @pytest.mark.parametrize(("slug", "assignment_id"), URLS_WITH_GET_PARAMS)
    def test_login_required_not_logged_in_get_params_urls(self, slug, assignment_id, client):
        url = reverse(slug)
        req = client.get(url, data={"assignment_id": assignment_id})
        assert req.status_code == 302

    @pytest.mark.parametrize(("slug", "assignment_id"), URLS_WITH_GET_PARAMS)
    def test_login_required_as_annotator_get_params_urls(self, slug, assignment_id, client):
        url = reverse(slug)
        login = client.login(username="annotator1", password="123")
        assert login is True
        req = client.get(url, data={"assignment_id": assignment_id})
        assert req.status_code == 200

    @pytest.mark.parametrize(("slug", "assignment_id"), URLS_WITH_GET_PARAMS)
    def test_login_required_as_non_annotator_get_params_urls(self, slug, assignment_id, client):
        url = reverse(slug)
        login = client.login(username="annotator3", password="123")
        assert login is True
        req = client.get(url, data={"assignment_id": assignment_id})
        assert req.status_code == 403

    @pytest.mark.parametrize(("slug", "param"), URLS_WITH_URL_PARAMS)
    def test_login_required_not_logged_in_url_params(self, slug, param, client):
        url = reverse(slug, args=(param,))
        req = client.get(url)
        assert req.status_code == 302

    @pytest.mark.parametrize(("slug", "param"), URLS_WITH_URL_PARAMS)
    def test_login_required_as_annotator_url_params(self, slug, param, client):
        url = reverse(slug, args=(param,))
        login = client.login(username="annotator1", password="123")
        assert login == True
        req = client.get(url)
        assert req.status_code == 200


@pytest.mark.django_db
class TestEditAssignmentView:
    @pytest.fixture(autouse=True)
    def setup(self, client):
        client.login(username="annotator1", password="123")
        response = client.get(reverse("annotate-batch", args=[4]))
        assert response.status_code == 200
        trigger = json.loads(response["HX-Trigger"])
        assignment_id = trigger["annotation-updated"]["assignment_id"]
        self.assignment = ExampleAssignment.objects.get(id=assignment_id)
        self.url = reverse("annotate-edit")

    def test_post_correct_labels(self, client):
        assert self.assignment.annotations.count() == 0
        labels = Label.objects.filter(project=self.assignment.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:2])

        response = client.post(
            self.url, data={"assignment_id": self.assignment.id, "labels": label_ids}
        )

        assert response.status_code == 204
        self.assignment.refresh_from_db()
        assert self.assignment.annotations.count() == 2
        assert sorted(self.assignment.annotations.values_list("label_id", flat=True)) == sorted(
            label_ids
        )

    def test_post_no_labels_parameter(self, client):
        # Set some annotations first to test their removal
        labels = Label.objects.filter(project=self.assignment.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:1])
        self.assignment.set_user_annotations(label_ids=label_ids, phase="ANNOTATION")
        assert self.assignment.annotations.count() == 1

        # Should this even be legal? (referring to the MultilabelFormAnnotation)
        response = client.post(self.url, data={"assignment_id": self.assignment.id})
        assert response.status_code == 204
        self.assignment.refresh_from_db()
        assert self.assignment.annotations.count() == 0

    def test_post_empty_labels_list(self, client):
        # Set some annotations first to test their removal
        labels = Label.objects.filter(project=self.assignment.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:1])
        self.assignment.set_user_annotations(label_ids=label_ids, phase="ANNOTATION")
        assert self.assignment.annotations.count() == 1

        response = client.post(self.url, data={"assignment_id": self.assignment.id, "labels": []})
        assert response.status_code == 204
        self.assignment.refresh_from_db()
        assert self.assignment.annotations.count() == 0

    def test_post_invalid_label_id(self, client):
        """
        The form is invalid, but the view logic proceeds and saves the annotation,
        ignoring the invalid label.
        """
        assert self.assignment.annotations.count() == 0
        invalid_label_id = 9999
        response = client.post(
            self.url, data={"assignment_id": self.assignment.id, "labels": [invalid_label_id]}
        )
        assert response.status_code == 204
        self.assignment.refresh_from_db()
        assert self.assignment.annotations.count() == 0

    def test_post_mixed_valid_and_invalid_label_ids(self, client):
        assert self.assignment.annotations.count() == 0
        labels = Label.objects.filter(project=self.assignment.example.batch.project)
        valid_label_id = labels.first().id
        invalid_label_id = 9999
        response = client.post(
            self.url,
            data={
                "assignment_id": self.assignment.id,
                "labels": [valid_label_id, invalid_label_id],
            },
        )
        assert response.status_code == 204
        self.assignment.refresh_from_db()
        assert self.assignment.annotations.count() == 1
        assert self.assignment.annotations.first().label.id == valid_label_id

    def test_post_non_integer_label_id(self, client):
        with pytest.raises(ValueError):
            client.post(
                self.url, data={"assignment_id": self.assignment.id, "labels": ["not-a-number"]}
            )

    def test_post_wrong_parameter_name(self, client):
        # Set some annotations first to test they are not removed
        labels = Label.objects.filter(project=self.assignment.example.batch.project)
        label_ids = list(labels.values_list("id", flat=True)[:1])
        self.assignment.set_user_annotations(label_ids=label_ids, phase="ANNOTATION")
        assert self.assignment.annotations.count() == 1

        response = client.post(
            self.url, data={"assignment_id": self.assignment.id, "wrong_labels": [1, 2]}
        )
        assert response.status_code == 204
        self.assignment.refresh_from_db()
        # The annotations are cleared because `getlist("labels")` is empty
        assert self.assignment.annotations.count() == 0

