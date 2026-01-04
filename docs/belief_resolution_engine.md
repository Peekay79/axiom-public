# Belief Resolution Engine Documentation

## Overview

The Belief Resolution Engine is a sophisticated system for generating thoughtful, safe, and context-aware resolution suggestions for belief conflicts in Axiom. It integrates with multiple components to provide personalized conflict resolution strategies that consider emotional state, user preferences, belief pressure, and goal alignment.

## Table of Contents

- [Architecture](#architecture)
- [Core Components](#core-components)
- [Resolution Logic](#resolution-logic)
- [Emotional Sensitivity](#emotional-sensitivity)
- [User Preference Weighting](#user-preference-weighting)
- [API Reference](#api-reference)
- [Integration Guide](#integration-guide)
- [Examples](#examples)
- [Best Practices](#best-practices)

## Architecture

The Belief Resolution Engine follows a layered architecture:

```
┌─────────────────────────────────────────┐
│           User Interface                │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│      BeliefResolutionEngine             │
│  ┌─────────────────────────────────────┐│
│  │    Resolution Strategy Logic       ││
│  └─────────────────────────────────────┘│
│  ┌─────────────────────────────────────┐│
│  │    Emotional & Preference Models   ││
│  └─────────────────────────────────────┘│
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│         Integration Layer               │
│  ┌───────────┬──────────────┬─────────┐ │
│  │Contradiction│ Pressure    │  Goal   │ │
│  │Explainer    │ Mapper      │Inference│ │
│  └───────────┴──────────────┴─────────┘ │
└─────────────────────────────────────────┘
```

## Core Components

### 1. BeliefResolutionEngine

The main orchestrator that:
- Accepts various input formats (belief tuples, BeliefConflict objects)
- Determines optimal resolution strategies
- Generates comprehensive resolution suggestions
- Integrates with supporting systems

### 2. Resolution Types

The engine supports multiple resolution strategies:

- **CLARIFICATION**: Seek more information to understand the conflict
- **VALUE_BRIDGE**: Find common ground between conflicting values
- **CONTEXT_QUALIFIER**: Add contextual boundaries to specify applicability
- **DEFER**: Postpone resolution when timing isn't appropriate
- **SPLIT_BELIEF**: Separate beliefs into different contexts
- **REFRAME**: Change perspective on the conflict
- **EVIDENCE_ACCUMULATION**: Gather more supporting evidence
- **TEMPORAL_SEQUENCING**: Order beliefs chronologically
- **PRAGMATIC_ACCEPTANCE**: Accept practical inconsistencies
- **PRINCIPLED_RESOLUTION**: Resolve based on core values

### 3. Data Models

#### UserPreferenceProfile

Captures user preferences for belief resolution:

```python
@dataclass
class UserPreferenceProfile:
    # Resolution style preferences (0.0-1.0)
    truth_seeking_weight: float = 0.5
    harmony_weight: float = 0.5
    pragmatic_weight: float = 0.5
    principled_weight: float = 0.5
    
    # Tolerance levels
    ambiguity_tolerance: float = 0.5
    uncertainty_tolerance: float = 0.5
    change_tolerance: float = 0.5
    
    # Timing and evidence preferences
    prefers_immediate_resolution: bool = False
    evidence_threshold: float = 0.7
    emotional_sensitivity: float = 0.7
```

#### EmotionalStateSnapshot

Represents current emotional context:

```python
@dataclass
class EmotionalStateSnapshot:
    primary_emotion: str                    # e.g., "anxious", "curious"
    intensity: float                        # 0.0-1.0
    confidence: float                       # 0.0-1.0
    stress_level: float = 0.5              # Current stress/tension
    emotional_stability: float = 0.5       # How stable the state is
    openness_to_change: float = 0.5        # Willingness to update beliefs
```

#### ResolutionSuggestion

The output of the resolution process:

```python
@dataclass
class ResolutionSuggestion:
    proposed_resolution: str                # Natural language strategy
    reasoning: str                         # Explanation of approach
    resolution_type: ResolutionType       # Strategy classification
    confidence: float                      # 0.0-1.0 confidence score
    requires_human_input: bool             # Whether human oversight needed
    associated_beliefs: List[UUID]         # Involved belief IDs
    suggested_follow_ups: List[str]        # Next steps
    emotional_impact: EmotionalImpact      # Expected emotional load
    alignment_score: float                 # Fit with user values (0.0-1.0)
    pressure_score: Optional[float]        # Urgency from pressure mapping
    goal_alignment: Optional[float]        # Alignment with inferred goals
    alternative_approaches: List[Dict]     # Alternative strategies
```

## Resolution Logic

### Conflict Type Analysis

The engine analyzes conflicts by type and applies appropriate strategies:

1. **Semantic Conflicts**: Focus on clarification and context
2. **Logical Conflicts**: Emphasize evidence and logical principles  
3. **Value Conflicts**: Seek bridges and shared principles
4. **Temporal Conflicts**: Order events and add time boundaries
5. **Definitional Conflicts**: Clarify terms and scope
6. **Causal Conflicts**: Examine mechanisms and conditions

### Strategy Selection Process

```
Input Analysis → Conflict Classification → Strategy Filtering → Preference Weighting → Final Selection
      ↓                    ↓                     ↓                    ↓                ↓
  Parse input      Determine conflict     Filter by emotion    Apply user weights   Choose best fit
  Get metadata     type and severity      and context         and goal alignment    strategy
```

### Confidence Calculation

Confidence scores are calculated considering:
- Base conflict explanation confidence
- Conflict severity adjustments
- Emotional state stability
- Belief pressure levels
- Integration success rates

## Emotional Sensitivity

### Emotional Patterns

The engine recognizes emotional patterns and adapts accordingly:

| Emotion | Preferred Strategies | Avoided Strategies | Approach | Timing |
|---------|---------------------|-------------------|----------|---------|
| Anxious | Defer, Clarification | Principled Resolution | Gentle | Extended |
| Frustrated | Pragmatic Acceptance | Defer | Action-oriented | Immediate |
| Curious | Clarification, Evidence | Pragmatic Acceptance | Exploratory | Moderate |
| Defensive | Value Bridge, Context | Principled Resolution | Validating | Extended |
| Confident | Principled, Evidence | Defer | Direct | Moderate |
| Neutral | Clarification, Context | None | Balanced | Moderate |

### Emotional Impact Assessment

The engine assesses the emotional impact of different strategies:

- **Low Impact**: Defer, Clarification, Context Qualifier
- **Medium Impact**: Value Bridge, Reframe, Pragmatic Acceptance  
- **High Impact**: Principled Resolution, Split Belief

Impact levels are adjusted based on current emotional state and stability.

## User Preference Weighting

### Preference Dimensions

Users can express preferences along multiple dimensions:

1. **Truth-seeking vs. Harmony**: Prioritize accuracy vs. internal peace
2. **Pragmatic vs. Principled**: Focus on outcomes vs. values
3. **Tolerance Levels**: Comfort with ambiguity, uncertainty, change
4. **Timing Preferences**: Immediate vs. reflective resolution
5. **Evidence Standards**: Thresholds for belief updates

### Weighting Algorithm

Strategies are scored based on user preferences:

```python
def score_strategy(strategy, preferences):
    base_score = strategy_preference_mapping[strategy]
    
    # Apply preference weights
    if strategy == EVIDENCE_ACCUMULATION:
        score = preferences.truth_seeking_weight * 0.9
    elif strategy == VALUE_BRIDGE:
        score = preferences.harmony_weight * 0.9
    
    # Adjust for tolerance levels
    if strategy == DEFER:
        score *= preferences.ambiguity_tolerance
    
    return min(1.0, max(0.0, score))
```

## API Reference

### Core Functions

#### BeliefResolutionEngine

```python
class BeliefResolutionEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None)
    
    async def resolve_conflict(
        self,
        conflict_input: Union[BeliefConflict, ConflictExplanation, Tuple[Belief, Belief]],
        emotional_state: Optional[EmotionalStateSnapshot] = None,
        user_preferences: Optional[UserPreferenceProfile] = None,
        include_alternatives: bool = True
    ) -> ResolutionSuggestion
```

#### Utility Functions

```python
def create_default_user_preferences() -> UserPreferenceProfile

def extract_emotional_state_from_journal(
    recent_entries: List[Dict[str, Any]]
) -> Optional[EmotionalStateSnapshot]

async def resolve_belief_conflict(
    belief_a: Belief,
    belief_b: Belief,
    user_preferences: Optional[UserPreferenceProfile] = None,
    emotional_context: Optional[EmotionalStateSnapshot] = None
) -> ResolutionSuggestion
```

### Configuration Options

```python
config = {
    "enable_pressure_mapping": True,        # Use belief pressure scores
    "enable_goal_inference": True,          # Consider goal alignment
    "enable_emotional_modeling": True,      # Apply emotional sensitivity
    "default_confidence_threshold": 0.6,    # Minimum confidence for suggestions
    "high_pressure_threshold": 0.8,        # Pressure level requiring attention
    "emotional_sensitivity": 0.7,          # How much emotions affect decisions
    "max_alternative_suggestions": 3,      # Number of alternatives to generate
    "require_human_input_threshold": 0.4   # Confidence level requiring oversight
}
```

## Integration Guide

### With Contradiction Explainer

The engine integrates seamlessly with the existing contradiction explainer:

```python
# Automatic integration - no setup required
engine = BeliefResolutionEngine()
result = await engine.resolve_conflict((belief_a, belief_b))
# Engine automatically uses ContradictionExplainer for analysis
```

### With Belief Pressure Mapper

Enable pressure-aware resolution:

```python
config = {"enable_pressure_mapping": True}
engine = BeliefResolutionEngine(config=config)

# Pressure scores automatically influence:
# - Resolution urgency
# - Human input requirements  
# - Strategy selection
```

### With Goal Inference

Align resolutions with inferred user goals:

```python
config = {"enable_goal_inference": True}
engine = BeliefResolutionEngine(config=config)

# Goal alignment scores inform:
# - Strategy effectiveness
# - Overall alignment ratings
# - Long-term consistency
```

### With Journal Engine

Automatic logging of resolution events:

```python
# Automatic integration when journal_engine is available
# Resolution events logged with tags:
# - "belief_resolution"
# - "resolution_{strategy_type}"
# - "conflict_{conflict_type}" 
# - "impact_{emotional_impact}"
```

## Examples

### Basic Usage

```python
from belief_resolution_engine import BeliefResolutionEngine
from belief_models import Belief

# Create beliefs in conflict
belief_a = Belief(
    statement="Exercise is always good for health",
    confidence=0.8
)

belief_b = Belief(
    statement="Some exercise can be harmful",
    confidence=0.7
)

# Resolve the conflict
engine = BeliefResolutionEngine()
resolution = await engine.resolve_conflict((belief_a, belief_b))

print(f"Strategy: {resolution.resolution_type.value}")
print(f"Resolution: {resolution.proposed_resolution}")
print(f"Confidence: {resolution.confidence:.2f}")
```

### With Emotional Context

```python
from belief_resolution_engine import EmotionalStateSnapshot

# Define emotional state
emotional_state = EmotionalStateSnapshot(
    primary_emotion="anxious",
    intensity=0.8,
    stress_level=0.9
)

# Resolve with emotional sensitivity
resolution = await engine.resolve_conflict(
    (belief_a, belief_b),
    emotional_state=emotional_state
)

# Anxious state will prefer gentle approaches like clarification
assert resolution.resolution_type in [ResolutionType.DEFER, ResolutionType.CLARIFICATION]
```

### With User Preferences

```python
from belief_resolution_engine import UserPreferenceProfile

# Create truth-seeking user profile
preferences = UserPreferenceProfile(
    truth_seeking_weight=0.9,
    harmony_weight=0.2,
    evidence_threshold=0.8
)

# Resolve with user preferences
resolution = await engine.resolve_conflict(
    (belief_a, belief_b),
    user_preferences=preferences
)

# Truth-seeking preference will favor evidence-based approaches
print(f"Alignment score: {resolution.alignment_score:.2f}")
```

### Multiple Alternatives

```python
# Get resolution with alternatives
resolution = await engine.resolve_conflict(
    (belief_a, belief_b),
    include_alternatives=True
)

print(f"Primary strategy: {resolution.resolution_type.value}")
print(f"Alternatives:")
for alt in resolution.alternative_approaches:
    print(f"  - {alt['strategy']}: {alt['description']}")
```

### Complex Integration

```python
# Full integration example
from belief_resolution_engine import (
    BeliefResolutionEngine,
    UserPreferenceProfile, 
    EmotionalStateSnapshot,
    extract_emotional_state_from_journal
)

# Setup with all integrations enabled
config = {
    "enable_pressure_mapping": True,
    "enable_goal_inference": True,
    "enable_emotional_modeling": True,
    "emotional_sensitivity": 0.8
}

engine = BeliefResolutionEngine(config=config)

# Extract emotional state from journal
journal_entries = get_recent_journal_entries()  # Your function
emotional_state = extract_emotional_state_from_journal(journal_entries)

# User with specific preferences
user_preferences = UserPreferenceProfile(
    truth_seeking_weight=0.7,
    harmony_weight=0.6,
    ambiguity_tolerance=0.4,
    stress_avoidance=0.8
)

# Comprehensive resolution
resolution = await engine.resolve_conflict(
    (belief_a, belief_b),
    emotional_state=emotional_state,
    user_preferences=user_preferences,
    include_alternatives=True
)

# Rich output with all context
print(f"""
Resolution Analysis:
===================
Strategy: {resolution.resolution_type.value}
Confidence: {resolution.confidence:.2f}
Alignment: {resolution.alignment_score:.2f}
Emotional Impact: {resolution.emotional_impact.value}
Requires Human Input: {resolution.requires_human_input}

Proposed Resolution:
{resolution.proposed_resolution}

Reasoning:
{resolution.reasoning}

Follow-ups:
{chr(10).join(f"- {follow_up}" for follow_up in resolution.suggested_follow_ups)}

Pressure Score: {resolution.pressure_score or 'N/A'}
Goal Alignment: {resolution.goal_alignment or 'N/A'}
""")
```

## Best Practices

### 1. Emotional Sensitivity

- Always consider emotional context when available
- Use gentle approaches during high-stress periods
- Allow extended reflection time for anxious states
- Prefer action-oriented solutions for frustrated states

### 2. User Preference Learning

- Start with default preferences and refine over time
- Pay attention to resolution acceptance rates
- Adjust thresholds based on user feedback
- Consider context-dependent preferences

### 3. Integration Patterns

- Enable all integrations for comprehensive analysis
- Handle integration failures gracefully
- Log resolution events for learning and audit
- Monitor performance impacts of integrations

### 4. Error Handling

- Always validate input formats
- Provide meaningful error messages
- Gracefully degrade when integrations fail
- Ensure all output fields are properly populated

### 5. Performance Considerations

- Cache user preferences when possible
- Batch pressure score calculations
- Use async/await for all integrations
- Monitor resolution generation time

### 6. Testing and Validation

- Test with diverse conflict types
- Validate emotional pattern responses
- Ensure preference weighting works correctly
- Test integration failure scenarios
- Verify output format consistency

## Troubleshooting

### Common Issues

1. **Low Confidence Scores**: Check conflict explanation quality and emotional stability
2. **Inappropriate Strategy Selection**: Verify user preferences and emotional patterns
3. **Integration Failures**: Ensure all dependencies are available and configured
4. **Performance Issues**: Monitor async operation efficiency and caching

### Debug Features

- Enable detailed logging for strategy selection
- Export resolution data for analysis
- Monitor integration success rates
- Track user satisfaction with suggestions

This comprehensive documentation provides everything needed to understand, integrate, and effectively use the Belief Resolution Engine in Axiom's cognitive architecture.