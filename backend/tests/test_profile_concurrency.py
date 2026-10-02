from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, local

from sqlalchemy import event
from sqlmodel import Session, select

from jobbr import db, services
from jobbr.models import Company, Job, Match, Profile, SavedCareerDraft


def concurrent_owner_ids():
    engine = db.get_engine()
    barrier = Barrier(2)
    state = local()

    def after_statement(connection, cursor, statement, parameters, context, executemany):
        if "FROM profile" in statement and not getattr(state, "read_owner", False):
            state.read_owner = True
            # Both sessions finish the empty owner query before either can reserve the guard.
            barrier.wait(timeout=2)

    def initialize():
        with Session(engine) as session:
            owner = services.get_profile(session)
            assert owner.id is not None
            return owner.id

    event.listen(engine, "after_cursor_execute", after_statement)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            ids = list(workers.map(lambda _: initialize(), range(2)))
    finally:
        event.remove(engine, "after_cursor_execute", after_statement)
    assert ids[0] == ids[1]
    with Session(engine) as session:
        profiles = session.exec(select(Profile)).all()
        assert len(profiles) == 1
        assert services.get_profile(session).id == ids[0]
        company = Company(name="Concurrency employer")
        session.add(company)
        session.flush()
        assert company.id is not None
        job = Job(company_id=company.id, title="Engineer")
        session.add(job)
        session.flush()
        match = services.rematch(session, job)
        assert match.profile_id == ids[0]
        session.add(
            SavedCareerDraft(
                job_id=job.id,
                profile_id=ids[0],
                result={"kind": "cover_letter"},
                source_fingerprint="x" * 64,
            )
        )
        session.commit()
    with Session(engine) as reopened:
        assert services.get_profile(reopened).id == ids[0]
        assert reopened.exec(select(Match)).one().profile_id == ids[0]
        assert reopened.exec(select(SavedCareerDraft)).one().profile_id == ids[0]
    return ids[0]


def test_first_owner_creation_is_serialized_in_sqlite(env):
    db.init_db()
    concurrent_owner_ids()
