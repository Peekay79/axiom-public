# Goal Drive Engine Documentation

## Table of Contents

1. [Overview](#overview)
2. [Theory of Operation](#theory-of-operation)
3. [Architecture](#architecture)
4. [API Reference](#api-reference)
5. [Configuration](#configuration)
6. [Usage Examples](#usage-examples)
7. [Integration Guide](#integration-guide)
8. [Performance Considerations](#performance-considerations)
9. [Troubleshooting](#troubleshooting)

## Overview

The Goal Drive Engine is a sophisticated cognitive system that infers goals from beliefs, tracks motivational drive strengths, detects conflicts between competing objectives, and recommends actions to pursue identified goals. It forms a core component of the Axiom cognitive architecture, bridging belief systems with actionable decision-making.

### Key Features

- **Goal Inference**: Automatically detects implicit and explicit goals from belief statements using semantic analysis
- **Drive Tracking**: Models the temporal evolution of goal drive strengths with emotional and contextual modulation
- **Conflict Detection**: Identifies and resolves motivational conflicts between competing goals
- **Action Selection**: Generates prioritized action recommendations based on utility optimization
- **Graph Analysis**: Maintains a Goal Influence Graph (GIG) to understand goal relationships
- **Integration**: Seamlessly works with belief systems, emotional modeling, and journaling components

## Theory of Operation

### Goal Emergence

Goals emerge from beliefs through pattern recognition and semantic analysis. The system recognizes several types of goal indicators:

1. **Explicit Intentions**: Direct statements of intention ("I want to...", "I plan to...")
2. **Implicit Desires**: Statements expressing preferences or values
3. **Obligation Patterns**: Normative statements indicating what "should" be done
4. **Avoidance Goals**: Things to prevent or stop doing
5. **Emergent Themes**: Goals that arise from clusters of related beliefs

### Drive Strength Dynamics

Goal drive strength represents the current motivational pressure toward a particular objective. It evolves according to several factors:

```
new_drive = (decayed_drive + pressure_level) × modulation_factor × contradiction_factor
```

Where:
- **Decayed Drive**: Previous drive strength reduced by temporal decay
- **Pressure Level**: Environmental and contextual pressure
- **Modulation Factor**: Emotional amplification or suppression
- **Contradiction Factor**: Impact of belief contradictions

### Motivational Conflict Theory

The system models six types of motivational conflicts:

1. **Resource Competition**: Goals competing for limited time, attention, or resources
2. **Value Contradiction**: Goals representing incompatible values or principles
3. **Temporal Conflict**: Goals with conflicting timeline demands
4. **Approach-Avoidance**: Wanting something while fearing its consequences
5. **Double Bind**: Situations where all options have negative consequences
6. **Priority Clash**: Multiple urgent goals demanding immediate attention

### Action Utility Model

Actions are evaluated using a utility function that considers:

```
utility = (alignment × confidence × goal_drive) + urgency_bonus - cost_penalty + emotion_factor
```

## Architecture

### Core Components

```
GoalDriveEngine
├── GoalInferenceEngine      # Infers goals from beliefs
├── DriveTrackingEngine      # Tracks drive strength evolution
├── ActionSelectionEngine    # Generates action recommendations
├── MotivationalConflictResolver  # Detects and resolves conflicts
└── GoalInfluenceGraph      # Maintains goal relationship graph
```

### Data Flow

1. **Input**: Beliefs, emotional state, user preferences, recent events
2. **Goal Inference**: Extract goals from belief patterns
3. **Graph Update**: Add goals and relationships to influence graph
4. **Drive Update**: Calculate new drive strengths with modulation
5. **Conflict Detection**: Identify motivational conflicts
6. **Action Generation**: Create prioritized action recommendations
7. **Output**: Comprehensive analysis with goals, conflicts, and actions

### Goal Influence Graph (GIG)

The GIG is a directed weighted graph where:
- **Nodes**: InferredGoal objects with associated metadata
- **Edges**: Relationships (support, conflict, dependency, hierarchy)
- **Weights**: Strength of relationships (0.0-1.0)

Graph analysis provides:
- Most influential goals (centrality measures)
- Conflict tracing and path analysis
- Unstable clusters identification
- Community detection

## API Reference

### GoalDriveEngine

The main orchestrating class for the goal drive system.

```python
class GoalDriveEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None, silent_mode: bool = False)
    
    def process_beliefs(self, 
                       beliefs: List[Belief],
                       emotional_state: Optional[EmotionalStateSnapshot] = None,
                       user_preferences: Optional[UserPreferenceProfile] = None,
                       contradiction_pressure: Optional[Dict[UUID, float]] = None,
                       recent_events: Optional[List[str]] = None) -> Dict[str, Any]
    
    def get_current_goals(self, filter_by_state: Optional[List[DriveState]] = None) -> List[InferredGoal]
    def get_goal_by_id(self, goal_id: UUID) -> Optional[InferredGoal]
    def force_goal_update(self, goal_id: UUID, updates: Dict[str, Any]) -> bool
    def simulate_goal_satisfaction(self, goal_id: UUID, satisfaction_level: float = 1.0) -> bool
    def get_statistics(self) -> Dict[str, Any]
```

### Core Data Classes

#### InferredGoal

Represents a goal inferred from beliefs and cognitive patterns.

```python
@dataclass
class InferredGoal:
    id: UUID
    goal_statement: str
    category: GoalCategory
    confidence: float           # How sure we are this is a real goal (0.0-1.0)
    importance: float          # How significant this goal is (0.0-1.0)
    urgency: float            # How time-sensitive this goal is (0.0-1.0)
    drive_strength: float     # Current motivational pressure (0.0-1.0)
    state: DriveState         # Current state (dormant, emerging, active, etc.)
    priority: GoalPriority    # Priority level (critical, high, medium, low)
    
    # Temporal aspects
    created_at: datetime
    last_activated: Optional[datetime]
    last_satisfied: Optional[datetime]
    estimated_timeline: Optional[str]  # "immediate", "short_term", "long_term"
    
    # Relationships
    supporting_beliefs: List[UUID]
    conflicting_beliefs: List[UUID]
    parent_goals: List[UUID]
    sub_goals: List[UUID]
    
    # Metadata
    tags: Set[str]
    source_patterns: List[str]
    emotional_associations: Dict[str, float]
```

#### GoalDriveSnapshot

Captures the state of goal drives at a specific moment for temporal tracking.

```python
@dataclass
class GoalDriveSnapshot:
    timestamp: datetime
    goal_id: UUID
    drive_strength: float
    pressure_level: float
    modulation_factor: float
    trend_direction: str       # "increasing", "decreasing", "stable"
    triggering_events: List[str]
    emotional_context: Optional[str]
    conflict_level: float
```

#### ActionCandidate

Represents a potential action to pursue a goal.

```python
@dataclass
class ActionCandidate:
    id: UUID
    description: str
    action_type: ActionType
    alignment_score: float     # How well this serves the goal (0.0-1.0)
    urgency: float            # How time-sensitive this action is (0.0-1.0)
    resource_cost: float      # How much effort/resources needed (0.0-1.0)
    confidence: float         # How sure we are this will work (0.0-1.0)
    emotional_impact: float   # Expected emotional effect (-1.0 to 1.0)
    target_goal_id: UUID
    prerequisites: List[str]
    expected_outcomes: List[str]
    potential_risks: List[str]
```

#### MotivationalConflict

Represents a conflict between goals or drives.

```python
@dataclass
class MotivationalConflict:
    id: UUID
    conflict_type: ConflictType
    primary_goal_id: UUID
    secondary_goal_id: UUID
    intensity: float          # How severe the conflict is (0.0-1.0)
    stability: float          # How persistent this conflict is (0.0-1.0)
    resolution_urgency: float # How urgently this needs resolution (0.0-1.0)
    description: str
    root_causes: List[str]
    impact_areas: List[str]
```

### Enums

#### GoalCategory
- `SURVIVAL`: Basic needs, safety
- `ACHIEVEMENT`: Performance, accomplishment
- `RELATIONSHIP`: Social connections, belonging
- `GROWTH`: Learning, self-improvement
- `PURPOSE`: Meaning, contribution
- `AUTONOMY`: Independence, control
- `SECURITY`: Stability, predictability
- `CREATIVITY`: Expression, innovation
- `TRUTH_SEEKING`: Understanding, knowledge
- `HARMONY`: Peace, balance, consistency

#### DriveState
- `DORMANT`: Below activation threshold
- `EMERGING`: Building pressure
- `ACTIVE`: Above activation threshold
- `CONFLICTED`: In tension with other goals
- `SATISFIED`: Recently fulfilled
- `SUPPRESSED`: Actively inhibited

#### ActionType
- `INFORMATION_GATHERING`: Research and learning
- `BELIEF_EXPLORATION`: Examining belief systems
- `BEHAVIOR_CHANGE`: Modifying actions or habits
- `COMMUNICATION`: Interpersonal interaction
- `PLANNING`: Strategic preparation
- `REFLECTION`: Self-examination
- `CONFLICT_RESOLUTION`: Addressing tensions
- `GOAL_REFINEMENT`: Clarifying objectives

## Configuration

### Engine Configuration

```python
config = {
    'inference': {
        'confidence_threshold': 0.1,    # Minimum confidence for goal inclusion
        'max_goals': 12                 # Maximum active goals
    },
    'tracking': {
        'decay_rate': 0.95,            # Daily decay factor for drive strength
        'history_file': 'data/logs/goal_drive_history.jsonl'
    },
    'action_selection': {
        'max_actions_per_goal': 3,     # Maximum actions per goal
        'total_action_limit': 10       # Total action recommendations
    },
    'conflict_resolution': {
        'conflict_threshold': 0.6      # Threshold for conflict detection
    }
}
```

### User Preference Profile

```python
preferences = UserPreferenceProfile(
    truth_seeking_weight=0.8,      # Priority on accuracy and understanding
    harmony_weight=0.6,            # Priority on internal consistency
    pragmatic_weight=0.7,          # Priority on practical outcomes
    principled_weight=0.9,         # Priority on value alignment
    ambiguity_tolerance=0.4,       # Comfort with unresolved conflicts
    uncertainty_tolerance=0.5,     # Comfort with "don't know"
    emotional_sensitivity=0.7,     # How much emotions affect decisions
    stress_avoidance=0.6          # Preference to avoid high-stress resolutions
)
```

## Usage Examples

### Basic Usage

```python
from goal_drive_engine import create_default_goal_drive_engine, EmotionalStateSnapshot
from belief_models import Belief

# Create beliefs
beliefs = [
    Belief(
        statement="I want to learn machine learning",
        confidence=0.8,
        importance=0.7,
        tags={'learning', 'AI', 'skills'}
    ),
    Belief(
        statement="I should improve my health",
        confidence=0.9,
        importance=0.8,
        tags={'health', 'wellness'}
    )
]

# Create emotional context
emotional_state = EmotionalStateSnapshot(
    primary_emotion="motivated",
    intensity=0.7,
    confidence=0.8
)

# Process beliefs
engine = create_default_goal_drive_engine()
result = engine.process_beliefs(beliefs, emotional_state=emotional_state)

# Examine results
print(f"Inferred {len(result['inferred_goals'])} goals")
print(f"Detected {len(result['motivational_conflict_report']['conflicts'])} conflicts")
print(f"Recommended {len(result['action_recommendations']['recommendations'])} actions")
```

### Advanced Processing

```python
from goal_drive_engine import GoalDriveEngine, UserPreferenceProfile

# Custom configuration
config = {
    'inference': {'confidence_threshold': 0.2, 'max_goals': 15},
    'tracking': {'decay_rate': 0.98},
    'action_selection': {'total_action_limit': 15}
}

# User preferences
preferences = UserPreferenceProfile(
    truth_seeking_weight=0.9,
    harmony_weight=0.4,
    pragmatic_weight=0.8,
    emotional_sensitivity=0.6
)

# Create engine with custom config
engine = GoalDriveEngine(config=config)

# Process with full context
result = engine.process_beliefs(
    beliefs=beliefs,
    emotional_state=emotional_state,
    user_preferences=preferences,
    recent_events=["Started online course", "Joined gym", "Read AI paper"]
)

# Access specific components
goals = result['inferred_goals']
graph = result['goal_influence_graph']
conflicts = result['motivational_conflict_report']
actions = result['action_recommendations']
```

### Goal Manipulation

```python
# Get current goals
current_goals = engine.get_current_goals()
active_goals = engine.get_current_goals(filter_by_state=[DriveState.ACTIVE])

# Update specific goal
if current_goals:
    goal_id = current_goals[0]['id']
    success = engine.force_goal_update(goal_id, {
        'importance': 0.95,
        'urgency': 0.8
    })
    
    # Simulate goal satisfaction
    engine.simulate_goal_satisfaction(goal_id, satisfaction_level=0.7)
```

### Graph Analysis

```python
# Access goal influence graph
graph = engine.goal_influence_graph

# Find most influential goals
influential_goals = graph.get_most_influential_goals(n=5)
for goal_id, influence_score in influential_goals:
    goal = graph.get_goal(goal_id)
    print(f"{goal.goal_statement}: {influence_score:.3f}")

# Trace conflicts
conflicts = graph.trace_goal_conflicts()
for conflict in conflicts:
    print(f"Conflict between goals: weight={conflict['conflict_weight']}")

# Identify unstable clusters
unstable = graph.identify_unstable_clusters()
for cluster in unstable:
    print(f"Unstable cluster: {cluster['size']} goals, {cluster['conflict_ratio']:.2f} conflict ratio")
```

## Integration Guide

### With Belief System

The Goal Drive Engine integrates seamlessly with the existing belief system:

```python
from belief_registry import BeliefRegistry
from goal_drive_engine import process_beliefs_for_goals

# Get beliefs from registry
registry = BeliefRegistry()
recent_beliefs = registry.get_recent_beliefs(days=7)

# Process for goals
result = process_beliefs_for_goals(recent_beliefs)
```

### With Emotional Modeling

Emotional states modulate goal drive strengths:

```python
from belief_resolution_engine import EmotionalStateSnapshot

# Different emotions affect different goal categories
emotional_contexts = {
    'anxious': EmotionalStateSnapshot("anxious", intensity=0.8),      # Boosts security goals
    'excited': EmotionalStateSnapshot("excited", intensity=0.7),     # Boosts achievement goals
    'curious': EmotionalStateSnapshot("curious", intensity=0.6),     # Boosts truth-seeking goals
}

for emotion, state in emotional_contexts.items():
    result = engine.process_beliefs(beliefs, emotional_state=state)
    print(f"Under {emotion} emotion: {len(result['inferred_goals'])} goals")
```

### With Journaling System

The engine automatically journals significant events when integrated:

```python
# Journaling is automatic if journal_engine is available
# Journal entries include:
# - Goal inference events
# - Conflict detection
# - Action recommendations
# - Drive strength changes

# Manual journal integration
if hasattr(result, 'journal_data'):
    journal_data = result['journal_data']
    # Process journal data as needed
```

### With Contradiction Analysis

The system integrates with contradiction detection:

```python
from contradiction_explainer import ContradictionExplainer

# Contradiction pressure affects drive strength
explainer = ContradictionExplainer()
contradictions = explainer.find_contradictions(beliefs)

# Create pressure map
pressure_map = {}
for contradiction in contradictions:
    for belief_id in contradiction.involved_beliefs:
        pressure_map[belief_id] = contradiction.severity

# Process with contradiction pressure
result = engine.process_beliefs(
    beliefs,
    contradiction_pressure=pressure_map
)
```

## Performance Considerations

### Scalability

- **Belief Count**: Tested up to 100 beliefs with reasonable performance
- **Goal Limit**: Default maximum of 12 active goals prevents explosion
- **Graph Size**: Automatically prunes stale goals to maintain performance
- **Processing Time**: Typically < 5 seconds for normal workloads

### Memory Usage

- **Goal Persistence**: Goals are maintained across processing cycles
- **History Logging**: Drive snapshots logged to JSONL files
- **Graph Storage**: In-memory graph with optional serialization
- **Cleanup**: Automatic removal of low-drive, old goals

### Optimization Tips

1. **Use Silent Mode**: For automated processing, enable `silent_mode=True`
2. **Batch Processing**: Process beliefs in batches rather than individually
3. **Configure Limits**: Adjust `max_goals` and action limits based on needs
4. **Filter Beliefs**: Pre-filter low-quality beliefs before processing
5. **Monitor Statistics**: Use `get_statistics()` to track performance

## Troubleshooting

### Common Issues

#### No Goals Inferred

**Symptoms**: Empty `inferred_goals` list
**Causes**:
- Beliefs lack clear intent patterns
- Confidence threshold too high
- Empty or very short belief statements

**Solutions**:
```python
# Lower confidence threshold
config = {'inference': {'confidence_threshold': 0.05}}

# Check belief quality
for belief in beliefs:
    print(f"'{belief.statement}' - confidence: {belief.confidence}")

# Add more explicit intent words
belief.statement = "I want to " + belief.statement
```

#### Excessive Conflicts

**Symptoms**: Many conflicts detected, high emotional load
**Causes**:
- Conflicting belief sets
- Low conflict threshold
- Competing high-priority goals

**Solutions**:
```python
# Raise conflict threshold
config = {'conflict_resolution': {'conflict_threshold': 0.8}}

# Review goal priorities
active_goals = engine.get_current_goals(filter_by_state=[DriveState.ACTIVE])
for goal in active_goals:
    if goal.priority == GoalPriority.CRITICAL:
        print(f"Critical goal: {goal.goal_statement}")
```

#### Poor Action Recommendations

**Symptoms**: Irrelevant or low-quality actions
**Causes**:
- Insufficient user preference data
- Misaligned emotional state
- Generic goal statements

**Solutions**:
```python
# Provide detailed user preferences
preferences = UserPreferenceProfile(
    truth_seeking_weight=0.9,  # Specific to user
    pragmatic_weight=0.8,      # Adjust based on user style
    emotional_sensitivity=0.7   # Consider user's emotional responsiveness
)

# Refine goal statements
engine.force_goal_update(goal_id, {
    'goal_statement': "Learn Python for data science applications",  # More specific
    'importance': 0.9
})
```

### Debugging Tools

#### Statistics Monitoring

```python
stats = engine.get_statistics()
print(f"Total runs: {stats['total_runs']}")
print(f"Goals inferred: {stats['goals_inferred']}")
print(f"Current goals: {stats['current_goals_count']}")
print(f"Graph density: {stats['graph_statistics']['density']}")
```

#### Drive History Analysis

```python
# Examine drive evolution for specific goal
history = engine.drive_tracking_engine.get_drive_history(goal_id, days=30)
for snapshot in history[-5:]:  # Last 5 snapshots
    print(f"{snapshot.timestamp}: drive={snapshot.drive_strength:.3f}, "
          f"trend={snapshot.trend_direction}")
```

#### Verbose Processing

```python
# Enable detailed logging
engine = GoalDriveEngine(silent_mode=False)

# Process with debug information
result = engine.process_beliefs(beliefs)
# Check logs in data/logs/goal_drive.log
```

### Error Recovery

The system includes several error recovery mechanisms:

1. **Graceful Degradation**: Invalid inputs result in empty results rather than crashes
2. **Silent Mode**: Production use should enable silent mode to handle errors gracefully
3. **State Persistence**: Goal state is maintained even if individual processing cycles fail
4. **Configuration Validation**: Invalid configuration values are ignored or corrected

For persistent issues, consider:
- Reviewing belief quality and format
- Checking integration with external systems
- Validating configuration parameters
- Examining log files for detailed error information

---

## API Quick Reference

### Main Functions
- `create_default_goal_drive_engine(silent_mode=False)` - Create engine with defaults
- `process_beliefs_for_goals(beliefs, emotional_state=None, user_preferences=None, engine=None)` - Convenience function

### Key Methods
- `engine.process_beliefs(beliefs, ...)` - Main processing method
- `engine.get_current_goals(filter_by_state=None)` - Get current goals
- `engine.get_statistics()` - Get processing statistics
- `graph.get_most_influential_goals(n=5)` - Get influential goals
- `graph.trace_goal_conflicts()` - Find goal conflicts

### Data Classes
- `InferredGoal` - Goal with drive strength and metadata
- `GoalDriveSnapshot` - Temporal drive state capture
- `ActionCandidate` - Recommended action with utility scoring
- `MotivationalConflict` - Conflict between goals
- `EmotionalStateSnapshot` - Emotional context
- `UserPreferenceProfile` - User preference weights