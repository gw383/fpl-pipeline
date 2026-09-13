"""Season configuration for the extraction pipeline.

Update CURRENT_SEASON at the start of each new FPL season. This value
is stamped onto every ingested row and used by the transformation
layer to select "this season's" data.
"""

CURRENT_SEASON = "2026-27"
