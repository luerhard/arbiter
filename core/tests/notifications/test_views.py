import re

from django.urls import reverse
from notifications.models import Notification
import pytest

from projects.models import BatchPhase


@pytest.mark.django_db
@pytest.mark.parametrize(("who", "status"), [("anonymous", 302), ("annotator", 200)])
def test_access(get_as, project_annotation, who, status):
    url = reverse("notifications-unread")

    assert get_as(url, who, project_annotation).status_code == status


@pytest.mark.django_db
class TestPhaseChangeCreatesNotifications:
    def test_set_phase_notifies_all_batch_users(self, project_annotation):
        batch = project_annotation["batch"]
        users = [*project_annotation["annotators"], project_annotation["expert"]]
        Notification.objects.filter(batch=batch).delete()

        batch.set_phase(BatchPhase.DISCUSSION)

        notifications = Notification.objects.filter(batch=batch)
        assert notifications.count() == len(users)
        assert {n.user for n in notifications} == set(users)
        for notification in notifications:
            assert notification.read_at is None
            assert "Discussion" in notification.message
            assert batch.project.name in notification.message

    def test_set_phase_without_change_creates_no_notifications(self, project_annotation):
        batch = project_annotation["batch"]
        Notification.objects.filter(batch=batch).delete()

        batch.set_phase(batch.current_phase)

        assert Notification.objects.filter(batch=batch).count() == 0

    def test_manual_phase_change_via_view_notifies(self, client, project_annotation):
        # Regression: ChangeBatchPhase binds a ModelForm to the batch instance,
        # which overwrites current_phase during validation. set_phase must
        # detect the change against the DB state, not the mutated instance,
        # or manual phase changes never notify anyone.
        batch = project_annotation["batch"]
        expert = project_annotation["expert"]
        Notification.objects.filter(batch=batch).delete()
        client.login(username=expert.username, password="123")

        response = client.post(
            reverse("change-batch-phase", args=[batch.id]),
            data={"current_phase": BatchPhase.DISCUSSION},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 204
        batch.refresh_from_db()
        assert batch.current_phase == BatchPhase.DISCUSSION
        notifications = Notification.objects.filter(batch=batch)
        # The acting expert gets a django message instead of a notification;
        # everyone else on the batch is notified.
        assert notifications.count() == 2
        assert {n.user for n in notifications} == set(project_annotation["annotators"])
        assert all("Discussion" in n.message for n in notifications)

    def test_auto_advance_notifies_for_both_batches(self, project_annotation):
        # When a batch finalizes and the next SETUP batch starts, users get a
        # notification for each transition.
        from django.utils import timezone

        from data.models import Example
        from projects.models import Batch
        from projects.models import ProjectRole
        from projects.models.batch import BatchUser

        data = project_annotation
        batch = data["batch"]
        a1, a2 = data["annotators"]
        label1 = data["labels"][0]

        # both annotators agree -> no discussion needed
        for user in (a1, a2):
            assignment = batch.assignments.get(user=user, phase=BatchPhase.ANNOTATION)
            assignment.set_user_annotations([label1.id])
        BatchUser.objects.filter(batch=batch).update(finalized_at=timezone.now())

        next_batch = Batch.objects.create(project=data["project"], current_phase=BatchPhase.SETUP)
        next_batch.users.add(a1, a2, through_defaults={"role": ProjectRole.ANNOTATOR})
        Example.objects.create(batch=next_batch, content="Next batch example")
        Notification.objects.all().delete()

        result = batch.advance_from_annotation_if_finalized()

        assert result == BatchPhase.FINAL
        assert Notification.objects.filter(batch=batch, user=a1).count() == 1
        assert Notification.objects.filter(batch=next_batch, user=a1).count() == 1
        assert "Annotation" in Notification.objects.get(batch=next_batch, user=a1).message


@pytest.mark.django_db
class TestNotificationViews:
    @pytest.fixture(autouse=True)
    def setup(self, client, project_annotation):
        self.client = client
        self.data = project_annotation
        self.user = self.data["annotators"][0]
        self.other_user = self.data["annotators"][1]
        self.batch = self.data["batch"]
        self.client.login(username=self.user.username, password="123")
        self.notification = Notification.objects.create(
            user=self.user,
            batch=self.batch,
            message="Batch moved to phase Discussion.",
        )
        self.unread_url = reverse("notifications-unread")

    def test_unread_returns_own_notifications_with_mark_read_button(self):
        Notification.objects.create(
            user=self.other_user,
            batch=self.batch,
            message="Someone else's notification",
        )

        response = self.client.get(self.unread_url)

        assert response.status_code == 200
        content = response.content.decode()
        assert self.notification.message in content
        assert "Someone else's notification" not in content
        assert reverse("notification-read", args=[self.notification.id]) in content

    def test_read_notifications_are_not_rendered(self):
        self.notification.mark_read()
        response = self.client.get(self.unread_url)
        assert self.notification.message not in response.content.decode()

    def test_mark_read(self):
        response = self.client.post(
            reverse("notification-read", args=[self.notification.id]),
        )

        assert response.status_code == 200
        self.notification.refresh_from_db()
        assert self.notification.read_at is not None

    def test_mark_read_is_idempotent(self):
        self.notification.mark_read()
        first_read_at = self.notification.read_at

        response = self.client.post(
            reverse("notification-read", args=[self.notification.id]),
        )

        assert response.status_code == 200
        self.notification.refresh_from_db()
        assert self.notification.read_at == first_read_at

    def test_poller_rendered_on_full_pages_when_logged_in(self):
        response = self.client.get(reverse("home"))
        content = response.content.decode()
        assert 'hx-trigger="load, every 15s, notifications-changed from:body"' in content
        assert self.unread_url in content

    def test_poller_absent_when_logged_out(self, client):
        client.logout()
        response = client.get(reverse("home"))
        assert self.unread_url not in response.content.decode()

    def test_cannot_mark_other_users_notification(self):
        other = Notification.objects.create(
            user=self.other_user,
            batch=self.batch,
            message="Not yours",
        )

        response = self.client.post(reverse("notification-read", args=[other.id]))

        assert response.status_code == 404
        other.refresh_from_db()
        assert other.read_at is None


@pytest.mark.django_db
class TestNotificationPile:
    """Many unread notifications must not cover the page: three toasts, the rest counted."""

    @pytest.fixture(autouse=True)
    def setup(self, client, project_annotation):
        self.client = client
        self.user, self.other_user = project_annotation["annotators"]
        self.batch = project_annotation["batch"]
        Notification.objects.all().delete()
        self.notifications = [
            Notification.objects.create(user=self.user, batch=self.batch, message=f"Message {i}")
            for i in range(5)
        ]
        client.login(username=self.user.username, password="123")

    def test_only_the_newest_three_are_shown_with_a_count_of_the_rest(self):
        content = self.client.get(reverse("notifications-unread")).content.decode()

        shown = re.findall(r"Message (\d)", content)
        assert shown == ["4", "3", "2"]
        assert "+ 2 more notifications" in " ".join(content.split())
        assert reverse("notifications-read-all") in content

    def test_no_count_when_all_are_shown(self):
        for notification in self.notifications[:2]:
            notification.mark_read()

        content = self.client.get(reverse("notifications-unread")).content.decode()

        assert len(re.findall(r"Message \d", content)) == 3
        assert 'id="notifications-more"' not in content

    def test_mark_all_read_marks_only_own_notifications(self):
        others = Notification.objects.create(user=self.other_user, batch=self.batch, message="x")

        response = self.client.post(reverse("notifications-read-all"))

        assert response.status_code == 200
        assert response["HX-Trigger"] == "notifications-changed"
        assert not Notification.objects.filter(user=self.user, read_at__isnull=True).exists()
        others.refresh_from_db()
        assert others.read_at is None

    def test_reading_one_reloads_the_toasts(self):
        response = self.client.post(
            reverse("notification-read", args=[self.notifications[0].id]),
        )

        assert response["HX-Trigger"] == "notifications-changed"
