from django.urls import reverse
import pytest


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("who", "status"),
    [
        ("anonymous", 302),
        ("annotator", 200),
        ("expert", 403),  # experts decide afterwards, they do not discuss
        ("outsider", 403),
    ],
)
def test_access(get_as, project_discussion, who, status):
    url = reverse("discuss-batch", args=(project_discussion["batch"].id,))

    assert get_as(url, who, project_discussion).status_code == status
