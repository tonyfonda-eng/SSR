import time
import threading
import logging
from typing import Callable, Dict

class TaskScheduler:
    """Manages independent background tasks running at fixed intervals."""
    
    def __init__(self):
        self.logger = logging.getLogger("SSR.Scheduler")
        self.tasks: Dict[str, threading.Thread] = {}
        self._running = False

    def schedule_task(self, name: str, interval_seconds: int, target_callable: Callable):
        """Registers a repetitive job inside the scheduling matrix."""
        if name in self.tasks:
            raise ValueError(f"Task {name} is already registered.")
            
        def task_wrapper():
            self.logger.info(f"Task loop started for: {name}")
            while self._running:
                try:
                    target_callable()
                except Exception as e:
                    self.logger.error(f"Execution fault encountered inside task [{name}]: {str(e)}")
                
                # Dynamic polling step resolution
                time.sleep(interval_seconds)

        self.tasks[name] = threading.Thread(target=task_wrapper, name=f"Task-{name}", daemon=True)

    def start(self):
        """Spins up all registered background runner worker threads."""
        if self._running:
            return
        self._running = True
        self.logger.info(f"Starting TaskScheduler with {len(self.tasks)} loops configured...")
        for name, thread in self.tasks.items():
            thread.start()

    def stop(self):
        """Signals all active task execution runners to pause loop polling cycles."""
        self._running = False
        self.logger.info("TaskScheduler stop signal issued.")
