"""A2 orchestration contract tests; all provider calls are mocked."""

import asyncio
from dataclasses import asdict
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from citysim.data import load_dataset
from citysim.engine import simulate
from citysim.models import Decision
from citysim.review_models import ReviewConstraints
from citysim.search import generate_candidates


REFERENCE = (
    Decision("M5", "saryarka"), Decision("M7", "nura"), Decision("M8", "nura"),
    Decision("M10", "nura"), Decision("M12"),
)


def response(payload, *, status="completed"):
    return SimpleNamespace(status=status, output_text=json.dumps(payload))


def wire_candidate(decisions):
    return {"decisions": [asdict(decision) for decision in decisions]}


def wire_round(candidates):
    return {"candidates": [wire_candidate(candidate) for candidate in candidates]}


class ReviewerTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()
        self.source = simulate(REFERENCE, self.dataset)
        self.constraints = ReviewConstraints()
        self.candidates = generate_candidates(self.source, self.dataset, self.constraints)

    def run_review(self, *args, **kwargs):
        from citysim.reviewer import review_scenario

        return review_scenario(*args, **kwargs)

    def make_client(self, replies):
        client = SimpleNamespace(
            responses=SimpleNamespace(create=AsyncMock(side_effect=replies)),
            close=AsyncMock(),
        )
        return client

    def test_demo_uses_s1_and_never_constructs_sdk(self):
        with patch("openai.AsyncOpenAI") as sdk:
            review, explanation = self.run_review(
                self.source, self.dataset, self.constraints, demo_mode=True,
            )
        sdk.assert_not_called()
        self.assertEqual(len(review.checks), 20)
        self.assertEqual(review.status, "completed_limited")
        self.assertEqual(explanation.mode, "demo")
        self.assertIsNone(explanation.warning)

    def test_missing_key_falls_back_without_constructing_sdk(self):
        with patch("openai.AsyncOpenAI") as sdk:
            review, explanation = self.run_review(
                self.source, self.dataset, self.constraints,
                demo_mode=False, api_key=None,
            )
        sdk.assert_not_called()
        self.assertEqual(review.status, "completed_limited")
        self.assertEqual(len(review.checks), 20)
        self.assertEqual(explanation.mode, "demo")
        self.assertIsNotNone(explanation.warning)

    def test_missing_or_blank_configuration_and_demo_credentials_skip_sdk(self):
        cases = (
            {"demo_mode": False, "api_key": " ", "model": "test-model"},
            {"demo_mode": False, "api_key": "key", "model": None},
            {"demo_mode": False, "api_key": "key", "model": " "},
            {"demo_mode": True, "api_key": "key", "model": "test-model"},
        )
        with patch("openai.AsyncOpenAI") as sdk:
            for options in cases:
                with self.subTest(options=options):
                    review, explanation = self.run_review(
                        self.source, self.dataset, self.constraints, **options,
                    )
                    self.assertEqual(review.status, "completed_limited")
                    self.assertEqual(len(review.checks), 20)
                    self.assertEqual(explanation.mode, "demo")
        sdk.assert_not_called()

    def test_zero_changes_and_all_locked_do_not_create_sdk(self):
        cases = (ReviewConstraints(max_changes=0),
                 ReviewConstraints(locked=self.source.decisions))
        with patch("openai.AsyncOpenAI") as sdk:
            for constraints in cases:
                with self.subTest(constraints=constraints):
                    review, explanation = self.run_review(
                        self.source, self.dataset, constraints,
                        demo_mode=False, api_key="test-key", model="test-model",
                    )
                    self.assertEqual(review.checks, ())
                    self.assertEqual(review.status, "completed_limited")
                    self.assertEqual(explanation.mode, "demo")
        sdk.assert_not_called()

    def test_invalid_source_or_constraints_raise_before_sdk(self):
        from citysim.engine import baseline

        invalid = ((baseline(self.dataset), self.constraints),
                   (self.source, ReviewConstraints(max_changes=True)))
        with patch("openai.AsyncOpenAI") as sdk:
            for source, constraints in invalid:
                with self.subTest(source=source, constraints=constraints):
                    with self.assertRaises(ValueError):
                        self.run_review(source, self.dataset, constraints,
                                        demo_mode=False, api_key="test-key", model="test-model")
        sdk.assert_not_called()

    def test_live_two_rounds_pass_original_source_and_locked_constraints(self):
        locked = (REFERENCE[1],)
        constraints = ReviewConstraints(locked=locked)
        first = next(c for c in generate_candidates(self.source, self.dataset, constraints)
                     if set(locked).issubset(c))
        second = next(c for c in generate_candidates(self.source, self.dataset, constraints)
                      if c != first)
        client = self.make_client((response(wire_round((first,))),
                                   response(wire_round((second,)))))
        with patch("openai.AsyncOpenAI", return_value=client) as sdk:
            review, explanation = self.run_review(
                self.source, self.dataset, constraints,
                demo_mode=False, api_key="secret-test-key", model="test-model",
            )
        self.assertEqual(client.responses.create.await_count, 2)
        self.assertEqual(client.close.await_count, 1)
        self.assertEqual(review.source, self.source)
        self.assertEqual(review.constraints, constraints)
        self.assertEqual(len(review.checks), 2)
        self.assertEqual(explanation.mode, "openai")
        self.assertIsNone(explanation.warning)
        calls = client.responses.create.await_args_list
        for index, call in enumerate(calls):
            encoded_input = json.dumps(call.kwargs.get("input", call.args[0] if call.args else {}))
            self.assertIn("source", encoded_input)
            self.assertIn("constraints", encoded_input)
            self.assertIn("previous_checks", encoded_input)
            request_payload = call.kwargs.get("input", call.args[0] if call.args else {})
            if isinstance(request_payload, str):
                request_payload = json.loads(request_payload)
            normalized_source = json.loads(json.dumps(asdict(self.source)))
            self.assertEqual(request_payload["source"], normalized_source)
            normalized_constraints = json.loads(json.dumps(asdict(constraints)))
            self.assertEqual(request_payload["constraints"], normalized_constraints)
            self.assertEqual(len(request_payload["previous_checks"]), index)
            self.assertNotIn("api_key", call.kwargs)
            self.assertIs(call.kwargs.get("store"), False)
            self.assertEqual(call.kwargs.get("max_output_tokens"), 4096)
            self.assertNotIn("reasoning", call.kwargs)
            self.assertNotIn("score", request_payload)
        sdk.assert_called_once_with(
            api_key="secret-test-key", timeout=15.0, max_retries=0,
        )

    def test_luna_uses_no_reasoning_and_other_models_keep_request_shape(self):
        for model in ("gpt-6-luna", "test-model", "gpt-4.1", "gpt-6-astra"):
            with self.subTest(model=model):
                first, second = self.candidates[:2]
                client = self.make_client((response(wire_round((first,))),
                                           response(wire_round((second,)))))
                with patch("openai.AsyncOpenAI", return_value=client):
                    review, explanation = self.run_review(
                        self.source, self.dataset, self.constraints,
                        demo_mode=False, api_key="key", model=model,
                    )
                self.assertEqual(client.responses.create.await_count, 2)
                self.assertEqual(explanation.mode, "openai")
                for call in client.responses.create.await_args_list:
                    self.assertEqual(call.kwargs["max_output_tokens"], 4096)
                    if model == "gpt-6-luna":
                        self.assertEqual(call.kwargs["reasoning"], {"effort": "none"})
                    else:
                        self.assertNotIn("reasoning", call.kwargs)

    def test_second_round_failure_keeps_first_round_verified_candidate(self):
        first = self.candidates[0]
        client = self.make_client((response(wire_round((first,))), RuntimeError("provider secret")))
        with patch("openai.AsyncOpenAI", return_value=client):
            review, explanation = self.run_review(
                self.source, self.dataset, self.constraints,
                demo_mode=False, api_key="key", model="test-model",
            )
        self.assertEqual(len(review.checks), 20)
        self.assertIn(first, tuple(check.decisions for check in review.checks))
        self.assertEqual(review.status, "completed_limited")
        self.assertEqual(explanation.mode, "demo")
        self.assertNotIn("provider secret", explanation.warning or "")

    def test_invented_scores_are_ignored_and_best_comes_from_engine(self):
        candidate = self.candidates[0]
        payload = wire_round((candidate,))
        payload["candidates"][0].update({"score": 999999, "cost": 0, "n_crit": -10})
        client = self.make_client((response(payload), response(wire_round(()))))
        with patch("openai.AsyncOpenAI", return_value=client):
            review, _ = self.run_review(self.source, self.dataset, self.constraints,
                                        demo_mode=False, api_key="key", model="test-model")
        check = next(c for c in review.checks if c.decisions == candidate)
        self.assertIsNotNone(check.result)
        self.assertEqual(check.result.cost, simulate(candidate, self.dataset).cost)
        self.assertEqual(check.result.after.score, simulate(candidate, self.dataset).after.score)
        self.assertNotEqual(check.result.after.score, 999999)

    def test_unknown_ids_and_wrong_count_reach_engine_as_rejected_checks(self):
        unknown = [{"measure_id": "M999", "district_id": "nura"}]
        wrong_count = [asdict(d) for d in REFERENCE[:4]]
        client = self.make_client((response({"candidates": [
            {"decisions": unknown}, {"decisions": wrong_count},
        ]}), response(wire_round((self.candidates[0],)))))
        with patch("openai.AsyncOpenAI", return_value=client):
            review, _ = self.run_review(self.source, self.dataset, self.constraints,
                                        demo_mode=False, api_key="key", model="test-model")
        self.assertEqual(len(review.checks), 3)
        self.assertIn("unknown_measure", {e.code for e in review.checks[0].errors})
        self.assertIn("decision_count", {e.code for e in review.checks[1].errors})
        self.assertTrue(all(check.result is None for check in review.checks[:2]))

    def test_locked_change_and_two_changes_from_original_a_are_rejected(self):
        locked = (REFERENCE[0],)
        constraints = ReviewConstraints(locked=locked)
        locked_change = next(candidate for candidate in self.candidates
                             if REFERENCE[0] not in candidate)
        first = self.candidates[0]
        two_changes = tuple(d for d in REFERENCE
                            if d.measure_id not in {"M5", "M7"}) + (
            Decision("M9", "saryarka"), Decision("M11", "esil"),
        )
        payload1 = wire_round((first,))
        payload2 = wire_round((locked_change, two_changes))
        client = self.make_client((response(payload1), response(payload2)))
        with patch("openai.AsyncOpenAI", return_value=client):
            review, _ = self.run_review(
                self.source, self.dataset, constraints,
                demo_mode=False, api_key="key", model="test-model",
            )
        locked_check = next(c for c in review.checks if set(c.decisions) == set(locked_change))
        multi_check = next(c for c in review.checks if set(c.decisions) == set(two_changes))
        self.assertIn("locked_changed", {issue.code for issue in locked_check.errors})
        self.assertIn("change_limit", {issue.code for issue in multi_check.errors})
        self.assertIsNone(locked_check.result)
        self.assertIsNone(multi_check.result)

    def test_deadline_after_first_round_keeps_first_verified_results_incomplete(self):
        first = self.candidates[0]
        clock = SimpleNamespace(value=0.0)

        async def respond(**kwargs):
            if client.responses.create.await_count == 2:
                clock.value = 36.0
                return response(wire_round((self.candidates[1],)))
            return response(wire_round((first,)))

        client = self.make_client(())
        client.responses.create = AsyncMock(side_effect=respond)
        with patch("openai.AsyncOpenAI", return_value=client), \
             patch("citysim.reviewer.monotonic", side_effect=lambda: clock.value), \
             patch("citysim.reviewer.generate_candidates", wraps=generate_candidates) as generate:
            review, explanation = self.run_review(
                self.source, self.dataset, self.constraints,
                demo_mode=False, api_key="key", model="test-model",
            )
        self.assertEqual(client.responses.create.await_count, 2)
        self.assertEqual(review.status, "incomplete")
        self.assertEqual(len(review.checks), 1)
        self.assertEqual(review.checks[0].decisions, first)
        self.assertEqual(explanation.mode, "openai")
        self.assertIsNotNone(explanation.warning)
        generate.assert_not_called()

    def test_duplicate_and_permuted_proposals_are_deduplicated_across_rounds(self):
        candidate = self.candidates[0]
        client = self.make_client((response(wire_round((candidate,))),
                                   response(wire_round((tuple(reversed(candidate)), candidate)))))
        with patch("openai.AsyncOpenAI", return_value=client):
            review, _ = self.run_review(self.source, self.dataset, self.constraints,
                                        demo_mode=False, api_key="key", model="test-model")
        self.assertEqual(len(review.checks), 1)

    def test_over_ten_raw_candidates_makes_entire_batch_malformed(self):
        rows = [{"decisions": [{"measure_id": "M999", "district_id": "nura"}]}]
        rows.extend(wire_candidate(candidate) for candidate in self.candidates[:10])
        client = self.make_client((response({"candidates": rows}), response(wire_round(()))))
        with patch("openai.AsyncOpenAI", return_value=client):
            review, explanation = self.run_review(
                self.source, self.dataset, self.constraints,
                demo_mode=False, api_key="key", model="test-model",
            )
        self.assertEqual(len(review.checks), 20)
        self.assertNotIn("unknown_measure", {
            issue.code for check in review.checks for issue in check.errors
        })
        self.assertEqual(review.status, "completed_limited")
        self.assertEqual(explanation.mode, "demo")

    def test_invalid_row_structure_rejects_batch_atomically(self):
        bad = {"candidates": [
                               {"decisions": [{"measure_id": "M999", "district_id": "nura"}]},
                               {"decisions": [{"measure_id": "M1"}]}]}
        client = self.make_client((response(bad), response(wire_round(()))))
        with patch("openai.AsyncOpenAI", return_value=client):
            review, explanation = self.run_review(
                self.source, self.dataset, self.constraints,
                demo_mode=False, api_key="key", model="test-model",
            )
        self.assertEqual(len(review.checks), 20)
        self.assertNotIn("unknown_measure", {
            issue.code for check in review.checks for issue in check.errors
        })
        self.assertEqual(explanation.mode, "demo")

    def test_invalid_json_empty_json_empty_text_and_noncompleted_status_fallback(self):
        bad_rows = (
            {"measure_id": True, "district_id": "nura"},
            {"measure_id": 7, "district_id": "nura"},
            {"measure_id": "M1"},
        )
        replies = (
            SimpleNamespace(status="completed", output_text="{"),
            response({"candidates": []}),
            SimpleNamespace(status="completed", output_text=""),
            response(wire_round((self.candidates[0],)), status="incomplete"),
            response({"candidates": [{"decisions": [bad_rows[0]]}]}),
            response({"candidates": [{"decisions": [bad_rows[1]]}]}),
            response({"candidates": [{"decisions": [bad_rows[2]]}]}),
            response({"candidates": [{"decisions": {"wrong": "array"}}]}),
            SimpleNamespace(status="completed", output_text=(
                '{"candidates":[],"candidates":[{"decisions":[]}]}'
            )),
            SimpleNamespace(status="completed", output_text='{"candidates":[],"extra":NaN}'),
            SimpleNamespace(status="completed", output_text=" " * 65_537),
        )
        for reply in replies:
            with self.subTest(reply=reply):
                client = self.make_client((reply,))
                with patch("openai.AsyncOpenAI", return_value=client):
                    review, explanation = self.run_review(
                        self.source, self.dataset, self.constraints,
                        demo_mode=False, api_key="key", model="test-model",
                    )
                self.assertEqual(len(review.checks), 20)
                self.assertEqual(review.status, "completed_limited")
                self.assertEqual(explanation.mode, "demo")

    def test_empty_candidates_trigger_demo_fallback(self):
        client = self.make_client((response(wire_round(())),))
        with patch("openai.AsyncOpenAI", return_value=client):
            review, explanation = self.run_review(
                self.source, self.dataset, self.constraints,
                demo_mode=False, api_key="key", model="test-model",
            )
        self.assertEqual(client.responses.create.await_count, 1)
        self.assertEqual(len(review.checks), 20)
        self.assertEqual(review.status, "completed_limited")
        self.assertEqual(explanation.mode, "demo")

    def test_reviewer_sends_only_two_provider_requests(self):
        candidate = self.candidates[0]
        client = self.make_client((response(wire_round((candidate,))),
                                   response(wire_round((candidate,))),
                                   response(wire_round((candidate,)))))
        with patch("openai.AsyncOpenAI", return_value=client):
            self.run_review(self.source, self.dataset, self.constraints,
                            demo_mode=False, api_key="key", model="test-model")
        self.assertEqual(client.responses.create.await_count, 2)

    def test_fallback_caps_at_twenty_total_and_preserves_prior_checks(self):
        first_ten = self.candidates[:10]
        invalid_response = SimpleNamespace(status="completed", output_text="not-json")
        client = self.make_client((response(wire_round(first_ten)), invalid_response))
        with patch("openai.AsyncOpenAI", return_value=client):
            review, explanation = self.run_review(
                self.source, self.dataset, self.constraints,
                demo_mode=False, api_key="key", model="test-model",
            )
        self.assertEqual(len(review.checks), 20)
        self.assertTrue(all(any(check.decisions == candidate for check in review.checks)
                            for candidate in first_ten))
        self.assertEqual(review.status, "completed_limited")
        self.assertEqual(explanation.mode, "demo")

    def test_invalid_candidates_count_toward_fallback_limit(self):
        invalid = tuple(tuple(
            Decision(f"unknown-{index}-{row}", None) for row in range(5)
        ) for index in range(10))
        client = self.make_client((response(wire_round(invalid)),
                                   RuntimeError("second round failed")))
        with patch("openai.AsyncOpenAI", return_value=client):
            review, _ = self.run_review(
                self.source, self.dataset, self.constraints,
                demo_mode=False, api_key="key", model="test-model",
            )
        self.assertEqual(client.responses.create.await_count, 2)
        self.assertEqual(len(review.checks), 20)
        self.assertEqual(sum(check.result is None for check in review.checks), 10)
        self.assertEqual(sum(check.result is not None for check in review.checks), 10)
        self.assertEqual(sum("unknown_measure" in {e.code for e in check.errors}
                             for check in review.checks), 10)

    def test_two_successful_full_rounds_fill_twenty_without_fallback(self):
        first_round, second_round = self.candidates[:10], self.candidates[10:20]
        client = self.make_client((response(wire_round(first_round)),
                                   response(wire_round(second_round))))
        with patch("openai.AsyncOpenAI", return_value=client):
            review, explanation = self.run_review(
                self.source, self.dataset, self.constraints,
                demo_mode=False, api_key="key", model="test-model",
            )
        self.assertEqual(client.responses.create.await_count, 2)
        self.assertEqual(len(review.checks), 20)
        self.assertTrue(all(check.result is not None for check in review.checks))
        self.assertEqual(review.status, "completed_limited")
        self.assertEqual(explanation.mode, "openai")
        second_input = json.loads(client.responses.create.await_args_list[1].kwargs["input"])
        self.assertEqual(len(second_input["previous_checks"]), 10)

    def test_fallback_generation_failure_keeps_first_verified_best_incomplete(self):
        improved = (
            Decision("M7", "nura"), Decision("M8", "nura"),
            Decision("M10", "nura"), Decision("M12"), Decision("M14"),
        )
        client = self.make_client((response(wire_round((improved,))),
                                   RuntimeError("provider failed")))
        with patch("openai.AsyncOpenAI", return_value=client), \
             patch("citysim.reviewer.generate_candidates", side_effect=RuntimeError("local failed")) as generate:
            review, explanation = self.run_review(
                self.source, self.dataset, self.constraints,
                demo_mode=False, api_key="key", model="test-model",
            )
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(review.status, "incomplete")
        self.assertEqual(review.best.decisions, improved)
        self.assertEqual(len(review.checks), 1)
        self.assertEqual(review.checks[0].result, simulate(improved, self.dataset))
        self.assertEqual(explanation.mode, "demo")
        self.assertIsNotNone(explanation.warning)

    def test_explanation_compares_a_to_b_and_does_not_claim_optimality_or_apply_b(self):
        client = self.make_client((response(wire_round((self.candidates[0],))),
                                   response(wire_round(()))))
        with patch("openai.AsyncOpenAI", return_value=client):
            review, explanation = self.run_review(
                self.source, self.dataset, self.constraints,
                demo_mode=False, api_key="key", model="test-model",
            )
        self.assertIn("A", explanation.text)
        self.assertIn("B", explanation.text)
        self.assertIn(str(review.source.cost), explanation.text)
        self.assertIn(str(review.best.cost), explanation.text)
        self.assertIn(str(review.source.after.n_crit), explanation.text)
        self.assertIn(str(review.best.after.n_crit), explanation.text)
        self.assertNotIn("оптимал", explanation.text.lower())
        self.assertIn(f"{review.best.after.score - review.source.after.score:+.6f}",
                      explanation.text)
        self.assertNotIn(f"{review.best.score_delta:+.6f}", explanation.text)
        self.assertEqual(review.source, self.source)

    def test_fallback_warning_does_not_leak_provider_exception_details(self):
        client = self.make_client((RuntimeError("secret endpoint /private"),))
        with patch("openai.AsyncOpenAI", return_value=client):
            _, explanation = self.run_review(self.source, self.dataset, self.constraints,
                                             demo_mode=False, api_key="key", model="test-model")
        self.assertEqual(explanation.mode, "demo")
        self.assertNotIn("secret endpoint", explanation.warning or "")
        self.assertNotIn("/private", explanation.warning or "")

    def test_real_async_request_timeout_cancels_call_and_falls_back(self):
        cancelled = []

        async def slow_create(**kwargs):
            try:
                await asyncio.sleep(.05)
            except asyncio.CancelledError:
                cancelled.append(True)
                raise
            return response(wire_round(()))

        client = self.make_client(())
        client.responses.create = AsyncMock(side_effect=slow_create)
        with patch("openai.AsyncOpenAI", return_value=client), \
             patch("citysim.reviewer.REQUEST_TIMEOUT_SECONDS", .001):
            review, explanation = self.run_review(
                self.source, self.dataset, self.constraints,
                demo_mode=False, api_key="key", model="test-model",
            )
        self.assertEqual(review.status, "completed_limited")
        self.assertEqual(len(review.checks), 20)
        self.assertEqual(explanation.mode, "demo")
        self.assertEqual(cancelled, [True])

    def test_call_inside_running_event_loop_falls_back_safely(self):
        from citysim.reviewer import review_scenario

        async def call_from_loop():
            return review_scenario(
                self.source, self.dataset, self.constraints,
                demo_mode=False, api_key="key", model="test-model",
            )

        with patch("openai.AsyncOpenAI") as sdk:
            review, explanation = asyncio.run(call_from_loop())
        sdk.assert_not_called()
        self.assertEqual(review.status, "completed_limited")
        self.assertEqual(explanation.mode, "demo")
        self.assertIsNotNone(explanation.warning)


if __name__ == "__main__":
    unittest.main()
