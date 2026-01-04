# 🧠 Theory of Mind for Axiom

A standalone module for **Theory of Mind (ToM)** reasoning — the ability to simulate, track, and reason about other agents' beliefs, goals, contradictions, **emotional states**, and **motivations** — without interfering with Axiom's own beliefs.

## 🎯 Overview

The Theory of Mind module provides a contained simulation environment for modeling other agents' mental states. It enables Axiom to:

- Simulate other agents' perspectives and reasoning
- Track beliefs, goals, and traits of different entities  
- Detect contradictions in agent belief systems
- **🧠❤️ Infer emotional states and motivations (NEW)**
- **🧠❤️ Generate empathy-driven summaries for journal reflection (NEW)**
- **🧠❤️ Score empathic alignment of responses (NEW)**
- **🧠❤️ Prime dialogue responses with empathy-aware context (NEW)**
- **🔄 Empathic Learning Loop - Adaptive tone preference learning (NEW)**
- Generate empathy-driven responses and predictions
- Support debate simulation and conflict modeling

## 🔒 **CRITICAL CONTAINMENT RULES**

⚠️ **THIS MODULE NEVER WRITES TO CORE MEMORY, BELIEF ENGINE, OR LONG-TERM GOALS**

1. **Memory Isolation**: All ToM memory records are tagged with `memoryType="agent_model"` and `agent_id`
2. **Belief Containment**: Agent beliefs are read-only simulations and never merged with Axiom's beliefs
3. **Simulation Firewall**: Perspective simulations are logged separately with tag `#perspective_sim`
4. **🧠❤️ Empathy Containment**: Emotional/intention inferences tagged `#empathy_inference` and `memoryType="simulation"`
5. **🧠❤️ Dialogue Priming Safeguards**: Empathy context guides but never generates LLM output; only influences tone
6. **🔄 Learning Loop Safeguards**: Tone profiles use simulation-only memory, capped at 50 agents, auto-decay after 30 days
7. **Audit Trail**: All operations are logged with timestamp, agent involved, and problem domain
8. **No Auto-Save**: Agent beliefs are not persisted without explicit calls from higher-level systems

## 📦 Installation & Usage

### Basic Usage

```python
from axiom.theory_of_mind import create_agent, simulate_perspective

# Create an agent model
agent = create_agent(
    agent_id="dr_lyra",
    name="Dr. Lyra",
    traits=["curious", "risk-averse"],
    goals=["study cognition"],
    beliefs={"AI safety": "must include emotional modeling"}
)

# Simulate their perspective on a problem
simulation = simulate_perspective(agent, "Should we deploy recursive AI?")
print(simulation.simulated_response)
```

### 🧠❤️ Empathy Engine (NEW)

The Empathy Engine extends Theory of Mind with emotional understanding and motivational inference:

```python
from axiom.theory_of_mind import (
    infer_agent_emotion, 
    model_agent_intentions,
    generate_empathy_summary,
    score_empathic_alignment
)

# Infer emotional state from context
agent = create_agent("alice", "Alice", traits=["defensive", "analytical"])
context = "I'm concerned that you're questioning my expertise on this matter."

emotional_state = infer_agent_emotion(agent, context)
print(f"Emotion: {emotional_state.emotion} (intensity: {emotional_state.intensity:.2f})")

# Model likely intentions
intentions = model_agent_intentions(agent, context)
print(f"Likely intentions: {intentions.intentions}")

# Generate empathy summary for journaling
empathy_summary = generate_empathy_summary(agent, context)
print(f"Empathy Analysis: {empathy_summary.summary_text}")

# Score empathic alignment of responses
good_response = "I understand your concern. Your expertise is valuable here."
poor_response = "You're wrong. Let's move on quickly."

good_alignment = score_empathic_alignment(agent, good_response, context)
poor_alignment = score_empathic_alignment(agent, poor_response, context)

print(f"Good response alignment: {good_alignment.alignment_score:.2f}")
print(f"Poor response alignment: {poor_alignment.alignment_score:.2f}")
```

### 🧠❤️ Empathy-Aware Dialogue Priming (NEW)

The empathy engine automatically enhances Axiom's dialogue responses by modeling user emotion and intent, then injecting guidance into the LLM prompt:

```python
# NOTE: This integration happens automatically in the LLM connector
# No direct API calls needed - the empathy priming is transparent

# Example of what happens behind the scenes:
# 1. User sends: "ExamplePerson: I'm worried this AI system might not work correctly"
# 2. Empathy engine identifies agent "ExamplePerson" and analyzes emotional state
# 3. Infers: emotion="anxious", intent="seek reassurance"  
# 4. Injects empathy context block into LLM prompt:
#
# [Empathy Context]
# Agent: ExamplePerson
# Emotion: anxious (confidence: 0.8)
# Intent: seek reassurance (confidence: 0.7)
# Suggested tone: reassuring and careful
# Empathy Notes: ExamplePerson appears anxious about system reliability
# #end_empathy_context
#
# 5. LLM generates response with empathy-guided tone
```

**Dialogue Priming Features:**
- **Automatic Agent Detection**: Identifies conversational partners (ExamplePerson, users) from context
- **Real-time Emotion Analysis**: Infers emotional states from user messages
- **Intent Modeling**: Understands user motivations and goals
- **Tone Guidance**: Maps emotions to appropriate response tones
- **Transparent Integration**: Works seamlessly without changing existing APIs
- **Selective Activation**: Only triggers for dialogue, not memory retrieval

## 🔄 **Empathic Learning Loop**

The empathic learning loop enables Axiom to continuously improve its empathy alignment by learning from successful tone preferences over time.

### How It Works

1. **Post-Dialogue Alignment Scoring**: After each empathy-guided response, the system evaluates alignment between the response tone and the agent's emotional state/intentions.

2. **Reflection Journaling**: High/low alignment scores are journaled with reasoning and improvement suggestions, tagged with `#empathy_alignment`.

3. **Tone Profile Learning**: For alignment scores > 80%, the system learns preferred tone mappings per agent and emotional context.

4. **Future Prompt Adaptation**: Learned tone preferences override default mappings in future empathy contexts.

5. **Decay and Cleanup**: Old tone patterns naturally decay, and profiles are cleaned up after 30 days of inactivity.

### Usage Example

```python
from axiom.theory_of_mind.learning_loop import (
    get_preferred_tone, update_tone_profile, 
    get_tone_profile_summary, reset_tone_profile
)

# Check if agent has learned tone preferences
preferred = get_preferred_tone("ExamplePerson", emotion="frustrated")
# Returns: "humorous and encouraging" (if previously learned)

# View agent's learning history
summary = get_tone_profile_summary("ExamplePerson")
print(f"Total interactions: {summary['entry_count']}")
print(f"Preferred tones: {summary['preferred_tones']}")

# Reset learning for fresh start (debugging)
reset_tone_profile("ExamplePerson")
```

### Sample Learned Tone Profile

```json
{
  "agent": "ExamplePerson",
  "preferred_tones": {
    "emotion_curious": "informative, playful",
    "emotion_anxious": "clear, confident, no fluff", 
    "emotion_frustrated": "lightly humorous, empathetic",
    "intent_avoid_blame": "understanding, diplomatic"
  },
  "entry_count": 12,
  "last_updated": "2025-08-05T18:13Z"
}
```

### Configuration

Learning can be configured via environment variables:
- `ENABLE_EMPATHIC_LEARNING=true/false` - Toggle learning system
- `MAX_TONE_PROFILES=50` - Maximum number of agent profiles
- `ALIGNMENT_CONFIDENCE_THRESHOLD=0.8` - Minimum score for learning

### Advanced Features

```python
from axiom.theory_of_mind import (
    update_agent_beliefs,
    detect_contradictions,
    summarize_agent,
    verify_containment
)

# Update agent beliefs from dialogue
updated_agent = update_agent_beliefs(agent, "I think we need more testing.")

# Detect internal contradictions
contradictions = detect_contradictions(agent)
for contradiction in contradictions:
    print(f"Contradiction: {contradiction.description}")

# Generate agent summary
summary = summarize_agent(agent)
print(summary.summary_text)

# Verify containment safeguards
if verify_containment():
    print("✅ Containment verified")
```

## 🧪 Use Cases

### 1. Debate Simulation
```python
# Model different debaters
scientist = create_agent("scientist", "Dr. Research", 
                        traits=["analytical", "cautious"],
                        beliefs={"evidence": "should guide all decisions"})

entrepreneur = create_agent("entrepreneur", "Alex Venture",
                           traits=["optimistic", "risk-taking"], 
                           beliefs={"speed": "is essential for innovation"})

# Simulate their perspectives on the same issue
issue = "Should we release this AI system now?"
sci_view = simulate_perspective(scientist, issue)
ent_view = simulate_perspective(entrepreneur, issue)
```

### 2. Empathy & Understanding
```python
# Model a user's mental state
user = create_agent("user_123", "Frustrated User",
                   traits=["impatient", "goal-oriented"],
                   beliefs={"time": "is valuable and shouldn't be wasted"})

# Understand their perspective on system delays
response = simulate_perspective(user, "The system is taking 30 seconds to load")
print(f"User likely feels: {response.simulated_response}")
```

### 3. Conflict Resolution
```python
# Model conflicting parties
party_a = create_agent("team_a", "Development Team",
                      goals=["ship features quickly"],
                      beliefs={"agility": "enables rapid iteration"})

party_b = create_agent("team_b", "QA Team", 
                      goals=["ensure system reliability"],
                      beliefs={"testing": "prevents costly mistakes"})

# Find common ground
issue = "How much testing should we do before release?"
dev_perspective = simulate_perspective(party_a, issue)
qa_perspective = simulate_perspective(party_b, issue)
```

## 📊 Data Models

### AgentModel
Core representation of an agent's mental state:
- `agent_id`: Unique identifier
- `name`: Human-readable name
- `traits`: Personality characteristics
- `goals`: Primary objectives
- `beliefs`: Key beliefs (topic → content mapping)
- `memory_refs`: Associated memory UUIDs
- `last_updated`: Timestamp of last modification

### PerspectiveSimulation
Result of simulating an agent's viewpoint:
- `simulated_response`: The agent's likely response
- `confidence`: Confidence score (0.0-1.0)
- `reasoning_chain`: Step-by-step reasoning
- `metadata`: Additional context (includes `#perspective_sim` tag)

### Contradiction
Detected inconsistency in agent beliefs:
- `belief_topic_a/b`: Conflicting belief topics
- `belief_content_a/b`: Conflicting belief contents
- `contradiction_type`: Type of contradiction (logical, factual, temporal)
- `severity`: Severity score (0.0-1.0)

### 🧠❤️ Empathy Models (NEW)

#### EmotionalState
Inferred emotional state of an agent:
- `emotion`: Detected emotion (e.g., 'anxious', 'defensive', 'confident')
- `intensity`: Emotional intensity (0.0-1.0)
- `confidence`: Confidence in emotion inference (0.0-1.0)
- `context`: Context that led to emotional inference
- `metadata`: Tagged with `memoryType="simulation"`

#### IntentionModel
Inferred motivations and intentions:
- `intentions`: List of likely intentions (e.g., ['gain influence', 'avoid blame'])
- `confidence`: Overall confidence in intention inference (0.0-1.0)
- `reasoning_chain`: Step-by-step reasoning for intentions
- `context`: Context that led to intention inference

#### EmpathySummary
Combined emotional and intentional analysis:
- `emotional_state`: Associated EmotionalState object
- `intentions`: Associated IntentionModel object
- `summary_text`: Natural language empathy summary
- `metadata`: Tagged with `#empathy_inference` and `memoryType="simulation"`

#### EmpathyAlignment
Evaluation of response alignment with agent state:
- `alignment_score`: How well response matches agent state (0.0-1.0)
- `reasoning`: Explanation of score assignment
- `suggestions`: Recommendations for improving alignment
- `agent_emotional_state`: Agent's inferred emotional state
- `agent_intentions`: Agent's inferred intentions

## 🛡️ Containment Verification

The module includes built-in safeguards:

```python
from axiom.theory_of_mind import verify_containment, get_audit_log

# Check containment status
if not verify_containment():
    print("⚠️ CONTAINMENT BREACH DETECTED")
    
# Review audit trail
audit_log = get_audit_log()
for event in audit_log[-5:]:  # Last 5 operations
    print(f"{event.operation} on {event.agent_id} at {event.timestamp}")
```

## 🔮 Future Capabilities (Planned)

The following features are commented in the code for future implementation:

- **Belief Comparison**: Compare beliefs across multiple agents
- **Contradiction Graphs**: Visualize belief conflicts and dependencies  
- **ToM Scoring**: Trust, predictability, and influence metrics
- **Agent Memory Prioritization**: Weight memories by agent relevance
- **Cross-Agent Reasoning**: Simulate multi-agent interactions
- **Temporal Belief Tracking**: Track how agent beliefs evolve over time

## 🚨 Warnings & Limitations

1. **Simulation Only**: This module creates simulations, not real agent understanding
2. **No Core Modifications**: Never modifies Axiom's actual beliefs or memory
3. **Limited Inference**: Current implementation uses rule-based logic; LLM integration planned
4. **No Persistence**: Agent models are cached in memory only (persistent storage integration planned)
5. **Simplified Psychology**: Real human psychology is far more complex than these models

## 🧪 Testing

Run the integration tests to verify functionality:

```bash
cd axiom/theory_of_mind
python test_engine.py
```

Expected output includes:
- ✅ All tests pass
- 🔒 Containment verification successful
- 📊 Audit log shows all operations

## 📝 Development Notes

- **Memory Tagging**: When integrated with Axiom's memory system, use `memoryType="agent_model"` and include `agent_id` in all records
- **Journal Integration**: Perspective simulations should be tagged `#perspective_sim` in journal entries  
- **🧠❤️ Empathy Integration**: Empathy analyses are tagged `#empathy_inference` and automatically added to journal entries when agent interactions are detected
- **🧠❤️ Memory Enrichment**: Memory entries with agent interactions automatically receive empathy metadata during ingestion
- **🧠❤️ Alignment Monitoring**: Low empathy alignment scores (< 0.5) trigger warnings in logs for response improvement
- **LLM Integration**: Replace rule-based belief extraction and contradiction detection with local LLM inference
- **Persistent Storage**: Implement loading/saving of agent models to Axiom's vector database

## 📞 Integration Points

The module is designed to integrate with:

- **Cognitive State Manager**: For higher-level reasoning about other minds
- **Memory System**: For persistent agent model storage and empathy metadata enrichment
- **Journal System**: For logging perspective simulations and empathy analyses
- **🧠❤️ Memory Manager**: Automatically adds empathy metadata during memory ingestion
- **🧠❤️ Journal Engine**: Generates empathy summaries for agent interactions
- **🧠❤️ LLM Connector**: Automatically injects empathy context into dialogue prompts
- **Contradiction Engine**: For cross-referencing with Axiom's own belief contradictions
- **Consciousness Pilot** (orchestration module for simulated cognition): For empathy and social reasoning enhancement

---

**Remember**: This is a simulation space, not a belief-altering system. All agent models are contained and isolated from Axiom's core cognitive architecture.