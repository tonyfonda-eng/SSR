import logging
from typing import List, Dict

class WorksheetSerializer:
    """Transforms raw dictionary projections into 2D row matrices for Google Sheets."""
    
    def __init__(self, projection_version: str = "1.1.0"):
        self.projection_version = projection_version
        self.logger = logging.getLogger("SSR.WorksheetSerializer")

    def serialize(self, sheet_name: str, rows: List[Dict]) -> List[List[any]]:
        """Converts database projection rows into structured matrices based on tab layouts."""
        if not rows:
            return []

        # Extract all distinct header keys dynamically from the collection documents
        headers = list(rows[0].keys())
        matrix = [headers] # First row is always the grid headers

        for row in rows:
            matrix_row = []
            for header in headers:
                matrix_row.append(row.get(header, ""))
            matrix.append(matrix_row)

        return matrix
