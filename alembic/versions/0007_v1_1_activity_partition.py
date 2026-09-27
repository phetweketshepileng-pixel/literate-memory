"""0007_v1_1_activity_partition: convert activity_logs into a table
partitioned by RANGE (created_at) (V1.1 review, database-bottlenecks
section — "activity_logs will grow unbounded and is on the write-hot
path"). Postgres cannot partition an existing table in place, so this
migration creates a new partitioned table, batch-copies existing rows,
and swaps names inside a transaction.

THIS IS THE ONE FORWARD-ONLY MIGRATION IN THE V1.1 SET. Running it against
a production database with existing activity_logs rows requires a
maintenance window sized to the batch copy (test the copy duration against
a staging snapshot first). A fresh deployment with no existing rows can
skip straight to a partitioned activity_logs at 0001 time instead — this
revision exists specifically for upgrading an already-running V1 database.

Revision ID: 0007_v1_1_activity_partition
Revises: 0006_v1_1_engagement
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_v1_1_activity_partition"
down_revision = "0006_v1_1_engagement"
branch_labels = None
depends_on = None

BATCH_SIZE = 50_000


def upgrade() -> None:
    conn = op.get_bind()

    # 1. New partitioned table, same columns/constraints as the original.
    #    PRIMARY KEY here must be composite (id, created_at): Postgres
    #    requires a partitioned table's primary/unique key to include every
    #    partitioning column — a real constraint that only surfaces when
    #    this migration is run against actual Postgres, not caught by unit
    #    tests against the ORM layer alone.
    op.execute(
        """
        CREATE TABLE activity_logs_new (
            id UUID DEFAULT uuid_generate_v4(),
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            action VARCHAR(255) NOT NULL,
            entity_type VARCHAR(100),
            entity_id UUID,
            ip_address VARCHAR(64),
            metadata JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
        """
    )
    op.execute("CREATE TABLE activity_logs_default PARTITION OF activity_logs_new DEFAULT")

    # 2. Batch-copy existing rows so this doesn't hold one giant lock/WAL burst.
    #    Ordered by id for a stable cursor across batches. (The original
    #    version of this loop had a dead first-iteration probe query with
    #    an unbound bind parameter — caught only when actually run against
    #    Postgres; removed here as it served no purpose the main
    #    INSERT...SELECT below doesn't already handle via COALESCE.)
    last_id = None
    while True:
        result = conn.execute(
            sa.text(
                """
                INSERT INTO activity_logs_new
                SELECT * FROM activity_logs
                WHERE id > COALESCE(:last_id, '00000000-0000-0000-0000-000000000000'::uuid)
                ORDER BY id
                LIMIT :batch_size
                RETURNING id
                """
            ),
            {"last_id": last_id, "batch_size": BATCH_SIZE},
        )
        rows = result.fetchall()
        if not rows:
            break
        last_id = rows[-1][0]
        if len(rows) < BATCH_SIZE:
            break

    # 3. Swap names inside a transaction (Alembic already runs this in one).
    op.execute("ALTER TABLE activity_logs RENAME TO activity_logs_old")
    op.execute("ALTER TABLE activity_logs_new RENAME TO activity_logs")

    # Index names are unique per-SCHEMA in Postgres, not per-table — renaming
    # the table doesn't free up its indexes' names, so idx_activity_logs_user
    # from the old table still holds that name and the create_index calls
    # below would collide with it. Rename the old indexes out of the way
    # first. (Caught only by running this migration against real Postgres.)
    op.execute("ALTER INDEX idx_activity_logs_user RENAME TO idx_activity_logs_user_old")
    op.execute("ALTER INDEX idx_activity_logs_entity RENAME TO idx_activity_logs_entity_old")

    op.create_index("idx_activity_logs_user", "activity_logs", ["user_id", "created_at"])
    op.create_index("idx_activity_logs_entity", "activity_logs", ["entity_type", "entity_id"])

    # 4. Pre-create the next 3 months of partitions; a scheduled maintenance
    #    job (Celery beat, monthly) keeps this rolling forward from here.
    op.execute(
        """
        DO $$
        DECLARE
            start_date date := date_trunc('month', now())::date;
            i int;
        BEGIN
            FOR i IN 0..2 LOOP
                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS activity_logs_%s PARTITION OF activity_logs
                     FOR VALUES FROM (%L) TO (%L)',
                    to_char(start_date + (i || ' month')::interval, 'YYYY_MM'),
                    start_date + (i || ' month')::interval,
                    start_date + ((i + 1) || ' month')::interval
                );
            END LOOP;
        END $$;
        """
    )

    # 5. Drop the old unpartitioned table only once the copy is verified.
    #    Left as a manual, explicit follow-up step (not auto-dropped here)
    #    so an operator can diff row counts between activity_logs and
    #    activity_logs_old before reclaiming the space:
    #      SELECT count(*) FROM activity_logs_old;
    #      SELECT count(*) FROM activity_logs;
    #      DROP TABLE activity_logs_old;  -- run manually once verified


def downgrade() -> None:
    raise NotImplementedError(
        "0007 is forward-only: reverting a partitioned activity_logs back to a "
        "single table requires the same batch-copy approach in reverse, and "
        "should be run as its own reviewed migration rather than an automatic "
        "downgrade, given the data-safety stakes of an audit-log table."
    )
