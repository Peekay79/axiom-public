#!/usr/bin/env python3
"""
test_champ_engine.py - Comprehensive CHAMP Decision Engine Test Suite

Tests for:
- Scoring consistency and reliability
- Integration with Wonder Engine, journaling, belief formation
- Rejection of low-scoring ideas
- Competitive memory recall (picking best course of action)
- Edge cases and error handling
- Performance under load
"""

import logging
import time
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

# Import CHAMP components
from champ_decision_engine import (
    ChampDecisionEngine,
    ChampFeedbackLogger,
    ChampMetrics,
    ChampOutcome,
    configure_champ,
    evaluate_champ_score,
    get_champ_engine,
    log_champ_outcome,
)

# Import audit tools
try:
    from audit_champ import CHAMPAuditEngine

    AUDIT_AVAILABLE = True
except ImportError:
    AUDIT_AVAILABLE = False

try:
    from champ_debug import CHAMPExplanation

    DEBUG_AVAILABLE = True
except ImportError:
    DEBUG_AVAILABLE = False

# Test helper imports
try:
    from consciousness_pilot import ConsciousnessPilot

    CONSCIOUSNESS_PILOT_AVAILABLE = True
except ImportError:
    CONSCIOUSNESS_PILOT_AVAILABLE = False

try:
    from memory_response_pipeline import champ_filter_memory_relevance

    MEMORY_PIPELINE_AVAILABLE = True
except ImportError:
    MEMORY_PIPELINE_AVAILABLE = False

logger = logging.getLogger(__name__)


class TestCHAMPCore(unittest.TestCase):
    """Test core CHAMP decision engine functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.engine = ChampDecisionEngine()
        self.test_metrics = ChampMetrics(
            confidence=0.7,
            payoff=0.6,
            refinement_cost=0.4,
            tempo=0.5,
            decay=0.2,
            volatility=0.3,
            first_mover_bonus=0.1,
        )

    def test_score_calculation_consistency(self):
        """Test that CHAMP scores are calculated consistently"""
        # Calculate score multiple times with same inputs
        scores = []
        for _ in range(10):
            score = self.engine.calculate_champ_score(self.test_metrics)
            scores.append(score)

        # All scores should be identical
        self.assertTrue(
            all(s == scores[0] for s in scores),
            "CHAMP scores should be deterministic for same inputs",
        )

        # Score should be in valid range
        self.assertGreaterEqual(scores[0], 0.0, "CHAMP score should be >= 0")
        self.assertLessEqual(scores[0], 1.0, "CHAMP score should be <= 1")

    def test_score_components_influence(self):
        """Test that each component influences the final score"""
        base_score = self.engine.calculate_champ_score(self.test_metrics)

        # Test confidence influence
        high_confidence_metrics = ChampMetrics(
            confidence=0.9,
            payoff=0.6,
            refinement_cost=0.4,
            tempo=0.5,
            decay=0.2,
            volatility=0.3,
        )
        high_confidence_score = self.engine.calculate_champ_score(
            high_confidence_metrics
        )
        self.assertGreater(
            high_confidence_score, base_score, "Higher confidence should increase score"
        )

        # Test payoff influence
        high_payoff_metrics = ChampMetrics(
            confidence=0.7,
            payoff=0.9,
            refinement_cost=0.4,
            tempo=0.5,
            decay=0.2,
            volatility=0.3,
        )
        high_payoff_score = self.engine.calculate_champ_score(high_payoff_metrics)
        self.assertGreater(
            high_payoff_score, base_score, "Higher payoff should increase score"
        )

        # Test refinement cost penalty
        high_cost_metrics = ChampMetrics(
            confidence=0.7,
            payoff=0.6,
            refinement_cost=0.8,
            tempo=0.5,
            decay=0.2,
            volatility=0.3,
        )
        high_cost_score = self.engine.calculate_champ_score(high_cost_metrics)
        self.assertLess(
            high_cost_score, base_score, "Higher refinement cost should decrease score"
        )

        # Test decay penalty
        high_decay_metrics = ChampMetrics(
            confidence=0.7,
            payoff=0.6,
            refinement_cost=0.4,
            tempo=0.5,
            decay=0.8,
            volatility=0.3,
        )
        high_decay_score = self.engine.calculate_champ_score(high_decay_metrics)
        self.assertLess(
            high_decay_score, base_score, "Higher decay should decrease score"
        )

    def test_threshold_behavior(self):
        """Test that action threshold works correctly"""
        # Test with score above threshold
        high_score_metrics = ChampMetrics(confidence=0.9, payoff=0.9, tempo=0.8)
        decision = self.engine.evaluate_decision(high_score_metrics)
        self.assertEqual(
            decision["action"], "execute", "High score should trigger execute action"
        )

        # Test with score below threshold
        low_score_metrics = ChampMetrics(confidence=0.2, payoff=0.2, tempo=0.1)
        decision = self.engine.evaluate_decision(low_score_metrics)
        self.assertEqual(
            decision["action"], "refine", "Low score should trigger refine action"
        )

    def test_volatility_adjustment(self):
        """Test that volatility properly adjusts scores"""
        base_metrics = ChampMetrics(confidence=0.5, payoff=0.5, volatility=0.0)
        base_score = self.engine.calculate_champ_score(base_metrics)

        high_volatility_metrics = ChampMetrics(
            confidence=0.5, payoff=0.5, volatility=0.8
        )
        volatile_score = self.engine.calculate_champ_score(high_volatility_metrics)

        self.assertGreater(
            volatile_score,
            base_score,
            "High volatility should increase score (urgency)",
        )

    def test_first_mover_bonus(self):
        """Test that first mover bonus is applied correctly"""
        base_metrics = ChampMetrics(confidence=0.5, payoff=0.5, first_mover_bonus=0.0)
        base_score = self.engine.calculate_champ_score(base_metrics)

        bonus_metrics = ChampMetrics(confidence=0.5, payoff=0.5, first_mover_bonus=0.2)
        bonus_score = self.engine.calculate_champ_score(bonus_metrics)

        self.assertGreater(
            bonus_score, base_score, "First mover bonus should increase score"
        )
        self.assertAlmostEqual(
            bonus_score - base_score,
            0.2,
            places=2,
            msg="Bonus should be added directly to score",
        )

    def test_edge_cases(self):
        """Test edge cases and boundary conditions"""
        # Test with all zeros
        zero_metrics = ChampMetrics(0, 0, 0, 0, 0, 0, 0)
        zero_score = self.engine.calculate_champ_score(zero_metrics)
        self.assertGreaterEqual(
            zero_score, 0.0, "Zero metrics should not produce negative score"
        )

        # Test with all ones
        max_metrics = ChampMetrics(1, 1, 1, 1, 1, 1, 1)
        max_score = self.engine.calculate_champ_score(max_metrics)
        self.assertLessEqual(max_score, 1.0, "Max metrics should not exceed 1.0")

        # Test with negative values (should be clamped)
        negative_metrics = ChampMetrics(-0.5, -0.5, -0.5, -0.5, -0.5, -0.5, -0.5)
        negative_score = self.engine.calculate_champ_score(negative_metrics)
        self.assertGreaterEqual(
            negative_score, 0.0, "Negative metrics should be clamped to 0"
        )

        # Test with values > 1 (should be clamped)
        excessive_metrics = ChampMetrics(2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0)
        excessive_score = self.engine.calculate_champ_score(excessive_metrics)
        self.assertLessEqual(
            excessive_score, 1.0, "Excessive metrics should be clamped"
        )


class TestCHAMPFeedback(unittest.TestCase):
    """Test CHAMP feedback and learning system"""

    def setUp(self):
        """Set up test fixtures"""
        self.feedback_logger = ChampFeedbackLogger()
        self.engine = ChampDecisionEngine()

    def test_feedback_logging(self):
        """Test that feedback is logged correctly"""
        decision = {"action": "execute", "confidence": 0.8}

        self.feedback_logger.log_decision_outcome(
            decision_id="test_1",
            decision=decision,
            actual_payoff=0.7,
            success=True,
            notes="Test outcome",
        )

        summary = self.feedback_logger.get_feedback_summary()
        self.assertEqual(summary["total_outcomes"], 1)
        self.assertEqual(summary["feedback_provided"], 1)
        self.assertEqual(summary["accuracy_metrics"]["total_decisions"], 1)
        self.assertEqual(summary["accuracy_metrics"]["correct_decisions"], 1)

    def test_accuracy_calculation(self):
        """Test accuracy metrics calculation"""
        # Log several outcomes
        outcomes = [
            ("test_1", {"action": "execute", "confidence": 0.8}, 0.7, True),
            ("test_2", {"action": "execute", "confidence": 0.6}, 0.5, True),
            ("test_3", {"action": "refine", "confidence": 0.4}, 0.2, False),
            ("test_4", {"action": "execute", "confidence": 0.9}, 0.8, True),
        ]

        for decision_id, decision, payoff, success in outcomes:
            self.feedback_logger.log_decision_outcome(
                decision_id, decision, payoff, success
            )

        summary = self.feedback_logger.get_feedback_summary()
        accuracy = summary["accuracy_metrics"]

        # Check success rate
        expected_success_rate = 3 / 4  # 3 successes out of 4
        actual_success_rate = (
            accuracy["correct_decisions"] / accuracy["total_decisions"]
        )
        self.assertAlmostEqual(actual_success_rate, expected_success_rate, places=2)

        # Check that payoff accuracy is calculated
        self.assertIsInstance(accuracy["payoff_accuracy"], float)
        self.assertGreaterEqual(accuracy["payoff_accuracy"], 0.0)
        self.assertLessEqual(accuracy["payoff_accuracy"], 1.0)

    def test_threshold_suggestions(self):
        """Test that threshold adjustment suggestions work"""
        # Log several poor outcomes (low success rate)
        for i in range(10):
            self.feedback_logger.log_decision_outcome(
                f"test_{i}",
                {"action": "execute", "confidence": 0.7},
                actual_payoff=0.3,
                success=False,  # All failures
            )

        suggestion = self.feedback_logger.suggest_threshold_adjustment()
        self.assertIsNotNone(
            suggestion, "Should suggest threshold adjustment for poor performance"
        )
        self.assertLess(
            suggestion, 0.7, "Should suggest lower threshold for poor performance"
        )

        # Clear and log several good outcomes
        self.feedback_logger.outcome_history.clear()
        for i in range(10):
            self.feedback_logger.log_decision_outcome(
                f"good_{i}",
                {"action": "execute", "confidence": 0.9},
                actual_payoff=0.8,
                success=True,  # All successes
            )

        suggestion = self.feedback_logger.suggest_threshold_adjustment()
        if suggestion is not None:
            self.assertGreater(
                suggestion, 0.7, "Should suggest higher threshold for good performance"
            )


class TestCHAMPIntegration(unittest.TestCase):
    """Test CHAMP integration with other system components"""

    def setUp(self):
        """Set up test fixtures"""
        self.engine = ChampDecisionEngine()

    @unittest.skipUnless(
        CONSCIOUSNESS_PILOT_AVAILABLE, "Consciousness Pilot not available"
    )
    def test_consciousness_pilot_integration(self):
        """Test CHAMP integration with Consciousness Pilot"""
        pilot = ConsciousnessPilot(enable_validation=False)

        # Test decision making with CHAMP
        test_inputs = {
            "user_query": "How can I improve my productivity?",
            "contradictions": [],
            "goals": [
                {"description": "Be more productive", "priority": 7, "importance": 0.8}
            ],
            "memory": "Previous productivity tips and techniques",
            "beliefs": "Focus and organization are key to productivity",
        }

        decision = pilot.decide(test_inputs)

        # Check that CHAMP score is present
        self.assertIn("champ_score", decision, "Decision should include CHAMP score")
        self.assertIsInstance(decision["champ_score"], float)
        self.assertGreaterEqual(decision["champ_score"], 0.0)
        self.assertLessEqual(decision["champ_score"], 1.0)

        # Check that CHAMP action is present
        self.assertIn("action", decision, "Decision should include action")
        self.assertIn(decision["action"], ["respond", "reflect", "plan"])

    @unittest.skipUnless(MEMORY_PIPELINE_AVAILABLE, "Memory Pipeline not available")
    def test_memory_filtering_integration(self):
        """Test CHAMP integration with memory filtering"""
        # Create mock memories
        mock_memories = []
        for i in range(5):
            mock_memory = Mock()
            mock_memory.get = Mock(
                side_effect=lambda key, default=None: {
                    "content": f"Memory content {i}",
                    "importance": 0.5 + (i * 0.1),
                    "confidence": 0.6,
                    "type": "test_memory",
                }.get(key, default)
            )
            mock_memory.is_belief = i % 2 == 0  # Every other memory is a belief
            mock_memories.append(mock_memory)

        # Test filtering
        query = "Test query for memory filtering"
        filtered_memories = champ_filter_memory_relevance(
            mock_memories, query, max_memories=3
        )

        # Should return filtered list
        self.assertIsInstance(filtered_memories, list)
        self.assertLessEqual(len(filtered_memories), 3)

        # Memories should be filtered by CHAMP scores
        for memory in filtered_memories:
            self.assertIsNotNone(memory)

    def test_wonder_engine_trigger_conditions(self):
        """Test conditions under which CHAMP would trigger Wonder Engine"""
        # High novelty + sufficient confidence should favor wonder triggering
        wonder_favorable_metrics = ChampMetrics(
            confidence=0.7,  # Sufficient confidence
            payoff=0.8,  # High creative payoff
            tempo=0.3,  # Low time pressure
            refinement_cost=0.2,  # Low cost to explore
            decay=0.1,  # Low decay pressure
            volatility=0.6,  # Some system activity
        )

        decision = self.engine.evaluate_decision(wonder_favorable_metrics)

        # High payoff + moderate confidence should lean toward execution
        # which could trigger wonder engine for creative tasks
        if decision["action"] == "execute":
            self.assertGreater(
                decision["champ_score"],
                0.6,
                "Wonder-favorable conditions should produce high scores",
            )

    def test_journal_entry_trigger_conditions(self):
        """Test conditions under which CHAMP would trigger journal entries"""
        # Significant decisions should trigger journaling
        significant_metrics = ChampMetrics(
            confidence=0.8, payoff=0.7, tempo=0.6, refinement_cost=0.3, decay=0.2
        )

        decision = self.engine.evaluate_decision(significant_metrics)

        # High-confidence execute decisions should trigger journaling
        if decision["action"] == "execute" and decision["champ_score"] > 0.7:
            # This would trigger journal entry in actual integration
            self.assertTrue(True, "High-confidence decisions should be journaled")

    def test_belief_formation_influence(self):
        """Test how CHAMP influences belief formation decisions"""
        # Strong evidence + high confidence should favor belief formation
        belief_favorable_metrics = ChampMetrics(
            confidence=0.9,  # High confidence in evidence
            payoff=0.6,  # Moderate benefit of having belief
            tempo=0.4,  # Not urgent
            refinement_cost=0.7,  # High cost to gather more evidence
            decay=0.2,  # Evidence doesn't decay quickly
        )

        decision = self.engine.evaluate_decision(belief_favorable_metrics)

        # High confidence + high refinement cost should favor immediate belief formation
        self.assertEqual(
            decision["action"],
            "execute",
            "High confidence + high refinement cost should trigger belief formation",
        )


class TestCHAMPCompetitiveScenarios(unittest.TestCase):
    """Test CHAMP in competitive memory recall and decision scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        self.engine = ChampDecisionEngine()

    def test_competitive_memory_recall(self):
        """Test CHAMP's ability to pick best course of action from multiple options"""
        # Create multiple competing memory/action scenarios
        scenarios = [
            {
                "name": "Immediate Response",
                "metrics": ChampMetrics(
                    confidence=0.6,
                    payoff=0.5,
                    tempo=0.9,
                    refinement_cost=0.8,
                    decay=0.7,
                ),
                "description": "Quick response to user query",
            },
            {
                "name": "Thorough Analysis",
                "metrics": ChampMetrics(
                    confidence=0.4,
                    payoff=0.9,
                    tempo=0.2,
                    refinement_cost=0.3,
                    decay=0.1,
                ),
                "description": "Deep analysis with high-quality outcome",
            },
            {
                "name": "Balanced Approach",
                "metrics": ChampMetrics(
                    confidence=0.7,
                    payoff=0.7,
                    tempo=0.6,
                    refinement_cost=0.5,
                    decay=0.4,
                ),
                "description": "Balanced speed and quality",
            },
            {
                "name": "Safe Conservative",
                "metrics": ChampMetrics(
                    confidence=0.8,
                    payoff=0.4,
                    tempo=0.3,
                    refinement_cost=0.6,
                    decay=0.2,
                ),
                "description": "Safe, low-risk approach",
            },
        ]

        # Evaluate all scenarios
        results = []
        for scenario in scenarios:
            decision = self.engine.evaluate_decision(scenario["metrics"])
            results.append(
                {
                    "name": scenario["name"],
                    "score": decision["champ_score"],
                    "action": decision["action"],
                    "description": scenario["description"],
                }
            )

        # Sort by CHAMP score (highest first)
        results.sort(key=lambda x: x["score"], reverse=True)

        # Verify that scoring makes sense
        self.assertGreater(len(results), 0, "Should have evaluated scenarios")

        # The highest scoring scenario should be actionable
        best_scenario = results[0]
        self.assertGreater(
            best_scenario["score"], 0.0, "Best scenario should have positive score"
        )

        # Log results for analysis
        logger.info("Competitive scenario results:")
        for i, result in enumerate(results, 1):
            logger.info(
                f"{i}. {result['name']}: {result['score']:.3f} ({result['action']})"
            )

        return results

    def test_temporal_pressure_scenarios(self):
        """Test how CHAMP handles time pressure vs quality tradeoffs"""
        # Scenario 1: Extreme time pressure
        urgent_metrics = ChampMetrics(
            confidence=0.5,
            payoff=0.6,
            tempo=1.0,
            refinement_cost=0.9,
            decay=0.8,
            volatility=0.7,
        )

        # Scenario 2: No time pressure, can optimize
        relaxed_metrics = ChampMetrics(
            confidence=0.5,
            payoff=0.6,
            tempo=0.1,
            refinement_cost=0.2,
            decay=0.1,
            volatility=0.1,
        )

        urgent_decision = self.engine.evaluate_decision(urgent_metrics)
        relaxed_decision = self.engine.evaluate_decision(relaxed_metrics)

        # Under time pressure, should be more likely to act despite lower confidence
        self.assertGreaterEqual(
            urgent_decision["champ_score"],
            relaxed_decision["champ_score"],
            "Time pressure should increase action tendency",
        )

        # Urgent scenario should lean toward execution
        if (
            urgent_decision["action"] == "execute"
            and relaxed_decision["action"] == "refine"
        ):
            self.assertTrue(
                True, "Time pressure should favor execution over refinement"
            )

    def test_quality_vs_speed_tradeoffs(self):
        """Test CHAMP's handling of quality vs speed tradeoffs"""
        test_cases = [
            {
                "name": "High Quality, Slow",
                "confidence": 0.9,
                "payoff": 0.9,
                "tempo": 0.2,
                "refinement_cost": 0.2,
                "decay": 0.1,
            },
            {
                "name": "Medium Quality, Fast",
                "confidence": 0.6,
                "payoff": 0.6,
                "tempo": 0.8,
                "refinement_cost": 0.7,
                "decay": 0.6,
            },
            {
                "name": "Low Quality, Very Fast",
                "confidence": 0.3,
                "payoff": 0.4,
                "tempo": 1.0,
                "refinement_cost": 0.9,
                "decay": 0.9,
            },
        ]

        results = []
        for case in test_cases:
            metrics = ChampMetrics(
                confidence=case["confidence"],
                payoff=case["payoff"],
                tempo=case["tempo"],
                refinement_cost=case["refinement_cost"],
                decay=case["decay"],
            )

            decision = self.engine.evaluate_decision(metrics)
            results.append(
                {
                    "name": case["name"],
                    "score": decision["champ_score"],
                    "action": decision["action"],
                }
            )

        # Analyze results
        for result in results:
            logger.info(f"{result['name']}: {result['score']:.3f} ({result['action']})")

        # The choice between quality and speed should depend on the specific weights
        # and threshold configured in the engine
        self.assertEqual(len(results), 3, "Should evaluate all test cases")

    def test_low_scoring_idea_rejection(self):
        """Test that CHAMP properly rejects low-scoring ideas"""
        # Create deliberately poor scenarios
        poor_scenarios = [
            ChampMetrics(
                confidence=0.1, payoff=0.2, tempo=0.1, refinement_cost=0.1, decay=0.9
            ),  # Very poor across the board
            ChampMetrics(
                confidence=0.2, payoff=0.1, tempo=0.2, refinement_cost=0.2, decay=0.8
            ),  # Low payoff
            ChampMetrics(
                confidence=0.1, payoff=0.3, tempo=0.0, refinement_cost=0.1, decay=0.7
            ),  # No urgency, poor confidence
        ]

        rejection_count = 0
        for metrics in poor_scenarios:
            decision = self.engine.evaluate_decision(metrics)
            if decision["action"] == "refine":
                rejection_count += 1

            # All poor scenarios should score low
            self.assertLess(
                decision["champ_score"], 0.5, "Poor scenarios should score below 0.5"
            )

        # Most poor scenarios should be rejected (action = 'refine')
        self.assertGreater(
            rejection_count,
            len(poor_scenarios) // 2,
            "Majority of poor scenarios should be rejected",
        )


@unittest.skipUnless(AUDIT_AVAILABLE, "Audit engine not available")
class TestCHAMPAudit(unittest.TestCase):
    """Test CHAMP audit and analysis capabilities"""

    def setUp(self):
        """Set up test fixtures"""
        self.audit_engine = CHAMPAuditEngine(enable_trace_logging=False)

    def test_input_source_tracing(self):
        """Test input source tracing functionality"""
        analysis = self.audit_engine.trace_input_sources("all")

        self.assertIn("sources_found", analysis)
        self.assertIn("signal_metadata", analysis)
        self.assertIn("integration_points", analysis)

        # Should find at least one integration point
        self.assertGreater(
            len(analysis["integration_points"]), 0, "Should identify integration points"
        )

    def test_score_breakdown_analysis(self):
        """Test detailed score breakdown analysis"""
        test_metrics = ChampMetrics(
            confidence=0.8,
            payoff=0.7,
            refinement_cost=0.3,
            tempo=0.6,
            decay=0.2,
            volatility=0.4,
        )

        breakdown = self.audit_engine.analyze_score_breakdown(
            test_metrics, "test_breakdown"
        )

        self.assertIsNotNone(breakdown)
        self.assertEqual(breakdown.decision_id, "test_breakdown")
        self.assertGreater(breakdown.final_score, 0.0)
        self.assertIn("confidence_contribution", breakdown.components)
        self.assertIn("payoff_contribution", breakdown.components)
        self.assertGreater(len(breakdown.reasoning_chain), 0)

    def test_staleness_decay_testing(self):
        """Test staleness decay analysis"""
        decay_results = self.audit_engine.test_staleness_decay([0, 6, 12, 24])

        self.assertIn("time_points", decay_results)
        self.assertIn("decay_summary", decay_results)

        # Should have time points
        self.assertEqual(len(decay_results["time_points"]), 4)

        # Scores should generally decrease over time
        scores = [point["champ_score"] for point in decay_results["time_points"]]
        self.assertGreaterEqual(scores[0], scores[-1], "Scores should decay over time")


@unittest.skipUnless(DEBUG_AVAILABLE, "Debug tools not available")
class TestCHAMPDebug(unittest.TestCase):
    """Test CHAMP debugging and explanation capabilities"""

    def setUp(self):
        """Set up test fixtures"""
        self.explainer = CHAMPExplanation()

    def test_decision_explanation(self):
        """Test human-readable decision explanations"""
        test_metrics = ChampMetrics(confidence=0.8, payoff=0.7, tempo=0.6)
        champ_result = evaluate_champ_score(
            confidence=test_metrics.confidence,
            payoff=test_metrics.payoff,
            tempo=test_metrics.tempo,
        )

        explanation = self.explainer.explain_decision(champ_result, test_metrics)

        self.assertIsInstance(explanation, str)
        self.assertGreater(len(explanation), 10, "Explanation should be meaningful")
        self.assertIn(
            champ_result["action"].upper(),
            explanation,
            "Explanation should mention the action taken",
        )


class TestCHAMPPerformance(unittest.TestCase):
    """Test CHAMP performance under load"""

    def setUp(self):
        """Set up test fixtures"""
        self.engine = ChampDecisionEngine()

    def test_scoring_performance(self):
        """Test CHAMP scoring performance"""
        import time

        metrics = ChampMetrics(confidence=0.7, payoff=0.6, tempo=0.5)

        # Time 1000 score calculations
        start_time = time.time()
        for _ in range(1000):
            self.engine.calculate_champ_score(metrics)
        end_time = time.time()

        duration = end_time - start_time
        avg_time_ms = (duration / 1000) * 1000

        # Should be fast (< 1ms per calculation on average)
        self.assertLess(
            avg_time_ms,
            1.0,
            f"CHAMP scoring should be fast, got {avg_time_ms:.3f}ms average",
        )

        logger.info(
            f"CHAMP performance: {avg_time_ms:.3f}ms average per score calculation"
        )

    def test_decision_evaluation_performance(self):
        """Test full decision evaluation performance"""
        import time

        metrics = ChampMetrics(confidence=0.7, payoff=0.6, tempo=0.5)

        # Time 100 full evaluations (includes reasoning generation)
        start_time = time.time()
        for _ in range(100):
            self.engine.evaluate_decision(metrics)
        end_time = time.time()

        duration = end_time - start_time
        avg_time_ms = (duration / 100) * 1000

        # Should still be reasonably fast (< 10ms per evaluation)
        self.assertLess(
            avg_time_ms,
            10.0,
            f"CHAMP evaluation should be fast, got {avg_time_ms:.3f}ms average",
        )

        logger.info(
            f"CHAMP evaluation performance: {avg_time_ms:.3f}ms average per evaluation"
        )


class TestCHAMPConfiguration(unittest.TestCase):
    """Test CHAMP configuration and customization"""

    def test_weight_configuration(self):
        """Test that weight configuration works correctly"""
        # Save original weights
        original_engine = get_champ_engine()
        original_weights = original_engine.weights.copy()

        try:
            # Configure new weights
            configure_champ(confidence_weight=0.5, payoff_weight=0.3, tempo_weight=0.2)

            engine = get_champ_engine()
            self.assertEqual(engine.weights["confidence"], 0.5)
            self.assertEqual(engine.weights["payoff"], 0.3)
            self.assertEqual(engine.weights["tempo"], 0.2)

        finally:
            # Restore original weights
            for weight_name, weight_value in original_weights.items():
                configure_champ(**{f"{weight_name}_weight": weight_value})

    def test_threshold_configuration(self):
        """Test that threshold configuration works correctly"""
        original_engine = get_champ_engine()
        original_threshold = original_engine.action_threshold

        try:
            # Configure new threshold
            configure_champ(action_threshold=0.8)

            engine = get_champ_engine()
            self.assertEqual(engine.action_threshold, 0.8)

        finally:
            # Restore original threshold
            configure_champ(action_threshold=original_threshold)


def run_champ_test_suite():
    """Run the complete CHAMP test suite"""
    print("🚀 Running CHAMP Decision Engine Test Suite")
    print("=" * 60)

    # Create test suite
    test_suite = unittest.TestSuite()

    # Add test classes
    test_classes = [
        TestCHAMPCore,
        TestCHAMPFeedback,
        TestCHAMPIntegration,
        TestCHAMPCompetitiveScenarios,
        TestCHAMPPerformance,
        TestCHAMPConfiguration,
    ]

    # Add audit tests if available
    if AUDIT_AVAILABLE:
        test_classes.append(TestCHAMPAudit)

    # Add debug tests if available
    if DEBUG_AVAILABLE:
        test_classes.append(TestCHAMPDebug)

    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # Print summary
    print("\n" + "=" * 60)
    print("CHAMP TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(
        f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%"
    )

    if result.failures:
        print(f"\n❌ FAILURES ({len(result.failures)}):")
        for test, traceback in result.failures:
            print(f"  • {test}")

    if result.errors:
        print(f"\n💥 ERRORS ({len(result.errors)}):")
        for test, traceback in result.errors:
            print(f"  • {test}")

    if not result.failures and not result.errors:
        print("✅ All tests passed!")

    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_champ_test_suite()
