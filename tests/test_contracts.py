from uuid import uuid4

import pytest
from pydantic import ValidationError

from synapse.models import Critique, RunInput


@pytest.mark.parametrize("topic", ["", "   ", "x" * 1001])
def test_topic_bounds(topic: str) -> None:
    with pytest.raises(ValidationError):
        RunInput(topic=topic, question="Compare the examples.")


def test_subquestions_are_bounded() -> None:
    with pytest.raises(ValidationError):
        RunInput(topic="Retrieval", question="Compare.", subquestions=["a"] * 4)


def test_rubric_rejects_out_of_range_scores() -> None:
    with pytest.raises(ValidationError):
        Critique(run_id=uuid4(), scores=[2, 2, 2, 2, 3], findings=[], total=11)
