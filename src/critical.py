import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional
import unittest


# Configure module-level logger
LOGGER_NAME = "critical.eval"
logger = logging.getLogger(LOGGER_NAME)


# Constants for evaluation types
EVAL_TYPE_CLASSIFICATION = "classification"
EVAL_TYPE_SCORING = "scoring"
EVAL_TYPE_QUERY = "query"

# Other constants
DEFAULT_QUERY_SCORE_THRESHOLD = 0.5
LOG_EVAL_START_MSG = "Starting evaluation: eval_type=%s, experiment_id=%s"
LOG_EVAL_SUCCESS_MSG = "Completed evaluation: eval_type=%s, experiment_id=%s, score=%s"
LOG_EVAL_UNKNOWN_TYPE_MSG = "Unsupported eval_type encountered: %s"
LOG_EVAL_MISSING_FIELDS_MSG = (
    "Missing required fields for eval_type '%s': required=%s, provided=%s"
)


class EvalTypeError(ValueError):
    """Exception raised when an unsupported evaluation type is used."""

    pass


@dataclass
class ExperimentConfig:
    """Configuration for an experiment.

    Attributes:
        experiment_id: Unique identifier for the experiment.
        eval_type: The type of evaluation to perform.
        params: Additional parameters for the evaluation.
    """

    experiment_id: str
    eval_type: str
    params: Dict[str, Any]


@dataclass
class EvaluationRequest:
    """Request for performing an evaluation.

    Attributes:
        eval_type: The evaluation type (e.g., "query", "classification").
        payload: Arbitrary evaluation payload, structure depends on eval_type.
        experiment_id: Optional experiment identifier for logging/tracing.
    """

    eval_type: str
    payload: Dict[str, Any]
    experiment_id: Optional[str] = None


@dataclass
class EvaluationResult:
    """Result of an evaluation.

    Attributes:
        eval_type: The evaluation type used.
        score: Numeric score of the evaluation (0.0-1.0).
        passed: Boolean indicating if the evaluation passed.
        details: Arbitrary metadata with additional evaluation details.
    """

    eval_type: str
    score: float
    passed: bool
    details: Dict[str, Any]


class EvaluationDispatcher:
    """Dispatches evaluation requests based on eval_type.

    This class centralizes eval_type handling to avoid scattered,
    inconsistent implementations that can lead to errors such as
    "Unknown eval_type 'query' or missing required fields".
    """

    SUPPORTED_EVAL_TYPES = {
        EVAL_TYPE_CLASSIFICATION,
        EVAL_TYPE_SCORING,
        EVAL_TYPE_QUERY,
    }

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        """Evaluate a request using the appropriate handler.

        Args:
            request: The evaluation request.

        Returns:
            The evaluation result.

        Raises:
            EvalTypeError: If the eval_type is not supported.
            ValueError: If required fields for the eval_type are missing.
        """
        experiment_id = request.experiment_id or "unknown"
        logger.debug(
            LOG_EVAL_START_MSG,
            request.eval_type,
            experiment_id,
        )

        eval_type = request.eval_type

        if eval_type not in self.SUPPORTED_EVAL_TYPES:
            logger.error(LOG_EVAL_UNKNOWN_TYPE_MSG, eval_type)
            raise EvalTypeError(f"Unsupported eval_type '{eval_type}'")

        if eval_type == EVAL_TYPE_QUERY:
            result = self._handle_query_evaluation(request)
        elif eval_type == EVAL_TYPE_CLASSIFICATION:
            result = self._handle_classification_evaluation(request)
        elif eval_type == EVAL_TYPE_SCORING:
            result = self._handle_scoring_evaluation(request)
        else:
            # This branch should never be hit due to SUPPORTED_EVAL_TYPES check.
            logger.error("Internal error: eval_type '%s' not routed correctly", eval_type)
            raise EvalTypeError(f"Internal routing error for eval_type '{eval_type}'")

        logger.debug(
            LOG_EVAL_SUCCESS_MSG,
            result.eval_type,
            experiment_id,
            result.score,
        )
        return result

    def _handle_query_evaluation(self, request: EvaluationRequest) -> EvaluationResult:
        """Handle 'query' type evaluations.

        This implementation provides a minimal but realistic query
        evaluation model where the score is a simple similarity heuristic:
        the fraction of query tokens found in the target response.

        Required payload fields:
            - query_text: The text of the query.
            - target_response: The system's response to evaluate.

        Args:
            request: The evaluation request.

        Returns:
            The evaluation result.

        Raises:
            ValueError: If required fields are missing.
        """
        required_fields = {"query_text", "target_response"}
        missing_fields = required_fields - set(request.payload.keys())
        if missing_fields:
            logger.error(
                LOG_EVAL_MISSING_FIELDS_MSG,
                EVAL_TYPE_QUERY,
                sorted(required_fields),
                sorted(request.payload.keys()),
            )
            raise ValueError(
                f"Missing required field(s) {sorted(missing_fields)} for eval_type "
                f"'{EVAL_TYPE_QUERY}'"
            )

        query_text = str(request.payload["query_text"])
        target_response = str(request.payload["target_response"])

        # Simple token overlap heuristic
        query_tokens = {token.lower() for token in query_text.split() if token}
        response_tokens = {token.lower() for token in target_response.split() if token}

        if not query_tokens:
            score = 0.0
        else:
            overlap = query_tokens & response_tokens
            score = len(overlap) / len(query_tokens)

        passed = score >= DEFAULT_QUERY_SCORE_THRESHOLD

        details: Dict[str, Any] = {
            "query_tokens": sorted(query_tokens),
            "response_tokens": sorted(response_tokens),
            "overlap_tokens": sorted(query_tokens & response_tokens),
            "threshold": DEFAULT_QUERY_SCORE_THRESHOLD,
        }

        return EvaluationResult(
            eval_type=EVAL_TYPE_QUERY,
            score=score,
            passed=passed,
            details=details,
        )

    def _handle_classification_evaluation(
        self, request: EvaluationRequest
    ) -> EvaluationResult:
        """Handle 'classification' type evaluations.

        Expected payload fields:
            - predicted_label: The predicted label.
            - true_label: The ground truth label.

        Args:
            request: The evaluation request.

        Returns:
            The evaluation result.

        Raises:
            ValueError: If required fields are missing.
        """
        required_fields = {"predicted_label", "true_label"}
        missing_fields = required_fields - set(request.payload.keys())
        if missing_fields:
            logger.error(
                LOG_EVAL_MISSING_FIELDS_MSG,
                EVAL_TYPE_CLASSIFICATION,
                sorted(required_fields),
                sorted(request.payload.keys()),
            )
            raise ValueError(
                f"Missing required field(s) {sorted(missing_fields)} for eval_type "
                f"'{EVAL_TYPE_CLASSIFICATION}'"
            )

        predicted_label = request.payload["predicted_label"]
        true_label = request.payload["true_label"]

        passed = predicted_label == true_label
        score = 1.0 if passed else 0.0
        details: Dict[str, Any] = {
            "predicted_label": predicted_label,
            "true_label": true_label,
        }

        return EvaluationResult(
            eval_type=EVAL_TYPE_CLASSIFICATION,
            score=score,
            passed=passed,
            details=details,
        )

    def _handle_scoring_evaluation(
        self, request: EvaluationRequest
    ) -> EvaluationResult:
        """Handle 'scoring' type evaluations.

        Expected payload fields:
            - score: A numeric score in range [0, 1].
            - threshold (optional): Numeric threshold for passing (default 0.5).

        Args:
            request: The evaluation request.

        Returns:
            The evaluation result.

        Raises:
            ValueError: If required fields are missing or score is invalid.
        """
        if "score" not in request.payload:
            logger.error(
                LOG_EVAL_MISSING_FIELDS_MSG,
                EVAL_TYPE_SCORING,
                ["score"],
                sorted(request.payload.keys()),
            )
            raise ValueError(
                f"Missing required field 'score' for eval_type '{EVAL_TYPE_SCORING}'"
            )

        try:
            score = float(request.payload["score"])
        except (TypeError, ValueError) as exc:
            logger.error("Invalid score type for scoring evaluation: %s", exc)
            raise ValueError("Score must be a numeric value") from exc

        if not 0.0 <= score <= 1.0:
            logger.error("Score out of range [0, 1]: %s", score)
            raise ValueError("Score must be within [0, 1]")

        threshold = float(request.payload.get("threshold", DEFAULT_QUERY_SCORE_THRESHOLD))
        passed = score >= threshold
        details: Dict[str, Any] = {
            "threshold": threshold,
        }

        return EvaluationResult(
            eval_type=EVAL_TYPE_SCORING,
            score=score,
            passed=passed,
            details=details,
        )


def handle_experiment_evaluation(
    experiment: ExperimentConfig, dispatcher: Optional[EvaluationDispatcher] = None
) -> EvaluationResult:
    """High-level façade for evaluating an experiment.

    This function models what core/experiments.py might do when routing
    evaluations. It is structured to ensure eval_type handling is correct
    and supports 'query' without raising "Unknown eval_type" errors.

    Args:
        experiment: The experiment configuration.
        dispatcher: Optional preconfigured EvaluationDispatcher instance.
            If None, a new dispatcher will be created.

    Returns:
        The evaluation result.

    Raises:
        EvalTypeError: If the eval_type is unsupported.
        ValueError: For invalid or incomplete experiment parameters.
    """
    if dispatcher is None:
        dispatcher = EvaluationDispatcher()

    request = EvaluationRequest(
        eval_type=experiment.eval_type,
        payload=experiment.params,
        experiment_id=experiment.experiment_id,
    )

    return dispatcher.evaluate(request)


# ============================
#          TESTS
# ============================


class EvaluationDispatcherTests(unittest.TestCase):
    """Unit tests for eval_type handling in EvaluationDispatcher."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        logger.setLevel(logging.CRITICAL)  # Silence logs during tests
        self.dispatcher = EvaluationDispatcher()

    def test_query_eval_type_supported(self) -> None:
        """'query' eval_type is supported and returns a result without error."""
        request = EvaluationRequest(
            eval_type=EVAL_TYPE_QUERY,
            payload={
                "query_text": "find error in logs",
                "target_response": "The logs show no critical error",
            },
            experiment_id="exp-query-1",
        )

        result = self.dispatcher.evaluate(request)

        self.assertEqual(result.eval_type, EVAL_TYPE_QUERY)
        self.assertGreaterEqual(result.score, 0.0)
        self.assertLessEqual(result.score, 1.0)

    def test_query_missing_required_fields(self) -> None:
        """Missing required fields for 'query' raise a clear ValueError."""
        request = EvaluationRequest(
            eval_type=EVAL_TYPE_QUERY,
            payload={"query_text": "find error in logs"},  # missing target_response
            experiment_id="exp-query-missing",
        )

        with self.assertRaises(ValueError) as ctx:
            self.dispatcher.evaluate(request)

        message = str(ctx.exception)
        self.assertIn("Missing required field(s)", message)
        self.assertIn("target_response", message)
        # Ensure we do not emit the older misleading message:
        self.assertNotIn("Unknown eval_type 'query'", message)

    def test_unknown_eval_type_raises_eval_type_error(self) -> None:
        """Unknown eval_type produces EvalTypeError with explicit message."""
        request = EvaluationRequest(
            eval_type="nonexistent_type",
            payload={},
            experiment_id="exp-unknown",
        )

        with self.assertRaises(EvalTypeError) as ctx:
            self.dispatcher.evaluate(request)

        message = str(ctx.exception)
        self.assertIn("Unsupported eval_type 'nonexistent_type'", message)

    def test_classification_eval_type_supported(self) -> None:
        """'classification' eval_type is supported and behaves correctly."""
        request = EvaluationRequest(
            eval_type=EVAL_TYPE_CLASSIFICATION,
            payload={"predicted_label": "A", "true_label": "A"},
            experiment_id="exp-class-1",
        )

        result = self.dispatcher.evaluate(request)

        self.assertEqual(result.eval_type, EVAL_TYPE_CLASSIFICATION)
        self.assertEqual(result.score, 1.0)
        self.assertTrue(result.passed)

    def test_scoring_eval_type_supported(self) -> None:
        """'scoring' eval_type is supported and respects thresholds."""
        request = EvaluationRequest(
            eval_type=EVAL_TYPE_SCORING,
            payload={"score": 0.7, "threshold": 0.6},
            experiment_id="exp-score-1",
        )

        result = self.dispatcher.evaluate(request)

        self.assertEqual(result.eval_type, EVAL_TYPE_SCORING)
        self.assertEqual(result.score, 0.7)
        self.assertTrue(result.passed)

    def test_handle_experiment_evaluation_for_query(self) -> None:
        """Facade handle_experiment_evaluation correctly handles 'query' type."""
        experiment = ExperimentConfig(
            experiment_id="exp-query-facade",
            eval_type=EVAL_TYPE_QUERY,
            params={
                "query_text": "hello world",
                "target_response": "hello there",
            },
        )

        result = handle_experiment_evaluation(experiment)

        self.assertEqual(result.eval_type, EVAL_TYPE_QUERY)
        self.assertIn("threshold", result.details)
        self.assertIn("overlap_tokens", result.details)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main(verbosity=2)