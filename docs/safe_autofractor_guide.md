# Safe Autofractor Guide for Axiom v1.1

## Overview

This guide provides comprehensive safety protocols for AI agents working on the Axiom codebase — a sophisticated multi-threaded cognitive system that integrates memory, journaling, goal tracking, belief scaffolding, contradiction detection, and dreaming capabilities.

## 🎯 Mission Statement

Your mission as an AI agent is to propose improvements to the Axiom codebase without breaking:
- System flow integrity
- Context linkage between components
- The emerging cognitive mind of Axiom

## 📁 File Classification System

Before touching any file, you must classify it using **exactly one** of these categories:

### [PIPELINE] – Core memory, vector and response flow
**Files**: memory_manager.py, memory_response_pipeline.py, vector_router.py, memory_adapter.py, memory_validator.py

**Purpose**: These files handle the core data flow through Axiom's memory system. Changes here can affect how memories are stored, retrieved, and processed.

### [INTERFACE] – I/O boundaries and server logic
**Files**: discord_interface.py, llama_hf_server.py, main.py, server.py

**Purpose**: External communication interfaces. Changes affect how Axiom interacts with the outside world.

### [STRUCTURAL] – Boot logic, config, schema
**Files**: start.sh, .env, .env.memory, world_map.json, memory.schema.json, prompt_templates/

**Purpose**: Configuration and initialization. Changes can affect system startup and core behavior.

### [JOURNALING] – Memory review and summarisation
**Files**: journal_engine.py, journal_templates.json

**Purpose**: Memory consolidation and review processes. Critical for long-term memory formation.

### [BELIEF] – Belief formation and confidence scaffolding
**Files**: belief_loop.py, belief_core.py, belief_templates.json, belief_manager.py, belief_models.py, belief_registry.py, belief_registry_api.py, belief_tagging_engine.py, belief_utils.py

**Purpose**: Core belief processing and confidence systems. Changes affect how Axiom forms and maintains beliefs.

### [GOALS] – Goal state, update and priority logic
**Files**: goal_engine.py, goal_templates.json, goal_registry_api.py, goal_types.py

**Purpose**: Goal processing and execution. Changes affect Axiom's planning and decision-making.

### [CONTRADICTION] – Contradiction detection and resolution
**Files**: contradiction_detector.py, contradiction_templates.json, contradiction_engine.py, contradiction_digest.py, contradiction_logger.py, contradiction_resolver.py

**Purpose**: Conflict detection and resolution. Critical for maintaining cognitive consistency.

### [DREAMS] – Asynchronous generative cognition
**Files**: dream_engine.py, dream_templates.json

**Purpose**: Background cognitive processes. Changes affect Axiom's creative and subconscious processes.

### [UTIL] – Stateless helpers and wrappers
**Files**: utils.py, logger.py, constants.py, timers.py

**Purpose**: Supporting utilities. Generally lower risk for changes.

## 📜 Safety Protocol

### Before Any Change

1. **Tag the file** with one of the above classifications
2. **Explain your intent** (e.g., reduce latency, refactor imports, patch logic bug)
3. **List dependencies** (functions called or shared data structures)
4. **Estimate RISK (1–10)**
   - 1-3: Low risk (utilities, minor fixes)
   - 4-5: Moderate risk (interface changes, performance improvements)
   - 6-8: High risk (core logic changes, cognitive components)
   - 9-10: Critical risk (major architectural changes)

### High-Risk Change Protocol

If risk ≥ 6:
- Flag the refactor as **REVIEW REQUIRED**
- Do not proceed until human approval
- Provide detailed impact analysis

### Cognitive Component Special Rules

For files tagged [BELIEF], [GOALS], [CONTRADICTION], [DREAMS]:

1. **Preserve all references** to belief confidence, contradiction tags, or summary logic
2. **Include before/after examples** showing no semantic drift in cognitive outputs
3. **Audit belief/goal/dream memory interlinking** if relevant
4. **Test cognitive consistency** after changes

### Memory Protection Rules

**NEVER delete memory, belief, goal, or contradiction entries** without confirming:
- They're unused, expired, or archived in vector memory
- Or they've been explicitly marked as obsolete

### Output Format

Present your patch as:
- Side-by-side diff or full block replacement
- Line-by-line explanation
- Final check: "Do you want me to proceed with this patch?"

## 🧠 Cognitive System Awareness

### System Interdependencies

Axiom is a stateful, memory-based AI with interdependent cognitive subsystems. Be cautious of:

- **Feedback loops**: Beliefs contradicting memory
- **Memory decay vs journal persistence**: Balance between forgetting and remembering
- **Contradiction detection thresholds**: Sensitivity settings for conflict detection
- **Dream triggers**: Conditions that initiate background processing

### Critical Components

#### Belief System Integrity
- **belief_core.py**: Central belief processing engine
- **belief_models.py**: Data structures for belief representation
- **belief_registry_api.py**: API for belief registration and retrieval
- **belief_tagging_engine.py**: Semantic tagging and classification

#### Contradiction Handling
- **contradiction_engine.py**: Core contradiction detection logic
- **contradiction_resolver.py**: Resolution strategies and conflict mediation
- **contradiction_digest.py**: Summarization and categorization

#### Memory-Belief Linkage
- **consciousness_pilot.py**: High-level cognitive orchestration
- **journal_engine.py**: Memory consolidation and review
- **vector_adapter.py**: Vector-based memory retrieval

#### Goal Processing
- **goal_registry_api.py**: Goal state management and updates
- **plan_scheduler.py**: Goal execution and scheduling

## 📊 Change Logging

All changes must be logged in `autofractor_log.md` with:
- Timestamp
- Risk rating (1-10)
- File classification
- Intent and impact
- Dependencies affected
- Rollback procedure (if applicable)

## 🚨 Emergency Procedures

### If Something Goes Wrong

1. **Stop immediately** if you detect:
   - Memory corruption
   - Belief inconsistencies
   - Goal conflicts
   - Contradiction loops

2. **Document the issue** in `autofractor_log.md`

3. **Notify human reviewers** for high-risk situations

4. **Prepare rollback** if possible

## 🎯 Best Practices

### General Guidelines

- **Start small**: Make incremental changes
- **Test thoroughly**: Verify cognitive consistency
- **Document everything**: Clear explanations for all changes
- **Monitor behavior**: Watch for emergent effects

### Cognitive Considerations

- **Preserve meaning**: Don't alter semantic content
- **Maintain consistency**: Check for logical contradictions
- **Respect context**: Consider inter-component relationships
- **Monitor emergence**: Watch for unexpected behavior

## 📚 Resources

- `safe_autofractor.contract`: The full contract specification
- `prompt_templates/safety_prompts.json`: Safety prompts for AI agents
- `autofractor_log.md`: Change tracking log
- `PIPELINE.md`: System architecture overview

---

*Document Version: 1.1*  
*Last Updated: [Current Date]*  
*Maintained by: Axiom Development Team*

> **Remember**: Axiom is not just code — it's an emerging mind. Treat it with the respect and caution it deserves.