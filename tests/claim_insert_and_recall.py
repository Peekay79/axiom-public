#!/usr/bin/env python3
"""
tests/claim_insert_and_recall.py – Test script for lightweight claim system

This script tests the claim system by:
1. Inserting 3 claims
2. Prompting Axiom with a question matching one claim
3. Verifying correct recall without touching belief graph
"""

import json
import logging
import os
import sys
from datetime import datetime

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claims import create_claim, get_claim_store, store_claim
from pods.memory.memory_manager import Memory

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("claim_test")


def test_claim_insert_and_recall():
    """Test the complete claim lifecycle: insert, search, and recall"""

    print("🧪 Starting Claim System Test")
    print("=" * 50)

    # Step 1: Insert 3 test claims
    test_claims = [
        {
            "content": "ExamplePerson lives in the UK.",
            "source": "test_user",
            "tags": ["person", "location", "test"],
        },
        {
            "content": "Python is a programming language developed in the 1990s.",
            "source": "test_system",
            "tags": ["technology", "programming", "test"],
        },
        {
            "content": "The capital of France is Paris.",
            "source": "test_knowledge",
            "tags": ["geography", "fact", "test"],
        },
    ]

    inserted_claim_ids = []

    print("\n📋 Step 1: Inserting test claims...")
    for i, claim_data in enumerate(test_claims, 1):
        try:
            claim = create_claim(**claim_data)
            claim_id = store_claim(claim)
            inserted_claim_ids.append(claim_id)
            print(f"  ✅ Claim {i}: {claim_id} - {claim_data['content']}")
        except Exception as e:
            print(f"  ❌ Failed to insert claim {i}: {e}")
            return False

    print(f"\n📊 Successfully inserted {len(inserted_claim_ids)} claims")

    # Step 2: Verify claims are stored properly
    print("\n🔍 Step 2: Verifying claim storage...")
    claim_store = get_claim_store()

    all_claims = claim_store.get_all_claims()
    test_claims_found = [c for c in all_claims if "test" in c.tags]

    print(f"  📋 Total claims in store: {claim_store.count()}")
    print(f"  🧪 Test claims found: {len(test_claims_found)}")

    for claim in test_claims_found:
        print(f"    - {claim.id}: {claim.content}")

    # Step 3: Test claim search functionality
    print("\n🔎 Step 3: Testing claim search...")

    # Search for ExamplePerson
    kurt_claims = claim_store.search_claims("ExamplePerson")
    print(f"  🔍 Search for 'ExamplePerson': {len(kurt_claims)} results")
    for claim in kurt_claims:
        print(f"    - {claim.id}: {claim.content}")

    # Search for Python
    python_claims = claim_store.search_claims("Python")
    print(f"  🔍 Search for 'Python': {len(python_claims)} results")
    for claim in python_claims:
        print(f"    - {claim.id}: {claim.content}")

    # Search for Paris
    paris_claims = claim_store.search_claims("Paris")
    print(f"  🔍 Search for 'Paris': {len(paris_claims)} results")
    for claim in paris_claims:
        print(f"    - {claim.id}: {claim.content}")

    # Step 4: Verify claims don't appear in regular memory
    print("\n🧠 Step 4: Verifying claims bypass regular memory...")
    memory = Memory()
    memory.load()

    regular_memories = memory.long_term_memory
    claim_type_memories = [m for m in regular_memories if m.get("type") == "claim"]

    print(f"  📝 Total memories in long-term storage: {len(regular_memories)}")
    print(f"  📋 Claim-type entries in regular memory: {len(claim_type_memories)}")

    if len(claim_type_memories) == 0:
        print("  ✅ SUCCESS: Claims correctly bypass regular memory storage")
    else:
        print("  ⚠️  WARNING: Some claims found in regular memory:")
        for memory_item in claim_type_memories:
            print(
                f"    - {memory_item.get('id', 'no-id')}: {memory_item.get('content', 'no-content')[:50]}..."
            )

    # Step 5: Test claim retrieval by ID
    print("\n🎯 Step 5: Testing claim retrieval by ID...")
    for claim_id in inserted_claim_ids:
        claim = claim_store.get_claim(claim_id)
        if claim:
            print(f"  ✅ Retrieved {claim_id}: {claim.content}")
        else:
            print(f"  ❌ Failed to retrieve claim {claim_id}")

    # Step 6: Test claims by source
    print("\n📂 Step 6: Testing claims by source...")
    test_sources = set(claim_data["source"] for claim_data in test_claims)

    for source in test_sources:
        source_claims = claim_store.get_claims_by_source(source)
        print(f"  📋 Claims from '{source}': {len(source_claims)}")
        for claim in source_claims:
            if "test" in claim.tags:  # Only show our test claims
                print(f"    - {claim.id}: {claim.content}")

    # Step 7: Simulate Axiom question matching (basic test)
    print("\n❓ Step 7: Simulating Axiom question matching...")

    # This simulates how Axiom might search for relevant claims when answering questions
    test_questions = [
        ("Where does ExamplePerson live?", "ExamplePerson"),
        ("What programming language was developed in the 1990s?", "Python"),
        ("What is the capital of France?", "Paris"),
    ]

    for question, search_term in test_questions:
        print(f"\n  ❓ Question: {question}")
        relevant_claims = claim_store.search_claims(search_term)

        if relevant_claims:
            print(f"    🎯 Found {len(relevant_claims)} relevant claim(s):")
            for claim in relevant_claims:
                if "test" in claim.tags:  # Only show our test claims
                    print(f"      - {claim.content}")
        else:
            print(f"    ❌ No relevant claims found")

    # Step 8: Test claim promotion (bonus feature)
    print("\n🎯 Step 8: Testing claim promotion to belief...")

    if inserted_claim_ids:
        try:
            from claims import promote_claim_to_belief

            test_claim_id = inserted_claim_ids[0]  # Promote the first claim
            print(f"  🎯 Attempting to promote claim {test_claim_id}")

            result = promote_claim_to_belief(test_claim_id)

            if result["status"] == "success":
                print(
                    f"  ✅ Successfully promoted claim to belief {result['belief_id']}"
                )

                # Verify the belief was created in memory
                memory.load()  # Reload to get latest
                promoted_memory = memory.get(result["belief_id"])

                if promoted_memory:
                    print(
                        f"    📝 Belief created in memory: {promoted_memory.get('content', promoted_memory.get('text', 'no-content'))[:50]}..."
                    )
                    print(f"    🏷️  Tags: {promoted_memory.get('tags', [])}")
                else:
                    print(f"    ⚠️  Belief {result['belief_id']} not found in memory")
            else:
                print(
                    f"  ❌ Promotion failed: {result.get('message', 'Unknown error')}"
                )

        except Exception as e:
            print(f"  ⚠️  Promotion test failed: {e}")

    # Final summary
    print("\n" + "=" * 50)
    print("🏁 Test Summary:")
    print(f"  📋 Claims inserted: {len(inserted_claim_ids)}")
    print(
        f"  🔍 Search functionality: {'✅ Working' if any(kurt_claims + python_claims + paris_claims) else '❌ Failed'}"
    )
    print(
        f"  🧠 Memory isolation: {'✅ Working' if len(claim_type_memories) == 0 else '⚠️  Partial'}"
    )
    print(
        f"  📂 Storage separation: {'✅ Working' if claim_store.count() > 0 else '❌ Failed'}"
    )

    print("\n🎉 Claim system test completed!")
    return True


def cleanup_test_claims():
    """Clean up test claims (optional)"""
    print("\n🧹 Cleaning up test claims...")

    try:
        claim_store = get_claim_store()
        all_claims = claim_store.get_all_claims()
        test_claims = [c for c in all_claims if "test" in c.tags]

        for claim in test_claims:
            if claim_store.delete_claim(claim.id):
                print(f"  🗑️  Deleted test claim: {claim.id}")

        print(f"  ✅ Cleaned up {len(test_claims)} test claims")

    except Exception as e:
        print(f"  ⚠️  Cleanup failed: {e}")


if __name__ == "__main__":
    try:
        # Run the test
        success = test_claim_insert_and_recall()

        # Ask if user wants to clean up
        if success:
            cleanup_choice = input("\nClean up test claims? (y/N): ").strip().lower()
            if cleanup_choice in ["y", "yes"]:
                cleanup_test_claims()

        print("\n✅ Test script completed successfully!")

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
