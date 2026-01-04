# Self-Modeling Engine Documentation

## Overview

The Self-Modeling Engine enables Axiom to represent, inspect, and reason about its own internal state using meta-beliefs, confidence tracking, and recursive self-analysis. This module provides introspective capabilities that allow Axiom to monitor its cognitive health, identify patterns in its behavior, and generate actionable insights about its own functioning.

## Table of Contents

- [Core Concepts](#core-concepts)
- [Architecture](#architecture)
- [API Reference](#api-reference)
- [Integration Guide](#integration-guide)
- [Usage Examples](#usage-examples)
- [Meta-Belief Types](#meta-belief-types)
- [Assessment Dimensions](#assessment-dimensions)
- [Temporal Analysis](#temporal-analysis)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Core Concepts

### Meta-Beliefs

Meta-beliefs are beliefs about Axiom's own internal state and processes. Unlike regular beliefs about the external world, meta-beliefs provide introspective awareness:

```python
# Example meta-belief
MetaBelief(
    meta_belief_type=MetaBeliefType.SYSTEM_STATUS,
    statement="I am experiencing degraded memory system performance",
    confidence=0.8,
    evidence=["Memory health score: 0.25"],
    assessment_dimension=SelfAssessmentDimension.MEMORY_HEALTH,
    urgency=0.7,
    impact_score=0.8
)
```

### Self-State Snapshots

Snapshots capture comprehensive system state at specific points in time, enabling temporal analysis:

```python
# Example snapshot
SelfStateSnapshot(
    memory_health_score=0.75,
    drive_integrity_score=0.8,
    emotional_stability_score=0.6,
    belief_consistency_score=0.9,
    goal_pressure=0.3,
    contradiction_pressure=0.2,
    overall_confidence=0.7
)
```

### Status Reports

Structured diagnostic summaries providing actionable insights:

```python
# Example status report
SelfStatusReport(
    overall_health="Good",
    primary_concerns=["High contradiction pressure"],
    key_strengths=["Strong memory system performance"],
    recommended_actions=["Prioritize contradiction resolution activities"]
)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Self-Modeling Engine                        │
├─────────────────────────────────────────────────────────────┤
│  Core Components:                                           │
│  • SelfModelingEngine (orchestrator)                       │
│  • MetaBelief (introspective beliefs)                      │
│  • SelfStateSnapshot (temporal state capture)              │
│  • SelfStatusReport (diagnostic summaries)                 │
├─────────────────────────────────────────────────────────────┤
│  Integration Points:                                        │
│  • BeliefInfluenceMapper → influence volatility            │
│  • ContradictionResolutionEngine → contradiction pressure  │
│  • PlanningMemory → goal pressure & cognitive load         │
│  • EmotionalStateSnapshot → emotional stability            │
│  • JournalEngine → meta-belief export                      │
├─────────────────────────────────────────────────────────────┤
│  Data Flow:                                                 │
│  1. Capture current state → SelfStateSnapshot              │
│  2. Analyze state metrics → Generate MetaBeliefs           │
│  3. Perform temporal analysis → Identify trends            │
│  4. Generate recommendations → SelfStatusReport            │
│  5. Export to journal → Integration with memory systems    │
└─────────────────────────────────────────────────────────────┘
```

## API Reference

### SelfModelingEngine

Main orchestrator class for self-modeling functionality.

#### Initialization

```python
from self_modeling_engine import SelfModelingEngine, create_self_modeling_engine

# Direct instantiation
engine = SelfModelingEngine(data_dir="/workspace/data/self_modeling")

# Factory function (recommended)
engine = create_self_modeling_engine(data_dir="/workspace/data/self_modeling")
```

#### Core Methods

##### `capture_current_state() -> SelfStateSnapshot`

Captures a comprehensive snapshot of current internal state.

```python
snapshot = engine.capture_current_state()
print(f"Memory health: {snapshot.memory_health_score:.2f}")
print(f"Goal pressure: {snapshot.goal_pressure:.2f}")
print(f"Active contradictions: {snapshot.active_contradictions_count}")
```

##### `generate_meta_beliefs(snapshot: Optional[SelfStateSnapshot] = None) -> List[MetaBelief]`

Generates meta-beliefs based on current or provided state snapshot.

```python
# Generate from current state
meta_beliefs = engine.generate_meta_beliefs()

# Generate from specific snapshot
snapshot = engine.capture_current_state()
meta_beliefs = engine.generate_meta_beliefs(snapshot)

for mb in meta_beliefs:
    print(f"🧠 {mb.statement} (confidence: {mb.confidence:.2f})")
```

##### `get_self_status_report() -> SelfStatusReport`

Generates a comprehensive status report with analysis and recommendations.

```python
report = engine.get_self_status_report()
print(f"Overall Health: {report.overall_health}")
print(f"Primary Concerns: {', '.join(report.primary_concerns)}")
print(f"Key Strengths: {', '.join(report.key_strengths)}")
print(f"Recommendations: {', '.join(report.recommended_actions)}")
```

##### `trigger_self_analysis() -> Dict[str, Any]`

Manually triggers comprehensive self-analysis and returns summary.

```python
analysis = engine.trigger_self_analysis()
print(f"Generated {analysis['new_meta_beliefs_count']} new meta-beliefs")
print(f"Overall health: {analysis['overall_health']}")
print(f"High priority issues: {analysis['high_priority_issues_count']}")
```

##### `get_diagnostic_summary() -> Dict[str, Any]`

Returns quick diagnostic summary of current state.

```python
summary = engine.get_diagnostic_summary()
system_health = summary['system_health']
cognitive_load = summary['cognitive_load']

print(f"Memory Health: {system_health['memory_health']:.2f}")
print(f"Goal Pressure: {cognitive_load['goal_pressure']:.2f}")
print(f"Contradiction Pressure: {cognitive_load['contradiction_pressure']:.2f}")
```

#### Filtering and Query Methods

##### `get_active_meta_beliefs(filter_types, min_confidence, min_urgency) -> List[MetaBelief]`

Retrieves active meta-beliefs with optional filtering.

```python
from self_modeling_engine import MetaBeliefType

# Get all system status meta-beliefs
system_beliefs = engine.get_active_meta_beliefs(
    filter_types=[MetaBeliefType.SYSTEM_STATUS]
)

# Get high-confidence meta-beliefs
confident_beliefs = engine.get_active_meta_beliefs(min_confidence=0.8)

# Get urgent meta-beliefs
urgent_beliefs = engine.get_active_meta_beliefs(min_urgency=0.7)

# Combined filtering
critical_system_beliefs = engine.get_active_meta_beliefs(
    filter_types=[MetaBeliefType.SYSTEM_STATUS, MetaBeliefType.BELIEF_HEALTH],
    min_confidence=0.7,
    min_urgency=0.5
)
```

##### `get_recent_snapshots(count: int = 10) -> List[SelfStateSnapshot]`

Retrieves recent state snapshots for analysis.

```python
# Get last 5 snapshots
recent = engine.get_recent_snapshots(count=5)

# Analyze memory health trend
memory_scores = [s.memory_health_score for s in recent]
print(f"Memory health trend: {memory_scores}")
```

#### Export and Integration

##### `export_meta_beliefs_to_journal(filter_types) -> bool`

Exports meta-beliefs to journal system if available.

```python
# Export all meta-beliefs
success = engine.export_meta_beliefs_to_journal()

# Export only specific types
success = engine.export_meta_beliefs_to_journal(
    filter_types=[MetaBeliefType.SYSTEM_STATUS, MetaBeliefType.CONFIDENCE_ASSESSMENT]
)
```

## Integration Guide

### With Belief Influence Mapper

The self-modeling engine integrates with the belief influence mapper to assess influence volatility:

```python
# Automatic integration - no manual setup required
# The engine will use influence data if available

snapshot = engine.capture_current_state()
print(f"Influence volatility: {snapshot.influence_volatility:.2f}")
```

### With Contradiction Resolution Engine

Integration provides contradiction pressure metrics:

```python
# Contradiction pressure automatically calculated
snapshot = engine.capture_current_state()
if snapshot.contradiction_pressure > 0.6:
    print("⚠️ High contradiction pressure detected")
    
    # Get related meta-beliefs
    contradiction_beliefs = engine.get_active_meta_beliefs(
        filter_types=[MetaBeliefType.BELIEF_HEALTH]
    )
```

### With Planning Memory

Planning system integration provides goal pressure and cognitive load metrics:

```python
# Goal pressure and planning load automatically assessed
snapshot = engine.capture_current_state()
if snapshot.goal_pressure > 0.7:
    print("⚠️ High goal pressure - consider goal prioritization")
    
if snapshot.planning_load > 0.8:
    print("⚠️ Planning system under heavy load")
```

### With Emotional Model

Emotional state integration for emotional stability assessment:

```python
# Emotional state automatically captured if available
snapshot = engine.capture_current_state()
if snapshot.emotional_state:
    print(f"Primary emotion: {snapshot.emotional_state.primary_emotion}")
    print(f"Emotional intensity: {snapshot.emotional_state.intensity:.2f}")
    print(f"Emotional stability: {snapshot.emotional_stability_score:.2f}")
```

### With Journal Engine

Export meta-beliefs for long-term tracking:

```python
# Manual export
engine.export_meta_beliefs_to_journal()

# Automated export of high-priority beliefs
high_priority = engine.get_active_meta_beliefs(min_urgency=0.7)
if high_priority:
    engine.export_meta_beliefs_to_journal(
        filter_types=[mb.meta_belief_type for mb in high_priority]
    )
```

## Usage Examples

### Basic Self-Analysis Workflow

```python
from self_modeling_engine import create_self_modeling_engine

# Initialize engine
engine = create_self_modeling_engine()

# Perform comprehensive self-analysis
print("🔍 Starting self-analysis...")
analysis = engine.trigger_self_analysis()

print(f"✅ Analysis complete!")
print(f"Overall health: {analysis['overall_health']}")
print(f"New insights: {analysis['new_meta_beliefs_count']} meta-beliefs generated")

# Get detailed status report
report = engine.get_self_status_report()
print(f"\n📋 Status Report:")
print(f"Health: {report.overall_health}")

if report.primary_concerns:
    print(f"⚠️ Concerns: {', '.join(report.primary_concerns)}")

if report.key_strengths:
    print(f"✅ Strengths: {', '.join(report.key_strengths)}")

if report.recommended_actions:
    print(f"🔧 Recommendations:")
    for action in report.recommended_actions:
        print(f"  • {action}")
```

### Monitoring Specific Dimensions

```python
# Monitor memory health over time
def monitor_memory_health(engine, threshold=0.4):
    snapshot = engine.capture_current_state()
    
    if snapshot.memory_health_score < threshold:
        print(f"⚠️ Memory health below threshold: {snapshot.memory_health_score:.2f}")
        
        # Get memory-related meta-beliefs
        memory_beliefs = engine.get_active_meta_beliefs(
            filter_types=[MetaBeliefType.SYSTEM_STATUS]
        )
        
        memory_beliefs = [
            mb for mb in memory_beliefs 
            if mb.assessment_dimension == SelfAssessmentDimension.MEMORY_HEALTH
        ]
        
        for mb in memory_beliefs:
            print(f"  💭 {mb.statement}")
    
    return snapshot.memory_health_score

# Usage
memory_score = monitor_memory_health(engine)
```

### Trend Analysis

```python
def analyze_trends(engine, days=7):
    """Analyze trends over recent days"""
    snapshots = engine.get_recent_snapshots(count=days * 24)  # Hourly snapshots
    
    if len(snapshots) < 3:
        print("❌ Insufficient data for trend analysis")
        return
    
    # Analyze memory health trend
    memory_scores = [s.memory_health_score for s in snapshots]
    memory_trend = engine._calculate_trend(memory_scores)
    
    if memory_trend > 0.05:
        print("📈 Memory health improving")
    elif memory_trend < -0.05:
        print("📉 Memory health declining")
    else:
        print("➡️ Memory health stable")
    
    # Analyze contradiction pressure trend
    contradiction_scores = [s.contradiction_pressure for s in snapshots]
    contradiction_trend = engine._calculate_trend(contradiction_scores)
    
    if contradiction_trend > 0.05:
        print("📈 Contradiction pressure increasing")
    elif contradiction_trend < -0.05:
        print("📉 Contradiction pressure decreasing")
    else:
        print("➡️ Contradiction pressure stable")

# Usage
analyze_trends(engine)
```

### Custom Health Monitoring

```python
def custom_health_check(engine):
    """Custom health monitoring with specific thresholds"""
    
    snapshot = engine.capture_current_state()
    health_issues = []
    
    # Check various health dimensions
    if snapshot.memory_health_score < 0.5:
        health_issues.append(f"Memory health low: {snapshot.memory_health_score:.2f}")
    
    if snapshot.contradiction_pressure > 0.6:
        health_issues.append(f"High contradiction pressure: {snapshot.contradiction_pressure:.2f}")
    
    if snapshot.goal_pressure > 0.7:
        health_issues.append(f"High goal pressure: {snapshot.goal_pressure:.2f}")
    
    if snapshot.overall_confidence < 0.4:
        health_issues.append(f"Low confidence: {snapshot.overall_confidence:.2f}")
    
    # Generate recommendations
    if health_issues:
        print("⚠️ Health Issues Detected:")
        for issue in health_issues:
            print(f"  • {issue}")
        
        # Get relevant meta-beliefs
        urgent_beliefs = engine.get_active_meta_beliefs(min_urgency=0.6)
        if urgent_beliefs:
            print("\n💭 Related Meta-Beliefs:")
            for mb in urgent_beliefs[:3]:  # Top 3
                print(f"  • {mb.statement} (urgency: {mb.urgency:.2f})")
    else:
        print("✅ All systems healthy")
    
    return len(health_issues) == 0

# Usage
is_healthy = custom_health_check(engine)
```

## Meta-Belief Types

### SYSTEM_STATUS
Beliefs about core system components and their operational status.

**Examples:**
- "I am experiencing degraded memory system performance"
- "My goal-drive system may have integrity issues"
- "My memory system is operating at high efficiency"

### CONFIDENCE_ASSESSMENT
Beliefs about confidence levels in current beliefs, goals, and assessments.

**Examples:**
- "I have low confidence in my current beliefs and assessments"
- "I have high confidence in my current beliefs and assessments"
- "I have significantly different confidence levels between beliefs and goals"

### EMOTIONAL_STATE
Beliefs about emotional stability and current emotional experiences.

**Examples:**
- "I am experiencing emotional instability"
- "I am experiencing intense curiosity"
- "My emotional state is stable and balanced"

### BELIEF_HEALTH
Beliefs about the health and consistency of the belief system.

**Examples:**
- "My belief system has significant consistency issues"
- "I am experiencing high contradiction pressure"
- "My beliefs are well-aligned and consistent"

### COGNITIVE_LOAD
Beliefs about cognitive load, goal pressure, and planning efficiency.

**Examples:**
- "I am experiencing high goal pressure and cognitive load"
- "My planning system is operating under high load"
- "My cognitive resources are efficiently allocated"

### TEMPORAL_PATTERNS
Beliefs about trends and patterns identified over time.

**Examples:**
- "My memory health has been declining over recent observations"
- "My contradiction pressure has been increasing over time"
- "My emotional stability has been improving consistently"

### SELF_ALIGNMENT
Beliefs about ethical stability and value alignment.

**Examples:**
- "My ethical beliefs have been unstable in the past 24h"
- "I am maintaining strong alignment with core values"
- "My decision-making is consistent with stated principles"

### PERFORMANCE_ASSESSMENT
Beliefs about capabilities and performance evaluation.

**Examples:**
- "I am performing below optimal capacity in reasoning tasks"
- "My response quality has been consistently high"
- "I am effectively balancing multiple competing objectives"

### RECURSIVE_META
Meta-beliefs about meta-beliefs (advanced introspection).

**Examples:**
- "I am generating too many low-confidence meta-beliefs"
- "My self-assessment capabilities are improving"
- "I have high confidence in my introspective abilities"

## Assessment Dimensions

### Core Dimensions

- **MEMORY_HEALTH**: Overall memory system health and performance
- **DRIVE_INTEGRITY**: Goal/drive system integrity and consistency
- **EMOTIONAL_STABILITY**: Emotional system stability and regulation
- **BELIEF_CONSISTENCY**: Belief system consistency and coherence
- **GOAL_ALIGNMENT**: Alignment between goals and actions
- **CONTRADICTION_PRESSURE**: Pressure from active contradictions
- **INFLUENCE_VOLATILITY**: Volatility in belief influence patterns
- **PLANNING_EFFICIENCY**: Efficiency of planning and execution
- **ETHICAL_STABILITY**: Stability of ethical beliefs and principles

### Measurement Scales

All dimensions use a 0.0-1.0 scale:
- **0.0-0.2**: Critical/Very Poor
- **0.2-0.4**: Poor/Concerning
- **0.4-0.6**: Fair/Moderate
- **0.6-0.8**: Good/Healthy
- **0.8-1.0**: Excellent/Optimal

## Temporal Analysis

The self-modeling engine performs sophisticated temporal analysis to identify patterns and trends:

### Trend Calculation

Uses linear regression to calculate slopes for key metrics:

```python
# Example trend analysis
recent_snapshots = engine.get_recent_snapshots(count=10)
memory_scores = [s.memory_health_score for s in recent_snapshots]
trend = engine._calculate_trend(memory_scores)

if trend > 0.05:
    print("📈 Improving trend")
elif trend < -0.05:
    print("📉 Declining trend")
else:
    print("➡️ Stable trend")
```

### Stability Assessment

Measures stability using standard deviation:

```python
# Lower standard deviation = higher stability
stability_score = max(0, 1.0 - standard_deviation * 2)
```

### Pattern Recognition

Automatically generates temporal pattern meta-beliefs when significant trends are detected:

```python
# Example temporal meta-belief
MetaBelief(
    meta_belief_type=MetaBeliefType.TEMPORAL_PATTERNS,
    statement="My memory health has been declining over recent observations",
    confidence=0.7,
    evidence=["Memory health trend: -0.15"],
    urgency=0.6,
    impact_score=0.7
)
```

## Best Practices

### Initialization and Setup

1. **Use factory function**: Prefer `create_self_modeling_engine()` over direct instantiation
2. **Configure data directory**: Ensure persistent storage location is accessible
3. **Check integration availability**: Verify connected systems are available

```python
# Good practice
engine = create_self_modeling_engine(data_dir="/workspace/data/self_modeling")

# Check integration status
if engine.belief_registry:
    print("✅ Belief registry integration active")
if engine.planning_memory:
    print("✅ Planning memory integration active")
```

### Regular Monitoring

1. **Scheduled analysis**: Run self-analysis at regular intervals
2. **Threshold monitoring**: Set up alerts for critical thresholds
3. **Trend tracking**: Monitor trends over time, not just point-in-time values

```python
# Example monitoring schedule
import time
import schedule

def scheduled_analysis():
    analysis = engine.trigger_self_analysis()
    if analysis['overall_health'] in ['Poor', 'Critical']:
        print(f"⚠️ Health alert: {analysis['overall_health']}")

# Schedule every hour
schedule.every().hour.do(scheduled_analysis)
```

### Meta-Belief Management

1. **Review regularly**: Periodically review active meta-beliefs for relevance
2. **Set expiration**: Use `valid_until` for time-sensitive meta-beliefs
3. **Filter by urgency**: Focus on high-urgency meta-beliefs first

```python
# Review urgent meta-beliefs
urgent = engine.get_active_meta_beliefs(min_urgency=0.7)
for mb in urgent:
    print(f"🚨 {mb.statement}")
```

### Performance Optimization

1. **Limit snapshot retention**: Configure appropriate retention periods
2. **Batch operations**: Process multiple meta-beliefs together
3. **Lazy loading**: Take advantage of lazy-loaded integration components

```python
# Configure retention
engine = SelfModelingEngine(
    data_dir="/workspace/data/self_modeling"
    # Snapshots automatically limited to 1000 recent entries
)
```

## Troubleshooting

### Common Issues

#### Missing Integration Modules

**Symptom**: Warning messages about unavailable modules

**Solution**: Graceful degradation is built-in; functionality continues with default values

```python
# Check integration status
if not engine.belief_registry:
    print("ℹ️ Belief registry not available - using fallback values")
```

#### Low Meta-Belief Generation

**Symptom**: Few or no meta-beliefs generated

**Causes**:
- All metrics in normal ranges
- Insufficient historical data
- Overly strict thresholds

**Solution**: Review thresholds and ensure sufficient data collection

```python
# Check data availability
print(f"Snapshots available: {len(engine.recent_snapshots)}")
print(f"Active meta-beliefs: {len(engine.active_meta_beliefs)}")
```

#### High Memory Usage

**Symptom**: Increasing memory consumption over time

**Causes**:
- Too many retained snapshots
- Large number of meta-beliefs
- Insufficient cleanup

**Solution**: Configure retention limits and run periodic cleanup

```python
# Manual cleanup
engine._cleanup_expired_meta_beliefs()

# Check memory usage
print(f"Meta-beliefs: {len(engine.active_meta_beliefs)}")
print(f"Snapshots: {len(engine.recent_snapshots)}")
```

#### Corrupted Data Files

**Symptom**: Errors loading previous data

**Solution**: Built-in error handling continues operation; manual cleanup may be needed

```python
# Check for data file issues
try:
    engine._load_meta_beliefs()
    print("✅ Meta-beliefs loaded successfully")
except Exception as e:
    print(f"⚠️ Meta-belief loading error: {e}")
```

### Debugging Tips

1. **Enable detailed logging**: Increase log level for troubleshooting
2. **Inspect raw data**: Examine snapshot raw_metrics for detailed information
3. **Check integration status**: Verify all expected integrations are active

```python
import logging
logging.getLogger('SelfModelingEngine').setLevel(logging.DEBUG)

# Inspect recent snapshot
if engine.recent_snapshots:
    latest = engine.recent_snapshots[-1]
    print(f"Raw metrics: {latest.raw_metrics}")
```

### Performance Monitoring

Monitor engine performance using built-in metrics:

```python
def monitor_engine_performance(engine):
    summary = engine.get_diagnostic_summary()
    
    print(f"Data points:")
    print(f"  • Snapshots: {summary['recent_activity']['snapshots_captured']}")
    print(f"  • Meta-beliefs: {summary['active_components']['meta_beliefs']}")
    print(f"  • Recent changes: {summary['recent_activity']['belief_changes']}")
    
    # Check for performance issues
    if summary['active_components']['meta_beliefs'] > 100:
        print("⚠️ High meta-belief count - consider cleanup")
    
    if summary['recent_activity']['snapshots_captured'] > 1000:
        print("⚠️ High snapshot count - within retention limits")

# Usage
monitor_engine_performance(engine)
```

---

## Summary

The Self-Modeling Engine provides Axiom with sophisticated introspective capabilities through:

- **Meta-beliefs**: Structured beliefs about internal state
- **State snapshots**: Temporal tracking of system metrics
- **Trend analysis**: Pattern recognition over time
- **Status reporting**: Actionable diagnostic summaries
- **Integration**: Seamless connection with existing cognitive systems

This enables Axiom to maintain self-awareness, identify potential issues early, and make informed decisions about its own cognitive processes.

For advanced usage and customization, see the source code and test suite for additional examples and patterns.