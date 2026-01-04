# Planning Memory System Documentation

## Overview

The Planning Memory system is a core component of Axiom that tracks planned goals and actions over time. It integrates with the CHAMP (Confidence Heuristic for Action Measured by Payoff) algorithm for intelligent decision-making and includes sophisticated features for recurring goals, belief-triggered reactivation, and comprehensive planning analytics.

### Key Features

- **CHAMP-Integrated Goal Evaluation**: Automatic scoring based on confidence, tempo, and payoff
- **Recurring Goal Templates**: Automated instantiation of daily, weekly, and monthly goals
- **Belief-Triggered Reactivation**: Smart reactivation of dropped goals based on belief context
- **Drive Strength Tracking**: Longitudinal tracking of goal motivation over time
- **Comprehensive Analytics**: Detailed statistics on goal completion, decay, and performance
- **Action Management**: Linked actions with execution tracking and goal impact feedback

## Architecture

### Data Models

#### PlannedGoal

The core goal representation with the following key attributes:

```python
@dataclass
class PlannedGoal:
    # Core identity
    goal_id: str
    goal_text: str
    
    # Belief integration
    inferred_from_belief_ids: List[str]
    
    # Temporal data
    created_at: datetime
    target_timeframe: Optional[Union[datetime, str]]
    deadline: Optional[datetime]
    last_updated: datetime
    next_review_date: Optional[datetime]
    
    # Scoring and evaluation
    urgency_score: float
    priority_confidence: float  # Current CHAMP score
    drive_strength_over_time: List[DriveStrengthEntry]
    champ_score_log: List[ChampScoreEntry]
    
    # Recurrence and lifecycle
    recurrence: Optional[str]
    recurrence_template_id: Optional[str]
    status: str  # active, completed, deferred, dropped, recurring_template
```

#### ActionCandidate

Actions linked to goals for execution tracking:

```python
@dataclass
class ActionCandidate:
    action_id: str
    goal_id: str
    action_text: str
    expected_impact: float
    confidence: float
    status: str  # pending, completed, skipped, failed
    execution_log: List[Dict[str, Any]]
    blocker_beliefs: List[str]
    repeat_pattern: Optional[str]
```

### Status Lifecycle

Goals progress through the following states:

1. **ACTIVE**: Currently being pursued
2. **COMPLETED**: Successfully achieved
3. **DEFERRED**: Temporarily paused
4. **DROPPED**: Abandoned or no longer relevant
5. **RECURRING_TEMPLATE**: Template for generating recurring instances

## CHAMP Integration

### CHAMP Score Calculation

The system calculates CHAMP scores based on:

- **Confidence**: Drive strength trend + belief support
- **Payoff**: Goal urgency and importance
- **Tempo**: Deadline proximity and staleness
- **Decay**: Time since last update

```python
# Example CHAMP evaluation
champ_score = (confidence * payoff * tempo) * (1.0 - decay)
```

### Decision Heuristics

CHAMP scores influence:

- **Deadline Assignment**: High CHAMP scores get near-term deadlines
- **Review Scheduling**: Low scores trigger more frequent reviews
- **Resource Allocation**: Priority ordering for action execution

## Recurring Goals

### Template System

Create recurring goal templates:

```python
# Create a daily recurring template
planning_memory.add_goal(
    goal_text="Daily reflection and journaling",
    urgency_score=0.7,
    recurrence="daily"
)

# The system will create "recurring_template" status
# Auto-instantiate daily instances at 8:00 AM
```

### Supported Patterns

- **DAILY**: Creates new instance each day at 8:00 AM
- **WEEKLY**: Creates instance at start of week (Monday 8:00 AM)
- **MONTHLY**: Creates instance at start of month (1st at 8:00 AM)
- **CUSTOM**: User-defined patterns (basic implementation)

### Auto-Instantiation

Call `schedule_recurring_goals()` to generate new instances:

```python
new_goals = planning_memory.schedule_recurring_goals()
print(f"Created {len(new_goals)} new recurring goal instances")
```

## Belief Triggers and Reactivation

### Review System

The system automatically reviews goals for:

- **Drive Strength Decay**: Motivation dropping below threshold
- **CHAMP Score Drops**: Significant score decreases
- **Staleness**: Goals not updated in configured timeframe
- **Scheduled Reviews**: Regular review cycles

### Belief Relevance Assessment

Dropped goals are assessed for reactivation based on:

1. **Active Belief Context**: Are source beliefs still relevant?
2. **Confidence Levels**: Belief strength and quality
3. **Contextual Relevance**: Current system state and priorities

### Reactivation Recommendations

The system provides structured recommendations:

```python
reviews = planning_memory.review_dropped_goals()
for review in reviews:
    print(f"Goal: {review['goal_text']}")
    print(f"Reason: {review['review_reason']}")
    print(f"Recommendation: {review['recommended_action']}")
    print(f"Belief Relevance: {review['belief_relevance_score']}")
```

## Usage Examples

### Basic Goal Management

```python
from planning_memory import PlanningMemory
from champ_decision_engine import ChampDecisionEngine

# Initialize system
champ_engine = ChampDecisionEngine()
planning_memory = PlanningMemory(champ_engine=champ_engine)

# Add a new goal
goal = planning_memory.add_goal(
    goal_text="Implement new AI safety protocols",
    inferred_from_beliefs=["belief_123", "belief_456"],
    target_timeframe="next week",
    urgency_score=0.8
)

# Log drive strength over time
planning_memory.log_drive_strength(
    goal.goal_id, 
    score=0.9, 
    notes="High motivation after safety meeting"
)

# Update goal status
planning_memory.update_goal_status(
    goal.goal_id, 
    "completed",
    notes="Successfully implemented new protocols"
)
```

### Action Management

```python
# Add actions to a goal
action = planning_memory.add_action(
    goal_id=goal.goal_id,
    action_text="Research current safety frameworks",
    expected_impact=0.6,
    confidence=0.8
)

# Update action status
planning_memory.update_action_status(
    action.action_id,
    "completed",
    notes="Completed comprehensive literature review"
)
```

### Analytics and Monitoring

```python
# Generate comprehensive statistics
stats = planning_memory.generate_planning_stats()
print(f"Goal completion rate: {stats['goals']['completion_rate']:.1%}")
print(f"Average CHAMP score: {stats['performance']['avg_champ_score']:.2f}")
print(f"Overdue goals: {stats['goals']['overdue_percentage']:.1%}")

# Get prioritized active goals
priority_goals = planning_memory.get_active_goals_by_priority()
for goal in priority_goals[:5]:  # Top 5
    print(f"{goal.goal_text} (CHAMP: {goal.priority_confidence:.2f})")

# Check overdue goals
overdue = planning_memory.get_overdue_goals()
if overdue:
    print(f"⚠️ {len(overdue)} goals are overdue!")
```

### Recurring Goal Management

```python
# Create recurring templates
daily_goal = planning_memory.add_goal(
    goal_text="Daily system health check",
    urgency_score=0.6,
    recurrence="daily"
)

weekly_goal = planning_memory.add_goal(
    goal_text="Weekly performance analysis",
    urgency_score=0.7,
    recurrence="weekly"
)

# Schedule new instances (typically called by scheduler)
new_instances = planning_memory.schedule_recurring_goals()
```

## Maintenance Tasks

### Periodic Cleanup

```python
# Archive old completed goals
archived_count = planning_memory.cleanup_completed_goals(days_old=30)
print(f"Archived {archived_count} old goals")

# Review stale goals
reviews = planning_memory.review_dropped_goals()
print(f"Generated {len(reviews)} review recommendations")
```

### Performance Monitoring

```python
# System health check
stats = planning_memory.generate_planning_stats()

# Alert if completion rate is low
if stats['goals']['completion_rate'] < 0.3:
    print("⚠️ Low goal completion rate - review planning process")

# Alert if too many overdue goals
if stats['goals']['overdue_percentage'] > 0.2:
    print("⚠️ High percentage of overdue goals - adjust deadlines")
```

## Integration Points

### CHAMP Decision Engine

The system integrates with Axiom's CHAMP engine for:

- Confidence scoring based on belief support
- Tempo evaluation from deadline proximity
- Payoff assessment from urgency and importance
- Decision timing for goal pursuit vs. abandonment

### Belief System

Integration with Axiom's belief system provides:

- **Goal Inference**: Create goals from belief conclusions
- **Relevance Assessment**: Evaluate dropped goal reactivation
- **Contradiction Detection**: Identify conflicting goals
- **Context Awareness**: Belief-driven priority adjustments

### Memory System

Uses Axiom's memory infrastructure for:

- **Persistent Storage**: JSONL files for goals and actions
- **Temporal Reasoning**: Time-based query capabilities
- **Vector Search**: Semantic similarity for goal clustering
- **Provenance Tracking**: Link goals to source memories

### Journal Integration

Goals and actions influence journaling through:

- **Reflection Prompts**: Goal progress triggers
- **Decision Logging**: CHAMP evaluation reasoning
- **Achievement Records**: Completion celebrations
- **Challenge Documentation**: Failure analysis

## Configuration

### Environment Variables

```bash
# Planning data directory
PLANNING_DATA_DIR=planning

# Review thresholds
DRIVE_DECAY_THRESHOLD=0.3
CHAMP_DROP_THRESHOLD=0.2
STALENESS_DAYS=7
REVIEW_INTERVAL_HOURS=24

# CHAMP integration
USE_CHAMP_ENGINE=true
CHAMP_CONFIDENCE_WEIGHT=0.4
CHAMP_PAYOFF_WEIGHT=0.3
CHAMP_TEMPO_WEIGHT=0.3
```

### Customization

```python
# Initialize with custom thresholds
planning_memory = PlanningMemory(
    data_dir="custom_planning",
    drive_decay_threshold=0.2,
    champ_drop_threshold=0.15,
    staleness_days=5,
    review_interval_hours=12
)
```

## API Reference

### Core Methods

#### Goal Management
- `add_goal(goal_text, inferred_from_beliefs, target_timeframe, urgency_score, recurrence)` → PlannedGoal
- `update_goal_status(goal_id, new_status, notes)` → bool
- `log_drive_strength(goal_id, timestamp, score, notes)` → bool
- `evaluate_champ(goal_id, goal)` → float

#### Action Management
- `add_action(goal_id, action_text, expected_impact, confidence, blocker_beliefs, repeat_pattern)` → ActionCandidate
- `update_action_status(action_id, status, notes)` → bool

#### Recurring Goals
- `schedule_recurring_goals()` → List[PlannedGoal]

#### Review and Analytics
- `review_dropped_goals()` → List[Dict[str, Any]]
- `generate_planning_stats()` → Dict[str, Any]

#### Queries
- `get_goal(goal_id)` → Optional[PlannedGoal]
- `get_action(action_id)` → Optional[ActionCandidate]
- `get_goals_by_status(status)` → List[PlannedGoal]
- `get_actions_by_goal(goal_id)` → List[ActionCandidate]
- `get_active_goals_by_priority()` → List[PlannedGoal]
- `get_overdue_goals()` → List[PlannedGoal]

#### Maintenance
- `cleanup_completed_goals(days_old)` → int

## Best Practices

### Goal Creation
1. **Specific Goals**: Use clear, measurable goal statements
2. **Belief Linking**: Always link goals to supporting beliefs
3. **Realistic Timeframes**: Set achievable deadlines
4. **Appropriate Urgency**: Use urgency scores thoughtfully

### Action Planning
1. **Granular Actions**: Break goals into specific, actionable steps
2. **Impact Assessment**: Estimate realistic expected impact
3. **Blocker Identification**: Document potential obstacles
4. **Progress Tracking**: Update action status regularly

### System Maintenance
1. **Regular Reviews**: Run review cycles consistently
2. **Stats Monitoring**: Check planning statistics weekly
3. **Cleanup Routine**: Archive old completed goals
4. **Threshold Tuning**: Adjust review thresholds based on performance

### Integration
1. **CHAMP Alignment**: Ensure CHAMP scores reflect actual priorities
2. **Belief Consistency**: Keep goal-belief links updated
3. **Memory Coherence**: Maintain consistency with memory system
4. **Journal Syncing**: Integrate with reflection and journaling

## Troubleshooting

### Common Issues

**Low CHAMP Scores**
- Check belief support for goals
- Verify deadline appropriateness
- Review drive strength trends

**High Goal Abandonment**
- Analyze drop reasons in review recommendations
- Adjust goal complexity and scope
- Improve initial urgency assessment

**Poor Recurring Goal Performance**
- Review template effectiveness
- Adjust recurrence patterns
- Monitor instance completion rates

**System Performance**
- Monitor cache sizes and file growth
- Run cleanup routines regularly
- Check for memory leaks in long-running instances

### Debug Tools

```python
# Enable debug logging
import logging
logging.getLogger('planning_memory').setLevel(logging.DEBUG)

# Inspect goal state
goal = planning_memory.get_goal(goal_id)
print(f"Drive history: {len(goal.drive_strength_over_time)} entries")
print(f"CHAMP history: {len(goal.champ_score_log)} entries")

# Check system stats
stats = planning_memory.generate_planning_stats()
print(f"System health: {stats}")
```

This comprehensive planning memory system provides robust goal and action management with intelligent automation through CHAMP integration and belief-driven decision making.