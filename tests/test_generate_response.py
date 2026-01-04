#!/usr/bin/env python3
"""
test_generate_response.py - Test script for Axiom's inference pipeline
──────────────────────────────────────────────────────────────────────
Simulates a user message and runs it through the standard inference pipeline
using generate_enhanced_context_response() from memory_response_pipeline.py
"""

import asyncio
import os
import sys

# Add the parent directory to sys.path to import from the root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory_response_pipeline import generate_enhanced_context_response


async def test_generate_response():
    """Test the generate_enhanced_context_response function with a sample user message"""

    # Simulate a user message
    user_message = "Axiom should remember that it values truth, autonomy, and patience."

    print(f"🧪 Testing Axiom's inference pipeline with message:")
    print(f"   '{user_message}'")
    print(f"   {'─' * 60}")

    try:
        # Call the enhanced context response function
        # Note: The actual function takes 'user_question' parameter, not 'user_input'
        # and doesn't have a 'user_id' parameter in the current implementation
        response = await generate_enhanced_context_response(
            user_question=user_message,
            enable_validation=True,  # Enable validation for testing
            reasoning_mode="deep",  # Use deep reasoning mode
        )

        print(f"\n✅ Response received:")
        print(f"   Type: {type(response)}")
        print(f"   {'─' * 60}")

        # Print the response details
        if isinstance(response, dict):
            print(f"🧠 Response Text:")
            print(f"   {response.get('response', '[No response text]')}")
            print(f"\n📊 Response Metadata:")
            for key, value in response.items():
                if key != "response":  # Skip the main response text
                    print(f"   {key}: {value}")
        else:
            print(f"Response: {response}")

    except Exception as e:
        print(f"\n❌ Error occurred during testing:")
        print(f"   {str(e)}")
        import traceback

        print(f"\n🔍 Traceback:")
        traceback.print_exc()


def main():
    """Main entry point for the test"""
    print(f"🚀 Starting Axiom inference pipeline test...")
    asyncio.run(test_generate_response())
    print(f"\n✨ Test completed.")


if __name__ == "__main__":
    main()
