# Value Inference Engine Documentation

**Version:** 1.0.0  
**Author:** Axiom Value Inference System  
**Last Updated:** 2025-01-27

## Overview

The Value Inference Engine is a sophisticated module for Axiom's cognitive architecture that deduces, tracks, and analyzes implicit value structures from beliefs, goals, actions, contradictions, emotional data, and planning decisions. It exposes which values are inferred, how they influence cognition, and where tensions or tradeoffs arise.

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Architecture](#architecture)
3. [Data Models](#data-models)
4. [Core Features](#core-features)
5. [API Reference](#api-reference)
6. [Usage Examples](#usage-examples)
7. [Integration Guide](#integration-guide)
8. [Configuration](#configuration)
9. [Testing](#testing)
10. [Performance Considerations](#performance-considerations)

## Core Concepts

### Values
Values are fundamental principles or standards that guide decision-making and behavior. The engine recognizes 15 core value types:

- **Autonomy**: Independence, self-direction, freedom of choice
- **Truth**: Accuracy, honesty, understanding, factual correctness
- **Safety**: Security, risk aversion, protection, stability
- **Curiosity**: Learning, exploration, investigation
- **Empathy**: Understanding others, compassion, emotional responsiveness
- **Efficiency**: Optimization, resource conservation, productivity
- **Creativity**: Innovation, novel solutions, artistic expression
- **Harmony**: Conflict avoidance, balance, peaceful resolution
- **Growth**: Self-improvement, development, continuous learning
- **Justice**: Fairness, equity, moral correctness
- **Loyalty**: Commitment, consistency, reliability
- **Pragmatism**: Practical solutions, utility, realistic approaches
- **Aesthetics**: Beauty, elegance, artistic appreciation
- **Transparency**: Openness, clarity, honest communication
- **Achievement**: Success, accomplishment, goal attainment

### Value Inference
The process of deducing implicit values from:
- **Belief patterns**: Repeated themes and confidence weights
- **Goal priorities**: CHAMP-scored planning objectives
- **Action choices**: Behavioral patterns and decision outcomes
- **Emotional responses**: Affective reactions to situations
- **Contradiction handling**: How conflicts are resolved

### Value Conflicts
Tensions between competing values that create internal contradictions or difficult tradeoffs. The engine detects, categorizes, and tracks these conflicts over time.

### Value Drift
Changes in the value system over time, including:
- **Emerging values**: New priorities gaining strength
- **Declining values**: Previously important values losing influence
- **Stability changes**: Shifts in how consistent values remain

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                Value Inference Engine                        │
├─────────────────────────────────────────────────────────────┤
│  Core Components:                                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ Value Inference │  │ Conflict        │  │ Trend        │ │
│  │ Logic           │  │ Detection       │  │ Analysis     │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ Pattern         │  │ Tradeoff        │  │ State        │ │
│  │ Matching        │  │ Analysis        │  │ Management   │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  Integration Layer:                                         │
│  • Belief Registry     • Planning Memory                   │
│  • Contradiction Engine • Emotional Model                  │
│  • Journaling System   • World Model Visualizer           │
├─────────────────────────────────────────────────────────────┤
│  Data Layer:                                               │
│  • Values Storage      • Conflicts Storage                 │
│  • Trends Storage      • Analytics Data                    │
└─────────────────────────────────────────────────────────────┘
```

## Data Models

### InferredValue

Core data structure representing a value inferred from behavior patterns.

```python
@dataclass
class InferredValue:
    id: UUID
    value_type: ValueType
    confidence_score: float          # 0.0-1.0: How certain we are
    influence_weight: float          # 0.0-1.0: Impact on decisions
    stability: ValueStability        # VOLATILE, EVOLVING, STABLE, CRYSTALLIZED
    
    # Evidence
    supporting_beliefs: List[UUID]
    supporting_goals: List[UUID]
    supporting_actions: List[UUID]
    contradicting_evidence: List[UUID]
    
    # Temporal tracking
    first_observed: datetime
    last_reinforced: datetime
    reinforcement_count: int
    drift_trend: float              # Positive = strengthening
    
    # Context
    dominant_contexts: List[str]    # work, learning, social, etc.
    emotional_associations: Dict[str, float]
    tags: Set[str]
```

### ValueConflict

Represents tension between competing values.

```python
@dataclass
class ValueConflict:
    id: UUID
    primary_value: UUID
    conflicting_value: UUID
    severity: ConflictSeverity      # MINOR, MODERATE, MAJOR, CRITICAL
    confidence: float
    frequency: int                  # How often this conflict occurs
    
    # Context
    triggering_contexts: List[str]
    example_situations: List[str]
    resolution_patterns: List[str]
    
    # Resolution tracking
    resolution_attempts: int
    successful_resolutions: int
    preferred_resolution_strategy: Optional[str]
```

### TradeoffAnalysis

Analysis of value tradeoffs in specific decisions.

```python
@dataclass
class TradeoffAnalysis:
    id: UUID
    situation_description: str
    competing_values: List[UUID]
    value_weights: Dict[str, float]  # Value ID -> influence weight
    
    decision_context: str
    chosen_option: str
    alternative_options: List[str]
    
    satisfaction_score: float       # How satisfied with choice
    regret_level: float            # Regret about alternatives
    tradeoff_rationale: str        # Explanation
```

### ValueTrendSnapshot

Point-in-time snapshot of the value system.

```python
@dataclass
class ValueTrendSnapshot:
    id: UUID
    timestamp: datetime
    
    top_values: List[Tuple[ValueType, float]]  # Ranked by influence
    emerging_values: List[ValueType]
    declining_values: List[ValueType]
    
    overall_coherence: float        # How well-aligned values are
    conflict_density: float         # Conflicts per value
    stability_index: float          # Overall stability
    drift_magnitude: float          # Change since last snapshot
```

## Core Features

### 1. Value Extraction & Inference

Automatically infers values from multiple sources:

#### From Beliefs
```python
# High-confidence beliefs about accuracy suggest Truth value
belief = Belief(
    statement="Accurate information is crucial for good decision making",
    confidence=0.9
)

# Engine detects truth-related keywords and high confidence
inferred_values = await engine.infer_values_from_beliefs([belief])
```

#### From Goals
```python
# CHAMP-scored goals indicate value priorities
goal = PlannedGoal(
    description="Learn advanced machine learning techniques",
    latest_champ_score={'overall_score': 0.8}
)

# Higher CHAMP scores suggest stronger value alignment
inferred_values = await engine.infer_values_from_goals([goal])
```

### 2. Conflict Detection

Identifies tensions between values:

```python
# Detects conflicts like Safety vs Curiosity
conflicts = await engine.detect_value_conflicts(beliefs, goals)

for conflict in conflicts:
    print(f"Conflict: {conflict.primary_value} vs {conflict.conflicting_value}")
    print(f"Severity: {conflict.severity}")
    print(f"Confidence: {conflict.confidence}")
```

### 3. Tradeoff Analysis

Analyzes value tradeoffs in decisions:

```python
analysis = await engine.analyze_tradeoffs(
    decision_context="Choosing development approach",
    competing_values=[ValueType.EFFICIENCY, ValueType.CREATIVITY],
    chosen_option="Use proven efficient method",
    alternative_options=["Explore creative new approach", "Hybrid solution"]
)

print(f"Satisfaction: {analysis.satisfaction_score}")
print(f"Regret: {analysis.regret_level}")
print(f"Rationale: {analysis.tradeoff_rationale}")
```

### 4. Trend Tracking

Monitors value system evolution:

```python
snapshot = await engine.track_value_drift(time_window_days=30)

print(f"Top values: {snapshot.top_values[:5]}")
print(f"Emerging: {snapshot.emerging_values}")
print(f"Declining: {snapshot.declining_values}")
print(f"Coherence: {snapshot.overall_coherence}")
```

### 5. Contextual Analysis

Provides context-aware value insights:

```python
# Get values active in work context
work_values = await engine.get_value_influences(context='work')

# Get general value landscape
all_values = await engine.get_value_influences()
```

## API Reference

### Core Methods

#### `async infer_values_from_beliefs(beliefs: List[Belief]) -> List[InferredValue]`

Infers values from belief patterns.

**Parameters:**
- `beliefs`: List of Belief objects to analyze

**Returns:** List of newly inferred values

**Example:**
```python
beliefs = [
    Belief(statement="Truth is important", confidence=0.8),
    Belief(statement="Safety first", confidence=0.9)
]
values = await engine.infer_values_from_beliefs(beliefs)
```

#### `async infer_values_from_goals(goals: List[PlannedGoal]) -> List[InferredValue]`

Infers values from planning goals with CHAMP scoring.

**Parameters:**
- `goals`: List of PlannedGoal objects

**Returns:** List of newly inferred values

#### `async detect_value_conflicts(beliefs=None, goals=None) -> List[ValueConflict]`

Detects conflicts between inferred values.

**Parameters:**
- `beliefs`: Optional belief evidence
- `goals`: Optional goal evidence

**Returns:** List of detected conflicts

#### `async analyze_tradeoffs(decision_context: str, competing_values: List[ValueType], chosen_option: str, alternative_options: List[str]) -> TradeoffAnalysis`

Analyzes value tradeoffs in decisions.

**Parameters:**
- `decision_context`: Description of decision situation
- `competing_values`: List of competing value types
- `chosen_option`: The chosen alternative
- `alternative_options`: Other options considered

**Returns:** TradeoffAnalysis object

#### `async track_value_drift(time_window_days=None) -> ValueTrendSnapshot`

Tracks changes in value system over time.

**Parameters:**
- `time_window_days`: Analysis window (default: 30 days)

**Returns:** ValueTrendSnapshot with trend data

#### `async get_value_influences(context=None) -> Dict[str, Any]`

Gets current value influences.

**Parameters:**
- `context`: Optional context filter

**Returns:** Dictionary of value influences

#### `async export_value_model(format="json") -> Dict[str, Any]`

Exports complete value model.

**Parameters:**
- `format`: Export format (currently only "json")

**Returns:** Complete value model data

### Utility Functions

#### `async create_value_inference_engine(config=None) -> ValueInferenceEngine`

Creates and initializes a value inference engine.

#### `async quick_value_analysis(beliefs: List[Belief], goals: List[PlannedGoal]) -> Dict[str, Any]`

Performs quick analysis of values from beliefs and goals.

## Usage Examples

### Basic Value Inference

```python
import asyncio
from value_inference_engine import create_value_inference_engine
from belief_models import Belief
from planning_memory import PlannedGoal

async def basic_inference():
    # Create engine
    engine = await create_value_inference_engine()
    
    # Create test beliefs
    beliefs = [
        Belief(
            statement="Accurate information leads to better decisions",
            confidence=0.9
        ),
        Belief(
            statement="Innovation requires taking calculated risks",
            confidence=0.7
        )
    ]
    
    # Infer values
    values = await engine.infer_values_from_beliefs(beliefs)
    
    for value in values:
        print(f"Inferred {value.value_type.value}: "
              f"confidence={value.confidence_score:.2f}, "
              f"influence={value.influence_weight:.2f}")

asyncio.run(basic_inference())
```

### Conflict Analysis

```python
async def analyze_conflicts():
    engine = await create_value_inference_engine()
    
    # Add some conflicting beliefs
    beliefs = [
        Belief(statement="Safety should be the top priority", confidence=0.9),
        Belief(statement="Innovation requires risk-taking", confidence=0.8),
        Belief(statement="Individual freedom is paramount", confidence=0.8),
        Belief(statement="Team harmony is essential", confidence=0.7)
    ]
    
    # Infer values and detect conflicts
    await engine.infer_values_from_beliefs(beliefs)
    conflicts = await engine.detect_value_conflicts()
    
    print(f"Detected {len(conflicts)} value conflicts:")
    for conflict in conflicts:
        print(f"  {conflict.severity.value}: "
              f"Value conflict with {conflict.confidence:.2f} confidence")

asyncio.run(analyze_conflicts())
```

### Tradeoff Decision Analysis

```python
async def analyze_decision():
    engine = await create_value_inference_engine()
    
    # Set up known values (in practice, these would be inferred)
    from value_inference_engine import InferredValue, ValueType
    
    efficiency_value = InferredValue(
        value_type=ValueType.EFFICIENCY,
        confidence_score=0.8,
        influence_weight=0.7
    )
    creativity_value = InferredValue(
        value_type=ValueType.CREATIVITY,
        confidence_score=0.7,
        influence_weight=0.6
    )
    
    engine.inferred_values[efficiency_value.id] = efficiency_value
    engine.inferred_values[creativity_value.id] = creativity_value
    
    # Analyze a decision
    analysis = await engine.analyze_tradeoffs(
        decision_context="Choosing development methodology",
        competing_values=[ValueType.EFFICIENCY, ValueType.CREATIVITY],
        chosen_option="Use agile methodology for quick iterations",
        alternative_options=[
            "Use waterfall for thorough planning",
            "Use design thinking for creative exploration"
        ]
    )
    
    print(f"Decision satisfaction: {analysis.satisfaction_score:.2f}")
    print(f"Regret level: {analysis.regret_level:.2f}")
    print(f"Rationale: {analysis.tradeoff_rationale}")

asyncio.run(analyze_decision())
```

### Value System Monitoring

```python
async def monitor_value_system():
    engine = await create_value_inference_engine()
    
    # Simulate value development over time
    # (In practice, this would happen naturally)
    
    # Initial values
    await engine.infer_values_from_beliefs([
        Belief(statement="Learning is important", confidence=0.8)
    ])
    
    # Track initial state
    snapshot1 = await engine.track_value_drift()
    print(f"Initial coherence: {snapshot1.overall_coherence:.2f}")
    
    # Add more values
    await engine.infer_values_from_beliefs([
        Belief(statement="Efficiency saves time", confidence=0.9),
        Belief(statement="Safety prevents problems", confidence=0.8)
    ])
    
    # Track changes
    snapshot2 = await engine.track_value_drift()
    print(f"Updated coherence: {snapshot2.overall_coherence:.2f}")
    print(f"Drift magnitude: {snapshot2.drift_magnitude:.2f}")
    
    # Export complete model
    model = await engine.export_value_model()
    print(f"Total values: {len(model['values'])}")
    print(f"Total conflicts: {len(model['conflicts'])}")

asyncio.run(monitor_value_system())
```

## Integration Guide

### Belief Registry Integration

```python
from belief_registry import BeliefRegistry

# The engine automatically integrates with belief registry
engine = await create_value_inference_engine()
await engine.initialize_integrations()

# Infer values from current beliefs
if engine.belief_registry:
    beliefs = await engine.belief_registry.get_all_beliefs()
    values = await engine.infer_values_from_beliefs(beliefs)
```

### Planning Memory Integration

```python
from planning_memory import PlanningMemory

# Integration with planning system
engine = await create_value_inference_engine()

# Infer values from current goals
if engine.planning_memory:
    goals = await engine.planning_memory.get_active_goals()
    values = await engine.infer_values_from_goals(goals)
```

### Journaling Integration

```python
# Value changes are automatically logged to journaling system
# when significant drift is detected

# Manual logging
if engine.journaling_enhancer:
    await engine.journaling_enhancer.add_reflection_note(
        content="Manual value reflection",
        tags=['values', 'self_analysis'],
        metadata={'source': 'value_inference_engine'}
    )
```

### World Model Integration

```python
# Values can be tagged to world model entities
model_export = await engine.export_value_model()

# Tag entities with value influences
for entity in world_model.entities:
    if entity.type == 'concept':
        # Get values relevant to this concept
        relevant_values = await engine.get_value_influences(
            context=entity.context
        )
        entity.add_tag('value_influences', relevant_values)
```

## Configuration

### Engine Configuration

```python
config = {
    'confidence_threshold': 0.6,    # Minimum confidence for value inference
    'influence_threshold': 0.5,     # Minimum influence for reporting
    'drift_threshold': 0.3,         # Threshold for significant drift
    'tracking_window_days': 30,     # Time window for trend analysis
}

engine = ValueInferenceEngine(config)
```

### Pattern Customization

```python
# Extend value patterns for domain-specific detection
custom_patterns = {
    ValueType.TRUTH: {
        'belief_keywords': ['accurate', 'factual', 'verified', 'evidence-based'],
        'goal_keywords': ['validate', 'confirm', 'check', 'verify'],
        'emotional_markers': ['satisfaction', 'confidence', 'certainty'],
        'behavioral_indicators': ['fact_checking', 'source_verification']
    }
}

# Apply custom patterns
engine.value_patterns.update(custom_patterns)
```

### Storage Configuration

```python
# Custom data directories
import os
os.environ['VALUE_DATA_DIR'] = '/custom/path/value_data'

# Files will be created at:
# /custom/path/value_data/values.jsonl
# /custom/path/value_data/conflicts.jsonl
# /custom/path/value_data/trends.jsonl
```

## Testing

### Running Tests

```bash
# Run all tests
python test_value_inference_engine.py

# Run specific test class
python -m unittest test_value_inference_engine.TestValueInferenceEngine

# Run with verbose output
python test_value_inference_engine.py -v
```

### Test Coverage

The test suite covers:
- ✅ Core value inference logic
- ✅ Pattern matching algorithms
- ✅ Conflict detection
- ✅ Tradeoff analysis
- ✅ Trend tracking
- ✅ Data model validation
- ✅ Integration scenarios
- ✅ Error handling
- ✅ Edge cases

### Mock Data

```python
from test_value_inference_engine import create_mock_beliefs, create_mock_goals

# Generate test data
beliefs = create_mock_beliefs(count=10)
goals = create_mock_goals(count=5)

# Use for testing
engine = ValueInferenceEngine()
values = await engine.infer_values_from_beliefs(beliefs)
```

## Performance Considerations

### Scalability

- **Value Storage**: JSONL format for efficient incremental updates
- **Memory Usage**: LRU caching for frequently accessed patterns
- **Processing**: Async operations for concurrent analysis
- **Snapshots**: Limited retention (100 snapshots) to control memory

### Optimization Tips

1. **Batch Processing**: Process multiple beliefs/goals together
2. **Context Filtering**: Use context filters to reduce processing scope
3. **Confidence Thresholds**: Adjust thresholds to focus on high-confidence values
4. **Periodic Cleanup**: Remove low-confidence values periodically

```python
# Efficient batch processing
beliefs = await belief_registry.get_beliefs_batch(limit=100)
values = await engine.infer_values_from_beliefs(beliefs)

# Context-specific analysis
work_values = await engine.get_value_influences(context='work')

# Cleanup low-confidence values
for value_id, value in list(engine.inferred_values.items()):
    if value.confidence_score < 0.3:
        del engine.inferred_values[value_id]
```

### Monitoring

```python
# Check engine statistics
stats = engine.inference_stats
print(f"Total inferences: {stats['total_inferences']}")
print(f"High confidence values: {stats['high_confidence_values']}")
print(f"Conflicts detected: {stats['conflicts_detected']}")
```

## Future Enhancements

### Planned Features

1. **Machine Learning Integration**
   - Neural pattern recognition for complex value inference
   - Automated pattern discovery from large datasets
   - Predictive modeling for value drift

2. **Advanced Conflict Resolution**
   - Sophisticated resolution strategy recommendation
   - Historical resolution success tracking
   - Context-aware resolution approaches

3. **Real-time Processing**
   - Stream processing for continuous value updates
   - Event-driven value inference triggers
   - Live value system monitoring

4. **Visualization**
   - Interactive value network graphs
   - Temporal value evolution charts
   - Conflict resolution workflows

### Extension Points

```python
# Custom value types
class CustomValueType(Enum):
    SUSTAINABILITY = "sustainability"
    INNOVATION = "innovation"

# Custom pattern matchers
class DomainSpecificMatcher:
    def match_pattern(self, text: str, domain: str) -> float:
        # Domain-specific pattern matching logic
        pass

# Custom conflict resolvers
class AdvancedConflictResolver:
    def suggest_resolution(self, conflict: ValueConflict) -> str:
        # Advanced resolution suggestion logic
        pass
```

## Troubleshooting

### Common Issues

1. **No Values Inferred**
   - Check confidence thresholds
   - Verify belief/goal content has recognizable patterns
   - Review pattern keywords for relevance

2. **Too Many Conflicts**
   - Adjust conflict detection sensitivity
   - Review value pattern overlap
   - Consider context-specific analysis

3. **Performance Issues**
   - Implement batch processing
   - Use context filtering
   - Optimize pattern matching

### Debug Mode

```python
import logging
logging.getLogger('value_inference_engine').setLevel(logging.DEBUG)

# Detailed inference logging
values = await engine.infer_values_from_beliefs(beliefs)
```

### State Inspection

```python
# Inspect current state
print(f"Active values: {len(engine.inferred_values)}")
print(f"Active conflicts: {len(engine.value_conflicts)}")
print(f"Trend snapshots: {len(engine.trend_snapshots)}")

# Export for analysis
model = await engine.export_value_model()
with open('debug_model.json', 'w') as f:
    json.dump(model, f, indent=2)
```

---

**Documentation Version:** 1.0.0  
**Engine Version:** 1.0.0  
**Last Updated:** 2025-01-27

For additional support or questions, please refer to the test suite examples or create an issue in the project repository.