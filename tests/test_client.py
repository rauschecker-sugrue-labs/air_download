"""Tests for air_download.client credential and URL resolution."""

import os

import pytest

from air_download.client import AIRClient


class TestResolveUrl:
    """Tests for AIRClient URL resolution logic."""

    def test_url_from_argument(self, tmp_path):
        cred_file = tmp_path / "creds.txt"
        cred_file.write_text(
            "AIR_USERNAME=user\nAIR_PASSWORD=pass\nAIR_URL=https://file.example.com/api/\n"
        )
        client = AIRClient(url="https://arg.example.com/api/", cred_path=cred_file)
        assert client.url == "https://arg.example.com/api/"

    def test_url_from_credential_file(self, tmp_path):
        cred_file = tmp_path / "creds.txt"
        cred_file.write_text(
            "AIR_USERNAME=user\nAIR_PASSWORD=pass\nAIR_URL=https://file.example.com/api/\n"
        )
        client = AIRClient(cred_path=cred_file)
        assert client.url == "https://file.example.com/api/"

    def test_url_from_env_var(self, monkeypatch, tmp_path):
        cred_file = tmp_path / "creds.txt"
        cred_file.write_text("AIR_USERNAME=user\nAIR_PASSWORD=pass\n")
        monkeypatch.setenv("AIR_URL", "https://env.example.com/api/")
        client = AIRClient(cred_path=cred_file)
        assert client.url == "https://env.example.com/api/"

    def test_url_trailing_slash_added(self, tmp_path):
        cred_file = tmp_path / "creds.txt"
        cred_file.write_text(
            "AIR_USERNAME=user\nAIR_PASSWORD=pass\nAIR_URL=https://example.com/api\n"
        )
        client = AIRClient(cred_path=cred_file)
        assert client.url == "https://example.com/api/"

    def test_url_trailing_slash_preserved(self, tmp_path):
        cred_file = tmp_path / "creds.txt"
        cred_file.write_text(
            "AIR_USERNAME=user\nAIR_PASSWORD=pass\nAIR_URL=https://example.com/api/\n"
        )
        client = AIRClient(cred_path=cred_file)
        assert client.url == "https://example.com/api/"

    def test_url_missing_raises_value_error(self, monkeypatch, tmp_path):
        cred_file = tmp_path / "creds.txt"
        cred_file.write_text("AIR_USERNAME=user\nAIR_PASSWORD=pass\n")
        monkeypatch.delenv("AIR_URL", raising=False)
        with pytest.raises(ValueError, match="AIR API URL not provided"):
            AIRClient(cred_path=cred_file)

    def test_url_priority_arg_over_file(self, tmp_path):
        cred_file = tmp_path / "creds.txt"
        cred_file.write_text(
            "AIR_USERNAME=user\nAIR_PASSWORD=pass\nAIR_URL=https://file.example.com/api/\n"
        )
        client = AIRClient(url="https://arg.example.com/api/", cred_path=cred_file)
        assert client.url == "https://arg.example.com/api/"

    def test_url_priority_file_over_env(self, monkeypatch, tmp_path):
        cred_file = tmp_path / "creds.txt"
        cred_file.write_text(
            "AIR_USERNAME=user\nAIR_PASSWORD=pass\nAIR_URL=https://file.example.com/api/\n"
        )
        monkeypatch.setenv("AIR_URL", "https://env.example.com/api/")
        client = AIRClient(cred_path=cred_file)
        assert client.url == "https://file.example.com/api/"


class TestCredentials:
    """Tests for AIRClient credential resolution."""

    def test_credentials_from_file(self, tmp_path):
        cred_file = tmp_path / "creds.txt"
        cred_file.write_text(
            "AIR_USERNAME=myuser\nAIR_PASSWORD=mypass\nAIR_URL=https://example.com/api/\n"
        )
        client = AIRClient(cred_path=cred_file)
        username, password = client._get_credentials()
        assert username == "myuser"
        assert password == "mypass"

    def test_credentials_from_env(self, monkeypatch, tmp_path):
        cred_file = tmp_path / "creds.txt"
        cred_file.write_text("AIR_URL=https://example.com/api/\n")
        monkeypatch.setenv("AIR_USERNAME", "envuser")
        monkeypatch.setenv("AIR_PASSWORD", "envpass")
        client = AIRClient(cred_path=cred_file)
        username, password = client._get_credentials()
        assert username == "envuser"
        assert password == "envpass"

    def test_missing_credentials_raises(self, monkeypatch, tmp_path):
        cred_file = tmp_path / "creds.txt"
        cred_file.write_text("AIR_URL=https://example.com/api/\n")
        monkeypatch.delenv("AIR_USERNAME", raising=False)
        monkeypatch.delenv("AIR_PASSWORD", raising=False)
        client = AIRClient(cred_path=cred_file)
        with pytest.raises(ValueError, match="AIR credentials not provided"):
            client._get_credentials()

    def test_empty_username_raises(self, monkeypatch, tmp_path):
        cred_file = tmp_path / "creds.txt"
        cred_file.write_text(
            "AIR_USERNAME=\nAIR_PASSWORD=pass\nAIR_URL=https://example.com/api/\n"
        )
        monkeypatch.delenv("AIR_USERNAME", raising=False)
        monkeypatch.delenv("AIR_PASSWORD", raising=False)
        client = AIRClient(cred_path=cred_file)
        with pytest.raises(ValueError, match="AIR credentials not provided"):
            client._get_credentials()

    def test_empty_password_raises(self, monkeypatch, tmp_path):
        cred_file = tmp_path / "creds.txt"
        cred_file.write_text(
            "AIR_USERNAME=user\nAIR_PASSWORD=\nAIR_URL=https://example.com/api/\n"
        )
        monkeypatch.delenv("AIR_USERNAME", raising=False)
        monkeypatch.delenv("AIR_PASSWORD", raising=False)
        client = AIRClient(cred_path=cred_file)
        with pytest.raises(ValueError, match="AIR credentials not provided"):
            client._get_credentials()

    def test_missing_cred_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="does not exist"):
            AIRClient(
                url="https://example.com/api/",
                cred_path=tmp_path / "nonexistent.txt",
            )

    def test_no_cred_path_uses_env(self, monkeypatch):
        monkeypatch.setenv("AIR_URL", "https://example.com/api/")
        monkeypatch.setenv("AIR_USERNAME", "envuser")
        monkeypatch.setenv("AIR_PASSWORD", "envpass")
        client = AIRClient()
        username, password = client._get_credentials()
        assert username == "envuser"
        assert password == "envpass"
