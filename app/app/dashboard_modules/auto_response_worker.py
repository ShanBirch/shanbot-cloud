#!/usr/bin/env python3
"""
Auto Response Background Worker
Continuously processes scheduled responses when Auto Mode is active.
"""

from response_review import process_scheduled_responses, get_scheduled_responses_stats
import time
import sys
import os
import logging
import argparse
from datetime import datetime

# Add the parent directories to the path to import modules correctly
current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)  # app directory
grandparent_dir = os.path.dirname(parent_dir)  # shanbot directory

sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, grandparent_dir)

# Import the processing function

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(
            os.path.dirname(__file__), 'auto_worker.log'))
    ]
)

logger = logging.getLogger(__name__)


def run_worker(test_mode=False):
    """
    Main worker loop that processes scheduled responses.

    Args:
        test_mode (bool): If True, run once and exit. If False, run continuously.
    """
    logger.info(
        f"🚀 Auto Response Worker starting {'(TEST MODE)' if test_mode else '(CONTINUOUS MODE)'}")

    if test_mode:
        logger.info("Running single test cycle...")
        try:
            processed_count = process_scheduled_responses()
            stats = get_scheduled_responses_stats()

            logger.info(f"✅ Test completed successfully!")
            logger.info(f"📊 Processed {processed_count} responses")
            logger.info(f"📊 Current stats: {stats}")

            return True
        except Exception as e:
            logger.error(f"❌ Test failed: {e}", exc_info=True)
            return False

    # Continuous mode
    logger.info("🔄 Starting continuous processing loop...")
    logger.info("💡 Press Ctrl+C to stop the worker")

    try:
        cycle_count = 0
        while True:
            cycle_count += 1

            try:
                # Process any due responses
                processed_count = process_scheduled_responses()

                if processed_count > 0:
                    logger.info(
                        f"✅ Cycle #{cycle_count}: Processed {processed_count} scheduled responses")
                else:
                    # Only log every 10th cycle when nothing is processed to reduce noise
                    if cycle_count % 10 == 0:
                        stats = get_scheduled_responses_stats()
                        logger.info(
                            f"⏳ Cycle #{cycle_count}: No responses due. Scheduled: {stats.get('scheduled', 0)}, Pending: {stats.get('pending_count', 0)}")

            except Exception as e:
                logger.error(
                    f"❌ Error in processing cycle #{cycle_count}: {e}", exc_info=True)

            # Wait 60 seconds before next check
            time.sleep(60)

    except KeyboardInterrupt:
        logger.info("🛑 Worker stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"💥 Worker crashed: {e}", exc_info=True)
        raise


def main():
    """Main entry point with command line argument parsing."""
    parser = argparse.ArgumentParser(
        description='Auto Response Background Worker')
    parser.add_argument('--test', action='store_true',
                        help='Run in test mode (single cycle then exit)')

    args = parser.parse_args()

    # Print startup banner
    print("=" * 60)
    print("🤖 SHANBOT AUTO RESPONSE WORKER")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'TEST' if args.test else 'CONTINUOUS'}")
    print("=" * 60)

    try:
        success = run_worker(test_mode=args.test)

        if args.test:
            if success:
                print("✅ Test completed successfully!")
                sys.exit(0)
            else:
                print("❌ Test failed!")
                sys.exit(1)

    except Exception as e:
        logger.error(f"💥 Worker failed to start: {e}", exc_info=True)
        print(f"❌ Worker failed: {e}")
        sys.exit(1)

    print("🏁 Worker finished")


if __name__ == "__main__":
    main()
