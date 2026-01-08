#!/usr/bin/env python3
"""
Test script for V2 Download Orchestrator - Smart Resume Functionality

Tests:
1. Check existing download state
2. Resume download (should skip video, retry subtitle)
3. Verify smart resume logic
"""

import sys
from PyQt5.QtCore import QCoreApplication, QTimer
from source.download_state_manager_v2 import DownloadStateManagerV2
from source.download_orchestrator_v2 import DownloadOrchestratorV2
from source.subtitle_manager import SubtitleManager
from source.translation_manager import SubtitleTranslator
from source.catalog_manager import CatalogManager

def test_smart_resume():
    """Test smart resume functionality with existing download"""

    app = QCoreApplication(sys.argv)

    print("=" * 60)
    print("V2 Download Orchestrator - Smart Resume Test")
    print("=" * 60)

    # Initialize components
    print("\n1. Initializing components...")
    state_manager = DownloadStateManagerV2()
    subtitle_manager = SubtitleManager()
    translator = SubtitleTranslator()
    catalog_manager = CatalogManager()

    orchestrator = DownloadOrchestratorV2(
        state_manager=state_manager,
        subtitle_manager=subtitle_manager,
        translator=translator
    )

    print("   ✓ Components initialized")

    # Check existing download state
    item_id = "movie_27205"
    print(f"\n2. Checking existing download state for {item_id}...")

    state = state_manager.get_download_state(item_id)
    if state:
        print(f"   Status: {state['status']}")
        print(f"   Video Status: {state['video_status']} ({state['video_progress']:.1f}%)")
        print(f"   Subtitle Status: {state['subtitle_status']} ({state['subtitle_progress']:.1f}%)")
        print(f"   Translation Status: {state['translation_status']} ({state['translation_progress']:.1f}%)")
        print(f"   Video Path: {state.get('download_path', 'N/A')}")
        print(f"   Subtitle Path: {state.get('subtitle_path', 'N/A')}")
    else:
        print(f"   ✗ No download state found for {item_id}")
        return 1

    # Get movie metadata from catalog
    print(f"\n3. Getting movie metadata from catalog...")
    movie = catalog_manager.get_movie_by_id(item_id)

    if not movie:
        print(f"   ✗ Movie {item_id} not found in catalog")
        return 1

    print(f"   Title: {movie['title']}")
    print(f"   Year: {movie['year']}")
    print(f"   Magnet Link: {movie['magnet_link'][:50]}...")

    # Extract subtitle config
    subtitle_info = movie.get('subtitle', {})
    if subtitle_info:
        print(f"   Subtitle file_id: {subtitle_info.get('file_id')}")
        print(f"   Subtitle language: {subtitle_info.get('language')}")
        print(f"   Needs translation: {subtitle_info.get('needs_translation')}")
    else:
        print("   ⚠ No subtitle config found in catalog")

    # Test smart resume
    print(f"\n4. Testing smart resume...")
    print(f"   Expected behavior:")
    print(f"   - Video is completed (100%) → should SKIP")
    print(f"   - Subtitle is pending (0%) → should DOWNLOAD")
    print(f"   - Translation is pending → should TRANSLATE if needed")

    # Connect signals to track behavior
    def on_video_progress(item_id, progress):
        print(f"   [Signal] Video progress: {progress:.1f}%")

    def on_subtitle_progress(item_id, progress):
        print(f"   [Signal] Subtitle progress: {progress:.1f}%")

    def on_video_status(item_id, status):
        print(f"   [Signal] Video status changed: {status}")

    def on_subtitle_status(item_id, status):
        print(f"   [Signal] Subtitle status changed: {status}")

    def on_complete(item_id, video_path, subtitle_path):
        print(f"\n   ✓ Download complete!")
        print(f"     Video: {video_path}")
        print(f"     Subtitle: {subtitle_path}")
        app.quit()

    def on_failed(item_id, component, error):
        print(f"\n   ✗ Download failed in {component}: {error}")
        app.quit()

    orchestrator.video_progress_updated.connect(on_video_progress)
    orchestrator.subtitle_progress_updated.connect(on_subtitle_progress)
    orchestrator.video_status_changed.connect(on_video_status)
    orchestrator.subtitle_status_changed.connect(on_subtitle_status)
    orchestrator.download_complete.connect(on_complete)
    orchestrator.download_failed.connect(on_failed)

    # Start download (should trigger smart resume)
    print(f"\n5. Starting download (smart resume)...")
    success = orchestrator.start_download(
        item_id=item_id,
        item_type='movie',
        magnet_link=movie['magnet_link'],
        title=movie['title'],
        metadata=movie
    )

    if success:
        print(f"   ✓ Download started successfully")
        print(f"\n6. Waiting for download to complete...")
        print(f"   (Press Ctrl+C to cancel)")

        # Set timeout to prevent hanging
        def timeout():
            print(f"\n   ⚠ Test timeout after 60 seconds")
            print(f"\n7. Checking final state...")
            final_state = state_manager.get_download_state(item_id)
            if final_state:
                print(f"   Video Status: {final_state['video_status']} ({final_state['video_progress']:.1f}%)")
                print(f"   Subtitle Status: {final_state['subtitle_status']} ({final_state['subtitle_progress']:.1f}%)")
            app.quit()

        QTimer.singleShot(60000, timeout)  # 60 second timeout

        return app.exec_()
    else:
        print(f"   ✗ Failed to start download")
        return 1

if __name__ == "__main__":
    try:
        exit_code = test_smart_resume()
        print("\n" + "=" * 60)
        print(f"Test completed with exit code: {exit_code}")
        print("=" * 60)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
