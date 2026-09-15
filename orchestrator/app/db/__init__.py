# Lightweight job store backed by a JSON file. Avoids the operational
# cost of Postgres/SQLite migrations for the MVP. When the time comes to
# add proper auth and multi-user, swap this for SQLAlchemy.
