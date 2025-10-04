#!/usr/bin/env python3
"""
Comprehensive script to visualize and test the LangGraph workflow structure
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

# Try both import paths to handle running from different directories
try:
    from services.nlp_service_v1 import NLPService
except ImportError:
    # If running from project root, try backend.services
    from backend.services.nlp_service_v1 import NLPService


def visualize_workflow():
    """Visualize the NLP service workflow"""
    print("🔍 LangGraph Workflow Visualization")
    print("=" * 50)

    # Initialize the NLP service
    try:
        # Try to get API key from environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("⚠️  Warning: OPENAI_API_KEY not found in environment")
            print("   Using dummy key for visualization purposes")
            api_key = "dummy-key-for-visualization"

        nlp_service = NLPService(api_key)

        # Get workflow structure
        structure = nlp_service.get_workflow_structure()

        print("\n📊 Workflow Structure:")
        print(f"   Entry Point: {structure['entry_point']}")
        print(f"   Nodes: {structure['nodes']}")
        print(f"   End Points: {structure['end_points']}")

        print("\n🔗 Edges:")
        for edge in structure["edges"]:
            condition = (
                f" ({edge.get('condition', '')})" if edge.get("condition") else ""
            )
            print(f"   {edge['from']} → {edge['to']} ({edge['type']}){condition}")

        # Generate Mermaid diagram
        print("\n🎨 Mermaid Diagram:")
        print("-" * 30)
        mermaid = nlp_service.visualize_workflow()
        print(mermaid)

        print("\n💡 To view this diagram:")
        print("   1. Copy the Mermaid code above")
        print("   2. Go to https://mermaid.live/")
        print("   3. Paste the code to see the visual diagram")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        print(
            "\n💡 Make sure you're running this from the project root or backend directory"
        )
        print("   and that all dependencies are installed.")
        return False


async def test_workflow_functionality():
    """Test the workflow creation and functionality"""
    print("\n🧪 Testing Workflow Functionality")
    print("=" * 50)

    try:
        nlp_service = NLPService("dummy-key-for-testing")

        # Test workflow structure
        print("\n1️⃣ Testing workflow structure...")
        structure = nlp_service.get_workflow_structure()
        print(f"   ✅ Nodes found: {structure['nodes']}")
        print(f"   ✅ Entry point: {structure['entry_point']}")
        print(f"   ✅ Number of edges: {len(structure['edges'])}")

        # Test Mermaid visualization
        print("\n2️⃣ Testing Mermaid diagram generation...")
        mermaid = nlp_service.visualize_workflow()
        if mermaid and "graph TD" in mermaid:
            print("   ✅ Mermaid diagram generated successfully")
            print(f"   ✅ Diagram length: {len(mermaid)} characters")
        else:
            print("   ❌ Failed to generate Mermaid diagram")

        # Test workflow creation
        print("\n3️⃣ Testing workflow creation...")
        try:
            workflow = nlp_service._create_workflow()
            print(f"   ✅ Workflow created: {type(workflow)}")
            print(f"   ✅ Workflow compiled: {hasattr(workflow, 'invoke')}")
            print(f"   ✅ Has ainvoke method: {hasattr(workflow, 'ainvoke')}")
        except Exception as e:
            print(f"   ❌ Error creating workflow: {e}")

        print("\n🎯 Workflow Summary:")
        print("   Router → Read/Write → End")

        return True

    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False


def main():
    """Main function with menu options"""
    print("🚀 LangGraph Workflow Tools")
    print("=" * 50)
    print("1. Visualize workflow structure")
    print("2. Test workflow functionality")
    print("3. Both (recommended)")
    print("4. Exit")

    try:
        choice = input("\nSelect an option (1-4, default=3): ").strip()

        if choice == "1":
            visualize_workflow()
        elif choice == "2":
            asyncio.run(test_workflow_functionality())
        elif choice == "3" or choice == "":
            # Default to option 3 (Both)
            visualize_workflow()
            asyncio.run(test_workflow_functionality())
        elif choice == "4":
            print("👋 Goodbye!")
        else:
            print("❌ Invalid choice. Please run the script again.")

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
