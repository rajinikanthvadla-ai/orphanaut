"""Tests for sign-in helpers (no network)."""

import json

import pytest

from orphanaut.auth import aws as aws_auth
from orphanaut.auth.aws import (
    ENV_PROFILE,
    AuthenticationError,
    AwsBrowserLogin,
    create_aws_session,
    list_local_profiles,
    list_sso_profiles,
    sso_settings_for_profile,
)
from orphanaut.auth.gcp import _service_account_credentials
from orphanaut.models import AuthConfig, AuthMethod, CloudProvider
from tests.fakes import FakeClient

AWS_CONFIG = """
[default]
region = us-east-1

[profile lab]
sso_session = school
sso_account_id = 111122223333
sso_role_name = Student

[sso-session school]
sso_start_url = https://school.awsapps.com/start
sso_region = eu-west-1

[profile legacy]
sso_start_url = https://old.awsapps.com/start
sso_region = us-west-2
"""


@pytest.fixture
def aws_files(tmp_path, monkeypatch):
    config = tmp_path / "config"
    creds = tmp_path / "credentials"
    config.write_text(AWS_CONFIG)
    creds.write_text("[default]\naws_access_key_id = AKIA\n\n[work]\naws_access_key_id = AKIA\n")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(config))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(creds))
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    return tmp_path


def test_local_profiles_lists_default_first(aws_files):
    assert list_local_profiles() == ["default", "lab", "legacy", "work"]


def test_local_profiles_include_env_vars(aws_files, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAX")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    assert list_local_profiles()[0] == ENV_PROFILE


def test_sso_profiles_and_settings(aws_files):
    assert list_sso_profiles() == ["lab", "legacy"]
    lab = sso_settings_for_profile("lab")
    assert lab.start_url == "https://school.awsapps.com/start"
    assert lab.region == "eu-west-1"
    assert (lab.account_id, lab.role_name) == ("111122223333", "Student")
    legacy = sso_settings_for_profile("legacy")
    assert legacy.region == "us-west-2"
    assert sso_settings_for_profile("default") is None


@pytest.mark.parametrize(
    ("key", "secret", "token", "message"),
    [
        ("", "", "", "required"),
        ("hello", "s", "", "doesn't look like"),
        ("ASIAXXXX", "s", "", "Session Token"),
    ],
)
def test_access_key_validation(key, secret, token, message):
    config = AuthConfig(method=AuthMethod.ACCESS_KEYS, access_key_id=key,
                        secret_access_key=secret, session_token=token)
    with pytest.raises(AuthenticationError, match=message):
        create_aws_session(config)


def test_access_keys_build_session():
    config = AuthConfig(method=AuthMethod.ACCESS_KEYS, access_key_id=" AKIATEST ",
                        secret_access_key=" secret ")
    session = create_aws_session(config)
    creds = session.get_credentials()
    assert creds.access_key == "AKIATEST"
    assert creds.secret_key == "secret"


def test_browser_login_device_flow(monkeypatch):
    oidc = FakeClient({
        "register_client": {"clientId": "cid", "clientSecret": "csec"},
        "start_device_authorization": {
            "deviceCode": "dev", "userCode": "ABCD-EFGH", "verificationUri": "https://x",
            "verificationUriComplete": "https://x?code=ABCD-EFGH", "expiresIn": 60,
            "interval": 1,
        },
        "create_token": {"accessToken": "tok"},
    })
    oidc.exceptions.AuthorizationPendingException = type("Pending", (Exception,), {})
    oidc.exceptions.SlowDownException = type("Slow", (Exception,), {})
    sso = FakeClient({
        "list_accounts": {"accountList": [{"accountId": "1", "accountName": "Lab"}]},
        "list_account_roles": {"roleList": [{"roleName": "Admin"}, {"roleName": "Read"}]},
        "get_role_credentials": {"roleCredentials": {
            "accessKeyId": "ASIA1", "secretAccessKey": "s", "sessionToken": "t"}},
    })
    monkeypatch.setattr(aws_auth.boto3, "client",
                        lambda name, **_kw: oidc if name == "sso-oidc" else sso)
    opened = []
    monkeypatch.setattr(aws_auth.webbrowser, "open", opened.append)

    login = AwsBrowserLogin("school.awsapps.com/start", "eu-west-1")
    code = login.start()
    assert code.user_code == "ABCD-EFGH"
    assert opened == ["https://x?code=ABCD-EFGH"]
    assert login.wait() == "tok"
    assert login.account_roles() == [("1", "Lab", "Admin"), ("1", "Lab", "Read")]
    session = login.session_for("1", "Admin", "us-east-1")
    assert session.get_credentials().token == "t"
    assert ("start_device_authorization", {
        "clientId": "cid", "clientSecret": "csec",
        "startUrl": "https://school.awsapps.com/start"}) in oidc.calls


def test_browser_login_requires_url():
    with pytest.raises(AuthenticationError, match="portal URL"):
        AwsBrowserLogin("", "us-east-1")


def test_gcp_service_account_validation():
    with pytest.raises(AuthenticationError, match="Paste"):
        _service_account_credentials(AuthConfig(provider=CloudProvider.GCP,
                                                method=AuthMethod.SERVICE_ACCOUNT))
    with pytest.raises(AuthenticationError, match="valid JSON"):
        _service_account_credentials(AuthConfig(provider=CloudProvider.GCP,
                                                method=AuthMethod.SERVICE_ACCOUNT,
                                                service_account_json="{nope"))
    with pytest.raises(AuthenticationError, match="isn't a service account"):
        _service_account_credentials(AuthConfig(
            provider=CloudProvider.GCP, method=AuthMethod.SERVICE_ACCOUNT,
            service_account_json=json.dumps({"type": "authorized_user"})))


def test_azure_service_principal_requires_fields():
    from orphanaut.auth.azure import azure_sign_in

    config = AuthConfig(provider=CloudProvider.AZURE, method=AuthMethod.SERVICE_PRINCIPAL,
                        tenant_id="t")
    with pytest.raises(AuthenticationError, match="required"):
        azure_sign_in(config)
