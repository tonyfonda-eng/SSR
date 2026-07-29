import logging
import time

class GoogleSheetsPublisherTask:
    """Scheduled runtime loop worker that syncs dirty SQLite tables to Google Sheets."""
    
    def __init__(self, google_publisher, health_service):
        self.publisher = google_publisher
        self.health = health_service
        self.logger = logging.getLogger("SSR.PublisherTask")

    def execute(self):
        """Sweeps dirty projection tables and flushes them upstream to the cockpit."""
        start_time = time.time()
        self.logger.info("Checking projection store for dirty tables to publish...")
        
        try:
            # Gather tracked sheets inside the persistence layer
            store = self.publisher.store
            dirty_sheets = store.get_dirty_sheets()
            
            if not dirty_sheets:
                self.logger.info("Zero tables dirty. Sync deferred.")
                return
                
            for sheet_name in dirty_sheets:
                self.logger.info(f"Publishing mutated table sheet state: {sheet_name}")
                
                # Execute full tabular flush
                self.publisher.publish_sheet(sheet_name)
                
                # Clear the mutation token in SQLite
                store.clear_dirty_token(sheet_name)
                
            latency = (time.time() - start_time) * 1000
            self.health.report_success("GoogleSheetsPublisher", latency_ms=latency)
            self.logger.info(f"Cockpit sync completed successfully in {latency:.2f}ms.")
            
        except Exception as e:
            self.logger.error(f"Failed to publish active cockpit layout updates: {str(e)}")
            self.health.report_failure("GoogleSheetsPublisher", error_msg=str(e))
