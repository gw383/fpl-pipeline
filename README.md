# Dashboard data

`fpl_serving.sqlite.gz` is the data file the FPL Analytics dashboard reads: a gzipped
SQLite database of the warehouse's analytics tables, exported by the
pipeline (`serving/export_data.py` on the main branch).

This branch is generated. It is replaced on every pipeline run, so don't
commit to it.

Last published: 2026-10-03 11:40 UTC
