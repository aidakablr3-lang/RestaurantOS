import pytest

from restaurant_os_api.modules.identity.domain.exceptions import InvalidEmailAddressError
from restaurant_os_api.modules.identity.domain.value_objects import EmailAddress


def test_valid_email_is_accepted() -> None:
    assert EmailAddress("owner@example.com").value == "owner@example.com"


def test_email_is_normalized_to_lowercase() -> None:
    assert EmailAddress("Owner@Example.COM").value == "owner@example.com"


@pytest.mark.parametrize(
    "invalid_value",
    [
        "",
        "not-an-email",
        "missing-domain@",
        "@missing-local-part.com",
        "spaces in@example.com",
        "double@@example.com",
    ],
)
def test_invalid_email_is_rejected(invalid_value: str) -> None:
    with pytest.raises(InvalidEmailAddressError):
        EmailAddress(invalid_value)


def test_equality_is_value_based() -> None:
    assert EmailAddress("a@example.com") == EmailAddress("A@Example.com")


def test_str_returns_normalized_value() -> None:
    assert str(EmailAddress("Owner@Example.com")) == "owner@example.com"
