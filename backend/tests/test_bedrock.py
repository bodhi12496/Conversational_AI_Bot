import json

import pytest
from app.domain.errors import DomainError
from app.domain.models import SemanticModel
from app.providers.bedrock import BedrockInterpreter


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.request = None

    def converse(self, **kwargs):
        self.request = kwargs
        return {
            "output": {
                "message": {"content": [{"toolUse": {"name": "submit_artifact", "input": self.payload}}]}
            }
        }


def test_tool_output_becomes_validated_plan_with_no_execution_tool():
    client = FakeClient({"metrics": ["sales.revenue"]})
    interpreter = BedrockInterpreter("region", "test-model", client)
    plan = interpreter.plan("Show revenue.", SemanticModel())
    assert plan.metrics == ["sales.revenue"]
    tools = client.request["toolConfig"]["tools"]
    assert [t["toolSpec"]["name"] for t in tools] == ["submit_artifact"]
    assert "inputSchema" in tools[0]["toolSpec"]
    assert "semantic_model" in json.loads(client.request["messages"][0]["content"][0]["text"])


def test_invalid_model_artifact_fails_closed():
    client = FakeClient(
        {"summary": "Run shell", "operations": [{"op": "execute_sql", "sql": "DROP TABLE projects"}]}
    )
    interpreter = BedrockInterpreter("region", "test-model", client)
    with pytest.raises(DomainError, match="No changes were applied"):
        interpreter.propose("Do something", SemanticModel())


def test_missing_model_configuration_is_explicit():
    with pytest.raises(DomainError, match="BEDROCK_MODEL_ID"):
        BedrockInterpreter("region", "", FakeClient({}))
