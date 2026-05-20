from project.audit_requirements import split_auditable_requirements


def test_split_auditable_requirements_excludes_local_versions(tmp_path):
    requirements = tmp_path / "requirements-lock.txt"
    requirements.write_text(
        "\n".join(
            [
                "requests==2.32.5",
                "torch==2.8.0+cu129",
                "torchvision==0.23.0+cu129",
                "urllib3==2.5.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    auditable, excluded = split_auditable_requirements(requirements)

    assert auditable == ["requests==2.32.5", "urllib3==2.5.0"]
    assert [item.requirement for item in excluded] == ["torch==2.8.0+cu129", "torchvision==0.23.0+cu129"]
    assert [item.line_number for item in excluded] == [2, 3]
