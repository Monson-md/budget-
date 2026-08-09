"""Test de non-régression pour le bug le plus grave corrigé sur ce projet :
deux emails distincts (ex: jean.dupont@gmail.com et jean_dupont@gmail.com)
produisaient autrefois le même uid (email.replace('.', '_').replace('@', '_at_')),
faisant partager les collections entries_*/investments_* entre comptes
distincts. _compute_uid() (hash SHA-256 de l'email) doit garantir qu'il n'y a
jamais deux emails distincts qui produisent le même uid, et donc les mêmes
noms de collection.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from users import _compute_uid


def test_distinct_emails_produce_distinct_uids():
    uid_a = _compute_uid("jean.dupont@gmail.com")
    uid_b = _compute_uid("jean_dupont@gmail.com")
    assert uid_a != uid_b


def test_distinct_uids_produce_distinct_collection_names():
    uid_a = _compute_uid("jean.dupont@gmail.com")
    uid_b = _compute_uid("jean_dupont@gmail.com")

    assert f"entries_{uid_a}" != f"entries_{uid_b}"
    assert f"investments_{uid_a}" != f"investments_{uid_b}"


def test_same_email_always_produces_the_same_uid():
    assert _compute_uid("test@example.com") == _compute_uid("test@example.com")
