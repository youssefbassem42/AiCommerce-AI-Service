from app.shared.cqrs.command import Command
from app.shared.cqrs.query import Query
from app.shared.cqrs.command_handler import CommandHandler
from app.shared.cqrs.query_handler import QueryHandler
from app.shared.cqrs.result import CommandResult, QueryResult


class TestCommand:
    def test_command_has_metadata(self):
        command = Command()
        assert command.command_id is not None
        assert command.occurred_at is not None
        assert command.correlation_id is None

    def test_command_with_correlation_id(self):
        command = Command(correlation_id="corr-123")
        assert command.correlation_id == "corr-123"

    def test_command_id_is_unique(self):
        c1 = Command()
        c2 = Command()
        assert c1.command_id != c2.command_id

    def test_subclass_extends_metadata(self):
        class CreateProductCommand(Command):
            name: str

        cmd = CreateProductCommand(name="test", correlation_id="corr-abc")
        assert cmd.name == "test"
        assert cmd.correlation_id == "corr-abc"
        assert cmd.command_id is not None


class TestQuery:
    def test_query_has_metadata(self):
        query = Query()
        assert query.query_id is not None
        assert query.occurred_at is not None
        assert query.correlation_id is None

    def test_query_with_correlation_id(self):
        query = Query(correlation_id="corr-456")
        assert query.correlation_id == "corr-456"

    def test_subclass_extends_metadata(self):
        class GetProductQuery(Query):
            product_id: str

        q = GetProductQuery(product_id="prod-1")
        assert q.product_id == "prod-1"
        assert q.query_id is not None


class TestCommandResult:
    def test_success_result(self):
        result = CommandResult(success=True, data="done")
        assert result.success is True
        assert result.data == "done"
        assert result.error is None

    def test_failure_result(self):
        result = CommandResult(success=False, error="something went wrong")
        assert result.success is False
        assert result.error == "something went wrong"
        assert result.data is None

    def test_with_correlation_id(self):
        result = CommandResult(success=True, data="ok", correlation_id="corr-789")
        assert result.correlation_id == "corr-789"


class TestQueryResult:
    def test_success_result(self):
        result = QueryResult(success=True, data={"items": []})
        assert result.success is True
        assert result.data == {"items": []}

    def test_failure_result(self):
        result = QueryResult(success=False, error="not found")
        assert result.success is False
        assert result.error == "not found"
